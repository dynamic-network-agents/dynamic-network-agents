import { z } from 'zod'
import { flowDtoSchema } from './flow'
import { linkDtoSchema } from './link'
import { nodeDtoSchema } from './node'

/** 仿真运行服务端 DTO。`status` 保持 string（由适配器兜底）。 */
export const simulationRunDtoSchema = z
  .object({
    runId: z.string(),
    scenarioId: z.string(),
    scenarioVersion: z.number(),
    status: z.string(),
    simTimeMs: z.number(),
    speed: z.number(),
    seed: z.number().optional(),
    startedAt: z.string().optional(),
    finishedAt: z.string().optional(),
    createdAt: z.string().optional(),
    updatedAt: z.string().optional(),
    error: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough()

const topologySummaryDtoSchema = z
  .object({
    nodeCount: z.number(),
    onlineNodeCount: z.number(),
    linkCount: z.number(),
    upLinkCount: z.number(),
    connectedComponents: z.number(),
  })
  .passthrough()

/** 拓扑快照服务端 DTO。links[] 必须保留 linkPlane，不根据节点对推导链路。 */
export const topologySnapshotDtoSchema = z
  .object({
    runId: z.string(),
    version: z.number(),
    simTimeMs: z.number(),
    generatedAt: z.string().optional(),
    nodes: z.array(nodeDtoSchema),
    links: z.array(linkDtoSchema),
    flows: z.array(flowDtoSchema).optional(),
    summary: topologySummaryDtoSchema.optional(),
  })
  .passthrough()

export type SimulationRunDto = z.infer<typeof simulationRunDtoSchema>
export type TopologySnapshotDto = z.infer<typeof topologySnapshotDtoSchema>
