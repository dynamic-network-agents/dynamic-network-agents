import { describe, expect, it } from 'vitest'
import {
  ClientErrorCode,
  isCancelledError,
  isNetworkError,
  isNotFoundError,
  isServerError,
  isTimeoutError,
  isValidationError,
} from './errors'
import { DEFAULT_TIMEOUT_MS, getApiClient, toApiError } from './client'

describe('toApiError（axios 错误映射）', () => {
  it('HTTP 错误：映射业务错误码并保留 requestId/字段错误', () => {
    const err = toApiError({
      isAxiosError: true,
      response: {
        status: 422,
        data: {
          code: 'SCENARIO_VALIDATION_FAILED',
          message: '链路缺失',
          details: {
            fieldErrors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
          },
          requestId: 'REQ-9',
        },
      },
      code: 'ERR_BAD_REQUEST',
      message: 'Request failed with status code 422',
    })
    expect(isValidationError(err)).toBe(true)
    expect(err.code).toBe('SCENARIO_VALIDATION_FAILED')
    expect(err.requestId).toBe('REQ-9')
    expect(err.fieldErrors).toEqual([
      { code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' },
    ])
  })

  it('HTTP 错误：无响应体时按状态码兜底 code/message', () => {
    const err = toApiError({
      isAxiosError: true,
      response: { status: 404 },
      code: 'ERR_BAD_REQUEST',
      message: 'x',
    })
    expect(isNotFoundError(err)).toBe(true)
    expect(err.code).toBe('RESOURCE_NOT_FOUND')
    expect(err.message).toBe('资源不存在')
  })

  it('服务端错误：500', () => {
    const err = toApiError({
      isAxiosError: true,
      response: { status: 500, data: { code: 'INTERNAL_ERROR', message: 'boom' } },
      message: 'x',
    })
    expect(isServerError(err)).toBe(true)
    expect(err.code).toBe('INTERNAL_ERROR')
  })

  it('取消：ERR_CANCELED → REQUEST_CANCELLED', () => {
    const err = toApiError({ isAxiosError: true, code: 'ERR_CANCELED', message: 'canceled' })
    expect(isCancelledError(err)).toBe(true)
    expect(err.code).toBe(ClientErrorCode.REQUEST_CANCELLED)
  })

  it('超时：ECONNABORTED → TIMEOUT', () => {
    const err = toApiError({
      isAxiosError: true,
      code: 'ECONNABORTED',
      message: 'timeout of 10000ms exceeded',
    })
    expect(isTimeoutError(err)).toBe(true)
    expect(err.code).toBe(ClientErrorCode.TIMEOUT)
  })

  it('网络错误：无 response → NETWORK_ERROR', () => {
    const err = toApiError({ isAxiosError: true, message: 'Network Error' })
    expect(isNetworkError(err)).toBe(true)
    expect(err.code).toBe(ClientErrorCode.NETWORK_ERROR)
  })

  it('非 axios 错误 → UNKNOWN_ERROR', () => {
    const err = toApiError(new Error('boom'))
    expect(err.code).toBe(ClientErrorCode.UNKNOWN_ERROR)
    expect(err.message).toBe('boom')
  })
})

describe('getApiClient', () => {
  it('单例 + baseURL + 默认超时', () => {
    const a = getApiClient()
    const b = getApiClient()
    expect(a).toBe(b)
    expect(a.defaults.baseURL).toBe('http://localhost:8000/api')
    expect(a.defaults.timeout).toBe(DEFAULT_TIMEOUT_MS)
  })
})
