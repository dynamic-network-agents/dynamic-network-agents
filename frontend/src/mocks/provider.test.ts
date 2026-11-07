import { describe, expect, it } from 'vitest'
import { NativeRealtimeProvider } from '@/api/realtime'
import { createRealtimeProvider } from './provider'
import { MockRealtimeProvider } from './realtime'

describe('createRealtimeProvider（Mock 开关）', () => {
  it('useMock=true 返回 Mock 实现', () => {
    expect(createRealtimeProvider(true)).toBeInstanceOf(MockRealtimeProvider)
  })

  it('useMock=false 返回真实实现（当前为空实现）', () => {
    const provider = createRealtimeProvider(false)
    expect(provider).toBeInstanceOf(NativeRealtimeProvider)
    expect(() => provider.subscribe('RUN-1', { onEvent: () => {} })).toThrow()
  })

  it('不传参时读取环境配置', () => {
    // .env.test 中 VITE_USE_MOCK=true
    expect(createRealtimeProvider()).toBeInstanceOf(MockRealtimeProvider)
  })
})
