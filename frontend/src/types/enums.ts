/**
 * 前端枚举定义，对齐《前后端数据模型与接口规范 v1.0》§4。
 *
 * 约定：
 * - 采用 `as const` 对象 + 同名联合类型；`linkType` 为开放小写字符串，不作为枚举。
 * - 未知枚举值不抛错、不臆造语义：`coerceEnum` / `coerceEnumInsensitive` 返回 `undefined`，
 *   由适配器在必填字段处 `?? 兜底值` 兜底、在可选字段处丢弃。
 * - 无 UNKNOWN/OTHER/CUSTOM 成员的枚举，兜底值取保守默认（便于评审与修订）：
 *   NodeType→OTHER、NodeStatus→UNKNOWN、LinkStatus→UNKNOWN、ScenarioEventType→CUSTOM；
 *   LinkPlane→DATA（赛题仅数据链路，未知按数据面兜底）、LinkDirection→BIDIRECTIONAL、
 *   ServiceType→DATA、FlowStatus→PENDING（未知视为未激活）、
 *   SimulationStatus→CREATED（未知视为初始态）、ScenarioStatus→DRAFT。
 * - 二轮枚举（AgentType/AgentStatus/TaskStatus/PolicyType/PolicyStatus 等）随 FE-006 补齐。
 */

export const NodeType = {
  UAV: 'UAV',
  UGV: 'UGV',
  USV: 'USV',
  UUV: 'UUV',
  RELAY: 'RELAY',
  BASE: 'BASE',
  C2: 'C2',
  EDGE: 'EDGE',
  OTHER: 'OTHER',
} as const
export type NodeType = (typeof NodeType)[keyof typeof NodeType]

export const NodeRole = {
  MEMBER: 'MEMBER',
  RELAY: 'RELAY',
  CLUSTER_HEAD: 'CLUSTER_HEAD',
  BACKBONE: 'BACKBONE',
  GATEWAY: 'GATEWAY',
  COORDINATOR: 'COORDINATOR',
} as const
export type NodeRole = (typeof NodeRole)[keyof typeof NodeRole]

export const NodeStatus = {
  ONLINE: 'ONLINE',
  OFFLINE: 'OFFLINE',
  DEGRADED: 'DEGRADED',
  UNKNOWN: 'UNKNOWN',
} as const
export type NodeStatus = (typeof NodeStatus)[keyof typeof NodeStatus]

export const LinkPlane = {
  CONTROL: 'CONTROL',
  DATA: 'DATA',
} as const
export type LinkPlane = (typeof LinkPlane)[keyof typeof LinkPlane]

export const LinkStatus = {
  UP: 'UP',
  DEGRADED: 'DEGRADED',
  DOWN: 'DOWN',
  UNKNOWN: 'UNKNOWN',
} as const
export type LinkStatus = (typeof LinkStatus)[keyof typeof LinkStatus]

export const LinkDirection = {
  BIDIRECTIONAL: 'BIDIRECTIONAL',
  UNIDIRECTIONAL: 'UNIDIRECTIONAL',
} as const
export type LinkDirection = (typeof LinkDirection)[keyof typeof LinkDirection]

export const ServiceType = {
  VOICE: 'VOICE',
  VIDEO: 'VIDEO',
  IMAGE: 'IMAGE',
  DATA: 'DATA',
} as const
export type ServiceType = (typeof ServiceType)[keyof typeof ServiceType]

export const FlowStatus = {
  PENDING: 'PENDING',
  ACTIVE: 'ACTIVE',
  DEGRADED: 'DEGRADED',
  INTERRUPTED: 'INTERRUPTED',
  FINISHED: 'FINISHED',
  REJECTED: 'REJECTED',
} as const
export type FlowStatus = (typeof FlowStatus)[keyof typeof FlowStatus]

export const SimulationStatus = {
  CREATED: 'CREATED',
  VALIDATING: 'VALIDATING',
  READY: 'READY',
  RUNNING: 'RUNNING',
  PAUSED: 'PAUSED',
  STOPPING: 'STOPPING',
  STOPPED: 'STOPPED',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
} as const
export type SimulationStatus = (typeof SimulationStatus)[keyof typeof SimulationStatus]

export const ScenarioStatus = {
  DRAFT: 'DRAFT',
  VALID: 'VALID',
  ARCHIVED: 'ARCHIVED',
} as const
export type ScenarioStatus = (typeof ScenarioStatus)[keyof typeof ScenarioStatus]

export const ScenarioEventType = {
  NODE_ONLINE: 'NODE_ONLINE',
  NODE_OFFLINE: 'NODE_OFFLINE',
  NODE_MOVE: 'NODE_MOVE',
  LINK_UP: 'LINK_UP',
  LINK_DOWN: 'LINK_DOWN',
  LINK_PARAM_CHANGE: 'LINK_PARAM_CHANGE',
  LINK_FLAP: 'LINK_FLAP',
  BANDWIDTH_CHANGE: 'BANDWIDTH_CHANGE',
  FLOW_ADD: 'FLOW_ADD',
  FLOW_REMOVE: 'FLOW_REMOVE',
  FLOW_QOS_CHANGE: 'FLOW_QOS_CHANGE',
  INTERFERENCE_CHANGE: 'INTERFERENCE_CHANGE',
  COORDINATOR_FAILURE: 'COORDINATOR_FAILURE',
  CUSTOM: 'CUSTOM',
} as const
export type ScenarioEventType = (typeof ScenarioEventType)[keyof typeof ScenarioEventType]

/** 首轮实时事件类型（§8.3 中与 Node/Link/Flow/Topology/Simulation 相关者；二轮事件延后）。 */
export const RealtimeEventType = {
  SIMULATION_STATUS_CHANGED: 'SIMULATION_STATUS_CHANGED',
  SIMULATION_TIME_UPDATED: 'SIMULATION_TIME_UPDATED',
  NODE_STATUS_CHANGED: 'NODE_STATUS_CHANGED',
  NODE_POSITION_UPDATED: 'NODE_POSITION_UPDATED',
  LINK_STATUS_CHANGED: 'LINK_STATUS_CHANGED',
  LINK_METRIC_UPDATED: 'LINK_METRIC_UPDATED',
  TOPOLOGY_UPDATED: 'TOPOLOGY_UPDATED',
  ROUTE_CHANGED: 'ROUTE_CHANGED',
  FLOW_STATUS_CHANGED: 'FLOW_STATUS_CHANGED',
  QOS_METRIC_UPDATED: 'QOS_METRIC_UPDATED',
  SIMULATION_COMPLETED: 'SIMULATION_COMPLETED',
  SIMULATION_ERROR: 'SIMULATION_ERROR',
} as const
export type RealtimeEventType = (typeof RealtimeEventType)[keyof typeof RealtimeEventType]

type EnumObject = Readonly<Record<string, string>>
export type EnumValue<T extends EnumObject> = T[keyof T]

/** 精确匹配枚举值；未知/非字符串返回 `undefined`（由调用方决定兜底或丢弃）。 */
export function coerceEnum<T extends EnumObject>(
  value: unknown,
  enumObj: T,
): EnumValue<T> | undefined {
  if (typeof value === 'string') {
    const hit = Object.values(enumObj).find((v) => v === value)
    if (hit) return hit as EnumValue<T>
  }
  return undefined
}

/** 大小写不敏感匹配枚举值（用于赛题 `status` 小写等旧字段归一）；未知返回 `undefined`。 */
export function coerceEnumInsensitive<T extends EnumObject>(
  value: unknown,
  enumObj: T,
): EnumValue<T> | undefined {
  if (typeof value === 'string') {
    const lower = value.toLowerCase()
    const hit = Object.values(enumObj).find((v) => v.toLowerCase() === lower)
    if (hit) return hit as EnumValue<T>
  }
  return undefined
}
