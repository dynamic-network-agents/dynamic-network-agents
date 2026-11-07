import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function AgentsPage() {
  const meta = pageMetaMap.agents
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
