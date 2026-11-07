import { describe, expect, it } from 'vitest'
import { topologySnapshotDtoSchema } from '@/schemas/simulation'
import { toTopologySnapshot } from './simulation'

describe('集成：样例 JSON 经 schema + adapter 转页面可用 ViewModel', () => {
  it('代表性快照 fixture 可转换，未知字段不崩溃', () => {
    const fixture = {
      runId: 'RUN-001',
      version: 18,
      simTimeMs: 12000,
      generatedAt: '2026-11-07T10:00:12.125+08:00',
      nodes: [
        {
          nodeId: 'UAV-001',
          name: '侦察无人机 001',
          nodeType: 'UAV',
          status: 'ONLINE',
          futureNodeField: 1,
        },
        { nodeId: 'C2-001', name: '指挥站', nodeType: 'C2', status: 'ONLINE' },
      ],
      links: [
        {
          linkId: 'L-0087-DATA',
          linkPlane: 'DATA',
          linkType: 'microwave',
          srcNodeId: 'UAV-001',
          dstNodeId: 'C2-001',
          direction: 'BIDIRECTIONAL',
          status: 'UP',
          params: {
            delayMs: 12.5,
            jitterMs: 3.0,
            bandwidthBps: 8000000,
            ber: 0.0001,
            packetLossRate: 0.02,
          },
        },
      ],
      flows: [
        {
          flowId: 'FLOW-VOICE-001',
          name: 'UAV-001 至 C2 语音',
          serviceType: 'VOICE',
          srcNodeId: 'UAV-001',
          dstNodeId: 'C2-001',
          priority: 1,
          requiredBandwidthBps: 64000,
          qos: { maxDelayMs: 150, maxJitterMs: 30 },
          status: 'ACTIVE',
        },
      ],
      summary: {
        nodeCount: 2,
        onlineNodeCount: 2,
        linkCount: 1,
        upLinkCount: 1,
        connectedComponents: 1,
      },
      futureSnapshotField: 'ignored',
    }

    const parsed = topologySnapshotDtoSchema.safeParse(fixture)
    expect(parsed.success).toBe(true)
    if (!parsed.success) return

    const vm = toTopologySnapshot(parsed.data)
    expect(vm.runId).toBe('RUN-001')
    expect(vm.nodes).toHaveLength(2)
    expect(vm.links[0].linkPlane).toBe('DATA')
    expect(vm.flows?.[0].status).toBe('ACTIVE')
    expect(vm.summary?.nodeCount).toBe(2)
  })
})
