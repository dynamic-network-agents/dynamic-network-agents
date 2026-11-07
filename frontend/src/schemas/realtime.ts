import { z } from 'zod'

/** 实时事件信封 DTO（§8.2）。eventType/data 保持开放，具体窄化在 store/UI 层。 */
export const realtimeEventEnvelopeDtoSchema = z
  .object({
    eventId: z.string(),
    eventType: z.string(),
    runId: z.string(),
    seq: z.number(),
    version: z.number().optional(),
    simTimeMs: z.number().optional(),
    timestamp: z.string().optional(),
    traceId: z.string().optional(),
    data: z.unknown(),
  })
  .passthrough()

export type RealtimeEventEnvelopeDto = z.infer<typeof realtimeEventEnvelopeDtoSchema>
