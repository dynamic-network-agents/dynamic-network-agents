/**
 * 统一 HTTP 客户端（FE-005）。
 * - 单一 Axios 实例；页面/模块不得自行创建 Axios 实例。
 * - baseURL 从 `getEnvConfig().apiBaseUrl` 读取；默认超时 10s，可按请求覆盖。
 * - 成功：响应拦截器统一解包 `data`（§7.2）；失败：统一抛 `ApiError`。
 * - 支持 `AbortSignal` 取消、`Idempotency-Key`、`If-Match`（§7.1）。
 */

import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig } from 'axios'
import { getEnvConfig } from '@/config/env'
import { ApiError, ClientErrorCode } from './errors'
import { serializeQueryParams } from './query'

export const DEFAULT_TIMEOUT_MS = 10_000

/** 查询类请求的传输选项。 */
export interface QueryOptions {
  signal?: AbortSignal
}

export interface RequestOptions {
  method: 'get' | 'post' | 'put' | 'patch' | 'delete'
  url: string
  params?: object
  data?: unknown
  signal?: AbortSignal
  timeout?: number
  headers?: Record<string, string>
  /** 幂等键（写操作重试场景，§7.1）。 */
  idempotencyKey?: string
  /** 乐观锁（更新场景，§7.1）。 */
  ifMatch?: string
}

let client: AxiosInstance | undefined

export function getApiClient(): AxiosInstance {
  if (client) return client
  const { apiBaseUrl } = getEnvConfig()
  const instance = axios.create({
    baseURL: apiBaseUrl,
    timeout: DEFAULT_TIMEOUT_MS,
    headers: { Accept: 'application/json' },
  })

  instance.interceptors.response.use(
    (response) => {
      const body = response.data as { data?: unknown } | undefined
      return body?.data as unknown as typeof response
    },
    (error) => Promise.reject(toApiError(error)),
  )

  client = instance
  return client
}

/** 发送请求并解包业务数据；任何失败统一以 `ApiError` 抛出。 */
export function request<T>(options: RequestOptions): Promise<T> {
  const { method, url, params, data, signal, timeout, headers, idempotencyKey, ifMatch } = options
  const config: AxiosRequestConfig = { method, url }
  if (params) config.params = serializeQueryParams(params)
  if (data !== undefined) config.data = data
  if (signal) config.signal = signal
  if (timeout !== undefined) config.timeout = timeout

  const extraHeaders: Record<string, string> = { ...headers }
  if (idempotencyKey) extraHeaders['Idempotency-Key'] = idempotencyKey
  if (ifMatch) extraHeaders['If-Match'] = ifMatch
  if (Object.keys(extraHeaders).length > 0) config.headers = extraHeaders

  return getApiClient().request(config) as unknown as Promise<T>
}

/** 归一化任意错误为 `ApiError`（导出以便单测错误映射）。 */
export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    if (status !== undefined) {
      return ApiError.fromHttpError(status, error.response?.data, error)
    }
    if (error.code === 'ERR_CANCELED') {
      return new ApiError(ClientErrorCode.REQUEST_CANCELLED, '请求已取消', undefined, {
        cause: error,
      })
    }
    if (error.code === 'ECONNABORTED' || /timeout/i.test(error.message)) {
      return new ApiError(ClientErrorCode.TIMEOUT, '请求超时', undefined, { cause: error })
    }
    return new ApiError(ClientErrorCode.NETWORK_ERROR, error.message || '网络错误', undefined, {
      cause: error,
    })
  }
  return new ApiError(
    ClientErrorCode.UNKNOWN_ERROR,
    error instanceof Error ? error.message : String(error),
    undefined,
    {
      cause: error,
    },
  )
}
