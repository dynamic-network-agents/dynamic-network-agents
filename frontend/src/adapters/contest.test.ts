import { describe, expect, it } from 'vitest'
import { contestLinkToNetworkLink } from './contest'

const sample = {
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
}

describe('contestLinkToNetworkLink', () => {
  it('旧拼写 bandwitdhBps 归一为 params.bandwidthBps', () => {
    expect(contestLinkToNetworkLink(sample).params.bandwidthBps).toBe(8000000)
  })

  it('status 小写归一为大写枚举', () => {
    expect(contestLinkToNetworkLink(sample).status).toBe('UP')
  })

  it('默认 linkPlane=DATA、direction=BIDIRECTIONAL，可显式覆盖', () => {
    const vm = contestLinkToNetworkLink(sample)
    expect(vm.linkPlane).toBe('DATA')
    expect(vm.direction).toBe('BIDIRECTIONAL')
    const ctrl = contestLinkToNetworkLink(sample, { linkPlane: 'CONTROL' })
    expect(ctrl.linkPlane).toBe('CONTROL')
  })

  it('linkType 透传、tsUs/time 保留', () => {
    const vm = contestLinkToNetworkLink(sample)
    expect(vm.linkType).toBe('microwave')
    expect(vm.tsUs).toBe(1798585182125680)
    expect(vm.time).toBe('10:30:02.125480')
  })
})
