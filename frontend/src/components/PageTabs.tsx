import { useSearchParams } from 'react-router-dom'
import { Suspense, type ReactNode } from 'react'
import Loading from './Loading'

export interface PageTab {
  id: string
  icon: string
  label: string
  content: ReactNode
}

interface Props {
  tabs: PageTab[]
  defaultTab?: string
  paramKey?: string
}

export default function PageTabs({ tabs, defaultTab, paramKey = 'tab' }: Readonly<Props>) {
  const [searchParams, setSearchParams] = useSearchParams()
  const activeId = searchParams.get(paramKey) ?? defaultTab ?? tabs[0]?.id

  const setTab = (id: string) => setSearchParams({ [paramKey]: id }, { replace: true })
  const active = tabs.find(t => t.id === activeId) ?? tabs[0]

  return (
    <div>
      <div className="flex gap-1 mb-5 p-1 rounded-xl bg-white/5 border border-border/30 w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeId === tab.id
                ? 'bg-primary/15 text-primary border border-primary/30 shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
            }`}
          >
            <span className="text-base leading-none">{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      <Suspense fallback={<Loading />}>
        {active?.content}
      </Suspense>
    </div>
  )
}
