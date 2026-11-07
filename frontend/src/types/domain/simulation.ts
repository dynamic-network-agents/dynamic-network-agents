import type { SimulationStatus } from '../enums'
import type { BusinessFlow } from './flow'
import type { NetworkLink } from './link'
import type { NetworkNode } from './node'

/** 仿真运行 ViewModel（§5.5）。`simTimeMs` 为仿真内部时间（ms，自 runId 起点累计）。 */
export interface SimulationRun {
  runId: string
  scenarioId: string
  scenarioVersion: number
  status: SimulationStatus
  simTimeMs: number
  speed: number
  seed?: number
  startedAt?: string
  finishedAt?: string
  createdAt?: string
  updatedAt?: string
  error?: Record<string, unknown>
}

/** 拓扑摘要（§7.8）。 */
export interface TopologySummary {
  nodeCount: number
  onlineNodeCount: number
  linkCount: number
  upLinkCount: number
  connectedComponents: number
}

/** 拓扑快照 ViewModel（§5.5 / §7.8）。`version` 在同一 runId 内单调递增。 */
export interface TopologySnapshot {
  runId: string
  version: number
  simTimeMs: number
  generatedAt?: string
  nodes: NetworkNode[]
  links: NetworkLink[]
  flows?: BusinessFlow[]
  summary?: TopologySummary
}
