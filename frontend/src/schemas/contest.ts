import { z } from 'zod'

/** 赛题链路参数原文（§6.1）：`bandwitdhBps` 为原文拼写（缺 d），适配层归一为 `bandwidthBps`。 */
export const contestLinkParamsDtoSchema = z
  .object({
    delayMs: z.number(),
    jitterMs: z.number(),
    bandwitdhBps: z.number(),
    ber: z.number().min(0).max(1),
    packetLossRate: z.number().min(0).max(1),
  })
  .passthrough()

/** 赛题链路样例原文（§6.1）：`status` 为小写、含 `time`/`tsUs`、无 `linkPlane`/`direction`。 */
export const contestLinkDtoSchema = z
  .object({
    linkId: z.string(),
    linkType: z.string(),
    srcNodeId: z.string(),
    dstNodeId: z.string(),
    status: z.string(),
    params: contestLinkParamsDtoSchema,
    time: z.string().optional(),
    tsUs: z.number().optional(),
  })
  .passthrough()

export type ContestLinkDto = z.infer<typeof contestLinkDtoSchema>
