import type { ReactNode } from 'react'
import {
  ApartmentOutlined,
  DashboardOutlined,
  ExperimentOutlined,
  FundOutlined,
  PlayCircleOutlined,
  ProfileOutlined,
  RobotOutlined,
} from '@ant-design/icons'

/**
 * 一级路由元信息：菜单、面包屑、页面标题的唯一事实源。
 * FE-003 仅一级路由；后续子路由在此扩展（如 `/topology/:nodeId`）。
 */
export interface PageMeta {
  key: string
  path: string
  title: string
  description: string
  icon: ReactNode
}

export const pageMeta: PageMeta[] = [
  {
    key: 'dashboard',
    path: '/',
    title: '系统总览',
    description: '当前仿真、网络摘要、业务 QoS、Agent 状态、最近实验',
    icon: <DashboardOutlined />,
  },
  {
    key: 'topology',
    path: '/topology',
    title: '网络拓扑',
    description: '节点/链路图、链路详情、路由路径、邻居/拓扑/路由表',
    icon: <ApartmentOutlined />,
  },
  {
    key: 'scenario',
    path: '/scenario',
    title: '场景配置',
    description: '节点、链路、业务流、动态事件、场景模板',
    icon: <ProfileOutlined />,
  },
  {
    key: 'simulation',
    path: '/simulation',
    title: '仿真控制台',
    description: '开始/暂停/恢复/停止/单步、时间轴、事件注入',
    icon: <PlayCircleOutlined />,
  },
  {
    key: 'agents',
    path: '/agents',
    title: 'Agent 监控',
    description: 'Agent 状态、A2A 消息、任务链路、工具调用、策略记录',
    icon: <RobotOutlined />,
  },
  {
    key: 'resources',
    path: '/resources',
    title: '资源与 QoS',
    description: '带宽分配、链路质量、业务 QoS、资源抢占',
    icon: <FundOutlined />,
  },
  {
    key: 'experiments',
    path: '/experiments',
    title: '实验分析',
    description: '指标统计、对比实验、事件复盘、结果导出',
    icon: <ExperimentOutlined />,
  },
]

/** 按 key 直接取用（页面组件使用，保证非空）。 */
export const pageMetaMap: Record<string, PageMeta> = Object.fromEntries(
  pageMeta.map((item) => [item.key, item]),
)

export function getPageMeta(key: string): PageMeta | undefined {
  return pageMeta.find((item) => item.key === key)
}

/**
 * 按 pathname 匹配一级路由（用于菜单高亮与面包屑）。
 * 根路径 `/` 仅精确匹配，其余支持精确与子路径前缀匹配。
 * 当前仅一级路由，路径互不为前缀，故首个命中即正确；
 * 后续引入嵌套子路由时再升级为最长前缀匹配。
 */
export function matchRoute(pathname: string): PageMeta | undefined {
  return pageMeta.find((item) =>
    item.path === '/'
      ? pathname === '/'
      : pathname === item.path || pathname.startsWith(`${item.path}/`),
  )
}
