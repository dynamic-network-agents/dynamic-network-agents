import type { NodeRole, NodeStatus, NodeType } from '../enums'

/** 节点坐标（§5.1）；坐标系待确认，见规范 M-01。 */
export interface Position {
  x: number
  y: number
  z?: number
  coordinateSystem?: string
}

/** 机动状态（速度 m/s、航向 deg）。 */
export interface Mobility {
  speedMps?: number
  headingDeg?: number
}

/** 节点资源摘要。 */
export interface NodeResources {
  energyPercent?: number
  computeCapacity?: number
  availableBandwidthBps?: number
}

/** 网络节点 ViewModel（§5.1）。可选字段缺失表示「未提供」，不用 0 代替。 */
export interface NetworkNode {
  nodeId: string
  name: string
  nodeType: NodeType
  role?: NodeRole
  status: NodeStatus
  position?: Position
  mobility?: Mobility
  resources?: NodeResources
  tags?: string[]
  createdAt?: string
  updatedAt?: string
}
