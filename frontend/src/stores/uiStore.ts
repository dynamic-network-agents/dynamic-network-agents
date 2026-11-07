import { create } from 'zustand'

/**
 * 本地 UI 状态（设计 §3.2）：当前选中、WebSocket 连接状态、显示偏好。
 * 这些是「本地临时态」，不持久化；表格筛选、抽屉开关等更细的页面态留在组件内部（§3.2）。
 */

/** WebSocket 连接状态。 */
export type WsStatus = 'idle' | 'connecting' | 'open' | 'closed'

export interface UiState {
  selectedNodeId: string | null
  selectedLinkId: string | null
  selectedFlowId: string | null
  wsStatus: WsStatus
  /** 用户显示偏好（键值开放，避免为单个偏好频繁改类型）。 */
  displayPrefs: Record<string, unknown>

  selectNode: (id: string | null) => void
  selectLink: (id: string | null) => void
  selectFlow: (id: string | null) => void
  clearSelection: () => void
  setWsStatus: (status: WsStatus) => void
  setDisplayPref: (key: string, value: unknown) => void
}

export const useUiStore = create<UiState>()((set) => ({
  selectedNodeId: null,
  selectedLinkId: null,
  selectedFlowId: null,
  wsStatus: 'idle',
  displayPrefs: {},

  selectNode: (selectedNodeId) => set({ selectedNodeId }),
  selectLink: (selectedLinkId) => set({ selectedLinkId }),
  selectFlow: (selectedFlowId) => set({ selectedFlowId }),
  clearSelection: () => set({ selectedNodeId: null, selectedLinkId: null, selectedFlowId: null }),
  setWsStatus: (wsStatus) => set({ wsStatus }),
  setDisplayPref: (key, value) =>
    set((state) => ({ displayPrefs: { ...state.displayPrefs, [key]: value } })),
}))

export const selectSelectedNodeId = (state: UiState) => state.selectedNodeId
export const selectSelectedLinkId = (state: UiState) => state.selectedLinkId
export const selectSelectedFlowId = (state: UiState) => state.selectedFlowId
export const selectWsStatus = (state: UiState) => state.wsStatus
export const selectDisplayPrefs = (state: UiState) => state.displayPrefs
