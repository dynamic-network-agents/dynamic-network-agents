import type { FlowStatus, ServiceType } from '../enums'

/** QoS 约束（§5.3）。数值门槛由场景/测试集提供，前端不写死阈值。 */
export interface QosRequirement {
  maxDelayMs?: number
  maxJitterMs?: number
  maxPacketLossRate?: number
  minBandwidthBps?: number
  minReliability?: number
  availabilityTarget?: number
}

/** QoS 违例项（§7.9）：指标、实际值、阈值、超限方向。 */
export interface QosViolation {
  flowId?: string
  metric: string
  actual: number
  threshold: number
  direction?: string
}

/** QoS 测量值（§5.8）；与 QoS 要求分离，`isCompliant` 由后端计算。 */
export interface QosMeasurement {
  delayMs?: number
  jitterMs?: number
  packetLossRate?: number
  throughputBps?: number
  availability?: number
  isCompliant?: boolean
  violations?: QosViolation[]
}

/** 业务流 ViewModel（§5.3）。`priority` 数值越小优先级越高（见规范 M-06）。 */
export interface BusinessFlow {
  flowId: string
  name: string
  serviceType: ServiceType
  srcNodeId: string
  dstNodeId: string
  priority: number
  requiredBandwidthBps: number
  qos: QosRequirement
  status: FlowStatus
  currentPath?: string[]
  allocatedBandwidthBps?: number
  measuredQos?: QosMeasurement
  createdAt?: string
  updatedAt?: string
}
