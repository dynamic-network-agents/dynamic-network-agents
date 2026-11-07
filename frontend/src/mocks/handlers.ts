import { http, HttpResponse } from 'msw'
import type { HttpHandler } from 'msw'
import type { ScenarioUpsertInput } from '@/api/scenarios'
import type { CreateSimulationInput, InjectSimulationEventInput } from '@/api/simulations'
import type { MockWorld } from './world'

/**
 * Mock REST handlers（FE-007）。
 *
 * 覆盖 `api/` 全部首轮端点，读写 `MockWorld`，统一 `{ code, message, data }` 信封；
 * 写操作推进运行态并产生实时事件，供 MockRealtimeProvider 推送，保证 REST 与 WS 一致。
 * Agent/策略/指标等二轮端点待类型补齐后追加。
 */

export const MOCK_API_BASE = 'http://localhost:8000/api'

function ok(data: unknown) {
  return HttpResponse.json({
    code: 'OK',
    message: 'success',
    data,
    requestId: 'REQ-MOCK',
    timestamp: '2026-11-07T10:00:00+08:00',
  })
}

function notFound(resource: string) {
  return HttpResponse.json(
    { code: 'RESOURCE_NOT_FOUND', message: `${resource}不存在` },
    { status: 404 },
  )
}

function readRunId(request: Request): string {
  return new URL(request.url).searchParams.get('runId') ?? ''
}

export function createMockHandlers(world: MockWorld): HttpHandler[] {
  const API = MOCK_API_BASE
  return [
    // ------------------------------------------------------------- 场景 §7.6
    http.get(`${API}/scenarios`, ({ request }) => {
      const url = new URL(request.url)
      const page = Number(url.searchParams.get('page') ?? 1)
      const pageSize = Number(url.searchParams.get('pageSize') ?? 20)
      const status = url.searchParams.get('status') ?? undefined
      return ok(world.listScenarios({ page, pageSize, status }))
    }),
    http.get(`${API}/scenarios/:id`, ({ params }) => {
      const scenario = world.getScenario(String(params.id))
      return scenario ? ok(scenario) : notFound('场景')
    }),
    http.post(`${API}/scenarios`, async ({ request }) => {
      const input = (await request.json()) as ScenarioUpsertInput
      return ok(world.createScenario(input))
    }),
    http.put(`${API}/scenarios/:id`, async ({ request, params }) => {
      const input = (await request.json()) as ScenarioUpsertInput
      const scenario = world.updateScenario(String(params.id), input)
      return scenario ? ok(scenario) : notFound('场景')
    }),
    http.delete(`${API}/scenarios/:id`, ({ params }) => {
      return world.deleteScenario(String(params.id)) ? ok(null) : notFound('场景')
    }),
    http.post(`${API}/scenarios/:id/validate`, ({ params }) => {
      return world.getScenario(String(params.id)) ? ok(world.validateScenario()) : notFound('场景')
    }),
    http.post(`${API}/scenarios/:id/clone`, ({ params }) => {
      const clone = world.cloneScenario(String(params.id))
      return clone ? ok(clone) : notFound('场景')
    }),

    // ------------------------------------------------------------- 仿真 §7.7
    http.get(`${API}/simulations/capabilities`, () => ok({ supportsStep: true })),
    http.post(`${API}/simulations`, async ({ request }) => {
      const input = (await request.json()) as CreateSimulationInput
      if (!world.getScenario(input.scenarioId)) return notFound('场景')
      return ok(world.createSimulation(input))
    }),
    http.get(`${API}/simulations/:id`, ({ params }) => {
      const run = world.getSimulation(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.get(`${API}/simulations/:id/status`, ({ params }) => {
      const run = world.getSimulationStatus(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/start`, ({ params }) => {
      const run = world.start(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/pause`, ({ params }) => {
      const run = world.pause(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/resume`, ({ params }) => {
      const run = world.resume(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/stop`, ({ params }) => {
      const run = world.stop(String(params.id))
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/step`, async ({ request, params }) => {
      const body = (await request.json()) as { steps?: number }
      const run = world.step(String(params.id), body.steps ?? 1)
      return run ? ok(run) : notFound('运行')
    }),
    http.patch(`${API}/simulations/:id/speed`, async ({ request, params }) => {
      const body = (await request.json()) as { speed: number }
      const run = world.setSpeed(String(params.id), body.speed)
      return run ? ok(run) : notFound('运行')
    }),
    http.post(`${API}/simulations/:id/events`, async ({ request, params }) => {
      const input = (await request.json()) as InjectSimulationEventInput
      const result = world.injectEvent(String(params.id), input)
      return result ? ok(result) : notFound('运行')
    }),
    http.get(`${API}/simulations/:id/topology`, ({ params }) => {
      const topology = world.getTopology(String(params.id))
      return topology ? ok(topology) : notFound('运行')
    }),

    // ------------------------------------------------------------- 拓扑/节点/链路 §7.8
    http.get(`${API}/nodes/:id`, ({ request, params }) => {
      const node = world.getNode(readRunId(request), String(params.id))
      return node ? ok(node) : notFound('节点')
    }),
    http.get(`${API}/links/:id`, ({ request, params }) => {
      const link = world.getLink(readRunId(request), String(params.id))
      return link ? ok(link) : notFound('链路')
    }),
    http.get(`${API}/nodes/:id/neighbors`, ({ request, params }) => {
      const result = world.getNodeNeighbors(readRunId(request), String(params.id))
      return result ? ok(result) : notFound('节点')
    }),
    http.get(`${API}/nodes/:id/routes`, ({ request, params }) => {
      const result = world.getNodeRoutes(readRunId(request), String(params.id))
      return result ? ok(result) : notFound('节点')
    }),

    // ------------------------------------------------------------- 业务/QoS/资源/Dashboard §7.9/7.11
    http.get(`${API}/flows`, ({ request }) => {
      const url = new URL(request.url)
      const runId = url.searchParams.get('runId') ?? ''
      const page = Number(url.searchParams.get('page') ?? 1)
      const pageSize = Number(url.searchParams.get('pageSize') ?? 20)
      const status = url.searchParams.get('status') ?? undefined
      const result = world.listFlows(runId, { page, pageSize, status })
      return result ? ok(result) : notFound('运行')
    }),
    http.get(`${API}/flows/:id`, ({ request, params }) => {
      const flow = world.getFlow(readRunId(request), String(params.id))
      return flow ? ok(flow) : notFound('业务流')
    }),
    http.get(`${API}/flows/:id/route`, ({ request, params }) => {
      const result = world.getFlowRoute(readRunId(request), String(params.id))
      return result ? ok(result) : notFound('业务流')
    }),
    http.get(`${API}/qos/summary`, ({ request }) => {
      const result = world.getQosSummary(readRunId(request))
      return result ? ok(result) : notFound('运行')
    }),
    http.get(`${API}/qos/flows/:id`, ({ request, params }) => {
      const result = world.getFlowQos(readRunId(request), String(params.id))
      return result ? ok(result) : notFound('业务流')
    }),
    http.get(`${API}/resources/allocation`, ({ request }) => {
      const result = world.getResourceAllocation(readRunId(request))
      return result ? ok(result) : notFound('运行')
    }),
    http.get(`${API}/resources/history`, ({ request }) => {
      const result = world.getResourceHistory(readRunId(request))
      return result ? ok(result) : notFound('运行')
    }),
    http.get(`${API}/dashboard/summary`, ({ request }) => {
      const result = world.getDashboardSummary(readRunId(request))
      return result ? ok(result) : notFound('运行')
    }),
  ]
}
