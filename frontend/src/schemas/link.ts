import { z } from 'zod'

/** 链路参数 DTO。ber / packetLossRate 为 0–1 小数，越界即校验失败。 */
export const linkParamsDtoSchema = z
  .object({
    delayMs: z.number(),
    jitterMs: z.number(),
    bandwidthBps: z.number(),
    ber: z.number().min(0).max(1),
    packetLossRate: z.number().min(0).max(1),
    rssiDbm: z.number().optional(),
    snrDb: z.number().optional(),
    frequencyHz: z.number().optional(),
  })
  .passthrough()

/** 链路服务端 DTO。枚举字段保持 string（由适配器兜底）；未知字段向前兼容。 */
export const linkDtoSchema = z
  .object({
    linkId: z.string(),
    linkPlane: z.string(),
    linkType: z.string(),
    srcNodeId: z.string(),
    dstNodeId: z.string(),
    direction: z.string(),
    status: z.string(),
    params: linkParamsDtoSchema,
    allocatedBandwidthBps: z.number().optional(),
    availableBandwidthBps: z.number().optional(),
    utilization: z.number().min(0).max(1).optional(),
    qualityScore: z.number().optional(),
    tsUs: z.number().optional(),
    time: z.string().optional(),
    updatedAt: z.string().optional(),
  })
  .passthrough()

export type LinkDto = z.infer<typeof linkDtoSchema>
export type LinkParamsDto = z.infer<typeof linkParamsDtoSchema>
