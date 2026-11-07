import { Suspense, useState } from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router'
import { AppBreadcrumb } from './AppBreadcrumb'
import { SideNav } from './SideNav'
import { TopBar } from './TopBar'
import { PageLoading } from '@/components/common/PageLoading'
import { getEnvConfig } from '@/config/env'
import styles from './AppLayout.module.css'

const { Sider, Header, Content } = Layout

/**
 * 主框架：深色侧边栏 + 顶部栏 + 面包屑 + 内容区。
 * 侧边栏可折叠；页面经 Suspense 懒加载，落地「页面级加载容器」。
 */
export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const { appTitle } = getEnvConfig()

  return (
    <Layout className={styles.layout}>
      <Sider
        className={styles.sider}
        theme="dark"
        width={220}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
      >
        <div className={styles.brand}>{collapsed ? 'DN' : appTitle}</div>
        <SideNav />
      </Sider>
      <Layout className={styles.body}>
        <Header className={styles.header}>
          <TopBar />
        </Header>
        <Content className={styles.content}>
          <AppBreadcrumb />
          <div className={styles.page}>
            <Suspense fallback={<PageLoading />}>
              <Outlet />
            </Suspense>
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
