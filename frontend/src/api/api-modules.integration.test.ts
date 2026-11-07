// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { http } from 'msw'
import { apiOk, server } from '../test/server'
import {
  cloneScenario,
  createScenario,
  createSimulation,
  deleteScenario,
  getDashboardSummary,
  getFlow,
  getFlowQos,
  getFlowRoute,
  getLink,
  getNode,
  getNodeNeighbors,
  getNodeRoutes,
  getQosSummary,
  getResourceAllocation,
  getResourceHistory,
  getScenario,
  getSimulation,
  getSimulationCapabilities,
  getSimulationStatus,
  getTopology,
  injectSimulationEvent,
  listFlows,
  listScenarios,
  pauseSimulation,
  resumeSimulation,
  setSimulationSpeed,
  startSimulation,
  stepSimulation,
  stopSimulation,
  updateScenario,
  validateScenario,
} from './index'

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
  requiredBandwidthBps: 100,
  qos: {},
  status: 'ACTIVE',
}
const scenarioDto = {
  scenarioId: 'SCN-1',
  name: 's',
  version: 1,
  status: 'DRAFT',
  nodes: [],
  links: [],
  flows: [],
}
const runDto = {
  runId: 'RUN-1',
  scenarioId: 'SCN-1',
  scenarioVersion: 1,
  status: 'READY',
  simTimeMs: 0,
  speed: 1,
}

describe('scenarios 模块', () => {
  it('列表/详情/创建/更新/删除/校验/克隆', async () => {
    let createdBody: unknown
    let updateBody: unknown
    let updateIfMatch: string | null = null

    server.use(
      http.get(`${API}/scenarios`, ({ request }) => {
        const url = new URL(request.url)
        expect(url.searchParams.get('page')).toBe('2')
        expect(url.searchParams.get('status')).toBe('DRAFT')
        return apiOk({ items: [scenarioDto], page: 2, pageSize: 20, total: 1 })
      }),
      http.get(`${API}/scenarios/:id`, () => apiOk(scenarioDto)),
      http.post(`${API}/scenarios`, async ({ request }) => {
        createdBody = await request.json()
        return apiOk(scenarioDto)
      }),
      http.put(`${API}/scenarios/:id`, async ({ request }) => {
        updateBody = await request.json()
        updateIfMatch = request.headers.get('If-Match')
        return apiOk(scenarioDto)
      }),
      http.delete(`${API}/scenarios/:id`, () => apiOk(null)),
      http.post(`${API}/scenarios/:id/validate`, () =>
        apiOk({ valid: true, errors: [], warnings: [] }),
      ),
      http.post(`${API}/scenarios/:id/clone`, () => apiOk(scenarioDto)),
    )

    const page = await listScenarios({ page: 2, status: 'DRAFT' })
    expect(page.total).toBe(1)
    expect(page.items[0].scenarioId).toBe('SCN-1')

    expect((await getScenario('SCN-1')).scenarioId).toBe('SCN-1')

    const input = { name: 's', nodes: [], links: [], flows: [] }
    await createScenario(input)
    expect(createdBody).toEqual(input)

    await updateScenario('SCN-1', input, { ifMatch: '"v1"', expectedVersion: 1 })
    expect(updateIfMatch).toBe('"v1"')
    expect(updateBody).toEqual({ ...input, expectedVersion: 1 })

    await deleteScenario('SCN-1')

    expect((await validateScenario('SCN-1', { version: 3, strict: true })).valid).toBe(true)

    expect((await cloneScenario('SCN-1')).scenarioId).toBe('SCN-1')
  })
})

describe('simulations 模块', () => {
  it('创建/详情/状态/控制/单步/调速/注入/能力', async () => {
    let createBody: unknown
    let createIdem: string | null = null
    let injectBody: unknown

    server.use(
      http.get(`${API}/simulations/capabilities`, () => apiOk({ supportsStep: true })),
      http.post(`${API}/simulations`, async ({ request }) => {
        createBody = await request.json()
        createIdem = request.headers.get('Idempotency-Key')
        return apiOk(runDto)
      }),
      http.get(`${API}/simulations/:id`, () => apiOk(runDto)),
      http.get(`${API}/simulations/:id/status`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/start`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/pause`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/resume`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/stop`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/step`, () => apiOk(runDto)),
      http.patch(`${API}/simulations/:id/speed`, () => apiOk(runDto)),
      http.post(`${API}/simulations/:id/events`, async ({ request }) => {
        injectBody = await request.json()
        return apiOk({ eventId: 'EV-1', accepted: true, scheduledAtSimTimeMs: 0 })
      }),
    )

    const createInput = { scenarioId: 'SCN-1', scenarioVersion: 1, seed: 1, speed: 1 }
    const created = await createSimulation(createInput, { idempotencyKey: 'IDEM-1' })
    expect(created.runId).toBe('RUN-1')
    expect(createBody).toEqual(createInput)
    expect(createIdem).toBe('IDEM-1')

    expect((await getSimulation('RUN-1')).runId).toBe('RUN-1')
    expect((await getSimulationStatus('RUN-1')).status).toBe('READY')

    for (const fn of [startSimulation, pauseSimulation, resumeSimulation, stopSimulation]) {
      expect((await fn('RUN-1')).runId).toBe('RUN-1')
    }

    await stepSimulation('RUN-1', { steps: 1 })
    await setSimulationSpeed('RUN-1', { speed: 5 })

    const inject = await injectSimulationEvent('RUN-1', {
      eventType: 'LINK_PARAM_CHANGE',
      triggerAtMs: 0,
      targetType: 'LINK',
      targetId: 'L-1',
      payload: {},
    })
    expect(inject.eventId).toBe('EV-1')
    expect(injectBody).toMatchObject({ eventType: 'LINK_PARAM_CHANGE', targetType: 'LINK' })

    expect(await getSimulationCapabilities()).toEqual({ supportsStep: true })
  })
})

describe('网络/业务/QoS/资源/Dashboard 模块', () => {
  it('拓扑/节点/链路/邻居/路由表', async () => {
    server.use(
      http.get(`${API}/simulations/:id/topology`, ({ request }) => {
        expect(new URL(request.url).searchParams.get('includeFlows')).toBe('true')
        return apiOk({
          runId: 'RUN-1',
          version: 1,
          simTimeMs: 0,
          nodes: [],
          links: [],
          summary: {
            nodeCount: 0,
            onlineNodeCount: 0,
            linkCount: 0,
            upLinkCount: 0,
            connectedComponents: 0,
          },
        })
      }),
      http.get(`${API}/nodes/:id`, ({ request }) => {
        expect(new URL(request.url).searchParams.get('runId')).toBe('RUN-1')
        return apiOk(nodeDto)
      }),
      http.get(`${API}/links/:id`, () => apiOk(linkDto)),
      http.get(`${API}/nodes/:id/neighbors`, () => apiOk({ nodeId: 'N-1', neighbors: [] })),
      http.get(`${API}/nodes/:id/routes`, () => apiOk({ nodeId: 'N-1', routes: [] })),
    )

    expect((await getTopology('RUN-1', { includeFlows: true })).version).toBe(1)
    expect((await getNode('N-1', 'RUN-1')).nodeId).toBe('N-1')
    expect((await getLink('L-1', 'RUN-1')).linkId).toBe('L-1')
    expect((await getNodeNeighbors('N-1', 'RUN-1')).nodeId).toBe('N-1')
    expect((await getNodeRoutes('N-1', 'RUN-1')).nodeId).toBe('N-1')
  })

  it('业务/QoS/资源/Dashboard', async () => {
    server.use(
      http.get(`${API}/flows`, () => apiOk({ items: [flowDto], page: 1, pageSize: 20, total: 1 })),
      http.get(`${API}/flows/:id`, () => apiOk(flowDto)),
      http.get(`${API}/flows/:id/route`, () => apiOk({ flowId: 'F-1', path: ['N-1', 'N-2'] })),
      http.get(`${API}/qos/summary`, () =>
        apiOk({ totalFlows: 1, compliantFlows: 1, nonCompliantFlows: 0, complianceRate: 1 }),
      ),
      http.get(`${API}/qos/flows/:id`, () => apiOk({ flowId: 'F-1' })),
      http.get(`${API}/resources/allocation`, () => apiOk({ runId: 'RUN-1' })),
      http.get(`${API}/resources/history`, () => apiOk([])),
      http.get(`${API}/dashboard/summary`, () => apiOk({ runId: 'RUN-1' })),
    )

    expect((await listFlows({ runId: 'RUN-1' })).total).toBe(1)
    expect((await getFlow('F-1', 'RUN-1')).flowId).toBe('F-1')
    expect((await getFlowRoute('F-1', 'RUN-1')).flowId).toBe('F-1')
    expect((await getQosSummary('RUN-1')).totalFlows).toBe(1)
    expect((await getFlowQos('F-1', 'RUN-1')).flowId).toBe('F-1')
    expect(await getResourceAllocation('RUN-1')).toEqual({ runId: 'RUN-1' })
    expect(await getResourceHistory('RUN-1')).toEqual([])
    expect(await getDashboardSummary('RUN-1')).toEqual({ runId: 'RUN-1' })
  })
})
