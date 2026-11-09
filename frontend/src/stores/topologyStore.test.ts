// @vitest-environment node
import { beforeEach, describe, expect, it } from 'vitest'
import { http } from 'msw'
import { apiErr, apiOk, server } from '../test/server'
import { topologySnapshotDtoSchema } from '@/schemas/simulation'
import { toTopologySnapshot } from '@/adapters/simulation'
import { FlowStatus, LinkStatus, NodeStatus, RealtimeEventType } from '@/types/enums'
import {
  applyTopologyEvent,
  selectFlowsById,
  selectLinksById,
  selectNodesById,
  selectTopologyRunId,
  selectTopologySnapshot,
  selectTopologySnapshotStatus,
  updateFlow,
  useTopologyStore,
} from './topologyStore'

const API = 'http://localhost:8000/api'

const nodeDto = { nodeId: 'N-1', name: 'A', nodeType: 'UAV', status: 'ONLINE' }
const linkDto = {
  linkId: 'L-1',
  linkPlane: 'DATA',
  linkType: 'microwave',
  srcNodeId: 'N-1',
  dstNodeId: 'N-2',
  direction: 'BIDIRECTIONAL',
  status: 'UP',
  params: { delayMs: 1, jitterMs: 0, bandwidthBps: 1000, ber: 0, packetLossRate: 0 },
}
const flowDto = {
  flowId: 'F-1',
  name: 'f',
  serviceType: 'DATA',
  srcNodeId: 'N-1',
  dstNodeId: 'N-2',
  priority: 1,
  requiredBandwidthBps: 1000,
  qos: {},
  status: 'ACTIVE',
}

function topologyDto(overrides: Record<string, unknown> = {}) {
  return {
    runId: 'RUN-1',
    version: 1,
    simTimeMs: 0,
    nodes: [nodeDto],
    links: [linkDto],
    flows: [flowDto],
    ...overrides,
  }
}

const parsedFixture = topologySnapshotDtoSchema.safeParse(topologyDto())
if (!parsedFixture.success) throw new Error('fixture invalid')
const snapshot = toTopologySnapshot(parsedFixture.data)

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('topologyStore loadTopology', () => {
  beforeEach(() => {
    useTopologyStore.getState().resetRun()
  })

  it('成功加载并适配，selector 派生索引', async () => {
    server.use(http.get(`${API}/simulations/RUN-1/topology`, () => apiOk(topologyDto())))
    await useTopologyStore.getState().loadTopology('RUN-1')
    const s = useTopologyStore.getState()
    expect(selectTopologySnapshotStatus(s)).toBe('success')
    expect(selectTopologySnapshot(s)?.runId).toBe('RUN-1')
    expect(selectNodesById(s).get('N-1')?.status).toBe(NodeStatus.ONLINE)
    expect(selectLinksById(s).get('L-1')?.linkPlane).toBe('DATA')
    expect(selectFlowsById(s).get('F-1')?.flowId).toBe('F-1')
  })

  it('HTTP 错误落 error', async () => {
    server.use(http.get(`${API}/simulations/RUN-1/topology`, () => apiErr(500)))
    await useTopologyStore.getState().loadTopology('RUN-1')
    const s = useTopologyStore.getState()
    expect(s.snapshot.status).toBe('error')
    expect(s.snapshot.error?.code).toBe('INTERNAL_ERROR')
  })

  it('校验失败（缺 links）落 VALIDATION_FAILED', async () => {
    const bad = topologyDto() as Record<string, unknown>
    delete bad.links
    server.use(http.get(`${API}/simulations/RUN-1/topology`, () => apiOk(bad)))
    await useTopologyStore.getState().loadTopology('RUN-1')
    expect(useTopologyStore.getState().snapshot.error?.code).toBe('VALIDATION_FAILED')
  })

  it('晚到旧 run 不覆盖新 run', async () => {
    const d = deferred<Response>()
    server.use(
      http.get(`${API}/simulations/RUN-A/topology`, () => d.promise),
      http.get(`${API}/simulations/RUN-B/topology`, () => apiOk(topologyDto({ runId: 'RUN-B' }))),
    )

    useTopologyStore.getState().resetRun('RUN-A')
    const pendingA = useTopologyStore.getState().loadTopology('RUN-A')

    useTopologyStore.getState().resetRun('RUN-B')
    await useTopologyStore.getState().loadTopology('RUN-B')
    expect(selectTopologyRunId(useTopologyStore.getState())).toBe('RUN-B')
    expect(useTopologyStore.getState().snapshot.data?.runId).toBe('RUN-B')

    d.resolve(apiOk(topologyDto({ runId: 'RUN-A' })))
    await pendingA
    expect(useTopologyStore.getState().snapshot.data?.runId).toBe('RUN-B')
  })
})

describe('applyTopologyEvent（纯函数）', () => {
  function evt(eventType: string, data: unknown, runId = 'RUN-1') {
    return { eventId: 'E', eventType, runId, seq: 1, data }
  }

  it('NODE_STATUS_CHANGED 更新节点状态', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.NODE_STATUS_CHANGED, { nodeId: 'N-1', newStatus: 'OFFLINE' }),
    )
    expect(out.nodes[0].status).toBe(NodeStatus.OFFLINE)
    expect(out).not.toBe(snapshot)
  })

  it('NODE_POSITION_UPDATED 更新坐标', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.NODE_POSITION_UPDATED, { nodeId: 'N-1', position: { x: 1, y: 2 } }),
    )
    expect(out.nodes[0].position).toEqual({ x: 1, y: 2 })
  })

  it('LINK_STATUS_CHANGED 更新链路状态', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.LINK_STATUS_CHANGED, { linkId: 'L-1', newStatus: 'DOWN' }),
    )
    expect(out.links[0].status).toBe(LinkStatus.DOWN)
  })

  it('LINK_METRIC_UPDATED 更新链路参数', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.LINK_METRIC_UPDATED, {
        linkId: 'L-1',
        params: { delayMs: 9, jitterMs: 1, bandwidthBps: 1000, ber: 0, packetLossRate: 0 },
      }),
    )
    expect(out.links[0].params.delayMs).toBe(9)
  })

  it('FLOW_STATUS_CHANGED 更新流状态', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.FLOW_STATUS_CHANGED, { flowId: 'F-1', status: 'INTERRUPTED' }),
    )
    expect(out.flows?.[0].status).toBe(FlowStatus.INTERRUPTED)
  })

  it('ROUTE_CHANGED 更新当前路径', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.ROUTE_CHANGED, { flowId: 'F-1', newPath: ['N-1', 'N-3'] }),
    )
    expect(out.flows?.[0].currentPath).toEqual(['N-1', 'N-3'])
  })

  it('QOS_METRIC_UPDATED 更新测量值', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.QOS_METRIC_UPDATED, { flowId: 'F-1', measurement: { delayMs: 5 } }),
    )
    expect(out.flows?.[0].measuredQos).toEqual({ delayMs: 5 })
  })

  it('TOPOLOGY_UPDATED 更新版本号', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.TOPOLOGY_UPDATED, { snapshotVersion: 7 }),
    )
    expect(out.version).toBe(7)
  })

  it('未知事件原样返回同一引用', () => {
    expect(applyTopologyEvent(snapshot, evt('SOMETHING_ELSE', {}))).toBe(snapshot)
  })

  it('缺字段原样返回同一引用', () => {
    expect(
      applyTopologyEvent(
        snapshot,
        evt(RealtimeEventType.NODE_STATUS_CHANGED, { newStatus: 'OFFLINE' }),
      ),
    ).toBe(snapshot)
  })

  it('不存在的 nodeId 走不匹配分支（内容不变但为新对象）', () => {
    const out = applyTopologyEvent(
      snapshot,
      evt(RealtimeEventType.NODE_STATUS_CHANGED, { nodeId: 'N-9', newStatus: 'OFFLINE' }),
    )
    expect(out.nodes[0].status).toBe(NodeStatus.ONLINE)
    expect(out).not.toBe(snapshot)
  })
})

describe('拓扑 selector 索引引用稳定性', () => {
  beforeEach(() => {
    useTopologyStore.getState().resetRun()
  })

  it('数据未变时返回同一 Map 引用', async () => {
    server.use(http.get(`${API}/simulations/RUN-1/topology`, () => apiOk(topologyDto())))
    await useTopologyStore.getState().loadTopology('RUN-1')
    const s = useTopologyStore.getState()
    expect(selectNodesById(s)).toBe(selectNodesById(s))
    expect(selectLinksById(s)).toBe(selectLinksById(s))
    expect(selectFlowsById(s)).toBe(selectFlowsById(s))
  })

  it('实时事件更新快照后返回新的 Map（内容已更新）', async () => {
    server.use(http.get(`${API}/simulations/RUN-1/topology`, () => apiOk(topologyDto())))
    await useTopologyStore.getState().loadTopology('RUN-1')
    const before = selectNodesById(useTopologyStore.getState())

    useTopologyStore.getState().applyRealtimeEvent({
      eventId: 'E-1',
      eventType: RealtimeEventType.NODE_STATUS_CHANGED,
      runId: 'RUN-1',
      seq: 1,
      data: { nodeId: 'N-1', newStatus: 'OFFLINE' },
    })

    const after = selectNodesById(useTopologyStore.getState())
    expect(after).not.toBe(before)
    expect(after.get('N-1')?.status).toBe(NodeStatus.OFFLINE)
  })
})

describe('updateFlow 无 flows', () => {
  it('无 flows 原样返回同一引用', () => {
    const noFlows = { ...snapshot, flows: undefined }
    expect(updateFlow(noFlows, 'F-1', { status: FlowStatus.INTERRUPTED })).toBe(noFlows)
  })
})
