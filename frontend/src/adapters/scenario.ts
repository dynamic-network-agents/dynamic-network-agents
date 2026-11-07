import type { ScenarioDto, ScenarioEventDto } from '@/schemas/scenario'
import { coerceEnum } from '@/types/enums'
import { ScenarioEventType, ScenarioStatus } from '@/types/enums'
import type { Scenario, ScenarioEvent } from '@/types/domain/scenario'
import { ScenarioEventTargetType } from '@/types/domain/scenario'
import { toBusinessFlow } from './flow'
import { toNetworkLink } from './link'
import { toNetworkNode } from './node'

function toTargetType(value: string) {
  return coerceEnum(value, ScenarioEventTargetType) ?? ScenarioEventTargetType.NETWORK
}

/** 动态事件 DTO → ViewModel：事件类型枚举兜底到 CUSTOM，目标类型兜底到 NETWORK（网络级事件）。 */
export function toScenarioEvent(dto: ScenarioEventDto): ScenarioEvent {
  return {
    eventId: dto.eventId,
    eventType: coerceEnum(dto.eventType, ScenarioEventType) ?? ScenarioEventType.CUSTOM,
    triggerAtMs: dto.triggerAtMs,
    targetType: toTargetType(dto.targetType),
    targetId: dto.targetId,
    payload: dto.payload,
    durationMs: dto.durationMs,
    enabled: dto.enabled,
    repeat: dto.repeat,
    description: dto.description,
  }
}

/** 场景 DTO → ViewModel：递归映射 nodes/links/flows/events。 */
export function toScenario(dto: ScenarioDto): Scenario {
  return {
    scenarioId: dto.scenarioId,
    name: dto.name,
    description: dto.description,
    version: dto.version,
    status: coerceEnum(dto.status, ScenarioStatus) ?? ScenarioStatus.DRAFT,
    seed: dto.seed,
    durationMs: dto.durationMs,
    nodes: dto.nodes.map(toNetworkNode),
    links: dto.links.map(toNetworkLink),
    flows: dto.flows.map(toBusinessFlow),
    events: dto.events?.map(toScenarioEvent),
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
  }
}
