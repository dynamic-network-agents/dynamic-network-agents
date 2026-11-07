import { describe, expect, it } from 'vitest'
import { LinkStatus, NodeType, coerceEnum, coerceEnumInsensitive } from './enums'

describe('coerceEnum', () => {
  it('命中已知枚举值时原样返回', () => {
    expect(coerceEnum('UP', LinkStatus)).toBe('UP')
  })

  it('未知枚举值返回 undefined（不抛错、不臆造）', () => {
    expect(coerceEnum('BOGUS', LinkStatus)).toBeUndefined()
  })

  it('非字符串返回 undefined', () => {
    expect(coerceEnum(42, LinkStatus)).toBeUndefined()
    expect(coerceEnum(null, LinkStatus)).toBeUndefined()
  })
})

describe('coerceEnumInsensitive', () => {
  it('大小写不敏感命中（"up" → UP、"Down" → DOWN）', () => {
    expect(coerceEnumInsensitive('up', LinkStatus)).toBe('UP')
    expect(coerceEnumInsensitive('Down', LinkStatus)).toBe('DOWN')
  })

  it('未知值返回 undefined', () => {
    expect(coerceEnumInsensitive('bogus', LinkStatus)).toBeUndefined()
  })
})

describe('枚举兜底成员', () => {
  it('NodeType 含 OTHER、LinkStatus 含 UNKNOWN', () => {
    expect(NodeType.OTHER).toBe('OTHER')
    expect(LinkStatus.UNKNOWN).toBe('UNKNOWN')
  })
})
