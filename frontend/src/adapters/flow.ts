import type { FlowDto, QosMeasurementDto, QosRequirementDto } from '@/schemas/flow'
import { coerceEnum } from '@/types/enums'
import { FlowStatus, ServiceType } from '@/types/enums'
import type { BusinessFlow, QosMeasurement, QosRequirement } from '@/types/domain/flow'

function toQosRequirement(dto: QosRequirementDto): QosRequirement {
  return { ...dto }
}

function toQosMeasurement(dto: QosMeasurementDto): QosMeasurement {
  return { ...dto }
}

/** 业务流 DTO → ViewModel：枚举兜底；QoS 要求/测量原样透传。 */
export function toBusinessFlow(dto: FlowDto): BusinessFlow {
  return {
    flowId: dto.flowId,
    name: dto.name,
    serviceType: coerceEnum(dto.serviceType, ServiceType) ?? ServiceType.DATA,
    srcNodeId: dto.srcNodeId,
    dstNodeId: dto.dstNodeId,
    priority: dto.priority,
    requiredBandwidthBps: dto.requiredBandwidthBps,
    qos: toQosRequirement(dto.qos),
    status: coerceEnum(dto.status, FlowStatus) ?? FlowStatus.PENDING,
    currentPath: dto.currentPath,
    allocatedBandwidthBps: dto.allocatedBandwidthBps,
    measuredQos: dto.measuredQos ? toQosMeasurement(dto.measuredQos) : undefined,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}
