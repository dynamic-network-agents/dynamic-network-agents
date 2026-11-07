import { describe, expect, it } from 'vitest'
import { formatPercent, formatSimTimeMs } from './format'

describe('formatSimTimeMs', () => {
  it('0 毫秒返回 0ms', () => {
    expect(formatSimTimeMs(0)).toBe('0ms')
  })

  it('仅毫秒', () => {
    expect(formatSimTimeMs(500)).toBe('500ms')
  })

  it('分秒毫秒组合', () => {
    expect(formatSimTimeMs((2 * 60 + 30) * 1000 + 500)).toBe('2m 30s 500ms')
  })

  it('时分秒组合（无毫秒）', () => {
    expect(formatSimTimeMs((1 * 3600 + 5 * 60 + 3) * 1000)).toBe('1h 5m 3s')
  })

  it('负值或非有限值抛出可读错误', () => {
    expect(() => formatSimTimeMs(-1)).toThrow(/非法的仿真时间/)
    expect(() => formatSimTimeMs(Number.NaN)).toThrow(/非法的仿真时间/)
  })
})

describe('formatPercent', () => {
  it('默认保留 1 位小数', () => {
    expect(formatPercent(0.0234)).toBe('2.3%')
  })

  it('可指定小数位', () => {
    expect(formatPercent(0.5, 0)).toBe('50%')
    expect(formatPercent(0.5, 2)).toBe('50.00%')
  })

  it('非有限值抛出可读错误', () => {
    expect(() => formatPercent(Number.NaN)).toThrow(/非法的比例/)
  })
})
