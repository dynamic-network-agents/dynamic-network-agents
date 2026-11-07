import { describe, expect, it } from 'vitest'
import { PageLoading } from './PageLoading'
import { renderWithProviders } from '@/test/renderWithProviders'

describe('PageLoading', () => {
  it('渲染加载指示器', () => {
    const { container } = renderWithProviders(<PageLoading />)
    expect(container.querySelector('.ant-spin')).toBeInTheDocument()
  })
})
