import { lazy } from 'react'
import PageTabs from '../components/PageTabs'

const MeanReversion = lazy(() => import('./MeanReversion'))
const Momentum      = lazy(() => import('./Momentum'))

export default function EntrySetups() {
  return (
    <PageTabs
      tabs={[
        { id: 'mean-reversion', icon: '↩', label: 'Mean Reversion', content: <MeanReversion /> },
        { id: 'momentum',       icon: '↑', label: 'Momentum VCP',   content: <Momentum /> },
      ]}
    />
  )
}
