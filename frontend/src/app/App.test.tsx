import { describe, expect, it } from 'vitest'
import { App } from './App'
import { renderWithProviders, screen } from '@/test/renderWithProviders'

describe('App', () => {
  it('挂载并渲染系统总览页面', async () => {
    renderWithProviders(<App />)
    expect(await screen.findByRole('heading', { level: 4, name: '系统总览' })).toBeInTheDocument()
  })
})
