import { create } from 'zustand'
import * as scenariosApi from '@/api/scenarios'
import { scenarioDtoSchema, type ScenarioDto } from '@/schemas/scenario'
import { scenarioValidateResultDtoSchema, type ScenarioValidateResultDto } from '@/schemas/api'
import { toScenario } from '@/adapters/scenario'
import type { Scenario } from '@/types/domain/scenario'
import type { Page } from '@/api/types'
import {
  errorSlice,
  idleSlice,
  loadingSlice,
  normalizeApiError,
  schemaValidationError,
  successSlice,
  type AsyncSlice,
} from './async'

/**
 * 场景 Store（FE-006）。
 * - 事实态（服务端）：`list`（分页）、`current`（单个）、`validateResult`（校验反馈）。
 * - 本地临时编辑态 `draft` 与事实态分离（表单在 FE-011 接续；反向 ViewModel→DTO 适配届时补）。
 * - 场景不按 runId 隔离（场景是独立配置实体），故无晚到守卫。
 */

interface ScenarioState {
  list: AsyncSlice<Scenario[]>
  current: AsyncSlice<Scenario>
  validateResult: AsyncSlice<ScenarioValidateResultDto>
  pagination: { page: number; pageSize: number; total: number }
  /** 本地临时编辑态（与事实态分离）。 */
  draft: scenariosApi.ScenarioUpsertInput | null

  resetScenario: () => void
  listScenarios: (params?: scenariosApi.ListScenariosParams) => Promise<void>
  loadScenario: (scenarioId: string) => Promise<void>
  createScenario: (input: scenariosApi.ScenarioUpsertInput) => Promise<void>
  updateScenario: (
    scenarioId: string,
    input: scenariosApi.ScenarioUpsertInput,
    options?: scenariosApi.UpdateScenarioOptions,
  ) => Promise<void>
  deleteScenario: (scenarioId: string) => Promise<void>
  validateScenario: (
    scenarioId: string,
    input?: scenariosApi.ScenarioValidateInput,
  ) => Promise<void>
  cloneScenario: (scenarioId: string) => Promise<void>
  setDraft: (draft: scenariosApi.ScenarioUpsertInput | null) => void
}

export const useScenarioStore = create<ScenarioState>()((set, get) => {
  function parseScenarioDto(dto: unknown): Scenario | null {
    const parsed = scenarioDtoSchema.safeParse(dto)
    return parsed.success ? toScenario(parsed.data) : null
  }

  /** 统一「请求单个场景 DTO → 校验 → 适配 → 落 current」。 */
  async function commitCurrent(fetch: () => Promise<ScenarioDto>) {
    set((s) => ({ current: loadingSlice(s.current) }))
    try {
      const dto = await fetch()
      const scenario = parseScenarioDto(dto)
      if (!scenario) {
        set({ current: errorSlice(schemaValidationError('场景数据解析失败'), get().current.data) })
        return
      }
      set({ current: successSlice(scenario) })
    } catch (error) {
      set({ current: errorSlice(normalizeApiError(error), get().current.data) })
    }
  }

  return {
    list: idleSlice<Scenario[]>(),
    current: idleSlice<Scenario>(),
    validateResult: idleSlice<ScenarioValidateResultDto>(),
    pagination: { page: 0, pageSize: 0, total: 0 },
    draft: null,

    resetScenario: () =>
      set({
        list: idleSlice<Scenario[]>(),
        current: idleSlice<Scenario>(),
        validateResult: idleSlice<ScenarioValidateResultDto>(),
        pagination: { page: 0, pageSize: 0, total: 0 },
        draft: null,
      }),

    listScenarios: async (params = {}) => {
      set((s) => ({ list: loadingSlice(s.list) }))
      try {
        const page: Page<ScenarioDto> = await scenariosApi.listScenarios(params)
        const items: Scenario[] = []
        for (const dto of page.items) {
          const scenario = parseScenarioDto(dto)
          if (!scenario) {
            set({ list: errorSlice(schemaValidationError('场景列表解析失败'), get().list.data) })
            return
          }
          items.push(scenario)
        }
        set({
          list: successSlice(items),
          pagination: { page: page.page, pageSize: page.pageSize, total: page.total },
        })
      } catch (error) {
        set({ list: errorSlice(normalizeApiError(error), get().list.data) })
      }
    },

    loadScenario: (scenarioId) => commitCurrent(() => scenariosApi.getScenario(scenarioId)),
    createScenario: (input) => commitCurrent(() => scenariosApi.createScenario(input)),
    updateScenario: (scenarioId, input, options) =>
      commitCurrent(() => scenariosApi.updateScenario(scenarioId, input, options)),
    cloneScenario: (scenarioId) => commitCurrent(() => scenariosApi.cloneScenario(scenarioId)),

    deleteScenario: async (scenarioId) => {
      try {
        await scenariosApi.deleteScenario(scenarioId)
        set((s) => ({
          current: s.current.data?.scenarioId === scenarioId ? idleSlice<Scenario>() : s.current,
          list: s.list.data
            ? { ...s.list, data: s.list.data.filter((it) => it.scenarioId !== scenarioId) }
            : s.list,
        }))
      } catch (error) {
        set({ current: errorSlice(normalizeApiError(error), get().current.data) })
      }
    },

    validateScenario: async (scenarioId, input = {}) => {
      set((s) => ({ validateResult: loadingSlice(s.validateResult) }))
      try {
        const dto = await scenariosApi.validateScenario(scenarioId, input)
        const parsed = scenarioValidateResultDtoSchema.safeParse(dto)
        if (!parsed.success) {
          set({
            validateResult: errorSlice(
              schemaValidationError('校验结果解析失败'),
              get().validateResult.data,
            ),
          })
          return
        }
        set({ validateResult: successSlice(parsed.data) })
      } catch (error) {
        set({ validateResult: errorSlice(normalizeApiError(error), get().validateResult.data) })
      }
    },

    setDraft: (draft) => set({ draft }),
  }
})

export const selectScenarioList = (state: ScenarioState) => state.list.data
export const selectScenarioListStatus = (state: ScenarioState) => state.list.status
export const selectScenarioCurrent = (state: ScenarioState) => state.current.data
export const selectScenarioCurrentStatus = (state: ScenarioState) => state.current.status
export const selectScenarioPagination = (state: ScenarioState) => state.pagination
export const selectScenarioValidateResult = (state: ScenarioState) => state.validateResult.data
export const selectScenarioDraft = (state: ScenarioState) => state.draft
