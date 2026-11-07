import type {
  RealtimeConnection,
  RealtimeProvider,
  RealtimeSubscriber,
  RealtimeSubscribeOptions,
} from '@/api/realtime'
import type { MockWorld } from './world'

/**
 * Mock 实时通道（FE-007）。
 *
 * 实现与真实 `RealtimeProvider` 相同的接口，桥接 `MockWorld` 的事件流：
 * 订阅时先补发 `lastSeq` 之后的事件（断线恢复），再注册监听未来事件；
 * 仅转发所订阅 runId 的事件，close 后不再推送。
 */
export class MockRealtimeProvider implements RealtimeProvider {
  constructor(private readonly world: MockWorld) {}

  subscribe(
    runId: string,
    subscriber: RealtimeSubscriber,
    options: RealtimeSubscribeOptions = {},
  ): RealtimeConnection {
    subscriber.onStatus?.('connecting')

    const lastSeq = options.lastSeq ?? 0
    for (const event of this.world.getEvents(runId)) {
      if (event.seq > lastSeq) subscriber.onEvent(event)
    }

    const unsubscribe = this.world.subscribe((event) => {
      if (event.runId === runId) subscriber.onEvent(event)
    })

    subscriber.onStatus?.('open')

    let closed = false
    return {
      close: () => {
        if (closed) return
        closed = true
        unsubscribe()
        subscriber.onStatus?.('closed')
      },
    }
  }
}
