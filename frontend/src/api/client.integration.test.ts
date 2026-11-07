// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { delay, http, HttpResponse } from 'msw'
import { apiOk, server } from '../test/server'
import {
  isCancelledError,
  isConflictError,
  isNetworkError,
  isServerError,
  isValidationError,
} from './errors'
import { request } from './client'

const API = 'http://localhost:8000/api'

describe('API client 集成（MSW）', () => {
  it('成功：统一解包 data', async () => {
    server.use(http.get(`${API}/ping`, () => apiOk({ hello: 'world' })))
    await expect(request<{ hello: string }>({ method: 'get', url: '/ping' })).resolves.toEqual({
      hello: 'world',
    })
  })

  it('409：冲突错误并保留 requestId', async () => {
    server.use(
      http.post(`${API}/simulations/RUN-1/start`, () =>
        HttpResponse.json(
          {
            code: 'SIMULATION_STATE_CONFLICT',
            message: 'simulation is not running',
            details: { currentStatus: 'PAUSED' },
            requestId: 'REQ-2',
          },
          { status: 409 },
        ),
      ),
    )
    const promise = request({ method: 'post', url: '/simulations/RUN-1/start' })
    await expect(promise).rejects.toSatisfy(isConflictError)
    await expect(promise).rejects.toMatchObject({
      code: 'SIMULATION_STATE_CONFLICT',
      requestId: 'REQ-2',
    })
  })

  it('422：提取字段错误', async () => {
    server.use(
      http.post(`${API}/scenarios/SCN-1/validate`, () =>
        HttpResponse.json(
          {
            code: 'SCENARIO_VALIDATION_FAILED',
            message: '校验失败',
            details: {
              fieldErrors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
            },
          },
          { status: 422 },
        ),
      ),
    )
    const promise = request({ method: 'post', url: '/scenarios/SCN-1/validate' })
    await expect(promise).rejects.toSatisfy(isValidationError)
    await expect(promise).rejects.toMatchObject({
      fieldErrors: [{ code: 'LINK_NOT_FOUND', path: 'links[0]', message: '链路不存在' }],
    })
  })

  it('500：服务端错误', async () => {
    server.use(
      http.get(`${API}/qos/summary`, () =>
        HttpResponse.json({ code: 'INTERNAL_ERROR', message: 'boom' }, { status: 500 }),
      ),
    )
    const promise = request({ method: 'get', url: '/qos/summary' })
    await expect(promise).rejects.toSatisfy(isServerError)
    await expect(promise).rejects.toMatchObject({ code: 'INTERNAL_ERROR' })
  })

  it('网络错误：无 HTTP 响应', async () => {
    server.use(http.get(`${API}/topology`, () => HttpResponse.error()))
    await expect(request({ method: 'get', url: '/topology' })).rejects.toSatisfy(isNetworkError)
  })

  it('取消：AbortController 中断请求', async () => {
    server.use(
      http.get(`${API}/scenarios/SCN-1`, async () => {
        await delay(300)
        return apiOk({ scenarioId: 'SCN-1' })
      }),
    )
    const controller = new AbortController()
    const promise = request({ method: 'get', url: '/scenarios/SCN-1', signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toSatisfy(isCancelledError)
  })
})
