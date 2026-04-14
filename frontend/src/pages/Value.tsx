import { lazy } from 'react'
import PageTabs from '../components/PageTabs'

const ValueUS     = lazy(() => import('./ValueUS'))
const ValueEU     = lazy(() => import('./ValueEU'))
const GlobalValue = lazy(() => import('./GlobalValue'))

export default function Value() {
  return (
    <PageTabs
      paramKey="region"
      defaultTab="us"
      tabs={[
        { id: 'us',     icon: '🇺🇸', label: 'VALUE US',     content: <ValueUS /> },
        { id: 'eu',     icon: '🇪🇺', label: 'VALUE EU',     content: <ValueEU /> },
        { id: 'global', icon: '🌍',  label: 'VALUE Global', content: <GlobalValue /> },
      ]}
    />
  )
}
