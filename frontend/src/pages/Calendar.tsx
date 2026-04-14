import { lazy } from 'react'
import PageTabs from '../components/PageTabs'

const EarningsCalendar = lazy(() => import('./EarningsCalendar'))
const CatalystCalendar = lazy(() => import('./CatalystCalendar'))

export default function Calendar() {
  return (
    <PageTabs
      tabs={[
        { id: 'earnings',  icon: '📅', label: 'Earnings',      content: <EarningsCalendar /> },
        { id: 'catalysts', icon: '⚡', label: 'Catalizadores', content: <CatalystCalendar /> },
      ]}
    />
  )
}
