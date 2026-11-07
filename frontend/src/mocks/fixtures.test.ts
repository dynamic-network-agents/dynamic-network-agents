import { describe, expect, it } from 'vitest'
import { scenarioDtoSchema } from '@/schemas/scenario'
import { topologySnapshotDtoSchema } from '@/schemas/simulation'
import { LinkStatus, NodeStatus } from '@/types/enums'
import { buildDefaultScenario, buildTopology, DEFAULT_SEED } from './fixtures'

describe('buildDefaultScenario（确定性 fixtures）', () => {
  it('满足 scenarioDtoSchema', () => {
    const parsed = scenarioDtoSchema.safeParse(buildDefaultScenario())
    expect(parsed.success).toBe(true)
  })

  it('同一 seed 结果可复现', () => {
    expect(buildDefaultScenario(DEFAULT_SEED)).toEqual(buildDefaultScenario(DEFAULT_SEED))
  })

  it('不同 seed 结果不同', () => {
    expect(buildDefaultScenario(1)).not.toEqual(buildDefaultScenario(2))
  })

  it('默认规模：8 节点 / 12 链路 / 3 业务流', () => {
    const scenario = buildDefaultScenario()
    expect(scenario.nodes).toHaveLength(8)
    expect(scenario.links).toHaveLength(12)
    expect(scenario.flows).toHaveLength(3)
    expect(scenario.events).toHaveLength(3)
  })
})

describe('buildTopology（场景 → 拓扑快照）', () => {
  it('满足 topologySnapshotDtoSchema 且汇总正确', () => {
    const scenario = buildDefaultScenario()
    const topology = buildTopology('RUN-1', scenario)
    const parsed = topologySnapshotDtoSchema.safeParse(topology)
    expect(parsed.success).toBe(true)
    expect(topology.summary).toEqual({
      nodeCount: 8,
      onlineNodeCount: 8,
      linkCount: 12,
      upLinkCount: 12,
      connectedComponents: 1,
    })
  })

  it('深拷贝：运行态变更不影响场景源数据', () => {
    const scenario = buildDefaultScenario()
    const topology = buildTopology('RUN-1', scenario)
    topology.nodes[0].status = NodeStatus.OFFLINE
    topology.links[0].status = LinkStatus.DOWN
    topology.links[0].params.delayMs = 999
    expect(scenario.nodes[0].status).toBe(NodeStatus.ONLINE)
    expect(scenario.links[0].status).toBe(LinkStatus.UP)
    expect(scenario.links[0].params.delayMs).not.toBe(999)
  })
})
