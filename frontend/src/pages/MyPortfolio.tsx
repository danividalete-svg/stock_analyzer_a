import { lazy } from 'react'
import PageTabs from '../components/PageTabs'

const PersonalPortfolio = lazy(() => import('./PersonalPortfolio'))
const Portfolio         = lazy(() => import('./Portfolio'))

export default function MyPortfolio() {
  return (
    <PageTabs
      tabs={[
        { id: 'positions', icon: '💼', label: 'Mis Posiciones', content: <PersonalPortfolio /> },
        { id: 'signals',   icon: '📊', label: 'Signal Tracker', content: <Portfolio /> },
      ]}
    />
  )
}
