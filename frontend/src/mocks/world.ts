/**
 * Mock 运行态仓库（FE-007）：REST 与 WebSocket 共享的单一事实源。
 *
 * 内存中维护 scenarios / runs / per-run 拓扑快照（带 version）与实时事件日志（seq 递增）。
 * 写操作推进状态并产生实时事件；`advance/step` 按确定性时间线触发场景事件与 TIME_UPDATED。
 * 数据与事件由固定 seed + 单调计数生成，同一操作序列结果可复现。
 */

import type { ListScenariosParams, ScenarioUpsertInput } from '@/api/scenarios'
import type { CreateSimulationInput, InjectSimulationEventInput } from '@/api/simulations'
import type { Page } from '@/api/types'
import type { FlowDto } from '@/schemas/flow'
import type { LinkDto, LinkParamsDto } from '@/schemas/link'
import type { NodeDto } from '@/schemas/node'
import type {
  EventInjectionResultDto,
  QosSummaryDto,
  ScenarioValidateResultDto,
} from '@/schemas/api'
import type { ScenarioDto } from '@/schemas/scenario'
import type { SimulationRunDto, TopologySnapshotDto } from '@/schemas/simulation'
import type { RealtimeEventEnvelope } from '@/types/domain/realtime'
import {
  FlowStatus,
  LinkStatus,
  NodeStatus,
  RealtimeEventType,
  ScenarioEventType,
  ScenarioStatus,
  SimulationStatus,
} from '@/types/enums'
import { buildDefaultScenario, buildTopology, DEFAULT_SEED } from './fixtures'

/** 单步推进的仿真时长（ms）。 */
export const STEP_MS = 1000

/** 确定性时间戳基准（与真实墙钟无关，保证事件可复现）。 */
const MOCK_EPOCH_MS = Date.UTC(2026, 10, 7, 2, 0, 0)

/** 时间线条目：场景计划事件 + 运行时注入事件。 */
interface TimelineEntry {
  eventId: string
  eventType: string
  triggerAtMs: number
  targetType: string
  targetId?: string
  payload: Record<string, unknown>
  durationMs?: number
  fired: boolean
}

interface RunState {
  run: SimulationRunDto
  topology: TopologySnapshotDto
  timeline: TimelineEntry[]
  events: RealtimeEventEnvelope[]
  seq: number
}

export interface ListFlowsQuery {
  page?: number
  pageSize?: number
  status?: string
}

export class MockWorld {
  private readonly seed: number
  private readonly scenarios = new Map<string, ScenarioDto>()
  private readonly runs = new Map<string, RunState>()
  private readonly listeners = new Set<(event: RealtimeEventEnvelope) => void>()
  private scenarioSeq = 0
  private runSeq = 0
  private injectSeq = 0

  constructor(seed: number = DEFAULT_SEED) {
    this.seed = seed
    const scenario = buildDefaultScenario(seed)
    this.scenarios.set(scenario.scenarioId, scenario)
  }

  getSeed(): number {
    return this.seed
  }

  // -------------------------------------------------------------------------
  // 事件订阅（供 MockRealtimeProvider 使用）
  // -------------------------------------------------------------------------

  /** 订阅全部 run 的实时事件；返回取消订阅函数。 */
  subscribe(listener: (event: RealtimeEventEnvelope) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** 某 run 已产生的实时事件（按 seq 升序）。 */
  getEvents(runId: string): RealtimeEventEnvelope[] {
    return [...(this.runs.get(runId)?.events ?? [])]
  }

  // -------------------------------------------------------------------------
  // 场景
  // -------------------------------------------------------------------------

  listScenarios(params: ListScenariosParams = {}): Page<ScenarioDto> {
    const page = params.page ?? 1
    const pageSize = params.pageSize ?? 20
    let all = [...this.scenarios.values()].sort((a, b) => a.scenarioId.localeCompare(b.scenarioId))
    if (params.status) all = all.filter((s) => s.status === params.status)
    const total = all.length
    const start = (page - 1) * pageSize
    return { items: all.slice(start, start + pageSize), page, pageSize, total }
  }

  getScenario(scenarioId: string): ScenarioDto | undefined {
    return this.scenarios.get(scenarioId)
  }

  createScenario(input: ScenarioUpsertInput): ScenarioDto {
    this.scenarioSeq += 1
    const scenarioId = `SCN-${String(this.scenarioSeq).padStart(3, '0')}`
    const now = this.isoAt(0)
    const scenario: ScenarioDto = {
      scenarioId,
      name: input.name,
      description: input.description,
      version: 1,
      status: ScenarioStatus.DRAFT,
      seed: input.seed,
      durationMs: input.durationMs,
      nodes: input.nodes,
      links: input.links,
      flows: input.flows,
      events: input.events,
      createdAt: now,
      updatedAt: now,
    }
    this.scenarios.set(scenarioId, scenario)
    return scenario
  }

  updateScenario(scenarioId: string, input: ScenarioUpsertInput): ScenarioDto | undefined {
    const existing = this.scenarios.get(scenarioId)
    if (!existing) return undefined
    const updated: ScenarioDto = {
      ...existing,
      name: input.name,
      description: input.description,
      seed: input.seed,
      durationMs: input.durationMs,
      nodes: input.nodes,
      links: input.links,
      flows: input.flows,
      events: input.events,
      version: existing.version + 1,
      updatedAt: this.isoAt(0),
    }
    this.scenarios.set(scenarioId, updated)
    return updated
  }

  deleteScenario(scenarioId: string): boolean {
    return this.scenarios.delete(scenarioId)
  }

  /** 校验（Mock 恒通过；字段级校验规则以接口规范为准，此处不臆造）。 */
  validateScenario(): ScenarioValidateResultDto {
    return { valid: true, errors: [], warnings: [] }
  }

  cloneScenario(scenarioId: string): ScenarioDto | undefined {
    const existing = this.scenarios.get(scenarioId)
    if (!existing) return undefined
    this.scenarioSeq += 1
    const clone: ScenarioDto = {
      ...structuredClone(existing),
      scenarioId: `SCN-${String(this.scenarioSeq).padStart(3, '0')}`,
      name: `${existing.name}（副本）`,
      version: 1,
      createdAt: this.isoAt(0),
      updatedAt: this.isoAt(0),
    }
    this.scenarios.set(clone.scenarioId, clone)
    return clone
  }

  // -------------------------------------------------------------------------
  // 仿真运行
  // -------------------------------------------------------------------------

  createSimulation(input: CreateSimulationInput): SimulationRunDto {
    const scenario = this.scenarios.get(input.scenarioId)
    if (!scenario) throw new Error(`场景不存在：${input.scenarioId}`)
    this.runSeq += 1
    const runId = `RUN-${String(this.runSeq).padStart(3, '0')}`
    const run: SimulationRunDto = {
      runId,
      scenarioId: input.scenarioId,
      scenarioVersion: input.scenarioVersion,
      status: SimulationStatus.READY,
      simTimeMs: 0,
      speed: input.speed ?? 1,
      seed: input.seed,
      createdAt: this.isoAt(0),
      updatedAt: this.isoAt(0),
    }
    const topology = buildTopology(runId, scenario, run.simTimeMs, 1)
    const timeline: TimelineEntry[] = (scenario.events ?? []).map((e) => ({
      eventId: e.eventId,
      eventType: e.eventType,
      triggerAtMs: e.triggerAtMs,
      targetType: e.targetType,
      targetId: e.targetId,
      payload: e.payload,
      durationMs: e.durationMs,
      fired: false,
    }))
    this.runs.set(runId, { run, topology, timeline, events: [], seq: 0 })
    return run
  }

  getSimulation(runId: string): SimulationRunDto | undefined {
    return this.runs.get(runId)?.run
  }

  getSimulationStatus(runId: string): SimulationRunDto | undefined {
    return this.getSimulation(runId)
  }

  start(runId: string): SimulationRunDto | undefined {
    return this.transition(runId, SimulationStatus.RUNNING)
  }

  pause(runId: string): SimulationRunDto | undefined {
    return this.transition(runId, SimulationStatus.PAUSED)
  }

  resume(runId: string): SimulationRunDto | undefined {
    return this.transition(runId, SimulationStatus.RUNNING)
  }

  stop(runId: string): SimulationRunDto | undefined {
    return this.transition(runId, SimulationStatus.STOPPED)
  }

  setSpeed(runId: string, speed: number): SimulationRunDto | undefined {
    const rs = this.runs.get(runId)
    if (!rs) return undefined
    rs.run.speed = speed
    rs.run.updatedAt = this.isoAt(rs.run.simTimeMs)
    this.emit(rs, RealtimeEventType.SIMULATION_TIME_UPDATED, {
      simTimeMs: rs.run.simTimeMs,
      speed,
    })
    return rs.run
  }

  step(runId: string, steps = 1): SimulationRunDto | undefined {
    const rs = this.runs.get(runId)
    if (!rs) return undefined
    this.advanceState(rs, steps * STEP_MS)
    return rs.run
  }

  /** 确定性推进仿真时钟，触发 TIME_UPDATED 与到期的场景/注入事件。 */
  advance(runId: string, ms: number): void {
    const rs = this.runs.get(runId)
    if (!rs) throw new Error(`run 不存在：${runId}`)
    this.advanceState(rs, ms)
  }

  injectEvent(
    runId: string,
    input: InjectSimulationEventInput,
  ): EventInjectionResultDto | undefined {
    const rs = this.runs.get(runId)
    if (!rs) return undefined
    this.injectSeq += 1
    const eventId = `INJ-${String(this.injectSeq).padStart(4, '0')}`
    rs.timeline.push({
      eventId,
      eventType: input.eventType,
      triggerAtMs: input.triggerAtMs,
      targetType: input.targetType,
      targetId: input.targetId,
      payload: input.payload,
      durationMs: input.durationMs,
      fired: false,
    })
    return { eventId, accepted: true, scheduledAtSimTimeMs: input.triggerAtMs }
  }

  getTopology(runId: string): TopologySnapshotDto | undefined {
    return this.runs.get(runId)?.topology
  }

  // -------------------------------------------------------------------------
  // 运行态只读派生（节点/链路/业务/QoS/资源/Dashboard，字段口径待确认者保持最小）
  // -------------------------------------------------------------------------

  getNode(runId: string, nodeId: string): NodeDto | undefined {
    return this.runs.get(runId)?.topology.nodes.find((n) => n.nodeId === nodeId)
  }

  getLink(runId: string, linkId: string): LinkDto | undefined {
    return this.runs.get(runId)?.topology.links.find((l) => l.linkId === linkId)
  }

  getFlow(runId: string, flowId: string): FlowDto | undefined {
    return this.runs.get(runId)?.topology.flows?.find((f) => f.flowId === flowId)
  }

  getNodeNeighbors(runId: string, nodeId: string): Record<string, unknown> | undefined {
    const topology = this.runs.get(runId)?.topology
    if (!topology) return undefined
    const neighbors = topology.links
      .filter((l) => l.srcNodeId === nodeId || l.dstNodeId === nodeId)
      .map((l) => (l.srcNodeId === nodeId ? l.dstNodeId : l.srcNodeId))
    return { nodeId, neighbors: [...new Set(neighbors)] }
  }

  getNodeRoutes(runId: string, nodeId: string): Record<string, unknown> | undefined {
    if (!this.getNode(runId, nodeId)) return undefined
    return { nodeId, routes: [] }
  }

  listFlows(runId: string, query: ListFlowsQuery = {}): Page<FlowDto> | undefined {
    const topology = this.runs.get(runId)?.topology
    if (!topology) return undefined
    const page = query.page ?? 1
    const pageSize = query.pageSize ?? 20
    let all = topology.flows ?? []
    if (query.status) all = all.filter((f) => f.status === query.status)
    const total = all.length
    const start = (page - 1) * pageSize
    return { items: all.slice(start, start + pageSize), page, pageSize, total }
  }

  getFlowRoute(runId: string, flowId: string): Record<string, unknown> | undefined {
    const flow = this.getFlow(runId, flowId)
    if (!flow) return undefined
    return { flowId, path: flow.currentPath ?? [] }
  }

  getQosSummary(runId: string): QosSummaryDto | undefined {
    const topology = this.runs.get(runId)?.topology
    if (!topology) return undefined
    const flows = topology.flows ?? []
    const compliantFlows = flows.filter((f) => f.status === FlowStatus.ACTIVE).length
    const totalFlows = flows.length
    return {
      totalFlows,
      compliantFlows,
      nonCompliantFlows: totalFlows - compliantFlows,
      complianceRate: totalFlows === 0 ? 1 : compliantFlows / totalFlows,
    }
  }

  getFlowQos(runId: string, flowId: string): Record<string, unknown> | undefined {
    if (!this.getFlow(runId, flowId)) return undefined
    return { flowId }
  }

  getResourceAllocation(runId: string): Record<string, unknown> | undefined {
    if (!this.runs.has(runId)) return undefined
    return { runId }
  }

  getResourceHistory(runId: string): unknown[] | undefined {
    if (!this.runs.has(runId)) return undefined
    return []
  }

  getDashboardSummary(runId: string): Record<string, unknown> | undefined {
    if (!this.runs.has(runId)) return undefined
    return { runId }
  }

  // -------------------------------------------------------------------------
  // 内部
  // -------------------------------------------------------------------------

  private transition(runId: string, status: SimulationStatus): SimulationRunDto | undefined {
    const rs = this.runs.get(runId)
    if (!rs) return undefined
    const previousStatus = rs.run.status
    rs.run.status = status
    rs.run.updatedAt = this.isoAt(rs.run.simTimeMs)
    this.emit(rs, RealtimeEventType.SIMULATION_STATUS_CHANGED, { status, previousStatus })
    return rs.run
  }

  private advanceState(rs: RunState, ms: number): void {
    const from = rs.run.simTimeMs
    const to = from + ms
    rs.run.simTimeMs = to
    rs.run.updatedAt = this.isoAt(to)
    this.emit(rs, RealtimeEventType.SIMULATION_TIME_UPDATED, {
      simTimeMs: to,
      speed: rs.run.speed,
    })
    const due = rs.timeline
      .filter((t) => !t.fired && t.triggerAtMs > from && t.triggerAtMs <= to)
      .sort((a, b) => a.triggerAtMs - b.triggerAtMs)
    for (const entry of due) {
      entry.fired = true
      this.applyTimelineEntry(rs, entry)
    }
  }

  private applyTimelineEntry(rs: RunState, entry: TimelineEntry): void {
    switch (entry.eventType) {
      case ScenarioEventType.NODE_ONLINE:
      case ScenarioEventType.NODE_OFFLINE: {
        const nodeId = entry.targetId
        const node = nodeId ? rs.topology.nodes.find((n) => n.nodeId === nodeId) : undefined
        if (!node) return
        const newStatus =
          entry.eventType === ScenarioEventType.NODE_ONLINE ? NodeStatus.ONLINE : NodeStatus.OFFLINE
        node.status = newStatus
        this.bumpVersion(rs)
        this.emit(rs, RealtimeEventType.NODE_STATUS_CHANGED, { nodeId: node.nodeId, newStatus })
        return
      }
      case ScenarioEventType.NODE_MOVE: {
        const nodeId = entry.targetId
        const node = nodeId ? rs.topology.nodes.find((n) => n.nodeId === nodeId) : undefined
        if (!node) return
        const raw = entry.payload.position as { x?: unknown; y?: unknown } | undefined
        if (!raw || typeof raw.x !== 'number' || typeof raw.y !== 'number') return
        node.position = { ...node.position, x: raw.x, y: raw.y }
        this.bumpVersion(rs)
        this.emit(rs, RealtimeEventType.NODE_POSITION_UPDATED, {
          nodeId: node.nodeId,
          position: node.position,
        })
        return
      }
      case ScenarioEventType.LINK_UP:
      case ScenarioEventType.LINK_DOWN: {
        const linkId = entry.targetId
        const link = linkId ? rs.topology.links.find((l) => l.linkId === linkId) : undefined
        if (!link) return
        const newStatus =
          entry.eventType === ScenarioEventType.LINK_UP ? LinkStatus.UP : LinkStatus.DOWN
        link.status = newStatus
        this.bumpVersion(rs)
        this.emit(rs, RealtimeEventType.LINK_STATUS_CHANGED, { linkId: link.linkId, newStatus })
        return
      }
      case ScenarioEventType.LINK_PARAM_CHANGE:
      case ScenarioEventType.BANDWIDTH_CHANGE: {
        const linkId = entry.targetId
        const link = linkId ? rs.topology.links.find((l) => l.linkId === linkId) : undefined
        if (!link) return
        const params = entry.payload.params
        if (typeof params === 'object' && params !== null) {
          link.params = { ...link.params, ...(params as LinkParamsDto) }
        } else if (typeof entry.payload.bandwidthBps === 'number') {
          link.params = { ...link.params, bandwidthBps: entry.payload.bandwidthBps }
        } else {
          return
        }
        this.bumpVersion(rs)
        this.emit(rs, RealtimeEventType.LINK_METRIC_UPDATED, {
          linkId: link.linkId,
          params: link.params,
        })
        return
      }
      default:
        // 未定义映射的场景事件（FLOW_*/INTERFERENCE/COORDINATOR_FAILURE/CUSTOM）不在首轮实时事件集内，忽略。
        return
    }
  }

  private bumpVersion(rs: RunState): void {
    rs.topology.version += 1
  }

  private emit(rs: RunState, eventType: string, data: unknown): RealtimeEventEnvelope {
    rs.seq += 1
    const event: RealtimeEventEnvelope = {
      eventId: `EVT-${rs.run.runId}-${String(rs.seq).padStart(6, '0')}`,
      eventType,
      runId: rs.run.runId,
      seq: rs.seq,
      version: rs.topology.version,
      simTimeMs: rs.run.simTimeMs,
      timestamp: this.isoAt(rs.run.simTimeMs),
      data,
    }
    rs.events.push(event)
    for (const listener of this.listeners) listener(event)
    return event
  }

  private isoAt(simTimeMs: number): string {
    return new Date(MOCK_EPOCH_MS + simTimeMs).toISOString()
  }
}
