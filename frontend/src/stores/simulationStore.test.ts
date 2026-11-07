// @vitest-environment node
import { beforeEach, describe, expect, it } from 'vitest'
import { http } from 'msw'
import { apiErr, apiOk, server } from '../test/server'
import { RealtimeEventType } from '@/types/enums'
import {
  selectSimulationRun,
  selectSimulationRunId,
  selectSimulationRunStatus,
  useSimulationStore,
} from './simulationStore'

const API = 'http://localhost:8000/api'

function runDto(overrides: Record<string, unknown> = {}) {
  return {
    runId: 'RUN-1',
    scenarioId: 'SCN-1',
    scenarioVersion: 1,
    status: 'RUNNING',
    simTimeMs: 0,
    speed: 1,
    ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('simulationStore', () => {
  beforeEach(() => {
    useSimulationStore.getState().resetRun()
  })

  it('初始为 idle、无 run', () => {
    expect(selectSimulationRunStatus(useSimulationStore.getState())).toBe('idle')
    expect(selectSimulationRun(useSimulationStore.getState())).toBeNull()
  })

  it('loadRun 成功：校验+适配后落 run', async () => {
    server.use(http.get(`${API}/simulations/RUN-1`, () => apiOk(runDto({ simTimeMs: 42 }))))
    await useSimulationStore.getState().loadRun('RUN-1')
    const s = useSimulationStore.getState()
    expect(s.run.status).toBe('success')
    expect(s.run.data?.runId).toBe('RUN-1')
    expect(s.run.data?.simTimeMs).toBe(42)
  })

  it('loadRun HTTP 错误：落 error 且 code 可追踪', async () => {
    server.use(
      http.get(`${API}/simulations/RUN-1`, () =>
        apiErr(500, { code: 'INTERNAL_ERROR', message: 'boom' }),
      ),
    )
    await useSimulationStore.getState().loadRun('RUN-1')
    const s = useSimulationStore.getState()
    expect(s.run.status).toBe('error')
    expect(s.run.error?.code).toBe('INTERNAL_ERROR')
  })

  it('loadRun 校验失败：缺 simTimeMs 落 VALIDATION_FAILED', async () => {
    const bad = runDto() as Record<string, unknown>
    delete bad.simTimeMs
    server.use(http.get(`${API}/simulations/RUN-1`, () => apiOk(bad)))
    await useSimulationStore.getState().loadRun('RUN-1')
    const s = useSimulationStore.getState()
    expect(s.run.status).toBe('error')
    expect(s.run.error?.code).toBe('VALIDATION_FAILED')
  })

  it('createRun 成功（无 runId 守卫）', async () => {
    server.use(http.post(`${API}/simulations`, () => apiOk(runDto({ runId: 'RUN-NEW' }))))
    await useSimulationStore.getState().createRun({ scenarioId: 'SCN-1', scenarioVersion: 1 })
    expect(useSimulationStore.getState().run.data?.runId).toBe('RUN-NEW')
  })

  it('applyRealtimeEvent 折算状态/时钟/完成/错误', async () => {
    server.use(
      http.get(`${API}/simulations/RUN-1`, () =>
        apiOk(runDto({ status: 'RUNNING', simTimeMs: 0 })),
      ),
    )
    await useSimulationStore.getState().loadRun('RUN-1')

    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E1',
      eventType: RealtimeEventType.SIMULATION_TIME_UPDATED,
      runId: 'RUN-1',
      seq: 1,
      data: { simTimeMs: 100, speed: 2 },
    })
    expect(useSimulationStore.getState().run.data?.simTimeMs).toBe(100)
    expect(useSimulationStore.getState().run.data?.speed).toBe(2)

    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E2',
      eventType: RealtimeEventType.SIMULATION_STATUS_CHANGED,
      runId: 'RUN-1',
      seq: 2,
      data: { status: 'PAUSED' },
    })
    expect(useSimulationStore.getState().run.data?.status).toBe('PAUSED')

    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E3',
      eventType: RealtimeEventType.SIMULATION_COMPLETED,
      runId: 'RUN-1',
      seq: 3,
      data: {},
    })
    expect(useSimulationStore.getState().run.data?.status).toBe('COMPLETED')

    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E4',
      eventType: RealtimeEventType.SIMULATION_ERROR,
      runId: 'RUN-1',
      seq: 4,
      data: { error: { msg: 'x' } },
    })
    expect(useSimulationStore.getState().run.data?.status).toBe('FAILED')
    expect(useSimulationStore.getState().run.data?.error).toEqual({ msg: 'x' })
  })

  it('applyRealtimeEvent 忽略未知类型与跨 run 事件、无数据时 no-op', async () => {
    // 无数据时 no-op（不抛错）
    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E0',
      eventType: RealtimeEventType.SIMULATION_COMPLETED,
      runId: 'RUN-1',
      seq: 0,
      data: {},
    })
    expect(useSimulationStore.getState().run.data).toBeNull()

    server.use(http.get(`${API}/simulations/RUN-1`, () => apiOk(runDto({ status: 'RUNNING' }))))
    useSimulationStore.getState().resetRun('RUN-1')
    expect(selectSimulationRunId(useSimulationStore.getState())).toBe('RUN-1')
    await useSimulationStore.getState().loadRun('RUN-1')

    // 未知类型 no-op
    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E1',
      eventType: 'SOMETHING_ELSE',
      runId: 'RUN-1',
      seq: 1,
      data: {},
    })
    expect(useSimulationStore.getState().run.data?.status).toBe('RUNNING')

    // 跨 run 忽略
    useSimulationStore.getState().applyRealtimeEvent({
      eventId: 'E2',
      eventType: RealtimeEventType.SIMULATION_COMPLETED,
      runId: 'OTHER',
      seq: 2,
      data: {},
    })
    expect(useSimulationStore.getState().run.data?.status).toBe('RUNNING')
  })

  it('晚到的旧 run 请求不覆盖新 run', async () => {
    const d = deferred<Response>()
    server.use(
      http.get(`${API}/simulations/RUN-A`, () => d.promise),
      http.get(`${API}/simulations/RUN-B`, () => apiOk(runDto({ runId: 'RUN-B' }))),
    )

    useSimulationStore.getState().resetRun('RUN-A')
    const pendingA = useSimulationStore.getState().loadRun('RUN-A')

    useSimulationStore.getState().resetRun('RUN-B')
    await useSimulationStore.getState().loadRun('RUN-B')
    expect(useSimulationStore.getState().run.data?.runId).toBe('RUN-B')

    d.resolve(apiOk(runDto({ runId: 'RUN-A' })))
    await pendingA
    expect(useSimulationStore.getState().run.data?.runId).toBe('RUN-B')
  })
})
