import { lazy } from 'react'
import PageTabs from '../components/PageTabs'

const MacroRadar     = lazy(() => import('./MacroRadar'))
const MacroCountries = lazy(() => import('./MacroCountries'))

export default function Macro() {
  return (
    <PageTabs
      tabs={[
        { id: 'radar',     icon: '📡', label: 'Radar',   content: <MacroRadar /> },
        { id: 'countries', icon: '🌍', label: 'Países',  content: <MacroCountries /> },
      ]}
    />
  )
}
