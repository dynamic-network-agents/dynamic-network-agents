import type { LinkDirection, LinkPlane, LinkStatus } from '../enums'

/** 链路参数（§5.2.2）。带宽 bps、时延/抖动 ms、ber/丢包率 0–1 小数。 */
export interface LinkParams {
  delayMs: number
  jitterMs: number
  bandwidthBps: number
  ber: number
  packetLossRate: number
  rssiDbm?: number
  snrDb?: number
  frequencyHz?: number
}

/**
 * 网络链路 ViewModel（§5.2）。
 * 控制链路与数据链路按独立 `linkId` + `linkPlane` 表达，不根据节点对推导；
 * `linkType` 为介质类型（小写开放字符串），与 `linkPlane` 正交。
 */
export interface NetworkLink {
  linkId: string
  linkPlane: LinkPlane
  linkType: string
  srcNodeId: string
  dstNodeId: string
  direction: LinkDirection
  status: LinkStatus
  params: LinkParams
  allocatedBandwidthBps?: number
  availableBandwidthBps?: number
  utilization?: number
  qualityScore?: number
  /** 源数据微秒时间戳（赛题字段）；内部权威时间源，`time` 仅作展示。 */
  tsUs?: number
  time?: string
  updatedAt?: string
}
