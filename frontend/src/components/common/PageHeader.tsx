import { Typography } from 'antd'

export interface PageHeaderProps {
  title: string
  description?: string
}

/** 页面级标题壳：标题 + 可选副标题说明。 */
export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 4 }}>
        {title}
      </Typography.Title>
      {description && <Typography.Text type="secondary">{description}</Typography.Text>}
    </div>
  )
}
