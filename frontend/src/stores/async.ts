/**
 * 异步请求状态机与运行隔离守卫（FE-006）。
 *
 * 约定：
 * - 每个异步数据切片统一 `status`（idle/loading/success/error）+ `data` + `error` 三者一起更新，
 *   避免出现「status=success 但 data 为空」之类的中间不一致态。
 * - loading / error 态保留上次 `data`，便于 UI 在刷新中继续展示旧数据。
 * - `isStaleRun` 用于丢弃「晚到的旧 run 请求」，防止切 run 后旧结果覆盖新 run（FE-006 验收项）。
 */

import { ApiError, isApiError } from '@/api/errors'
import { toApiError } from '@/api/client'
import type { FieldError } from '@/api/types'

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

/** 单个异步数据切片的统一状态。 */
export interface AsyncSlice<T> {
  status: AsyncStatus
  data: T | null
  error: ApiError | null
}

export function idleSlice<T>(): AsyncSlice<T> {
  return { status: 'idle', data: null, error: null }
}

/** 进入 loading：保留上次 data（刷新中仍展示旧数据），清空 error。 */
export function loadingSlice<T>(prev?: AsyncSlice<T> | null): AsyncSlice<T> {
  return { status: 'loading', data: prev?.data ?? null, error: null }
}

export function successSlice<T>(data: T): AsyncSlice<T> {
  return { status: 'success', data, error: null }
}

/** 进入 error：保留上次 data，落 error。 */
export function errorSlice<T>(error: ApiError, prevData: T | null = null): AsyncSlice<T> {
  return { status: 'error', data: prevData, error }
}

/** DTO 校验失败时构造 422 业务错误（code 对齐 §7.3 `VALIDATION_FAILED`）。 */
export function schemaValidationError(message: string, fieldErrors?: FieldError[]): ApiError {
  return new ApiError('VALIDATION_FAILED', message, 422, { fieldErrors })
}

/**
 * 归一化任意错误为 `ApiError`。`request()` 已经统一抛 `ApiError`，这里做防御性兜底：
 * 已是 `ApiError` 则原样返回（避免二次包裹为 `UNKNOWN_ERROR`），否则走 `toApiError` 归一。
 */
export function normalizeApiError(error: unknown): ApiError {
  return isApiError(error) ? error : toApiError(error)
}

/**
 * 运行隔离守卫：请求发起时的 runId 与 store 当前绑定的 runId 不一致，说明用户已切换运行、
 * 该请求是「晚到的旧 run」——返回 true，调用方应丢弃结果。
 * 任一为 null 表示未绑定/未切换，不视为过期（例如创建运行、首次加载）。
 */
export function isStaleRun(startedRunId: string | null, currentRunId: string | null): boolean {
  return startedRunId !== null && currentRunId !== null && startedRunId !== currentRunId
}
