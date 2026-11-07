/**
 * 确定性演示数据（FE-007）。
 *
 * 由固定 seed 生成默认场景与拓扑快照：同一 seed 得到完全一致的数据（含位置/参数抖动）。
 * 拓扑由场景派生时对 nodes/links/flows 做深拷贝，避免运行态变更污染场景源数据。
 */

import type { FlowDto } from '@/schemas/flow'
import type { LinkDto } from '@/schemas/link'
import type { NodeDto } from '@/schemas/node'
import type { ScenarioDto, ScenarioEventDto } from '@/schemas/scenario'
import type { TopologySnapshotDto } from '@/schemas/simulation'
import {
  FlowStatus,
  LinkDirection,
  LinkPlane,
  LinkStatus,
  NodeRole,
  NodeStatus,
  NodeType,
  ScenarioEventType,
  ScenarioStatus,
  ServiceType,
} from '@/types/enums'
import { createRandom, type Random } from './random'

/** 默认固定 seed：保证演示数据与事件可复现。 */
export const DEFAULT_SEED = 20261107

const NODE_TYPES = [
  NodeType.C2,
  NodeType.UAV,
  NodeType.UAV,
  NodeType.UGV,
  NodeType.UGV,
  NodeType.RELAY,
  NodeType.UAV,
  NodeType.EDGE,
] as const

const NODE_ROLES = [
  NodeRole.COORDINATOR,
  NodeRole.MEMBER,
  NodeRole.MEMBER,
  NodeRole.MEMBER,
  NodeRole.MEMBER,
  NodeRole.RELAY,
  NodeRole.MEMBER,
  NodeRole.GATEWAY,
] as const

/** 12 条链路：8 节点环 + 4 条弦，结构固定（仅参数用 seed 抖动）。 */
const LINK_PAIRS: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [4, 5],
  [5, 6],
  [6, 7],
  [7, 0],
  [0, 3],
  [1, 5],
  [2, 6],
  [4, 7],
]

const FLOW_DEFS = [
  { serviceType: ServiceType.VOICE, src: 0, dst: 4, priority: 1, requiredBandwidthBps: 64_000 },
  { serviceType: ServiceType.VIDEO, src: 1, dst: 6, priority: 2, requiredBandwidthBps: 2_000_000 },
  { serviceType: ServiceType.DATA, src: 2, dst: 7, priority: 3, requiredBandwidthBps: 1_000_000 },
] as const

function buildNodes(random: Random): NodeDto[] {
  const count = NODE_TYPES.length
  return NODE_TYPES.map((nodeType, i) => ({
    nodeId: `N-${String(i + 1).padStart(2, '0')}`,
    name: `节点${i + 1}`,
    nodeType,
    role: NODE_ROLES[i],
    status: NodeStatus.ONLINE,
    position: {
      x: Math.round(Math.cos((2 * Math.PI * i) / count) * 300 + random.int(-20, 20)),
      y: Math.round(Math.sin((2 * Math.PI * i) / count) * 300 + random.int(-20, 20)),
    },
    resources: { energyPercent: random.int(60, 100) },
  }))
}

function buildLinks(random: Random, nodes: NodeDto[]): LinkDto[] {
  return LINK_PAIRS.map(([s, d], i) => ({
    linkId: `L-${String(i + 1).padStart(2, '0')}`,
    linkPlane: LinkPlane.DATA,
    linkType: i % 2 === 0 ? 'microwave' : 'radio',
    srcNodeId: nodes[s].nodeId,
    dstNodeId: nodes[d].nodeId,
    direction: LinkDirection.BIDIRECTIONAL,
    status: LinkStatus.UP,
    params: {
      delayMs: random.int(1, 20),
      jitterMs: random.int(0, 5),
      bandwidthBps: random.int(1000, 5000) * 1000,
      ber: 0,
      packetLossRate: Number((random.next() * 0.02).toFixed(4)),
    },
  }))
}

function buildFlows(nodes: NodeDto[]): FlowDto[] {
  return FLOW_DEFS.map((f, i) => ({
    flowId: `F-${String(i + 1).padStart(2, '0')}`,
    name: `业务流${i + 1}`,
    serviceType: f.serviceType,
    srcNodeId: nodes[f.src].nodeId,
    dstNodeId: nodes[f.dst].nodeId,
    priority: f.priority,
    requiredBandwidthBps: f.requiredBandwidthBps,
    qos: {
      minBandwidthBps: f.requiredBandwidthBps,
      maxDelayMs: f.serviceType === ServiceType.VOICE ? 150 : undefined,
    },
    status: FlowStatus.ACTIVE,
    currentPath: [nodes[f.src].nodeId, nodes[f.dst].nodeId],
  }))
}

function buildEvents(): ScenarioEventDto[] {
  return [
    {
      eventId: 'SE-01',
      eventType: ScenarioEventType.NODE_OFFLINE,
      triggerAtMs: 5000,
      targetType: 'NODE',
      targetId: 'N-03',
      payload: {},
      enabled: true,
    },
    {
      eventId: 'SE-02',
      eventType: ScenarioEventType.LINK_DOWN,
      triggerAtMs: 10_000,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
      enabled: true,
    },
    {
      eventId: 'SE-03',
      eventType: ScenarioEventType.LINK_UP,
      triggerAtMs: 15_000,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
      enabled: true,
    },
  ]
}

/** 由 seed 生成默认场景（8 节点 / 12 链路 / 3 业务流 + 3 条时间线事件）。 */
export function buildDefaultScenario(seed: number = DEFAULT_SEED): ScenarioDto {
  const random = createRandom(seed)
  const nodes = buildNodes(random)
  const links = buildLinks(random, nodes)
  const flows = buildFlows(nodes)
  const events = buildEvents()
  return {
    scenarioId: 'SCN-DEFAULT',
    name: '默认演示场景',
    description: '由固定 seed 生成的确定性演示场景（8 节点 / 12 链路 / 3 业务流）',
    version: 1,
    status: ScenarioStatus.VALID,
    seed,
    durationMs: 60_000,
    nodes,
    links,
    flows,
    events,
  }
}

function connectedComponents(nodeCount: number, links: LinkDto[]): number {
  const parent = Array.from({ length: nodeCount }, (_, i) => i)
  const find = (x: number): number => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]]
      x = parent[x]
    }
    return x
  }
  const union = (a: number, b: number) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent[rb] = ra
  }
  // links 的 src/dst 均形如 `N-xx`，序号 = 数值 - 1（fixture 内部约定）。
  for (const link of links) {
    const s = Number(link.srcNodeId.replace(/\D/g, '')) - 1
    const d = Number(link.dstNodeId.replace(/\D/g, '')) - 1
    if (
      Number.isInteger(s) &&
      Number.isInteger(d) &&
      s >= 0 &&
      d >= 0 &&
      s < nodeCount &&
      d < nodeCount
    ) {
      union(s, d)
    }
  }
  const roots = new Set<number>()
  for (let i = 0; i < nodeCount; i++) roots.add(find(i))
  return roots.size
}

/**
 * 由场景派生拓扑快照（runId/version/simTimeMs + 深拷贝 nodes/links/flows + 汇总）。
 * 深拷贝保证运行态变更不会污染场景源数据，也不会跨 run 串数据。
 */
export function buildTopology(
  runId: string,
  scenario: ScenarioDto,
  simTimeMs = 0,
  version = 1,
): TopologySnapshotDto {
  const nodes = structuredClone(scenario.nodes)
  const links = structuredClone(scenario.links)
  const flows = scenario.flows ? structuredClone(scenario.flows) : undefined
  return {
    runId,
    version,
    simTimeMs,
    nodes,
    links,
    flows,
    summary: {
      nodeCount: nodes.length,
      onlineNodeCount: nodes.filter((n) => n.status === NodeStatus.ONLINE).length,
      linkCount: links.length,
      upLinkCount: links.filter((l) => l.status === LinkStatus.UP).length,
      connectedComponents: connectedComponents(nodes.length, links),
    },
  }
}
