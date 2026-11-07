import type { SimulationRunDto } from '@/schemas/simulation'
import type { EventInjectionResultDto } from '@/schemas/api'
import { request, type QueryOptions } from './client'
import type { SimulationCapabilitiesDto } from './types'

/** 创建运行请求体（§7.7）。 */
export interface CreateSimulationInput {
  scenarioId: string
  scenarioVersion: number
  seed?: number
  speed?: number
  options?: {
    enableAgents?: boolean
    enableRealtimeEvents?: boolean
  }
}

/** 单步推进请求体（§7.7）。 */
export interface StepSimulationInput {
  steps?: number
}

/** 调速请求体（§7.7）。 */
export interface SetSimulationSpeedInput {
  speed: number
}

/** 运行时注入事件请求体（§7.7）。 */
export interface InjectSimulationEventInput {
  eventType: string
  triggerAtMs: number
  targetType: string
  targetId?: string
  payload: Record<string, unknown>
  durationMs?: number
}

/** 写操作传输选项（幂等键，§7.1）。 */
export interface WriteOptions {
  idempotencyKey?: string
}

export function createSimulation(
  input: CreateSimulationInput,
  options: WriteOptions = {},
): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({
    method: 'post',
    url: '/simulations',
    data: input,
    idempotencyKey: options.idempotencyKey,
  })
}

export function getSimulation(runId: string, options?: QueryOptions): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({
    method: 'get',
    url: `/simulations/${runId}`,
    signal: options?.signal,
  })
}

/**
 * 运行状态（§7.7 `GET /simulations/{runId}/status`）。
 * 状态端点可能返回轻量载荷，字段口径待确认；按 §7.7「控制响应返回最新 SimulationRun」统一按
 * `SimulationRunDto` 处理（含 status/simTimeMs 等）。
 */
export function getSimulationStatus(
  runId: string,
  options?: QueryOptions,
): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({
    method: 'get',
    url: `/simulations/${runId}/status`,
    signal: options?.signal,
  })
}

export function startSimulation(runId: string): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({ method: 'post', url: `/simulations/${runId}/start` })
}

export function pauseSimulation(runId: string): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({ method: 'post', url: `/simulations/${runId}/pause` })
}

export function resumeSimulation(runId: string): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({ method: 'post', url: `/simulations/${runId}/resume` })
}

export function stopSimulation(runId: string): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({ method: 'post', url: `/simulations/${runId}/stop` })
}

export function stepSimulation(
  runId: string,
  input: StepSimulationInput = {},
): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({
    method: 'post',
    url: `/simulations/${runId}/step`,
    data: input,
  })
}

export function setSimulationSpeed(
  runId: string,
  input: SetSimulationSpeedInput,
): Promise<SimulationRunDto> {
  return request<SimulationRunDto>({
    method: 'patch',
    url: `/simulations/${runId}/speed`,
    data: input,
  })
}

export function injectSimulationEvent(
  runId: string,
  input: InjectSimulationEventInput,
  options: WriteOptions = {},
): Promise<EventInjectionResultDto> {
  return request<EventInjectionResultDto>({
    method: 'post',
    url: `/simulations/${runId}/events`,
    data: input,
    idempotencyKey: options.idempotencyKey,
  })
}

export function getSimulationCapabilities(
  options?: QueryOptions,
): Promise<SimulationCapabilitiesDto> {
  return request<SimulationCapabilitiesDto>({
    method: 'get',
    url: '/simulations/capabilities',
    signal: options?.signal,
  })
}
