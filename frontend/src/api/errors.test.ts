import { describe, expect, it } from 'vitest'
import {
  ApiError,
  ClientErrorCode,
  getFieldErrors,
  isApiError,
  isAuthError,
  isCancelledError,
  isConflictError,
  isNetworkError,
  isNotFoundError,
  isServerError,
  isTimeoutError,
  isValidationError,
} from './errors'

describe('ApiError.fromHttpError', () => {
  it('解析业务错误码/消息并保留 requestId 与 details', () => {
    const err = ApiError.fromHttpError(409, {
      code: 'SIMULATION_STATE_CONFLICT',
      message: 'simulation is not running',
      details: { runId: 'RUN-1', currentStatus: 'PAUSED' },
      requestId: 'REQ-2',
    })
    expect(err.status).toBe(409)
    expect(err.code).toBe('SIMULATION_STATE_CONFLICT')
    expect(err.message).toBe('simulation is not running')
    expect(err.requestId).toBe('REQ-2')
    expect(err.details).toEqual({ runId: 'RUN-1', currentStatus: 'PAUSED' })
  })

  it('从 details.fieldErrors 提取字段错误', () => {
    const err = ApiError.fromHttpError(422, {
      code: 'SCENARIO_VALIDATION_FAILED',
      message: '校验失败',
      details: {
        fieldErrors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
      },
    })
    expect(getFieldErrors(err)).toEqual([
      { code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' },
    ])
  })

  it('回退 details.errors 提取字段错误', () => {
    const err = ApiError.fromHttpError(422, {
      code: 'SCENARIO_VALIDATION_FAILED',
      message: '校验失败',
      details: { errors: [{ code: 'X', path: 'a', message: 'm' }] },
    })
    expect(getFieldErrors(err)).toEqual([{ code: 'X', path: 'a', message: 'm' }])
  })

  it('无响应体时按 §7.3 状态码映射兜底', () => {
    const err = ApiError.fromHttpError(503)
    expect(err.code).toBe('DEPENDENCY_UNAVAILABLE')
    expect(err.message).toBe('仿真器/算法服务不可用')
  })

  it('未知状态码兜底为 HTTP_xxx', () => {
    expect(ApiError.fromHttpError(599).code).toBe('HTTP_599')
  })
})

describe('分类判断', () => {
  it('isApiError 只识别 ApiError 实例', () => {
    expect(isApiError(new ApiError('X', 'm'))).toBe(true)
    expect(isApiError(new Error('m'))).toBe(false)
    expect(isApiError({ code: 'X' })).toBe(false)
  })

  it.each([
    ['isValidationError', isValidationError, 422],
    ['isConflictError', isConflictError, 409],
    ['isNotFoundError', isNotFoundError, 404],
    ['isServerError', isServerError, 500],
  ] as const)('%s 命中对应状态码', (_name, guard, status) => {
    expect(guard(new ApiError('C', 'm', status))).toBe(true)
    expect(guard(new ApiError('C', 'm', 200))).toBe(false)
  })

  it('isAuthError 命中 401/403', () => {
    expect(isAuthError(new ApiError('C', 'm', 401))).toBe(true)
    expect(isAuthError(new ApiError('C', 'm', 403))).toBe(true)
    expect(isAuthError(new ApiError('C', 'm', 404))).toBe(false)
  })

  it('传输层错误按 code 区分', () => {
    expect(isNetworkError(new ApiError(ClientErrorCode.NETWORK_ERROR, 'm'))).toBe(true)
    expect(isTimeoutError(new ApiError(ClientErrorCode.TIMEOUT, 'm'))).toBe(true)
    expect(isCancelledError(new ApiError(ClientErrorCode.REQUEST_CANCELLED, 'm'))).toBe(true)
  })
})
