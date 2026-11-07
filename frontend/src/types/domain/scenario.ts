import type { ScenarioEventType, ScenarioStatus } from '../enums'
import type { BusinessFlow } from './flow'
import type { NetworkLink } from './link'
import type { NetworkNode } from './node'

export const ScenarioEventTargetType = {
  NODE: 'NODE',
  LINK: 'LINK',
  FLOW: 'FLOW',
  NETWORK: 'NETWORK',
} as const
export type ScenarioEventTargetType =
  (typeof ScenarioEventTargetType)[keyof typeof ScenarioEventTargetType]

/** 动态事件（§5.4）；payload 为事件参数，宽松对象。 */
export interface ScenarioEvent {
  eventId: string
  eventType: ScenarioEventType
  triggerAtMs: number
  targetType: ScenarioEventTargetType
  targetId?: string
  payload: Record<string, unknown>
  durationMs?: number
  enabled: boolean
  repeat?: Record<string, unknown>
  description?: string
}

/** 场景 ViewModel（§5.4）。 */
export interface Scenario {
  scenarioId: string
  name: string
  description?: string
  version: number
  status: ScenarioStatus
  seed?: number
  durationMs?: number
  nodes: NetworkNode[]
  links: NetworkLink[]
  flows: BusinessFlow[]
  events?: ScenarioEvent[]
  createdAt?: string
  updatedAt?: string
}
