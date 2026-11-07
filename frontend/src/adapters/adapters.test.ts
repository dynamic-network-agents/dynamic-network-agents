import { describe, expect, it } from 'vitest'
import { toBusinessFlow } from './flow'
import { toNetworkLink } from './link'
import { toNetworkNode } from './node'
import { toScenario } from './scenario'
import { toSimulationRun, toTopologySnapshot } from './simulation'

describe('toNetworkNode', () => {
  it('字段映射 + 未知枚举兜底 + 可选字段缺失', () => {
    const vm = toNetworkNode({ nodeId: 'n1', name: 'A', nodeType: 'BOGUS', status: 'ONLINE' })
    expect(vm.nodeId).toBe('n1')
    expect(vm.nodeType).toBe('OTHER')
    expect(vm.status).toBe('ONLINE')
    expect(vm.role).toBeUndefined()
    expect(vm.position).toBeUndefined()
  })
})

describe('toNetworkLink', () => {
  it('未知 linkPlane/status 兜底，参数单位原样透传', () => {
    const vm = toNetworkLink({
      linkId: 'L1',
      linkPlane: 'BOGUS',
      linkType: 'microwave',
      srcNodeId: 'A',
      dstNodeId: 'B',
      direction: 'BIDIRECTIONAL',
      status: 'BOGUS',
      params: {
        delayMs: 12.5,
        jitterMs: 3,
        bandwidthBps: 8000000,
        ber: 0.0001,
        packetLossRate: 0.02,
      },
    })
    expect(vm.linkPlane).toBe('DATA')
    expect(vm.status).toBe('UNKNOWN')
    expect(vm.params.delayMs).toBe(12.5)
    expect(vm.params.bandwidthBps).toBe(8000000)
    expect(vm.params.packetLossRate).toBe(0.02)
  })
})

describe('toBusinessFlow', () => {
  it('未知枚举兜底 + 可选 measuredQos 缺失', () => {
    const vm = toBusinessFlow({
      flowId: 'F1',
      name: 'f',
      serviceType: 'BOGUS',
      srcNodeId: 'A',
      dstNodeId: 'B',
      priority: 1,
      requiredBandwidthBps: 64000,
      qos: {},
      status: 'BOGUS',
    })
    expect(vm.serviceType).toBe('DATA')
    expect(vm.status).toBe('PENDING')
    expect(vm.measuredQos).toBeUndefined()
    expect(vm.qos).toEqual({})
  })
})

describe('toScenario', () => {
  it('递归映射 nodes/links/flows/events，事件枚举兜底', () => {
    const vm = toScenario({
      scenarioId: 'SCN-1',
      name: 's',
      version: 1,
      status: 'VALID',
      nodes: [{ nodeId: 'n1', name: 'A', nodeType: 'UAV', status: 'ONLINE' }],
      links: [
        {
          linkId: 'L1',
          linkPlane: 'DATA',
          linkType: 'microwave',
          srcNodeId: 'n1',
          dstNodeId: 'n2',
          direction: 'BIDIRECTIONAL',
          status: 'UP',
          params: { delayMs: 1, jitterMs: 1, bandwidthBps: 1, ber: 0, packetLossRate: 0 },
        },
      ],
      flows: [
        {
          flowId: 'F1',
          name: 'f',
          serviceType: 'VOICE',
          srcNodeId: 'n1',
          dstNodeId: 'n2',
          priority: 1,
          requiredBandwidthBps: 1,
          qos: {},
          status: 'ACTIVE',
        },
      ],
      events: [
        {
          eventId: 'E1',
          eventType: 'BOGUS',
          triggerAtMs: 0,
          targetType: 'LINK',
          targetId: 'L1',
          payload: {},
          enabled: true,
        },
      ],
    })
    expect(vm.nodes).toHaveLength(1)
    expect(vm.links[0].linkPlane).toBe('DATA')
    expect(vm.flows[0].serviceType).toBe('VOICE')
    expect(vm.events?.[0].eventType).toBe('CUSTOM')
  })
})

describe('toSimulationRun / toTopologySnapshot', () => {
  it('仿真运行与快照映射', () => {
    const run = toSimulationRun({
      runId: 'RUN-1',
      scenarioId: 'SCN-1',
      scenarioVersion: 1,
      status: 'RUNNING',
      simTimeMs: 1000,
      speed: 1,
    })
    expect(run.status).toBe('RUNNING')
    expect(run.simTimeMs).toBe(1000)

    const snapshot = toTopologySnapshot({
      runId: 'RUN-1',
      version: 3,
      simTimeMs: 1000,
      nodes: [{ nodeId: 'n1', name: 'A', nodeType: 'UAV', status: 'ONLINE' }],
      links: [],
    })
    expect(snapshot.version).toBe(3)
    expect(snapshot.nodes).toHaveLength(1)
  })
})
