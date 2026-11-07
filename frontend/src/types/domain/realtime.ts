import type {
  FlowStatus,
  LinkStatus,
  NodeStatus,
  RealtimeEventType,
  SimulationStatus,
} from '../enums'
import type { QosMeasurement } from './flow'
import type { LinkParams } from './link'
import type { Position } from './node'

/**
 * 实时事件信封（§8.2）。
 * `eventType` 保持开放 string（向前兼容）；已知首轮事件的 data 形态见 `RealtimeEventDataMap`。
 * `seq` 在单 runId 事件流内严格递增。
 */
export interface RealtimeEventEnvelope {
  eventId: string
  eventType: string
  runId: string
  seq: number
  version?: number
  simTimeMs?: number
  timestamp?: string
  traceId?: string
  data: unknown
}

/** 首轮实时事件的 data 形态（§8.3）。 */
export interface RealtimeEventDataMap {
  SIMULATION_STATUS_CHANGED: { status: SimulationStatus; previousStatus?: SimulationStatus }
  SIMULATION_TIME_UPDATED: { simTimeMs: number; speed?: number }
  NODE_STATUS_CHANGED: { nodeId: string; oldStatus?: NodeStatus; newStatus: NodeStatus }
  NODE_POSITION_UPDATED: { nodeId: string; position: Position }
  LINK_STATUS_CHANGED: { linkId: string; oldStatus?: LinkStatus; newStatus: LinkStatus }
  LINK_METRIC_UPDATED: { linkId: string; params: LinkParams }
  TOPOLOGY_UPDATED: { snapshotVersion: number; changeSummary?: Record<string, unknown> }
  ROUTE_CHANGED: { flowId: string; oldPath?: string[]; newPath: string[] }
  FLOW_STATUS_CHANGED: { flowId: string; status: FlowStatus }
  QOS_METRIC_UPDATED: { flowId: string; measurement: QosMeasurement }
  SIMULATION_COMPLETED: { result?: Record<string, unknown> }
  SIMULATION_ERROR: { error: Record<string, unknown> }
}

export type RealtimeEventData<K extends RealtimeEventType> = RealtimeEventDataMap[K]

/** 窄化后的首轮实时事件（data 按 eventType 定型）。 */
export type RealtimeEvent<K extends RealtimeEventType = RealtimeEventType> =
  RealtimeEventEnvelope & {
    eventType: K
    data: RealtimeEventDataMap[K]
  }
