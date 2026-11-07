import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function ExperimentsPage() {
  const meta = pageMetaMap.experiments
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
