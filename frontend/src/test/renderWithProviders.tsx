import { render, type RenderOptions } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { Providers } from '@/app/providers'

/**
 * 统一测试渲染入口：用与生产一致的 Provider 包裹被测组件。
 * FE-003（Router）/ FE-006（Store）/ Query 等 Provider 就绪后，在此按需叠加，
 * 避免各测试自行维护 Provider 组合。
 */
function AllProviders({ children }: { children: ReactNode }) {
  return <Providers>{children}</Providers>
}

export function renderWithProviders(ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  return render(ui, { wrapper: AllProviders, ...options })
}

// 复用 Testing Library 的查询与交互 API，测试统一从此处导入。
export * from '@testing-library/react'
