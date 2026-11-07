import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CopyButton } from './CopyButton'
import { renderWithProviders } from '@/test/renderWithProviders'

function mockClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
  })
}

describe('CopyButton', () => {
  it('点击后复制文本并显示「已复制」', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    mockClipboard(writeText)

    renderWithProviders(<CopyButton text="link-001" />)

    const button = screen.getByRole('button', { name: '复制到剪贴板' })
    expect(button).toHaveTextContent('复制')

    fireEvent.click(button)
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('link-001'))
    expect(await screen.findByText('已复制')).toBeInTheDocument()

    // 再次点击覆盖「清空已有定时器」分支
    fireEvent.click(button)
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2))
  })

  it('复制失败时保持原文案并打印错误', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const writeText = vi.fn().mockRejectedValue(new Error('剪贴板不可用'))
    mockClipboard(writeText)

    renderWithProviders(<CopyButton text="link-002" />)

    fireEvent.click(screen.getByRole('button', { name: '复制到剪贴板' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('link-002'))
    expect(errorSpy).toHaveBeenCalled()
    expect(screen.getByRole('button', { name: '复制到剪贴板' })).toHaveTextContent('复制')
  })
})
