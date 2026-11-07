import { request, type QueryOptions } from './client'
import type { ResourceAllocationSnapshotDto, ResourceHistoryDto } from './types'

/** 资源分配快照（§7.9 `GET /resources/allocation`，可选 `linkId` 过滤）。字段口径待与官方确认。 */
export function getResourceAllocation(
  runId: string,
  linkId?: string,
  options?: QueryOptions,
): Promise<ResourceAllocationSnapshotDto> {
  return request<ResourceAllocationSnapshotDto>({
    method: 'get',
    url: '/resources/allocation',
    params: { runId, linkId },
    signal: options?.signal,
  })
}

/** 资源变化记录（§7.9 `GET /resources/history`）。字段口径待与官方确认。 */
export function getResourceHistory(
  runId: string,
  options?: QueryOptions,
): Promise<ResourceHistoryDto> {
  return request<ResourceHistoryDto>({
    method: 'get',
    url: '/resources/history',
    params: { runId },
    signal: options?.signal,
  })
}
