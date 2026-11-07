import { z } from 'zod'
import { flowDtoSchema } from './flow'
import { linkDtoSchema } from './link'
import { nodeDtoSchema } from './node'

const scenarioEventDtoSchema = z
  .object({
    eventId: z.string(),
    eventType: z.string(),
    triggerAtMs: z.number(),
    targetType: z.string(),
    targetId: z.string().optional(),
    payload: z.record(z.string(), z.unknown()),
    durationMs: z.number().optional(),
    enabled: z.boolean(),
    repeat: z.record(z.string(), z.unknown()).optional(),
    description: z.string().optional(),
  })
  .passthrough()

/** 场景服务端 DTO。`status`/事件枚举保持 string（由适配器兜底）；未知字段向前兼容。 */
export const scenarioDtoSchema = z
  .object({
    scenarioId: z.string(),
    name: z.string(),
    description: z.string().optional(),
    version: z.number(),
    status: z.string(),
    seed: z.number().optional(),
    durationMs: z.number().optional(),
    nodes: z.array(nodeDtoSchema),
    links: z.array(linkDtoSchema),
    flows: z.array(flowDtoSchema),
    events: z.array(scenarioEventDtoSchema).optional(),
    createdAt: z.string().optional(),
    updatedAt: z.string().optional(),
  })
  .passthrough()

export type ScenarioDto = z.infer<typeof scenarioDtoSchema>
export type ScenarioEventDto = z.infer<typeof scenarioEventDtoSchema>
