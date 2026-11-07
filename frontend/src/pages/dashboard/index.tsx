import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function DashboardPage() {
  const meta = pageMetaMap.dashboard
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
