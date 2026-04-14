import { useSearchParams } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import Loading from '../components/Loading'

const ValueUS    = lazy(() => import('./ValueUS'))
const ValueEU    = lazy(() => import('./ValueEU'))
const GlobalValue = lazy(() => import('./GlobalValue'))

type Region = 'us' | 'eu' | 'global'

const TABS: { id: Region; flag: string; label: string }[] = [
  { id: 'us',     flag: '🇺🇸', label: 'VALUE US' },
  { id: 'eu',     flag: '🇪🇺', label: 'VALUE EU' },
  { id: 'global', flag: '🌍',  label: 'VALUE Global' },
]

export default function Value() {
  const [searchParams, setSearchParams] = useSearchParams()
  const region = (searchParams.get('region') as Region) ?? 'us'

  const setRegion = (r: Region) => setSearchParams({ region: r }, { replace: true })

  return (
    <div>
      {/* Regional tab bar */}
      <div className="flex gap-1 mb-5 p-1 rounded-xl bg-white/5 border border-border/30 w-fit">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setRegion(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              region === tab.id
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
            }`}
          >
            <span className="text-base leading-none">{tab.flag}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Region content */}
      <Suspense fallback={<Loading />}>
        {region === 'us'     && <ValueUS />}
        {region === 'eu'     && <ValueEU />}
        {region === 'global' && <GlobalValue />}
      </Suspense>
    </div>
  )
}
