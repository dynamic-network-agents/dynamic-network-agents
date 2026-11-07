/**
 * Mock 系统（FE-007）。
 *
 * 导出确定性随机、fixtures、运行态仓库、REST handlers、Mock 实时 Provider 与 Mock 开关工厂。
 * `browser.ts`（依赖 msw/browser）不在此 barrel 导出，由 `main.tsx` 直接引用，避免 node 测试误加载。
 */

export * from './random'
export * from './fixtures'
export * from './world'
export * from './handlers'
export * from './realtime'
export * from './provider'
