import { z } from 'zod'

const qosRequirementDtoSchema = z
  .object({
    maxDelayMs: z.number().optional(),
    maxJitterMs: z.number().optional(),
    maxPacketLossRate: z.number().min(0).max(1).optional(),
    minBandwidthBps: z.number().optional(),
    minReliability: z.number().min(0).max(1).optional(),
    availabilityTarget: z.number().optional(),
  })
  .passthrough()

export const qosViolationDtoSchema = z
  .object({
    flowId: z.string().optional(),
    metric: z.string(),
    actual: z.number(),
    threshold: z.number(),
    direction: z.string().optional(),
  })
  .passthrough()

const qosMeasurementDtoSchema = z
  .object({
    delayMs: z.number().optional(),
    jitterMs: z.number().optional(),
    packetLossRate: z.number().min(0).max(1).optional(),
    throughputBps: z.number().optional(),
    availability: z.number().min(0).max(1).optional(),
    isCompliant: z.boolean().optional(),
    violations: z.array(qosViolationDtoSchema).optional(),
  })
  .passthrough()

/** 业务流服务端 DTO。枚举字段保持 string（由适配器兜底）；未知字段向前兼容。 */
export const flowDtoSchema = z
  .object({
    flowId: z.string(),
    name: z.string(),
    serviceType: z.string(),
    srcNodeId: z.string(),
    dstNodeId: z.string(),
    priority: z.number(),
    requiredBandwidthBps: z.number(),
    qos: qosRequirementDtoSchema,
    status: z.string(),
    currentPath: z.array(z.string()).optional(),
    allocatedBandwidthBps: z.number().optional(),
    measuredQos: qosMeasurementDtoSchema.optional(),
    createdAt: z.string().optional(),
    updatedAt: z.string().optional(),
  })
  .passthrough()

export type FlowDto = z.infer<typeof flowDtoSchema>
export type QosRequirementDto = z.infer<typeof qosRequirementDtoSchema>
export type QosMeasurementDto = z.infer<typeof qosMeasurementDtoSchema>
