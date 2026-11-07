import type { NodeDto } from '@/schemas/node'
import { coerceEnum } from '@/types/enums'
import { NodeRole, NodeStatus, NodeType } from '@/types/enums'
import type { NetworkNode } from '@/types/domain/node'

/** 节点 DTO → ViewModel：枚举兜底；可选枚举（role）未知则丢弃；坐标/机动/资源原样透传。 */
export function toNetworkNode(dto: NodeDto): NetworkNode {
  return {
    nodeId: dto.nodeId,
    name: dto.name,
    nodeType: coerceEnum(dto.nodeType, NodeType) ?? NodeType.OTHER,
    role: dto.role ? coerceEnum(dto.role, NodeRole) : undefined,
    status: coerceEnum(dto.status, NodeStatus) ?? NodeStatus.UNKNOWN,
    position: dto.position,
    mobility: dto.mobility,
    resources: dto.resources,
    tags: dto.tags,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}
