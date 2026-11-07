import { HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

/**
 * FE-005/007 API 集成测试共用的 MSW server（无默认 handler）。
 * 生命周期（listen / resetHandlers / close）已由 `src/test/setup.ts` 全局接入，
 * 各测试文件无需再调用 setup；用 `server.use(...)` 覆盖具体路由即可。
 */
export const server = setupServer()

/** 成功信封（§7.2）。 */
export function apiOk(data: unknown) {
  return HttpResponse.json({
    code: 'OK',
    message: 'success',
    data,
    requestId: 'REQ-TEST-1',
    timestamp: '2026-11-07T10:00:00+08:00',
  })
}

/** 错误信封（§7.2），默认 500。 */
export function apiErr(status: number, body?: Record<string, unknown>) {
  return HttpResponse.json(body ?? { code: 'INTERNAL_ERROR', message: 'error' }, { status })
}
