import { Breadcrumb } from 'antd'
import { Link, useLocation } from 'react-router'
import { getPageMeta, matchRoute } from '@/app/pageMeta'

/**
 * 面包屑：由当前路由匹配结果生成，与菜单/页面标题共用同一份路由元信息。
 */
export function AppBreadcrumb() {
  const { pathname } = useLocation()
  const current = matchRoute(pathname)
  const home = getPageMeta('dashboard')

  if (!current || current.path === '/') {
    return <Breadcrumb items={[{ title: home?.title ?? '系统总览' }]} />
  }

  return (
    <Breadcrumb
      items={[{ title: <Link to="/">{home?.title ?? '系统总览'}</Link> }, { title: current.title }]}
    />
  )
}
