import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { server } from './server'

// jsdom 未实现 matchMedia / ResizeObserver，AntD v5 依赖它们，这里补齐（仅 jsdom 环境需要）。
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
  window.ResizeObserver = window.ResizeObserver || ResizeObserverMock
}

// 每个用例结束后卸载组件并恢复 spy，保证测试隔离、单个测试不依赖执行顺序。
afterEach(() => {
  if (typeof window !== 'undefined') {
    cleanup()
  }
  vi.restoreAllMocks()
})

// MSW server 生命周期（FE-007）：beforeAll 启动 / afterEach 重置 handler / afterAll 关闭，
// 全局统一接线，各测试文件无需再自行维护（见 server.ts）。
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
