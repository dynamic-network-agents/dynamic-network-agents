import { request, type QueryOptions } from './client'
import type { DashboardSummaryDto } from './types'

/**
 * 系统总览摘要（§7.11 `GET /dashboard/summary`）。
 * 规范只描述内容（仿真状态/时间、节点在线/链路可用/连通度、活跃业务/QoS 达标率、
 * Agent 在线/任务数、最近策略/告警），未给字段名——暂以 `DashboardSummaryDto`（不透明）返回，
 * 字段口径待与官方确认，由 Dashboard feature 任务收敛。
 */
export function getDashboardSummary(
  runId?: string,
  options?: QueryOptions,
): Promise<DashboardSummaryDto> {
  return request<DashboardSummaryDto>({
    method: 'get',
    url: '/dashboard/summary',
    params: { runId },
    signal: options?.signal,
  })
}
