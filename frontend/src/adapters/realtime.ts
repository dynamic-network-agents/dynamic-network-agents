import type { RealtimeEventEnvelopeDto } from '@/schemas/realtime'
import type { RealtimeEventEnvelope } from '@/types/domain/realtime'

/** 实时事件信封直通（eventType/data 保持开放，按 eventType 窄化在 store/UI 层进行）。 */
export function toRealtimeEventEnvelope(dto: RealtimeEventEnvelopeDto): RealtimeEventEnvelope {
  return { ...dto }
}
