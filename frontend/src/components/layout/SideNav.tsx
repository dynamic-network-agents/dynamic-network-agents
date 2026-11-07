import { Menu } from 'antd'
import { useLocation, useNavigate } from 'react-router'
import { matchRoute, pageMeta } from '@/app/pageMeta'

/**
 * 侧边导航：菜单项由路由元信息生成，选中态由当前 pathname 匹配得出。
 */
export function SideNav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const selected = matchRoute(pathname)

  const items = pageMeta.map((item) => ({
    key: item.path,
    icon: item.icon,
    label: item.title,
  }))

  return (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={selected ? [selected.path] : []}
      items={items}
      onClick={({ key }) => navigate(key)}
    />
  )
}
