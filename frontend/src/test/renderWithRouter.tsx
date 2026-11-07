import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { RouteObject } from 'react-router'
import { render, type RenderOptions } from '@testing-library/react'
import { Providers } from '@/app/providers'
import { routeConfig } from '@/app/routes'

export interface RenderRouterOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: string[]
}

/**
 * 把 RouteObject 转成声明式 <Route> 树，供测试用 <Routes> 渲染。
 * 与生产共用的 routeConfig 保持单一来源；测试走声明式路由，
 * 避免数据路由在导航时 new Request() 触发 jsdom/undici 的 AbortSignal 类不一致。
 */
function toRouteElement(route: RouteObject, prefix = ''): ReactElement {
  const children = route.children?.map((child, index) => {
    const key = child.index ? `${prefix}index-${index}` : `${prefix}${child.path}-${index}`
    if (child.index) {
      return <Route key={key} index element={child.element} />
    }
    return <Route key={key} path={child.path} element={child.element} />
  })

  return (
    <Route path={route.path} element={route.element}>
      {children}
    </Route>
  )
}

/** 用内存路由渲染整个应用；页面懒加载，需配合 findBy* 等待。 */
export function renderWithRouter(options: RenderRouterOptions = {}) {
  const { initialEntries = ['/'], ...renderOptions } = options
  return render(
    <Providers>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>{toRouteElement(routeConfig)}</Routes>
      </MemoryRouter>
    </Providers>,
    renderOptions,
  )
}
