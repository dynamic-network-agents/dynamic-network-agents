import { Card, Empty } from 'antd'
import { PageHeader } from './PageHeader'

export interface PagePlaceholderProps {
  title: string
  description?: string
}

/** 页面占位壳：FE-003 阶段各一级页面统一使用，后续任务替换为真实内容。 */
export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <Card style={{ marginTop: 16 }}>
        <Empty description={`${title} 页面建设中（FE-003 占位）`} />
      </Card>
    </div>
  )
}
