import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function TopologyPage() {
  const meta = pageMetaMap.topology
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
