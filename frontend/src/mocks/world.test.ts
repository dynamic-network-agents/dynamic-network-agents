import { describe, expect, it } from 'vitest'
import {
  LinkStatus,
  NodeStatus,
  RealtimeEventType,
  ScenarioStatus,
  SimulationStatus,
} from '@/types/enums'
import { DEFAULT_SEED } from './fixtures'
import { MockWorld, STEP_MS } from './world'

const DEFAULT_RUN = { scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 }

describe('MockWorld 场景', () => {
  it('构造时内置默认场景', () => {
    const world = new MockWorld()
    expect(world.getScenario('SCN-DEFAULT')?.status).toBe(ScenarioStatus.VALID)
    expect(world.listScenarios().total).toBe(1)
  })

  it('创建/更新/删除/克隆/校验', () => {
    const world = new MockWorld()
    const created = world.createScenario({ name: 's1', nodes: [], links: [], flows: [] })
    expect(created.scenarioId).toBe('SCN-001')
    expect(created.status).toBe(ScenarioStatus.DRAFT)

    expect(world.listScenarios().total).toBe(2)
    expect(world.getScenario(created.scenarioId)?.name).toBe('s1')

    const updated = world.updateScenario(created.scenarioId, {
      name: 's2',
      nodes: [],
      links: [],
      flows: [],
    })
    expect(updated?.version).toBe(2)
    expect(updated?.name).toBe('s2')

    const clone = world.cloneScenario(created.scenarioId)
    expect(clone?.scenarioId).toBe('SCN-002')
    expect(clone?.name).toContain('副本')

    expect(world.validateScenario()).toEqual({ valid: true, errors: [], warnings: [] })

    expect(world.deleteScenario(created.scenarioId)).toBe(true)
    expect(world.getScenario(created.scenarioId)).toBeUndefined()
  })
})

describe('MockWorld 仿真运行', () => {
  it('创建运行：READY + 拓扑快照', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    expect(run.status).toBe(SimulationStatus.READY)
    expect(run.simTimeMs).toBe(0)
    expect(world.getTopology(run.runId)?.nodes).toHaveLength(8)
    expect(world.getTopology(run.runId)?.version).toBe(1)
  })

  it('创建运行引用不存在的场景抛错', () => {
    const world = new MockWorld()
    expect(() => world.createSimulation({ scenarioId: 'NOPE', scenarioVersion: 1 })).toThrow()
  })

  it('启停控制产生状态事件且 seq 递增', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.start(run.runId)
    expect(world.getSimulation(run.runId)?.status).toBe(SimulationStatus.RUNNING)
    world.pause(run.runId)
    world.resume(run.runId)
    world.stop(run.runId)
    expect(world.getSimulation(run.runId)?.status).toBe(SimulationStatus.STOPPED)

    const events = world.getEvents(run.runId)
    expect(events).toHaveLength(4)
    expect(events.every((e) => e.eventType === RealtimeEventType.SIMULATION_STATUS_CHANGED)).toBe(
      true,
    )
    expect(events.map((e) => e.seq)).toEqual([1, 2, 3, 4])
  })

  it('setSpeed 更新速度并发出 TIME_UPDATED', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.setSpeed(run.runId, 5)
    expect(world.getSimulation(run.runId)?.speed).toBe(5)
    expect(world.getEvents(run.runId)[0].eventType).toBe(RealtimeEventType.SIMULATION_TIME_UPDATED)
  })

  it('step 推进一个步长并产生 TIME_UPDATED', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.step(run.runId)
    expect(world.getSimulation(run.runId)?.simTimeMs).toBe(STEP_MS)
    expect(world.getEvents(run.runId)[0].eventType).toBe(RealtimeEventType.SIMULATION_TIME_UPDATED)
  })
})

describe('MockWorld 事件生成（时间线）', () => {
  it('advance 触发场景事件并更新拓扑', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.advance(run.runId, 5000)

    const topology = world.getTopology(run.runId)
    expect(topology?.nodes.find((n) => n.nodeId === 'N-03')?.status).toBe(NodeStatus.OFFLINE)
    expect(topology?.version).toBe(2)

    const events = world.getEvents(run.runId)
    expect(events.some((e) => e.eventType === RealtimeEventType.SIMULATION_TIME_UPDATED)).toBe(true)
    expect(events.some((e) => e.eventType === RealtimeEventType.NODE_STATUS_CHANGED)).toBe(true)
  })

  it('注入事件在推进到触发时刻时产生实时事件', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    const injected = world.injectEvent(run.runId, {
      eventType: 'LINK_DOWN',
      triggerAtMs: 1000,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
    })
    expect(injected?.accepted).toBe(true)

    world.advance(run.runId, 1000)
    const events = world.getEvents(run.runId)
    expect(events.some((e) => e.eventType === RealtimeEventType.LINK_STATUS_CHANGED)).toBe(true)
    expect(world.getTopology(run.runId)?.links.find((l) => l.linkId === 'L-05')?.status).toBe(
      LinkStatus.DOWN,
    )
  })

  it('触发时刻等于当前仿真时刻（含 0）的事件也会触发', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.injectEvent(run.runId, {
      eventType: 'LINK_DOWN',
      triggerAtMs: 0,
      targetType: 'LINK',
      targetId: 'L-05',
      payload: {},
    })
    world.step(run.runId)
    expect(world.getTopology(run.runId)?.links.find((l) => l.linkId === 'L-05')?.status).toBe(
      LinkStatus.DOWN,
    )
  })

  it('未定义映射的事件类型不产生实时事件、不抛错', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)
    world.injectEvent(run.runId, {
      eventType: 'FLOW_ADD',
      triggerAtMs: 500,
      targetType: 'FLOW',
      targetId: 'F-01',
      payload: {},
    })
    world.advance(run.runId, 1000)
    // 仅 TIME_UPDATED，无 FLOW 类实时事件
    expect(world.getEvents(run.runId).map((e) => e.eventType)).toEqual([
      RealtimeEventType.SIMULATION_TIME_UPDATED,
    ])
  })
})

describe('MockWorld 隔离与可复现', () => {
  it('跨 run 事件与拓扑互不串扰', () => {
    const world = new MockWorld()
    const runA = world.createSimulation(DEFAULT_RUN)
    const runB = world.createSimulation(DEFAULT_RUN)

    world.start(runA.runId)
    world.advance(runA.runId, 5000)

    expect(world.getEvents(runB.runId)).toHaveLength(0)
    expect(world.getTopology(runB.runId)?.nodes.find((n) => n.nodeId === 'N-03')?.status).toBe(
      NodeStatus.ONLINE,
    )
    expect(world.getTopology(runA.runId)?.nodes.find((n) => n.nodeId === 'N-03')?.status).toBe(
      NodeStatus.OFFLINE,
    )
  })

  it('同一 seed + 相同操作序列结果可复现', () => {
    const seed = 12345
    const ops = (world: MockWorld) => {
      const scenario = world.createScenario({ name: 'r', nodes: [], links: [], flows: [] })
      const run = world.createSimulation(DEFAULT_RUN)
      world.start(run.runId)
      world.advance(run.runId, 5000)
      return { scenario, run: world.getSimulation(run.runId), events: world.getEvents(run.runId) }
    }
    expect(ops(new MockWorld(seed))).toEqual(ops(new MockWorld(seed)))
  })
})

describe('MockWorld 只读派生', () => {
  it('节点/链路/邻居/业务/QoS/资源/Dashboard 派生', () => {
    const world = new MockWorld()
    const run = world.createSimulation(DEFAULT_RUN)

    expect(world.getNode(run.runId, 'N-01')?.nodeId).toBe('N-01')
    expect(world.getLink(run.runId, 'L-01')?.linkId).toBe('L-01')
    expect(world.getFlow(run.runId, 'F-01')?.flowId).toBe('F-01')

    const neighbors = world.getNodeNeighbors(run.runId, 'N-01')
    expect((neighbors?.neighbors as string[]).length).toBeGreaterThan(0)

    expect(world.getNodeRoutes(run.runId, 'N-01')).toEqual({ nodeId: 'N-01', routes: [] })
    expect(world.getFlowRoute(run.runId, 'F-01')).toMatchObject({ flowId: 'F-01' })
    expect(world.listFlows(run.runId)?.total).toBe(3)

    expect(world.getQosSummary(run.runId)?.totalFlows).toBe(3)
    expect(world.getFlowQos(run.runId, 'F-01')).toEqual({ flowId: 'F-01' })
    expect(world.getResourceAllocation(run.runId)).toEqual({ runId: run.runId })
    expect(world.getResourceHistory(run.runId)).toEqual([])
    expect(world.getDashboardSummary(run.runId)).toEqual({ runId: run.runId })
  })

  it('getSeed 返回构造 seed', () => {
    expect(new MockWorld(DEFAULT_SEED).getSeed()).toBe(DEFAULT_SEED)
  })
})
