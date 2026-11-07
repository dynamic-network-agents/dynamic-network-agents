import { create } from 'zustand'
import { createJSONStorage, persist, type StateStorage } from 'zustand/middleware'

/**
 * 全局运行上下文（设计 §3.2）：projectId / scenarioId / runId。
 *
 * 仅这三者持久化（刷新后可按 runId 恢复）；domain 数据（拓扑/仿真/场景）仍内存、按需重拉，
 * 不整包持久化。切换 run 时由页面/编排层调用各 domain store 的 `resetRun` 清理，本 store 不直接
 * 依赖 domain store（保持 app → domain 单向、避免循环依赖）。
 */

export interface AppState {
  projectId: string | null
  scenarioId: string | null
  runId: string | null
  setProjectId: (id: string | null) => void
  setScenarioId: (id: string | null) => void
  setRunId: (id: string | null) => void
  resetRunContext: () => void
}

/** localStorage 缺省（node 测试/SSR）时降级为不持久化，不抛错。 */
const safeStorage: StateStorage = {
  getItem: (name) => {
    try {
      return typeof localStorage === 'undefined' ? null : localStorage.getItem(name)
    } catch {
      return null
    }
  },
  setItem: (name, value) => {
    try {
      if (typeof localStorage !== 'undefined') localStorage.setItem(name, value)
    } catch {
      /* noop */
    }
  },
  removeItem: (name) => {
    try {
      if (typeof localStorage !== 'undefined') localStorage.removeItem(name)
    } catch {
      /* noop */
    }
  },
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      projectId: null,
      scenarioId: null,
      runId: null,
      setProjectId: (projectId) => set({ projectId }),
      setScenarioId: (scenarioId) => set({ scenarioId }),
      setRunId: (runId) => set({ runId }),
      resetRunContext: () => set({ projectId: null, scenarioId: null, runId: null }),
    }),
    {
      name: 'app-context',
      storage: createJSONStorage(() => safeStorage),
      partialize: (state) => ({
        projectId: state.projectId,
        scenarioId: state.scenarioId,
        runId: state.runId,
      }),
    },
  ),
)

export const selectProjectId = (state: AppState) => state.projectId
export const selectScenarioId = (state: AppState) => state.scenarioId
export const selectRunId = (state: AppState) => state.runId
