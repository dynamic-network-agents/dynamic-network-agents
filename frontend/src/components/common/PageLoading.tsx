import { Spin } from 'antd'

/** 页面级加载容器：懒加载页面的 Suspense fallback。 */
export function PageLoading() {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 240,
      }}
    >
      <Spin size="large" />
    </div>
  )
}
