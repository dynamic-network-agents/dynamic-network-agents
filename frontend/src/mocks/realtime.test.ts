import { describe, expect, it } from 'vitest'
import { RealtimeEventType } from '@/types/enums'
import { MockRealtimeProvider } from './realtime'
import { MockWorld } from './world'

function makeWorld() {
  const world = new MockWorld()
  const run = world.createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })
  world.start(run.runId)
  world.advance(run.runId, 5000)
  return { world, run }
}

describe('MockRealtimeProvider', () => {
  it('订阅时补发 lastSeq 之后的事件', () => {
    const { world, run } = makeWorld()
    const provider = new MockRealtimeProvider(world)

    const all: string[] = []
    provider.subscribe(run.runId, { onEvent: (e) => all.push(e.eventType) })
    expect(all).toContain(RealtimeEventType.SIMULATION_STATUS_CHANGED)
    expect(all).toContain(RealtimeEventType.SIMULATION_TIME_UPDATED)
    expect(all).toContain(RealtimeEventType.NODE_STATUS_CHANGED)

    const lastSeq = world.getEvents(run.runId).length
    const sinceLast: string[] = []
    provider.subscribe(run.runId, { onEvent: (e) => sinceLast.push(e.eventId) }, { lastSeq })
    expect(sinceLast).toHaveLength(0)
  })

  it('仅转发所订阅 runId 的事件', () => {
    const world = new MockWorld()
    const runA = world.createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })
    const runB = world.createSimulation({ scenarioId: 'SCN-DEFAULT', scenarioVersion: 1 })

    const provider = new MockRealtimeProvider(world)
    const received: string[] = []
    provider.subscribe(runA.runId, { onEvent: (e) => received.push(e.runId) })

    world.start(runB.runId)
    world.start(runA.runId)
    expect(received).toEqual([runA.runId])
  })

  it('close 后不再推送', () => {
    const { world, run } = makeWorld()
    const provider = new MockRealtimeProvider(world)

    const received: string[] = []
    const connection = provider.subscribe(run.runId, { onEvent: (e) => received.push(e.eventType) })
    connection.close()
    const countAtClose = received.length

    world.pause(run.runId)
    expect(received).toHaveLength(countAtClose)
  })

  it('报告连接状态：connecting → open → closed', () => {
    const { world, run } = makeWorld()
    const provider = new MockRealtimeProvider(world)
    const statuses: string[] = []
    const connection = provider.subscribe(run.runId, {
      onEvent: () => {},
      onStatus: (s) => statuses.push(s),
    })
    connection.close()
    expect(statuses).toEqual(['connecting', 'open', 'closed'])
  })
})
