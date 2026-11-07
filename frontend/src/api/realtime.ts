import type { RealtimeEventEnvelope } from '@/types/domain/realtime'

/**
 * 实时通道抽象（FE-007）。
 *
 * 真实与 Mock 实现同一 `RealtimeProvider` 接口，页面/Store 不感知数据来源。
 * 真实 WebSocket 通道细节（§8.1 鉴权、§8.4 心跳间隔与重连）在接口规范中标注「待与官方确认」，
 * 因此 `NativeRealtimeProvider` 暂留空实现，待后端就绪后补齐。
 */

export type RealtimeConnectionStatus = 'connecting' | 'open' | 'closed' | 'error'

export interface RealtimeSubscriber {
  onEvent: (event: RealtimeEventEnvelope) => void
  onStatus?: (status: RealtimeConnectionStatus) => void
}

export interface RealtimeConnection {
  close: () => void
}

export interface RealtimeSubscribeOptions {
  /** 断线恢复：只补发 seq 大于该值的事件。 */
  lastSeq?: number
  /** 事件类型过滤（服务端能力，Mock 按需实现）。 */
  filters?: string[]
}

export interface RealtimeProvider {
  subscribe(
    runId: string,
    subscriber: RealtimeSubscriber,
    options?: RealtimeSubscribeOptions,
  ): RealtimeConnection
}

/** 真实 WebSocket 客户端（§8.1 `ws(s)://{host}/ws/v1/runs/{runId}`）。 */
export class NativeRealtimeProvider implements RealtimeProvider {
  subscribe(): RealtimeConnection {
    throw new Error(
      '真实 WebSocket 通道尚未就绪（§8.1 鉴权、§8.4 心跳待与官方确认），当前请使用 Mock 模式。',
    )
  }
}
