/**
 * 统一错误归一化与分类（对齐 §7.3 状态码/错误码映射）。
 *
 * 约定：
 * - 所有请求失败（HTTP 错误、网络/超时/取消）统一抛 `ApiError`，页面据此反馈，不各自判断。
 * - `ApiError.status` 为 HTTP 状态；传输层错误（网络/超时/取消）无 `status`，用 `code` 区分：
 *   `NETWORK_ERROR` / `TIMEOUT` / `REQUEST_CANCELLED` / `UNKNOWN_ERROR`。
 * - 服务端 `requestId` 与 `details` 原样保留，保证错误可追踪；字段错误从 `details.fieldErrors`
 *   （回退 `details.errors`）提取，键名以「可选 fieldErrors」为准、待与官方确认。
 */

import type { ApiErrorBody, FieldError } from './types'

/** 客户端侧错误码（无 HTTP 状态时使用）。 */
export const ClientErrorCode = {
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT',
  REQUEST_CANCELLED: 'REQUEST_CANCELLED',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
} as const
export type ClientErrorCode = (typeof ClientErrorCode)[keyof typeof ClientErrorCode]

export interface ApiErrorOptions {
  requestId?: string
  details?: Record<string, unknown>
  fieldErrors?: FieldError[]
  cause?: unknown
}

export class ApiError extends Error {
  readonly status?: number
  readonly code: string
  readonly requestId?: string
  readonly details?: Record<string, unknown>
  readonly fieldErrors?: FieldError[]
  readonly cause?: unknown

  constructor(code: string, message: string, status?: number, options: ApiErrorOptions = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = options.requestId
    this.details = options.details
    this.fieldErrors = options.fieldErrors
    this.cause = options.cause
    Object.setPrototypeOf(this, ApiError.prototype)
  }

  /** 由 HTTP 状态 + 响应体构造；`code`/`message` 缺失时按 §7.3 映射兜底。 */
  static fromHttpError(status: number, body?: unknown, cause?: unknown): ApiError {
    const parsed = parseErrorBody(body)
    const details = parsed?.details
    const code = parsed?.code ?? httpStatusToCode(status)
    const message = parsed?.message ?? httpStatusToMessage(status)
    return new ApiError(code, message, status, {
      requestId: parsed?.requestId,
      details,
      fieldErrors: extractFieldErrors(details),
      cause,
    })
  }

  /**
   * 由「HTTP 2xx 但业务 code 非 OK」的响应体构造业务错误（HTTP 层未报错、但业务失败）。
   * 这种响应属于规范外兜底：HTTP 成功但信封 `code` 表示失败，不能当作成功解包。
   */
  static fromBusinessError(body: unknown, status: number, cause?: unknown): ApiError {
    const parsed = parseErrorBody(body)
    const code = parsed?.code ?? 'BUSINESS_ERROR'
    const message = parsed?.message ?? '业务处理失败'
    return new ApiError(code, message, status, {
      requestId: parsed?.requestId,
      details: parsed?.details,
      fieldErrors: extractFieldErrors(parsed?.details),
      cause,
    })
  }
}

function parseErrorBody(body: unknown): ApiErrorBody | undefined {
  if (typeof body !== 'object' || body === null) return undefined
  const value = body as Record<string, unknown>
  if (typeof value.code !== 'string' || typeof value.message !== 'string') return undefined
  return value as unknown as ApiErrorBody
}

function extractFieldErrors(details?: Record<string, unknown>): FieldError[] | undefined {
  if (!details) return undefined
  const raw = details.fieldErrors ?? details.errors
  if (!Array.isArray(raw)) return undefined
  const result = raw.filter(isFieldError)
  return result.length > 0 ? result : undefined
}

function isFieldError(value: unknown): value is FieldError {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return typeof record.code === 'string' && typeof record.message === 'string'
}

const STATUS_CODE_MAP: Record<number, string> = {
  400: 'INVALID_ARGUMENT',
  401: 'UNAUTHORIZED',
  403: 'FORBIDDEN',
  404: 'RESOURCE_NOT_FOUND',
  409: 'CONFLICT',
  422: 'VALIDATION_FAILED',
  429: 'RATE_LIMITED',
  500: 'INTERNAL_ERROR',
  502: 'DEPENDENCY_UNAVAILABLE',
  503: 'DEPENDENCY_UNAVAILABLE',
  504: 'DEPENDENCY_TIMEOUT',
}

function httpStatusToCode(status: number): string {
  return STATUS_CODE_MAP[status] ?? `HTTP_${status}`
}

const STATUS_MESSAGE_MAP: Record<number, string> = {
  400: '参数格式错误',
  401: '未认证',
  403: '无权限',
  404: '资源不存在',
  409: '版本或状态冲突',
  422: '业务校验不通过',
  429: '请求频率受限',
  500: '服务内部错误',
  502: '仿真器/算法服务不可用',
  503: '仿真器/算法服务不可用',
  504: '下游调用超时',
}

function httpStatusToMessage(status: number): string {
  return STATUS_MESSAGE_MAP[status] ?? `HTTP ${status}`
}

// ---------------------------------------------------------------------------
// 分类判断（供页面区分字段错误 / 冲突 / 系统故障，做对应反馈）
// ---------------------------------------------------------------------------

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

/** 业务校验不通过（422，通常带字段错误）。 */
export function isValidationError(value: unknown): value is ApiError {
  return isApiError(value) && value.status === 422
}

/** 版本或状态冲突（409）。 */
export function isConflictError(value: unknown): value is ApiError {
  return isApiError(value) && value.status === 409
}

/** 资源不存在（404）。 */
export function isNotFoundError(value: unknown): value is ApiError {
  return isApiError(value) && value.status === 404
}

/** 未认证 / 无权限（401/403）。 */
export function isAuthError(value: unknown): value is ApiError {
  return isApiError(value) && (value.status === 401 || value.status === 403)
}

/** 服务/依赖错误（>=500）。 */
export function isServerError(value: unknown): value is ApiError {
  return isApiError(value) && value.status !== undefined && value.status >= 500
}

/** 网络错误（无 HTTP 响应）。 */
export function isNetworkError(value: unknown): value is ApiError {
  return isApiError(value) && value.code === ClientErrorCode.NETWORK_ERROR
}

/** 请求超时。 */
export function isTimeoutError(value: unknown): value is ApiError {
  return isApiError(value) && value.code === ClientErrorCode.TIMEOUT
}

/** 用户主动取消。 */
export function isCancelledError(value: unknown): value is ApiError {
  return isApiError(value) && value.code === ClientErrorCode.REQUEST_CANCELLED
}

/** 提取字段错误（无则空数组）。 */
export function getFieldErrors(value: unknown): FieldError[] {
  return isApiError(value) ? (value.fieldErrors ?? []) : []
}
