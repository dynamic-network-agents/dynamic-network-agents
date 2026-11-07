import { PagePlaceholder } from '@/components/common/PagePlaceholder'
import { pageMetaMap } from '@/app/pageMeta'

export default function SimulationPage() {
  const meta = pageMetaMap.simulation
  return <PagePlaceholder title={meta.title} description={meta.description} />
}
