import { useState } from 'react'
import api, { getCsvUrl } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Card, CardContent } from '@/components/ui/card'

interface HistorySnapshot {
  date: string
  files: string[]
}
interface HistoryIndex {
  updated: string
  snapshots: HistorySnapshot[]
}

const CSV_CATALOG = [
  {
    group: 'VALUE',
    items: [
      { key: 'value-us', label: 'Value US — Oportunidades', desc: 'Todos los tickers VALUE analizados (US)', file: 'value_opportunities.csv' },
      { key: 'value-us-full', label: 'Value US — Conviction Full', desc: 'Con conviction score, grado y razones (US)', file: 'value_conviction.csv' },
      { key: 'value-eu', label: 'Value EU — Oportunidades', desc: 'Blue chips europeos VALUE analizados', file: 'european_value_opportunities.csv' },
      { key: 'value-eu-full', label: 'Value EU — Conviction Full', desc: 'Con conviction score, FCF, dividendos (EU)', file: 'european_value_conviction.csv' },
    ],
  },
  {
    group: 'Señales',
    items: [
      { key: 'mean-reversion', label: 'Mean Reversion', desc: 'Oversold bounces y pullbacks detectados', file: 'mean_reversion_opportunities.csv' },
      { key: 'momentum', label: 'Momentum / VCP', desc: 'Setups VCP y Minervini detectados', file: 'momentum_opportunities.csv' },
      { key: 'options-flow', label: 'Options Flow', desc: 'Actividad de opciones inusual y whale', file: 'options_flow.csv' },
    ],
  },
  {
    group: 'Insiders',
    items: [
      { key: 'insiders', label: 'Recurring Insiders US', desc: '742+ tickers con compras internas recurrentes', file: 'recurring_insiders.csv' },
      { key: 'insiders-eu', label: 'Recurring Insiders EU', desc: 'Insiders europeos FTSE100/DAX40', file: 'eu_recurring_insiders.csv' },
    ],
  },
  {
    group: 'Fundamentales',
    items: [
      { key: 'fundamental', label: 'Fundamental Scores US', desc: 'FCF, dividendos, ROE, margen, cobertura intereses', file: 'fundamental_scores.csv' },
      { key: 'fundamental-eu', label: 'Fundamental Scores EU', desc: 'Métricas fundamentales blue chips europeos', file: 'european_fundamental_scores.csv' },
    ],
  },
]

function SnapshotRow({ snap, csvBase }: { snap: HistorySnapshot; csvBase: string }) {
  const [open, setOpen] = useState(false)

  const key_files: Record<string, string> = {
    'value_opportunities.csv': 'VALUE US',
    'european_value_opportunities.csv': 'VALUE EU',
    'european_value_conviction.csv': 'EU Conviction',
    'mean_reversion_opportunities.csv': 'Mean Rev',
    'recurring_insiders.csv': 'Insiders',
    'fundamental_scores.csv': 'Fundamentals',
    'momentum_opportunities.csv': 'Momentum',
    'options_flow.csv': 'Options',
  }

  return (
    <div className="border-b border-border/30 last:border-0">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-white/5 active:scale-[0.99] transition-all"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono font-bold text-primary">{snap.date}</span>
          <span className="text-[0.65rem] font-semibold text-muted-foreground/60 bg-muted/30 px-2 py-0.5 rounded">{snap.files.length} archivos</span>
        </div>
        <span className="text-muted-foreground text-xs">{open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="px-4 pb-3 flex flex-wrap gap-2">
          {snap.files.map(f => (
            <a
              key={f}
              href={`${csvBase}/history/${snap.date}/${f}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs px-2.5 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
            >
              ↓ {key_files[f] ?? f.replace('.csv', '')}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Datos() {
  const csvBase = (import.meta.env.VITE_CSV_BASE as string | undefined) || ''

  const { data: historyData } = useApi<HistoryIndex | null>(() =>
    api.get<HistoryIndex>(`${csvBase}/history/index.json`).catch(() => ({ data: null as unknown as HistoryIndex })),
    []
  )

  const snapshots: HistorySnapshot[] = historyData?.snapshots ?? []
  const historyUpdated = historyData?.updated ?? ''

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Datos & Historial</h2>
        <p className="text-sm text-muted-foreground">
          Descarga CSVs actualizados diariamente · Historial de hasta 45 días para backtesting
        </p>
      </div>

      {/* Current CSVs */}
      <div className="mb-8 animate-fade-in-up" style={{ animationDelay: '60ms' }}>
        <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">
          Datos Actuales
        </h3>
        <div className="space-y-6">
          {CSV_CATALOG.map((group, gi) => (
            <div key={group.group} className="animate-fade-in-up" style={{ animationDelay: `${(gi + 1) * 80}ms` }}>
              <div className="text-xs font-bold uppercase tracking-widest gradient-title mb-2 px-1">
                {group.group}
              </div>
              <Card className="glass">
                {group.items.map((item, i) => (
                  <div
                    key={item.key}
                    className={`flex items-center justify-between px-5 py-3 ${i < group.items.length - 1 ? 'border-b border-border/30' : ''}`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-foreground">{item.label}</div>
                      <div className="text-xs text-muted-foreground truncate">{item.desc}</div>
                    </div>
                    <div className="flex items-center gap-2 ml-4 shrink-0">
                      <span className="text-[0.65rem] text-muted-foreground/60 font-mono hidden sm:block">{item.file}</span>
                      <a
                        href={getCsvUrl(item.key)}
                        download={item.file}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs px-3 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary active:scale-[0.98] transition-all"
                      >
                        ↓ CSV
                      </a>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          ))}
        </div>
      </div>

      {/* Historical archive */}
      <div className="animate-fade-in-up" style={{ animationDelay: '400ms' }}>
        <div className="flex items-center gap-3 mb-4">
          <h3 className="text-sm font-bold uppercase tracking-widest gradient-title">
            Historial
          </h3>
          {historyUpdated && (
            <span className="text-[0.65rem] text-muted-foreground/60">
              último índice: {historyUpdated}
            </span>
          )}
          <span className="text-[0.65rem] text-muted-foreground/60">
            · Archivado diariamente · Máx. 45 días
          </span>
        </div>

        {snapshots.length > 0 ? (
          <Card className="glass">
            {snapshots.map(snap => (
              <SnapshotRow key={snap.date} snap={snap} csvBase={csvBase} />
            ))}
          </Card>
        ) : (
          <Card className="glass">
            <CardContent className="py-12 text-center">
              <div className="text-3xl mb-3 opacity-20">📂</div>
              <p className="text-sm text-muted-foreground">
                Sin historial disponible aún.
                {!csvBase && (
                  <span className="block text-xs mt-1 text-amber-400">
                    (Modo desarrollo — historial disponible en producción)
                  </span>
                )}
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
