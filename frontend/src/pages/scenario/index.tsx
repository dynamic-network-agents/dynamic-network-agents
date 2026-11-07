import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function ScenarioPage() {
  const meta = pageMetaMap.scenario
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
