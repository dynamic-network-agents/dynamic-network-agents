import type { SimulationRunDto, TopologySnapshotDto } from '@/schemas/simulation'
import { coerceEnum } from '@/types/enums'
import { SimulationStatus } from '@/types/enums'
import type { SimulationRun, TopologySnapshot } from '@/types/domain/simulation'
import { toBusinessFlow } from './flow'
import { toNetworkLink } from './link'
import { toNetworkNode } from './node'

/** 仿真运行 DTO → ViewModel。 */
export function toSimulationRun(dto: SimulationRunDto): SimulationRun {
  return {
    runId: dto.runId,
    scenarioId: dto.scenarioId,
    scenarioVersion: dto.scenarioVersion,
    status: coerceEnum(dto.status, SimulationStatus) ?? SimulationStatus.CREATED,
    simTimeMs: dto.simTimeMs,
    speed: dto.speed,
    seed: dto.seed,
    startedAt: dto.startedAt,
    finishedAt: dto.finishedAt,
    createdAt: dto.createdAt,
    updatedAt: dto.updatedAt,
    error: dto.error,
  }
}

/** 拓扑快照 DTO → ViewModel。links[] 逐条保留 linkPlane，不根据节点对推导。 */
export function toTopologySnapshot(dto: TopologySnapshotDto): TopologySnapshot {
  return {
    runId: dto.runId,
    version: dto.version,
    simTimeMs: dto.simTimeMs,
    generatedAt: dto.generatedAt,
    nodes: dto.nodes.map(toNetworkNode),
    links: dto.links.map(toNetworkLink),
    flows: dto.flows?.map(toBusinessFlow),
    summary: dto.summary,
  }
}
