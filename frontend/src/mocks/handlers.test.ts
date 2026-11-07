// @vitest-environment node
import { beforeEach, describe, expect, it } from 'vitest'
import { getDashboardSummary } from '@/api/dashboard'
import { getFlow, getFlowRoute, listFlows } from '@/api/flows'
import { getFlowQos, getQosSummary } from '@/api/qos'
import { getResourceAllocation, getResourceHistory } from '@/api/resources'
import {
  cloneScenario,
  createScenario,
  deleteScenario,
  getScenario,
  listScenarios,
  updateScenario,
  validateScenario,
} from '@/api/scenarios'
import {
  createSimulation,
  getSimulation,
  getSimulationCapabilities,
  getSimulationStatus,
  injectSimulationEvent,
  pauseSimulation,
  resumeSimulation,
  setSimulationSpeed,
  startSimulation,
  stepSimulation,
  stopSimulation,
} from '@/api/simulations'
import { getLink, getNode, getNodeNeighbors, getNodeRoutes, getTopology } from '@/api/topology'
import type { RealtimeEventEnvelope } from '@/types/domain/realtime'
import { LinkStatus, RealtimeEventType } from '@/types/enums'
import { server } from '../test/server'
import { createMockHandlers } from './handlers'
import { MockRealtimeProvider } from './realtime'
import { MockWorld } from './world'

let world: MockWorld
let provider: MockRealtimeProvider

beforeEach(() => {
  world = new MockWorld()
  provider = new MockRealtimeProvider(world)
  server.use(...createMockHandlers(world))
})

describe('Mock REST：场景写入与读取一致', () => {
  it('创建后列表与详情可见', async () => {
    const created = await createScenario({ name: '演示', nodes: [], links: [], flows: [] })
    const list = await listScenarios()
    expect(list.items.some((s) => s.scenarioId === created.scenarioId)).toBe(true)
    expect((await getScenario(created.scenarioId)).name).toBe('演示')
  })

  it('更新/校验/克隆/删除', async () => {
    const created = await createScenario({ name: 'a', nodes: [], links: [], flows: [] })
    const updated = await updateScenario(created.scenarioId, {
      name: 'b',
      nodes: [],
      links: [],
      flows: [],
    })
    expect(updated.version).toBe(2)

    expect((await validateScenario(created.scenarioId)).valid).toBe(true)
    expect((await cloneScenario(created.scenarioId)).name).toContain('副本')

    await deleteScenario(created.scenarioId)
    await expect(getScenario(created.scenarioId)).rejects.toMatchObject({ status: 404 })
  })

  it('不存在的场景返回 404', async () => {
    await expect(getScenario('NOPE')).rejects.toMatchObject({
      status: 404,
      code: 'RESOURCE_NOT_FOUND',
    })
  })
})

describe('Mock REST：仿真写入 → GET 与 WS 事件一致', () => {
  it('创建/启动/注入/步进在 REST 与 WS 两侧一致', async () => {
    const run = await createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })
    expect((await getSimulation(run.runId)).status).toBe('READY')

    const events: RealtimeEventEnvelope[] = []
    provider.subscribe(run.runId, { onEvent: (e) => events.push(e) })

    await startSimulation(run.runId)
    expect(events.some((e) => e.eventType === RealtimeEventType.SIMULATION_STATUS_CHANGED)).toBe(
      true,
    )
    expect((await getSimulation(run.runId)).status).toBe('RUNNING')
    expect((await getSimulationStatus(run.runId)).status).toBe('RUNNING')

    await injectSimulationEvent(run.runId, {
      eventType: 'LINK_DOWN',
      triggerAtMs: 1000,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
    })
    await stepSimulation(run.runId, { steps: 1 })
    expect(events.some((e) => e.eventType === RealtimeEventType.LINK_STATUS_CHANGED)).toBe(true)

    const topology = await getTopology(run.runId)
    expect(topology.links.find((l) => l.linkId === 'L-05')?.status).toBe(LinkStatus.DOWN)

    await pauseSimulation(run.runId)
    await resumeSimulation(run.runId)
    await setSimulationSpeed(run.runId, { speed: 4 })
    expect((await getSimulation(run.runId)).speed).toBe(4)
    await stopSimulation(run.runId)
    expect((await getSimulation(run.runId)).status).toBe('STOPPED')
  })

  it('切换 run 不串数据', async () => {
    const runA = await createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })
    const runB = await createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })

    await injectSimulationEvent(runA.runId, {
      eventType: 'LINK_DOWN',
      triggerAtMs: 1000,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
    })
    await stepSimulation(runA.runId, { steps: 1 })

    const topoA = await getTopology(runA.runId)
    const topoB = await getTopology(runB.runId)
    expect(topoA.links.find((l) => l.linkId === 'L-05')?.status).toBe(LinkStatus.DOWN)
    expect(topoB.links.find((l) => l.linkId === 'L-05')?.status).toBe('UP')
  })

  it('能力声明与不存在的运行 404', async () => {
    expect(await getSimulationCapabilities()).toEqual({ supportsStep: true })
    await expect(getSimulation('NOPE')).rejects.toMatchObject({ status: 404 })
    await expect(getTopology('NOPE')).rejects.toMatchObject({ status: 404 })
  })
})

describe('Mock REST：运行态只读派生', () => {
  it('拓扑/节点/链路/邻居/路由/业务/QoS/资源/Dashboard', async () => {
    const run = await createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })

    expect((await getTopology(run.runId)).nodes).toHaveLength(8)
    expect((await getNode('N-01', run.runId)).nodeId).toBe('N-01')
    expect((await getLink('L-01', run.runId)).linkId).toBe('L-01')
    expect(
      ((await getNodeNeighbors('N-01', run.runId)).neighbors as string[]).length,
    ).toBeGreaterThan(0)
    expect(await getNodeRoutes('N-01', run.runId)).toEqual({ nodeId: 'N-01', routes: [] })

    expect((await listFlows({ runId: run.runId })).total).toBe(3)
    expect((await getFlow('F-01', run.runId)).flowId).toBe('F-01')
    expect(await getFlowRoute('F-01', run.runId)).toMatchObject({ flowId: 'F-01' })

    expect((await getQosSummary(run.runId)).totalFlows).toBe(3)
    expect(await getFlowQos('F-01', run.runId)).toEqual({ flowId: 'F-01' })
    expect(await getResourceAllocation(run.runId)).toEqual({ runId: run.runId })
    expect(await getResourceHistory(run.runId)).toEqual([])
    expect(await getDashboardSummary(run.runId)).toEqual({ runId: run.runId })
  })

  it('运行态只读端点对不存在资源返回 404', async () => {
    const run = await createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })
    await expect(getNode('NOPE', run.runId)).rejects.toMatchObject({ status: 404 })
    await expect(getFlow('NOPE', run.runId)).rejects.toMatchObject({ status: 404 })
    await expect(getFlowQos('NOPE', run.runId)).rejects.toMatchObject({ status: 404 })
  })
})
