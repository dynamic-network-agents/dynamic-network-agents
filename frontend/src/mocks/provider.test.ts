import { describe, expect, it } from 'vitest'
import { NativeRealtimeProvider } from '@/api/realtime'
import { createRealtimeProvider } from './provider'
import { MockRealtimeProvider } from './realtime'

describe('createRealtimeProvider（Mock 开关）', () => {
  it('useMock=true 返回 Mock 实现', () => {
    expect(createRealtimeProvider(true)).toBeInstanceOf(MockRealtimeProvider)
  })

  it('useMock=false 返回真实实现（通道未就绪时上报 error 而非抛异常）', () => {
    const provider = createRealtimeProvider(false)
    expect(provider).toBeInstanceOf(NativeRealtimeProvider)

    const statuses: string[] = []
    const errors: Error[] = []
    const connection = provider.subscribe('RUN-1', {
      onEvent: () => {},
      onStatus: (s) => statuses.push(s),
      onError: (e) => errors.push(e),
    })
    expect(statuses).toContain('error')
    expect(errors).toHaveLength(1)
    expect(errors[0].message).toContain('尚未就绪')
    expect(connection).toHaveProperty('close')
  })

  it('不传参时读取环境配置', () => {
    // .env.test 中 VITE_USE_MOCK=true
    expect(createRealtimeProvider()).toBeInstanceOf(MockRealtimeProvider)
  })
})
