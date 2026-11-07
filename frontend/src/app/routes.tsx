import { lazy } from 'react'
import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router'
import { AppLayout } from '@/components/layout/AppLayout'
import { pageMeta } from './pageMeta'

const DashboardPage = lazy(() => import('@/pages/dashboard'))
const TopologyPage = lazy(() => import('@/pages/topology'))
const ScenarioPage = lazy(() => import('@/pages/scenario'))
const SimulationPage = lazy(() => import('@/pages/simulation'))
const AgentsPage = lazy(() => import('@/pages/agents'))
const ResourcesPage = lazy(() => import('@/pages/resources'))
const ExperimentsPage = lazy(() => import('@/pages/experiments'))
const NotFoundPage = lazy(() => import('@/pages/not-found'))

const pageElements: Record<string, ReactNode> = {
  dashboard: <DashboardPage />,
  topology: <TopologyPage />,
  scenario: <ScenarioPage />,
  simulation: <SimulationPage />,
  agents: <AgentsPage />,
  resources: <ResourcesPage />,
  experiments: <ExperimentsPage />,
}

/**
 * 全量路由配置，生产（createBrowserRouter）与测试（createMemoryRouter）共用。
 * 布局作为根路由，一级页面作为其子路由；未知路径落到 404。
 */
export const routeConfig: RouteObject = {
  path: '/',
  element: <AppLayout />,
  children: [
    ...pageMeta.map((item) => {
      const element = pageElements[item.key]
      return item.path === '/' ? { index: true, element } : { path: item.path.slice(1), element }
    }),
    { path: '*', element: <NotFoundPage /> },
  ],
}
