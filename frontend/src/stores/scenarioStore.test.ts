// @vitest-environment node
import { beforeEach, describe, expect, it } from 'vitest'
import { http } from 'msw'
import { apiErr, apiOk, server } from '../test/server'
import {
  selectScenarioCurrent,
  selectScenarioCurrentStatus,
  selectScenarioDraft,
  selectScenarioList,
  selectScenarioListStatus,
  selectScenarioPagination,
  selectScenarioValidateResult,
  useScenarioStore,
} from './scenarioStore'

const API = 'http://localhost:8000/api'

function scenarioDto(overrides: Record<string, unknown> = {}) {
  return {
    scenarioId: 'SCN-1',
    name: '场景1',
    version: 1,
    status: 'DRAFT',
    nodes: [],
    links: [],
    flows: [],
    ...overrides,
  }
}

const upsertInput = {
  name: '场景1',
  nodes: [],
  links: [],
  flows: [],
}

describe('scenarioStore', () => {
  beforeEach(() => {
    useScenarioStore.getState().resetScenario()
  })

  it('初始为 idle', () => {
    const s = useScenarioStore.getState()
    expect(selectScenarioListStatus(s)).toBe('idle')
    expect(selectScenarioCurrentStatus(s)).toBe('idle')
    expect(s.validateResult.status).toBe('idle')
    expect(selectScenarioDraft(s)).toBeNull()
  })

  it('listScenarios 成功：适配列表 + 分页', async () => {
    server.use(
      http.get(`${API}/scenarios`, () =>
        apiOk({
          items: [scenarioDto(), scenarioDto({ scenarioId: 'SCN-2', name: '场景2' })],
          page: 1,
          pageSize: 10,
          total: 2,
        }),
      ),
    )
    await useScenarioStore.getState().listScenarios({ page: 1, pageSize: 10 })
    const s = useScenarioStore.getState()
    expect(selectScenarioListStatus(s)).toBe('success')
    expect(selectScenarioList(s)).toHaveLength(2)
    expect(selectScenarioPagination(s)).toEqual({ page: 1, pageSize: 10, total: 2 })
  })

  it('listScenarios 校验失败：缺 name 落 VALIDATION_FAILED', async () => {
    const bad = scenarioDto() as Record<string, unknown>
    delete bad.name
    server.use(
      http.get(`${API}/scenarios`, () => apiOk({ items: [bad], page: 1, pageSize: 10, total: 1 })),
    )
    await useScenarioStore.getState().listScenarios()
    const s = useScenarioStore.getState()
    expect(s.list.status).toBe('error')
    expect(s.list.error?.code).toBe('VALIDATION_FAILED')
  })

  it('listScenarios HTTP 错误落 error', async () => {
    server.use(http.get(`${API}/scenarios`, () => apiErr(500)))
    await useScenarioStore.getState().listScenarios()
    expect(useScenarioStore.getState().list.error?.code).toBe('INTERNAL_ERROR')
  })

  it('loadScenario 成功', async () => {
    server.use(http.get(`${API}/scenarios/SCN-1`, () => apiOk(scenarioDto({ version: 3 }))))
    await useScenarioStore.getState().loadScenario('SCN-1')
    expect(selectScenarioCurrent(useScenarioStore.getState())?.version).toBe(3)
    expect(selectScenarioCurrentStatus(useScenarioStore.getState())).toBe('success')
  })

  it('createScenario 成功落 current', async () => {
    server.use(http.post(`${API}/scenarios`, () => apiOk(scenarioDto({ scenarioId: 'SCN-NEW' }))))
    await useScenarioStore.getState().createScenario(upsertInput)
    expect(useScenarioStore.getState().current.data?.scenarioId).toBe('SCN-NEW')
  })

  it('updateScenario 成功落 current', async () => {
    server.use(http.put(`${API}/scenarios/SCN-1`, () => apiOk(scenarioDto({ version: 2 }))))
    await useScenarioStore.getState().updateScenario('SCN-1', upsertInput)
    expect(useScenarioStore.getState().current.data?.version).toBe(2)
  })

  it('cloneScenario 成功落 current', async () => {
    server.use(
      http.post(`${API}/scenarios/SCN-1/clone`, () =>
        apiOk(scenarioDto({ scenarioId: 'SCN-CLONE' })),
      ),
    )
    await useScenarioStore.getState().cloneScenario('SCN-1')
    expect(useScenarioStore.getState().current.data?.scenarioId).toBe('SCN-CLONE')
  })

  it('deleteScenario 成功后从列表移除并清空匹配 current', async () => {
    server.use(
      http.get(`${API}/scenarios`, () =>
        apiOk({
          items: [scenarioDto(), scenarioDto({ scenarioId: 'SCN-2', name: '场景2' })],
          page: 1,
          pageSize: 10,
          total: 2,
        }),
      ),
      http.get(`${API}/scenarios/SCN-1`, () => apiOk(scenarioDto())),
      http.delete(`${API}/scenarios/SCN-1`, () => apiOk(null)),
    )
    await useScenarioStore.getState().listScenarios()
    await useScenarioStore.getState().loadScenario('SCN-1')
    await useScenarioStore.getState().deleteScenario('SCN-1')
    const s = useScenarioStore.getState()
    expect(selectScenarioList(s)).toHaveLength(1)
    expect(selectScenarioList(s)?.[0].scenarioId).toBe('SCN-2')
    expect(selectScenarioCurrent(s)).toBeNull()
  })

  it('validateScenario 成功落 validateResult', async () => {
    server.use(
      http.post(`${API}/scenarios/SCN-1/validate`, () =>
        apiOk({
          valid: false,
          errors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
          warnings: [],
        }),
      ),
    )
    await useScenarioStore.getState().validateScenario('SCN-1')
    const result = selectScenarioValidateResult(useScenarioStore.getState())
    expect(result?.valid).toBe(false)
    expect(result?.errors).toHaveLength(1)
  })

  it('validateScenario HTTP 错误落 error', async () => {
    server.use(http.post(`${API}/scenarios/SCN-1/validate`, () => apiErr(500)))
    await useScenarioStore.getState().validateScenario('SCN-1')
    expect(useScenarioStore.getState().validateResult.error?.code).toBe('INTERNAL_ERROR')
  })

  it('setDraft 与 resetScenario', () => {
    useScenarioStore.getState().setDraft(upsertInput)
    expect(selectScenarioDraft(useScenarioStore.getState())).not.toBeNull()
    useScenarioStore.getState().resetScenario()
    expect(selectScenarioDraft(useScenarioStore.getState())).toBeNull()
  })
})
