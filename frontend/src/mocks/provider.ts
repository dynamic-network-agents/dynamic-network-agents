import { NativeRealtimeProvider, type RealtimeProvider } from '@/api/realtime'
import { getEnvConfig } from '@/config/env'
import { MockRealtimeProvider } from './realtime'
import { MockWorld } from './world'

/**
 * 默认共享世界（FE-007）：浏览器 MSW worker 与 MockRealtimeProvider 共用同一份运行态，
 * 保证 REST 查询结果与 WebSocket 推送一致。
 */
export const defaultMockWorld = new MockWorld()

/**
 * Mock 开关：按 `useMock` 选择实时 Provider，Mock 与真实实现同一接口。
 * 页面/Store 只依赖 `RealtimeProvider` 接口，不感知数据来源。
 */
export function createRealtimeProvider(
  useMock: boolean = getEnvConfig().useMock,
): RealtimeProvider {
  return useMock ? new MockRealtimeProvider(defaultMockWorld) : new NativeRealtimeProvider()
}
