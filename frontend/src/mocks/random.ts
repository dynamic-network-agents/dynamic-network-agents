/**
 * 确定性随机（FE-007）。
 *
 * 采用 mulberry32 实现的可播种 PRNG：同一 seed 产生同一序列，保证 Mock 数据与事件可复现。
 * 仅供 Mock 使用，不用于业务逻辑随机（业务随机由算法服务负责）。
 */

export interface Random {
  /** [0, 1) 均匀分布。 */
  next(): number
  /** [min, max] 闭区间整数。 */
  int(min: number, max: number): number
  /** 从数组中随机取一个元素。 */
  pick<T>(items: readonly T[]): T
  /** 返回打乱后的新数组（不改动入参）。 */
  shuffle<T>(items: readonly T[]): T[]
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function createRandom(seed: number): Random {
  const next = mulberry32(seed)
  return {
    next,
    int(min, max) {
      const lo = Math.ceil(min)
      const hi = Math.floor(max)
      return Math.floor(next() * (hi - lo + 1)) + lo
    },
    pick(items) {
      if (items.length === 0) throw new Error('random.pick 不能用于空数组')
      return items[Math.floor(next() * items.length)]
    },
    shuffle(items) {
      const arr = [...items]
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(next() * (i + 1))
        ;[arr[i], arr[j]] = [arr[j], arr[i]]
      }
      return arr
    },
  }
}
