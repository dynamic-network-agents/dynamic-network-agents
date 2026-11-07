import { setupWorker } from 'msw/browser'
import { createMockHandlers } from './handlers'
import { defaultMockWorld } from './provider'

/**
 * 浏览器端 MSW worker（FE-007）。
 *
 * 仅在 `useMock=true` 时由 `main.tsx` 启动；worker 与 `defaultMockWorld` 共享同一份运行态。
 * 注意：本文件依赖 `msw/browser`（引用 window），勿在 node 测试中导入；测试用 `msw/node` 的 server。
 */

const worker = setupWorker(...createMockHandlers(defaultMockWorld))

export function shouldStartMockWorker(useMock: boolean): boolean {
  return useMock
}

export async function startMockWorker(useMock: boolean): Promise<void> {
  if (!shouldStartMockWorker(useMock)) return
  await worker.start()
}
