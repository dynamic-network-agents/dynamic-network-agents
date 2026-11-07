import { Avatar, Badge, Space, Tag, Typography } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { getEnvConfig } from '@/config/env'

/**
 * 顶部栏：项目名称 + 静态占位（仿真状态、WS 连接、用户）。
 * 真实状态待 FE-006/007 接入 Store 与 WebSocket 后替换。
 */
export function TopBar() {
  const { appTitle, useMock } = getEnvConfig()

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        width: '100%',
      }}
    >
      <Typography.Title level={5} style={{ margin: 0 }}>
        {appTitle}
      </Typography.Title>
      <Space size="middle">
        {useMock && <Tag color="orange">Mock 模式</Tag>}
        <Tag>仿真状态：未开始</Tag>
        <Badge status="default" text="WS 未连接" />
        <Avatar size="small" icon={<UserOutlined />} />
      </Space>
    </div>
  )
}
