import { describe, expect, it } from 'vitest'
import { serializeQueryParams } from './query'

describe('serializeQueryParams', () => {
  it('忽略 undefined / null', () => {
    expect(serializeQueryParams({ a: undefined, b: null, c: 'x' })).toEqual({ c: 'x' })
  })

  it('数组用逗号连接', () => {
    expect(serializeQueryParams({ ids: ['ER-1', 'ER-2'] })).toEqual({ ids: 'ER-1,ER-2' })
  })

  it('空数组忽略', () => {
    expect(serializeQueryParams({ ids: [] })).toEqual({})
  })

  it('保留 string/number/boolean', () => {
    expect(serializeQueryParams({ page: 2, includeFlows: true, status: 'DRAFT' })).toEqual({
      page: 2,
      includeFlows: true,
      status: 'DRAFT',
    })
  })

  it('默认空对象', () => {
    expect(serializeQueryParams()).toEqual({})
  })
})
