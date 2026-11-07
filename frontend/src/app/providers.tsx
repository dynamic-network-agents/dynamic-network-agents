import type { ReactNode } from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

/**
 * 全局 Provider 聚合点。
 * FE-003 引入 Ant Design，统一挂 ConfigProvider（中文语言包）；
 * 后续 Store（FE-006）、Query 等 Provider 在此按需叠加。
 */
export function Providers({ children }: { children: ReactNode }) {
  return <ConfigProvider locale={zhCN}>{children}</ConfigProvider>
}
