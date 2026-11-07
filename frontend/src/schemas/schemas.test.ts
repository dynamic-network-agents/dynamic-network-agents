import { describe, expect, it } from 'vitest'
import {
  eventInjectionResultDtoSchema,
  qosSummaryDtoSchema,
  scenarioValidateResultDtoSchema,
} from './api'
import { contestLinkDtoSchema } from './contest'
import { linkDtoSchema } from './link'
import { topologySnapshotDtoSchema } from './simulation'

const validLink = {
  linkId: 'L-0087-DATA',
  linkPlane: 'DATA',
  linkType: 'microwave',
  srcNodeId: 'GND-005',
  dstNodeId: 'AIR-003',
  direction: 'BIDIRECTIONAL',
  status: 'UP',
  params: {
    delayMs: 12.5,
    jitterMs: 3.0,
    bandwidthBps: 8000000,
    ber: 0.0001,
    packetLossRate: 0.02,
  },
}

describe('linkDtoSchema', () => {
  it('合法链路 DTO 通过', () => {
    expect(linkDtoSchema.safeParse(validLink).success).toBe(true)
  })

  it('未知扩展字段不导致失败（向前兼容）', () => {
    expect(linkDtoSchema.safeParse({ ...validLink, futureField: 123 }).success).toBe(true)
  })

  it('非法数值（丢包率越界 >1）校验失败', () => {
    const result = linkDtoSchema.safeParse({
      ...validLink,
      params: { ...validLink.params, packetLossRate: 2.5 },
    })
    expect(result.success).toBe(false)
  })
})

describe('contestLinkDtoSchema', () => {
  it('赛题链路样例（旧拼写 + 小写 status）通过', () => {
    const result = contestLinkDtoSchema.safeParse({
      linkId: 'L0087',
      linkType: 'microwave',
      srcNodeId: 'GND005',
      dstNodeId: 'AIR003',
      status: 'up',
      params: {
        delayMs: 12.5,
        jitterMs: 3.0,
        bandwitdhBps: 8000000,
        ber: 0.0001,
        packetLossRate: 0.02,
      },
      time: '10:30:02.125480',
      tsUs: 1798585182125680,
    })
    expect(result.success).toBe(true)
  })
})

describe('scenarioValidateResultDtoSchema', () => {
  it('校验结果（valid/errors/warnings）通过', () => {
    const result = scenarioValidateResultDtoSchema.safeParse({
      valid: false,
      errors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
      warnings: [],
    })
    expect(result.success).toBe(true)
  })

  it('缺少 errors 字段校验失败', () => {
    expect(scenarioValidateResultDtoSchema.safeParse({ valid: true }).success).toBe(false)
  })
})

describe('eventInjectionResultDtoSchema', () => {
  it('事件注入结果通过', () => {
    const result = eventInjectionResultDtoSchema.safeParse({
      eventId: 'EV-1',
      accepted: true,
      scheduledAtSimTimeMs: 0,
    })
    expect(result.success).toBe(true)
  })
})

describe('qosSummaryDtoSchema', () => {
  it('QoS 汇总（含 violations）通过', () => {
    const result = qosSummaryDtoSchema.safeParse({
      totalFlows: 2,
      compliantFlows: 1,
      nonCompliantFlows: 1,
      complianceRate: 0.5,
      byServiceType: { DATA: { total: 2, compliant: 1 } },
      violations: [
        { flowId: 'F-1', metric: 'delayMs', actual: 80, threshold: 50, direction: 'HIGH' },
      ],
    })
    expect(result.success).toBe(true)
  })
})

describe('topologySnapshotDtoSchema', () => {
  it('含 nodes/links/flows 的快照通过校验', () => {
    const result = topologySnapshotDtoSchema.safeParse({
      runId: 'RUN-001',
      version: 1,
      simTimeMs: 0,
      nodes: [{ nodeId: 'N1', name: 'A', nodeType: 'UAV', status: 'ONLINE' }],
      links: [validLink],
      flows: [
        {
          flowId: 'FLOW-1',
          name: 'f',
          serviceType: 'VOICE',
          srcNodeId: 'N1',
          dstNodeId: 'N2',
          priority: 1,
          requiredBandwidthBps: 64000,
          qos: {},
          status: 'ACTIVE',
        },
      ],
      summary: {
        nodeCount: 1,
        onlineNodeCount: 1,
        linkCount: 1,
        upLinkCount: 1,
        connectedComponents: 1,
      },
    })
    expect(result.success).toBe(true)
  })
})
