import { useSearchParams } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import Loading from '../components/Loading'

const MacroRadar     = lazy(() => import('./MacroRadar'))
const MacroCountries = lazy(() => import('./MacroCountries'))

type Tab = 'radar' | 'countries'

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'radar',     icon: '📡', label: 'Macro Radar' },
  { id: 'countries', icon: '🌍', label: 'Países' },
]

export default function Macro() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = (searchParams.get('tab') as Tab) ?? 'radar'

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
        {tab === 'radar'     && <MacroRadar />}
        {tab === 'countries' && <MacroCountries />}
      </Suspense>
    </div>
  )
}
