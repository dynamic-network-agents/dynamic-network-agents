import { describe, expect, it } from 'vitest'
import { isValidationError } from '@/api/errors'
import {
  errorSlice,
  idleSlice,
  isStaleRun,
  loadingSlice,
  schemaValidationError,
  successSlice,
} from './async'

describe('AsyncSlice 状态机', () => {
  it('idleSlice 初始为空', () => {
    expect(idleSlice()).toEqual({ status: 'idle', data: null, error: null })
  })

  it('loadingSlice 保留上次 data、清空 error', () => {
    expect(loadingSlice(successSlice('x'))).toEqual({ status: 'loading', data: 'x', error: null })
  })

  it('loadingSlice 无上次数据时 data 为 null', () => {
    expect(loadingSlice()).toEqual({ status: 'loading', data: null, error: null })
  })

  it('successSlice 落数据、清空 error', () => {
    expect(successSlice('ok')).toEqual({ status: 'success', data: 'ok', error: null })
  })

  it('errorSlice 保留上次 data、落 error', () => {
    const err = schemaValidationError('bad')
    expect(errorSlice(err, 'prev')).toEqual({ status: 'error', data: 'prev', error: err })
  })
})

describe('schemaValidationError', () => {
  it('构造 422 VALIDATION_FAILED，携带字段错误', () => {
    const err = schemaValidationError('解析失败', [{ code: 'X', path: 'a', message: 'm' }])
    expect(isValidationError(err)).toBe(true)
    expect(err.code).toBe('VALIDATION_FAILED')
    expect(err.status).toBe(422)
    expect(err.fieldErrors).toEqual([{ code: 'X', path: 'a', message: 'm' }])
  })
})

describe('isStaleRun', () => {
  it('相同 runId 不过期', () => {
    expect(isStaleRun('A', 'A')).toBe(false)
  })

  it('不同 runId 过期', () => {
    expect(isStaleRun('A', 'B')).toBe(true)
  })

  it('任一为 null 不过期', () => {
    expect(isStaleRun(null, 'B')).toBe(false)
    expect(isStaleRun('A', null)).toBe(false)
    expect(isStaleRun(null, null)).toBe(false)
  })
})
