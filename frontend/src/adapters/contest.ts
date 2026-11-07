import type { ContestLinkDto } from '@/schemas/contest'
import { coerceEnumInsensitive } from '@/types/enums'
import { LinkDirection, LinkPlane, LinkStatus } from '@/types/enums'
import type { NetworkLink } from '@/types/domain/link'

export interface ContestLinkImportOptions {
  linkPlane?: LinkPlane
  direction?: LinkDirection
}

/**
 * 赛题链路样例 → NetworkLink（§6.1 / §6.2 导入适配）。
 * - `bandwitdhBps`（旧拼写）→ `params.bandwidthBps`
 * - `status` 小写归一（"up" → UP）
 * - `linkType` 透传为介质串；`linkPlane`/`direction` 赛题无此字段，默认 DATA / BIDIRECTIONAL（可覆盖）
 * - `time`/`tsUs` 同时保留，内部以 `tsUs` 为权威时间源
 */
export function contestLinkToNetworkLink(
  dto: ContestLinkDto,
  options: ContestLinkImportOptions = {},
): NetworkLink {
  return {
    linkId: dto.linkId,
    linkPlane: options.linkPlane ?? LinkPlane.DATA,
    linkType: dto.linkType,
    srcNodeId: dto.srcNodeId,
    dstNodeId: dto.dstNodeId,
    direction: options.direction ?? LinkDirection.BIDIRECTIONAL,
    status: coerceEnumInsensitive(dto.status, LinkStatus) ?? LinkStatus.UNKNOWN,
    params: {
      delayMs: dto.params.delayMs,
      jitterMs: dto.params.jitterMs,
      bandwidthBps: dto.params.bandwitdhBps,
      ber: dto.params.ber,
      packetLossRate: dto.params.packetLossRate,
    },
    tsUs: dto.tsUs,
    time: dto.time,
  }
}
