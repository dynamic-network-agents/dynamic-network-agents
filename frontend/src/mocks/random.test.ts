import { describe, expect, it } from 'vitest'
import { createRandom } from './random'

describe('createRandom（确定性随机）', () => {
  it('同一 seed 产生同一序列', () => {
    const a = createRandom(42)
    const b = createRandom(42)
    expect(Array.from({ length: 10 }, () => a.next())).toEqual(
      Array.from({ length: 10 }, () => b.next()),
    )
  })

  it('不同 seed 产生不同序列', () => {
    const a = createRandom(1)
    const b = createRandom(2)
    expect(Array.from({ length: 10 }, () => a.next())).not.toEqual(
      Array.from({ length: 10 }, () => b.next()),
    )
  })

  it('next 落在 [0,1)', () => {
    const r = createRandom(7)
    for (let i = 0; i < 100; i++) {
      const v = r.next()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThan(1)
    }
  })

  it('int 落在闭区间内', () => {
    const r = createRandom(3)
    for (let i = 0; i < 100; i++) {
      const v = r.int(2, 5)
      expect(v).toBeGreaterThanOrEqual(2)
      expect(v).toBeLessThanOrEqual(5)
      expect(Number.isInteger(v)).toBe(true)
    }
  })

  it('pick 从数组中取元素', () => {
    const r = createRandom(9)
    const items = ['a', 'b', 'c'] as const
    for (let i = 0; i < 20; i++) {
      expect(items).toContain(r.pick(items))
    }
  })

  it('shuffle 返回不改动入参的排列', () => {
    const r = createRandom(5)
    const items = [1, 2, 3, 4, 5]
    const shuffled = r.shuffle(items)
    expect(items).toEqual([1, 2, 3, 4, 5])
    expect([...shuffled].sort()).toEqual([1, 2, 3, 4, 5])
  })
})
