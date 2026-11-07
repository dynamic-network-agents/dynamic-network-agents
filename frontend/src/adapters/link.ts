import type { LinkDto } from '@/schemas/link'
import { coerceEnum } from '@/types/enums'
import { LinkDirection, LinkPlane, LinkStatus } from '@/types/enums'
import type { NetworkLink } from '@/types/domain/link'

/** 链路 DTO → ViewModel：枚举兜底；参数单位（bps / ms / 0–1）原样透传。 */
export function toNetworkLink(dto: LinkDto): NetworkLink {
  return {
    linkId: dto.linkId,
    linkPlane: coerceEnum(dto.linkPlane, LinkPlane) ?? LinkPlane.DATA,
    linkType: dto.linkType,
    srcNodeId: dto.srcNodeId,
    dstNodeId: dto.dstNodeId,
    direction: coerceEnum(dto.direction, LinkDirection) ?? LinkDirection.BIDIRECTIONAL,
    status: coerceEnum(dto.status, LinkStatus) ?? LinkStatus.UNKNOWN,
    params: { ...dto.params },
    allocatedBandwidthBps: dto.allocatedBandwidthBps,
    availableBandwidthBps: dto.availableBandwidthBps,
    utilization: dto.utilization,
    qualityScore: dto.qualityScore,
    tsUs: dto.tsUs,
    time: dto.time,
    updatedAt: dto.updatedAt,
  }
}
