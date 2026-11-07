import { z } from 'zod'
import { qosViolationDtoSchema } from './flow'

/**
 * API 响应载荷 schema（规范 §7 中给出明确字段名者）。
 * - 场景校验结果（§7.6）：`data.valid` / `errors[]` / `warnings[]`。
 * - 运行时事件注入结果（§7.7）：`eventId` / `accepted` / `scheduledAtSimTimeMs`。
 * - QoS 汇总（§7.9）：`totalFlows` / `compliantFlows` / `nonCompliantFlows` / `complianceRate`
 *   / `byServiceType` / `violations[]`。
 * 其余聚合响应字段口径规范未给字段名，暂不建 schema（见 `src/api/types.ts` 的不透明类型说明）。
 */

const fieldErrorSchema = z
  .object({
    code: z.string(),
    path: z.string(),
    message: z.string(),
  })
  .passthrough()

/** 场景校验结果 DTO（§7.6）。 */
export const scenarioValidateResultDtoSchema = z
  .object({
    valid: z.boolean(),
    errors: z.array(fieldErrorSchema),
    warnings: z.array(fieldErrorSchema),
  })
  .passthrough()

/** 运行时事件注入结果 DTO（§7.7）。 */
export const eventInjectionResultDtoSchema = z
  .object({
    eventId: z.string(),
    accepted: z.boolean(),
    scheduledAtSimTimeMs: z.number(),
  })
  .passthrough()

/** QoS 汇总 DTO（§7.9）。`byServiceType` 结构规范未明确，宽松透传。 */
export const qosSummaryDtoSchema = z
  .object({
    totalFlows: z.number(),
    compliantFlows: z.number(),
    nonCompliantFlows: z.number(),
    complianceRate: z.number(),
    byServiceType: z.record(z.string(), z.unknown()).optional(),
    violations: z.array(qosViolationDtoSchema).optional(),
  })
  .passthrough()

export type ScenarioValidateResultDto = z.infer<typeof scenarioValidateResultDtoSchema>
export type EventInjectionResultDto = z.infer<typeof eventInjectionResultDtoSchema>
export type QosSummaryDto = z.infer<typeof qosSummaryDtoSchema>
