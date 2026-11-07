import { describe, expect, it } from 'vitest'
import { getPageMeta, matchRoute, pageMeta } from './pageMeta'

describe('pageMeta 路由元信息', () => {
  it('提供 7 个一级路由', () => {
    expect(pageMeta).toHaveLength(7)
    expect(pageMeta.map((item) => item.key)).toEqual([
      'dashboard',
      'topology',
      'scenario',
      'simulation',
      'agents',
      'resources',
      'experiments',
    ])
  })

  it('getPageMeta 命中返回对应 meta', () => {
    expect(getPageMeta('topology')?.path).toBe('/topology')
  })

  it('getPageMeta 未命中返回 undefined', () => {
    expect(getPageMeta('unknown')).toBeUndefined()
  })

  it('matchRoute 精确匹配根路径', () => {
    expect(matchRoute('/')?.key).toBe('dashboard')
  })

  it('matchRoute 精确匹配一级路径', () => {
    expect(matchRoute('/topology')?.key).toBe('topology')
  })

  it('matchRoute 前缀匹配子路径', () => {
    expect(matchRoute('/topology/nodes')?.key).toBe('topology')
  })

  it('matchRoute 未匹配返回 undefined', () => {
    expect(matchRoute('/unknown')).toBeUndefined()
  })
})
