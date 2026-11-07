import { create } from 'zustand'
import * as simulationsApi from '@/api/simulations'
import { simulationRunDtoSchema, type SimulationRunDto } from '@/schemas/simulation'
import { toSimulationRun } from '@/adapters/simulation'
import type { SimulationRun } from '@/types/domain/simulation'
import type { RealtimeEventEnvelope } from '@/types/domain/realtime'
import { coerceEnum, RealtimeEventType, SimulationStatus } from '@/types/enums'
import {
  errorSlice,
  idleSlice,
  isStaleRun,
  loadingSlice,
  normalizeApiError,
  schemaValidationError,
  successSlice,
  type AsyncSlice,
} from './async'

/**
 * 仿真运行 Store（FE-006）。
 * - `runId` 只由 `resetRun` 绑定；异步 action 均以显式 runId 发起，回包后做晚到守卫。
 * - 服务端事实态（run）与本地编辑态分离；run 切片按 `AsyncSlice` 四态管理。
 * - 实时事件折算为 run 状态变更（`applyRealtimeEvent`），跨 run 事件被忽略。
 */

interface SimulationState {
  /** 当前绑定的 runId（`resetRun` 设置，用于晚到旧请求守卫）。 */
  runId: string | null
  run: AsyncSlice<SimulationRun>

  resetRun: (runId?: string | null) => void
  loadRun: (runId: string) => Promise<void>
  loadStatus: (runId: string) => Promise<void>
  createRun: (input: simulationsApi.CreateSimulationInput) => Promise<void>
  start: (runId: string) => Promise<void>
  pause: (runId: string) => Promise<void>
  resume: (runId: string) => Promise<void>
  stop: (runId: string) => Promise<void>
  step: (runId: string, input?: simulationsApi.StepSimulationInput) => Promise<void>
  setSpeed: (runId: string, input: simulationsApi.SetSimulationSpeedInput) => Promise<void>
  /** 将实时事件（状态/时钟/完成/错误）折算为 run 状态变更。 */
  applyRealtimeEvent: (event: RealtimeEventEnvelope) => void
}

export const useSimulationStore = create<SimulationState>()((set, get) => {
  /** 统一「请求 SimulationRun DTO → 校验 → 适配 → 落 run 切片」，带 runId 晚到守卫。 */
  async function commitRun(startedRunId: string | null, fetch: () => Promise<SimulationRunDto>) {
    set((s) => ({ run: loadingSlice(s.run) }))
    try {
      const dto = await fetch()
      const parsed = simulationRunDtoSchema.safeParse(dto)
      if (!parsed.success) {
        if (isStaleRun(startedRunId, get().runId)) return
        set({ run: errorSlice(schemaValidationError('仿真运行数据解析失败'), get().run.data) })
        return
      }
      if (isStaleRun(startedRunId, get().runId)) return
      set({ run: successSlice(toSimulationRun(parsed.data)) })
    } catch (error) {
      if (isStaleRun(startedRunId, get().runId)) return
      set({ run: errorSlice(normalizeApiError(error), get().run.data) })
    }
  }

  /** 就地 patch 当前 run.data，保持切片 status/error 不变（实时事件不改变请求状态）。 */
  function patchRun(patch: Partial<SimulationRun>) {
    const current = get().run.data
    if (!current) return
    set((s) => ({ run: { ...s.run, data: { ...current, ...patch } } }))
  }

  return {
    runId: null,
    run: idleSlice<SimulationRun>(),

    resetRun: (runId) => set({ runId: runId ?? null, run: idleSlice<SimulationRun>() }),

    loadRun: (runId) => commitRun(runId, () => simulationsApi.getSimulation(runId)),
    loadStatus: (runId) => commitRun(runId, () => simulationsApi.getSimulationStatus(runId)),
    // 创建运行不绑定既有 runId（新 run 尚未确定），守卫传 null（不判过期）。
    createRun: (input) => commitRun(null, () => simulationsApi.createSimulation(input)),
    start: (runId) => commitRun(runId, () => simulationsApi.startSimulation(runId)),
    pause: (runId) => commitRun(runId, () => simulationsApi.pauseSimulation(runId)),
    resume: (runId) => commitRun(runId, () => simulationsApi.resumeSimulation(runId)),
    stop: (runId) => commitRun(runId, () => simulationsApi.stopSimulation(runId)),
    step: (runId, input) => commitRun(runId, () => simulationsApi.stepSimulation(runId, input)),
    setSpeed: (runId, input) =>
      commitRun(runId, () => simulationsApi.setSimulationSpeed(runId, input)),

    applyRealtimeEvent: (event) => {
      // 跨 run 隔离：忽略不属于当前 run 的事件。
      if (get().runId !== null && event.runId !== get().runId) return
      switch (event.eventType) {
        case RealtimeEventType.SIMULATION_STATUS_CHANGED: {
          const status = coerceEnum((event.data as { status?: unknown }).status, SimulationStatus)
          if (status) patchRun({ status })
          break
        }
        case RealtimeEventType.SIMULATION_TIME_UPDATED: {
          const data = event.data as { simTimeMs?: unknown; speed?: unknown }
          if (typeof data.simTimeMs === 'number') {
            patchRun({
              simTimeMs: data.simTimeMs,
              ...(typeof data.speed === 'number' ? { speed: data.speed } : {}),
            })
          }
          break
        }
        case RealtimeEventType.SIMULATION_COMPLETED:
          patchRun({ status: SimulationStatus.COMPLETED })
          break
        case RealtimeEventType.SIMULATION_ERROR: {
          const err = (event.data as { error?: unknown }).error
          patchRun({
            status: SimulationStatus.FAILED,
            ...(typeof err === 'object' && err !== null
              ? { error: err as Record<string, unknown> }
              : {}),
          })
          break
        }
        default:
          break
      }
    },
  }
})

export const selectSimulationRun = (state: SimulationState) => state.run.data
export const selectSimulationRunStatus = (state: SimulationState) => state.run.status
export const selectSimulationRunId = (state: SimulationState) => state.runId
