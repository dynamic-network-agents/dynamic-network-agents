import type { FlowDto } from '@/schemas/flow'
import type { LinkDto } from '@/schemas/link'
import type { NodeDto } from '@/schemas/node'
import type { ScenarioDto, ScenarioEventDto } from '@/schemas/scenario'
import type { ScenarioValidateResultDto } from '@/schemas/api'
import { request, type QueryOptions } from './client'
import type { Page } from './types'

/** 创建/更新场景的请求体（§7.6）；`scenarioId`/`version`/时间字段由后端生成。 */
export interface ScenarioUpsertInput {
  name: string
  description?: string
  seed?: number
  durationMs?: number
  nodes: NodeDto[]
  links: LinkDto[]
  flows: FlowDto[]
  events?: ScenarioEventDto[]
}

/** 场景校验请求体（§7.6）。 */
export interface ScenarioValidateInput {
  version?: number
  strict?: boolean
}

export interface UpdateScenarioOptions {
  /** 乐观锁：`If-Match` 头（§7.1/7.6）。 */
  ifMatch?: string
  /** 乐观锁：请求体 `expectedVersion`（§7.6）。 */
  expectedVersion?: number
}

export interface ListScenariosParams {
  page?: number
  pageSize?: number
  status?: string
}

export function listScenarios(
  params: ListScenariosParams = {},
  options?: QueryOptions,
): Promise<Page<ScenarioDto>> {
  return request<Page<ScenarioDto>>({
    method: 'get',
    url: '/scenarios',
    params,
    signal: options?.signal,
  })
}

export function getScenario(scenarioId: string, options?: QueryOptions): Promise<ScenarioDto> {
  return request<ScenarioDto>({
    method: 'get',
    url: `/scenarios/${scenarioId}`,
    signal: options?.signal,
  })
}

export function createScenario(input: ScenarioUpsertInput): Promise<ScenarioDto> {
  return request<ScenarioDto>({ method: 'post', url: '/scenarios', data: input })
}

export function updateScenario(
  scenarioId: string,
  input: ScenarioUpsertInput,
  options: UpdateScenarioOptions = {},
): Promise<ScenarioDto> {
  const data =
    options.expectedVersion !== undefined
      ? { ...input, expectedVersion: options.expectedVersion }
      : input
  return request<ScenarioDto>({
    method: 'put',
    url: `/scenarios/${scenarioId}`,
    data,
    ifMatch: options.ifMatch,
  })
}

export function deleteScenario(scenarioId: string): Promise<void> {
  return request<void>({ method: 'delete', url: `/scenarios/${scenarioId}` })
}

export function validateScenario(
  scenarioId: string,
  input: ScenarioValidateInput = {},
): Promise<ScenarioValidateResultDto> {
  return request<ScenarioValidateResultDto>({
    method: 'post',
    url: `/scenarios/${scenarioId}/validate`,
    data: input,
  })
}

export function cloneScenario(scenarioId: string): Promise<ScenarioDto> {
  return request<ScenarioDto>({ method: 'post', url: `/scenarios/${scenarioId}/clone` })
}
