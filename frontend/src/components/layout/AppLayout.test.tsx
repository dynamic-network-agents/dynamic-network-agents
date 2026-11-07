import { describe, expect, it } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { pageMeta } from '@/app/pageMeta'
import { renderWithRouter } from '@/test/renderWithRouter'

describe('AppLayout 全局布局与路由', () => {
  it.each(pageMeta.map((meta) => [meta.path, meta.title] as const))(
    '路由 %s 渲染「%s」页面',
    async (path, title) => {
      renderWithRouter({ initialEntries: [path] })
      expect(await screen.findByRole('heading', { level: 4, name: title })).toBeInTheDocument()
    },
  )

  it('渲染全部一级菜单项', async () => {
    renderWithRouter()
    const items = await screen.findAllByRole('menuitem')
    expect(items).toHaveLength(7)
    expect(items.some((el) => el.textContent?.includes('网络拓扑'))).toBe(true)
  })

  it('默认在根路径渲染系统总览', async () => {
    renderWithRouter()
    expect(await screen.findByRole('heading', { level: 4, name: '系统总览' })).toBeInTheDocument()
  })

  it('当前路由菜单高亮', async () => {
    renderWithRouter({ initialEntries: ['/topology'] })
    await screen.findByRole('heading', { level: 4, name: '网络拓扑' })
    const selected = document.querySelector('.ant-menu-item-selected')
    expect(selected).not.toBeNull()
    expect(selected).toHaveTextContent('网络拓扑')
  })

  it('点击菜单跳转到对应页面', async () => {
    renderWithRouter()
    await screen.findByRole('heading', { level: 4, name: '系统总览' })
    const target = screen
      .getAllByRole('menuitem')
      .find((el) => el.textContent?.includes('仿真控制台'))
    expect(target).toBeDefined()
    fireEvent.click(target!)
    expect(await screen.findByRole('heading', { level: 4, name: '仿真控制台' })).toBeInTheDocument()
  })

  it('侧边栏折叠切换', async () => {
    renderWithRouter()
    await screen.findByRole('heading', { level: 4, name: '系统总览' })
    expect(document.querySelector('.ant-layout-sider')).not.toHaveClass(
      'ant-layout-sider-collapsed',
    )
    fireEvent.click(document.querySelector('.ant-layout-sider-trigger')!)
    expect(document.querySelector('.ant-layout-sider')).toHaveClass('ant-layout-sider-collapsed')
  })

  it('未知路径进入 404', async () => {
    renderWithRouter({ initialEntries: ['/unknown'] })
    expect(await screen.findByText('页面不存在或已被移除')).toBeInTheDocument()
  })

  it('404 点击返回上一页回到上页', async () => {
    renderWithRouter({ initialEntries: ['/topology', '/unknown'] })
    await screen.findByText('页面不存在或已被移除')
    fireEvent.click(screen.getByRole('button', { name: '返回上一页' }))
    expect(await screen.findByRole('heading', { level: 4, name: '网络拓扑' })).toBeInTheDocument()
  })

  it('404 点击回到首页进入系统总览', async () => {
    renderWithRouter({ initialEntries: ['/unknown'] })
    await screen.findByText('页面不存在或已被移除')
    fireEvent.click(screen.getByRole('button', { name: '回到首页' }))
    expect(await screen.findByRole('heading', { level: 4, name: '系统总览' })).toBeInTheDocument()
  })
})
