import type { QosSummaryDto } from '@/schemas/api'
import { request, type QueryOptions } from './client'
import type { QosFlowDetailDto } from './types'

/** QoS 汇总（§7.9 `GET /qos/summary`）。 */
export function getQosSummary(runId: string, options?: QueryOptions): Promise<QosSummaryDto> {
  return request<QosSummaryDto>({
    method: 'get',
    url: '/qos/summary',
    params: { runId },
    signal: options?.signal,
  })
}

/** 单业务 QoS 详情（§7.9 `/qos/flows/{flowId}`）。字段口径待与官方确认。 */
export function getFlowQos(
  flowId: string,
  runId: string,
  options?: QueryOptions,
): Promise<QosFlowDetailDto> {
  return request<QosFlowDetailDto>({
    method: 'get',
    url: `/qos/flows/${flowId}`,
    params: { runId },
    signal: options?.signal,
  })
}
