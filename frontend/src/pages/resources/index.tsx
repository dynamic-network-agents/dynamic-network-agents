import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function ResourcesPage() {
  const meta = pageMetaMap.resources
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
