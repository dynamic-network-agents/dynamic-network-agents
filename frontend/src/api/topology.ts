import type { LinkDto } from '@/schemas/link'
import type { NodeDto } from '@/schemas/node'
import type { TopologySnapshotDto } from '@/schemas/simulation'
import { request, type QueryOptions } from './client'
import type { NodeNeighborsDto, NodeRoutesDto } from './types'

export interface GetTopologyParams {
  includeFlows?: boolean
  sinceVersion?: number
}

/** 拓扑快照（§7.8 `GET /simulations/{runId}/topology`）。 */
export function getTopology(
  runId: string,
  params: GetTopologyParams = {},
  options?: QueryOptions,
): Promise<TopologySnapshotDto> {
  return request<TopologySnapshotDto>({
    method: 'get',
    url: `/simulations/${runId}/topology`,
    params,
    signal: options?.signal,
  })
}

/** 节点详情（§7.8，运行态必须传 `runId`）。 */
export function getNode(nodeId: string, runId: string, options?: QueryOptions): Promise<NodeDto> {
  return request<NodeDto>({
    method: 'get',
    url: `/nodes/${nodeId}`,
    params: { runId },
    signal: options?.signal,
  })
}

/** 链路详情（§7.8，运行态必须传 `runId`）。 */
export function getLink(linkId: string, runId: string, options?: QueryOptions): Promise<LinkDto> {
  return request<LinkDto>({
    method: 'get',
    url: `/links/${linkId}`,
    params: { runId },
    signal: options?.signal,
  })
}

/** 邻居表（§7.8）。字段口径待与官方确认。 */
export function getNodeNeighbors(
  nodeId: string,
  runId: string,
  options?: QueryOptions,
): Promise<NodeNeighborsDto> {
  return request<NodeNeighborsDto>({
    method: 'get',
    url: `/nodes/${nodeId}/neighbors`,
    params: { runId },
    signal: options?.signal,
  })
}

/** 节点路由表（§7.8）。字段口径待与官方确认。 */
export function getNodeRoutes(
  nodeId: string,
  runId: string,
  options?: QueryOptions,
): Promise<NodeRoutesDto> {
  return request<NodeRoutesDto>({
    method: 'get',
    url: `/nodes/${nodeId}/routes`,
    params: { runId },
    signal: options?.signal,
  })
}
