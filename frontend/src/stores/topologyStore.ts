import { create } from 'zustand'
import * as topologyApi from '@/api/topology'
import { topologySnapshotDtoSchema } from '@/schemas/simulation'
import { toTopologySnapshot } from '@/adapters/simulation'
import type { TopologySnapshot } from '@/types/domain/simulation'
import type { RealtimeEventEnvelope } from '@/types/domain/realtime'
import type { BusinessFlow } from '@/types/domain/flow'
import type { NetworkLink } from '@/types/domain/link'
import type { NetworkNode } from '@/types/domain/node'
import { coerceEnum, FlowStatus, LinkStatus, NodeStatus, RealtimeEventType } from '@/types/enums'
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
 * 拓扑 Store（FE-006）。
 * - 只保存拓扑快照事实态；节点/链路/业务流的索引（byId）用 selector 现算，不重复存。
 * - 实时事件经纯函数 `applyTopologyEvent` 折算为快照变更；跨 run 事件被忽略。
 */

interface TopologyState {
  /** 当前绑定的 runId（`resetRun` 设置，用于晚到旧请求守卫）。 */
  runId: string | null
  snapshot: AsyncSlice<TopologySnapshot>

  resetRun: (runId?: string | null) => void
  loadTopology: (runId: string, params?: topologyApi.GetTopologyParams) => Promise<void>
  applyRealtimeEvent: (event: RealtimeEventEnvelope) => void
}

/** 就地替换快照中单个节点（不可变，返回新快照）。 */
export function updateNode(
  snapshot: TopologySnapshot,
  nodeId: string,
  patch: Partial<NetworkNode>,
): TopologySnapshot {
  return {
    ...snapshot,
    nodes: snapshot.nodes.map((n) => (n.nodeId === nodeId ? { ...n, ...patch } : n)),
  }
}

/** 就地替换快照中单条链路（不可变，返回新快照）。 */
export function updateLink(
  snapshot: TopologySnapshot,
  linkId: string,
  patch: Partial<NetworkLink>,
): TopologySnapshot {
  return {
    ...snapshot,
    links: snapshot.links.map((l) => (l.linkId === linkId ? { ...l, ...patch } : l)),
  }
}

/** 就地替换快照中单个业务流（不可变，返回新快照；无 flows 时原样返回）。 */
export function updateFlow(
  snapshot: TopologySnapshot,
  flowId: string,
  patch: Partial<BusinessFlow>,
): TopologySnapshot {
  if (!snapshot.flows) return snapshot
  return {
    ...snapshot,
    flows: snapshot.flows.map((f) => (f.flowId === flowId ? { ...f, ...patch } : f)),
  }
}

/**
 * 实时事件 → 拓扑快照变更（纯函数，便于单测）。
 * 不支持/不相关的事件原样返回快照引用，调用方可据此跳过无意义 set。
 */
export function applyTopologyEvent(
  snapshot: TopologySnapshot,
  event: RealtimeEventEnvelope,
): TopologySnapshot {
  switch (event.eventType) {
    case RealtimeEventType.NODE_STATUS_CHANGED: {
      const d = event.data as { nodeId?: unknown; newStatus?: unknown }
      if (typeof d.nodeId !== 'string') return snapshot
      const newStatus = coerceEnum(d.newStatus, NodeStatus)
      return newStatus ? updateNode(snapshot, d.nodeId, { status: newStatus }) : snapshot
    }
    case RealtimeEventType.NODE_POSITION_UPDATED: {
      const d = event.data as { nodeId?: unknown; position?: unknown }
      if (typeof d.nodeId !== 'string' || typeof d.position !== 'object' || d.position === null) {
        return snapshot
      }
      return updateNode(snapshot, d.nodeId, { position: d.position as NetworkNode['position'] })
    }
    case RealtimeEventType.LINK_STATUS_CHANGED: {
      const d = event.data as { linkId?: unknown; newStatus?: unknown }
      if (typeof d.linkId !== 'string') return snapshot
      const newStatus = coerceEnum(d.newStatus, LinkStatus)
      return newStatus ? updateLink(snapshot, d.linkId, { status: newStatus }) : snapshot
    }
    case RealtimeEventType.LINK_METRIC_UPDATED: {
      const d = event.data as { linkId?: unknown; params?: unknown }
      if (typeof d.linkId !== 'string' || typeof d.params !== 'object' || d.params === null) {
        return snapshot
      }
      return updateLink(snapshot, d.linkId, { params: d.params as NetworkLink['params'] })
    }
    case RealtimeEventType.FLOW_STATUS_CHANGED: {
      const d = event.data as { flowId?: unknown; status?: unknown }
      if (typeof d.flowId !== 'string') return snapshot
      const status = coerceEnum(d.status, FlowStatus)
      return status ? updateFlow(snapshot, d.flowId, { status }) : snapshot
    }
    case RealtimeEventType.ROUTE_CHANGED: {
      const d = event.data as { flowId?: unknown; newPath?: unknown }
      if (typeof d.flowId !== 'string' || !Array.isArray(d.newPath)) return snapshot
      return updateFlow(snapshot, d.flowId, { currentPath: d.newPath as string[] })
    }
    case RealtimeEventType.QOS_METRIC_UPDATED: {
      const d = event.data as { flowId?: unknown; measurement?: unknown }
      if (
        typeof d.flowId !== 'string' ||
        typeof d.measurement !== 'object' ||
        d.measurement === null
      ) {
        return snapshot
      }
      return updateFlow(snapshot, d.flowId, {
        measuredQos: d.measurement as BusinessFlow['measuredQos'],
      })
    }
    case RealtimeEventType.TOPOLOGY_UPDATED: {
      const d = event.data as { snapshotVersion?: unknown }
      if (typeof d.snapshotVersion !== 'number') return snapshot
      return { ...snapshot, version: d.snapshotVersion }
    }
    default:
      return snapshot
  }
}

export const useTopologyStore = create<TopologyState>()((set, get) => ({
  runId: null,
  snapshot: idleSlice<TopologySnapshot>(),

  resetRun: (runId) => set({ runId: runId ?? null, snapshot: idleSlice<TopologySnapshot>() }),

  loadTopology: async (runId, params = {}) => {
    const startedRunId = runId
    set((s) => ({ snapshot: loadingSlice(s.snapshot) }))
    try {
      const dto = await topologyApi.getTopology(runId, params)
      const parsed = topologySnapshotDtoSchema.safeParse(dto)
      if (!parsed.success) {
        if (isStaleRun(startedRunId, get().runId)) return
        set({
          snapshot: errorSlice(schemaValidationError('拓扑快照解析失败'), get().snapshot.data),
        })
        return
      }
      if (isStaleRun(startedRunId, get().runId)) return
      set({ snapshot: successSlice(toTopologySnapshot(parsed.data)) })
    } catch (error) {
      if (isStaleRun(startedRunId, get().runId)) return
      set({ snapshot: errorSlice(normalizeApiError(error), get().snapshot.data) })
    }
  },

  applyRealtimeEvent: (event) => {
    if (get().runId !== null && event.runId !== get().runId) return
    const current = get().snapshot.data
    if (!current) return
    const next = applyTopologyEvent(current, event)
    if (next !== current) set((s) => ({ snapshot: { ...s.snapshot, data: next } }))
  },
}))

export const selectTopologySnapshot = (state: TopologyState) => state.snapshot.data
export const selectTopologySnapshotStatus = (state: TopologyState) => state.snapshot.status
export const selectTopologyRunId = (state: TopologyState) => state.runId

export function selectNodesById(state: TopologyState): Map<string, NetworkNode> {
  return new Map((state.snapshot.data?.nodes ?? []).map((n) => [n.nodeId, n]))
}

export function selectLinksById(state: TopologyState): Map<string, NetworkLink> {
  return new Map((state.snapshot.data?.links ?? []).map((l) => [l.linkId, l]))
}

export function selectFlowsById(state: TopologyState): Map<string, BusinessFlow> {
  return new Map((state.snapshot.data?.flows ?? []).map((f) => [f.flowId, f]))
}
