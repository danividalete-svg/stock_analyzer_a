import { useSearchParams } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import Loading from '../components/Loading'

const PersonalPortfolio = lazy(() => import('./PersonalPortfolio'))
const Portfolio         = lazy(() => import('./Portfolio'))

type Tab = 'positions' | 'signals'

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'positions', icon: '💼', label: 'Mis Posiciones' },
  { id: 'signals',   icon: '📊', label: 'Signal Tracker' },
]

export default function MyPortfolio() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = (searchParams.get('tab') as Tab) ?? 'positions'

  const setTab = (t: Tab) => setSearchParams({ tab: t }, { replace: true })

  return (
    <div>
      <div className="flex gap-1 mb-5 p-1 rounded-xl bg-white/5 border border-border/30 w-fit">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.id
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
            }`}
          >
            <span className="text-base leading-none">{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      <Suspense fallback={<Loading />}>
        {tab === 'positions' && <PersonalPortfolio />}
        {tab === 'signals'   && <Portfolio />}
      </Suspense>
    </div>
  )
}
