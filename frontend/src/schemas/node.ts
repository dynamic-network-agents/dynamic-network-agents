import { z } from 'zod'

const positionDtoSchema = z
  .object({
    x: z.number(),
    y: z.number(),
    z: z.number().optional(),
    coordinateSystem: z.string().optional(),
  })
  .passthrough()

const mobilityDtoSchema = z
  .object({
    speedMps: z.number().optional(),
    headingDeg: z.number().optional(),
  })
  .passthrough()

const nodeResourcesDtoSchema = z
  .object({
    energyPercent: z.number().min(0).max(100).optional(),
    computeCapacity: z.number().optional(),
    availableBandwidthBps: z.number().optional(),
  })
  .passthrough()

/** 节点服务端 DTO。枚举字段保持 string（由适配器兜底）；未知字段向前兼容。 */
export const nodeDtoSchema = z
  .object({
    nodeId: z.string(),
    name: z.string(),
    nodeType: z.string(),
    role: z.string().optional(),
    status: z.string(),
    position: positionDtoSchema.optional(),
    mobility: mobilityDtoSchema.optional(),
    resources: nodeResourcesDtoSchema.optional(),
    tags: z.array(z.string()).optional(),
    createdAt: z.string().optional(),
    updatedAt: z.string().optional(),
  })
  .passthrough()

export type NodeDto = z.infer<typeof nodeDtoSchema>
