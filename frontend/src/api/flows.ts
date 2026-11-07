import type { FlowDto } from '@/schemas/flow'
import { request, type QueryOptions } from './client'
import type { FlowRouteDto, Page } from './types'

export interface ListFlowsParams {
  runId?: string
  status?: string
  page?: number
  pageSize?: number
}

/** 业务流列表（§7.9 `GET /flows`）。 */
export function listFlows(
  params: ListFlowsParams = {},
  options?: QueryOptions,
): Promise<Page<FlowDto>> {
  return request<Page<FlowDto>>({ method: 'get', url: '/flows', params, signal: options?.signal })
}

/** 业务流详情（§7.9，运行态必须传 `runId`）。 */
export function getFlow(flowId: string, runId: string, options?: QueryOptions): Promise<FlowDto> {
  return request<FlowDto>({
    method: 'get',
    url: `/flows/${flowId}`,
    params: { runId },
    signal: options?.signal,
  })
}

/** 业务当前路径（§7.9 `/flows/{flowId}/route`）。字段口径待与官方确认。 */
export function getFlowRoute(
  flowId: string,
  runId: string,
  options?: QueryOptions,
): Promise<FlowRouteDto> {
  return request<FlowRouteDto>({
    method: 'get',
    url: `/flows/${flowId}/route`,
    params: { runId },
    signal: options?.signal,
  })
}
