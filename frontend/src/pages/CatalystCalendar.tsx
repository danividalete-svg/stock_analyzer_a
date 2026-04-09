import { useState, useMemo } from 'react'
import { fetchCatalysts, type CatalystEvent } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import StaleDataBanner from '../components/StaleDataBanner'
import { Card } from '@/components/ui/card'
import { ChevronDown, ChevronRight } from 'lucide-react'

// ─── Config ───────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG = {
  MACRO:          { label: 'Macro', color: '#6366f1', bg: 'bg-indigo-500/15',  border: 'border-indigo-500/30',  text: 'text-indigo-400',  icon: '📊' },
  EARNINGS:       { label: 'Earnings', color: '#10b981', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: '📈' },
  FDA:            { label: 'FDA', color: '#f97316', bg: 'bg-orange-500/15', border: 'border-orange-500/30', text: 'text-orange-400', icon: '💊' },
  OPTIONS_EXPIRY: { label: 'OpEx', color: '#a855f7', bg: 'bg-purple-500/15',  border: 'border-purple-500/30',  text: 'text-purple-400',  icon: '⏰' },
  DIVIDEND:       { label: 'Dividendo', color: '#f59e0b', bg: 'bg-amber-500/15',  border: 'border-amber-500/30',  text: 'text-amber-400',  icon: '💰' },
} as const

const DIRECTION_CONFIG = {
  BULLISH:  { label: '↑ Alcista',  cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  BEARISH:  { label: '↓ Bajista',  cls: 'text-red-400 bg-red-500/10 border-red-500/30' },
  VOLATILE: { label: '↕ Volátil',  cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  UNKNOWN:  { label: '? Desconocido', cls: 'text-muted-foreground bg-muted/10 border-border/30' },
}

const IMPACT_CONFIG = {
  HIGH:   'bg-red-500/15 text-red-400 border-red-500/30',
  MEDIUM: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  LOW:    'bg-muted/15 text-muted-foreground border-border/30',
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function daysLabel(days: number): string {
  if (days === 0) return 'Hoy'
  if (days === 1) return 'Mañana'
  if (days <= 7) return `en ${days}d`
  if (days <= 30) return `en ${Math.round(days / 7)}sem`
  return `en ${Math.round(days / 30)}m`
}

function groupByWeek(events: CatalystEvent[]): Array<{ weekLabel: string; events: CatalystEvent[] }> {
  const groups: Record<string, CatalystEvent[]> = {}
  for (const e of events) {
    const d = new Date(e.date + 'T00:00:00')
    const days = e.days_away
    let key: string
    if (days <= 7) key = 'Esta semana'
    else if (days <= 14) key = 'Próxima semana'
    else {
      const month = d.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
      key = month.charAt(0).toUpperCase() + month.slice(1)
    }
    if (!groups[key]) groups[key] = []
    groups[key].push(e)
  }
  return Object.entries(groups).map(([weekLabel, events]) => ({ weekLabel, events }))
}

// ─── Earnings History Pill ────────────────────────────────────────────────────

function EarningsHistoryBar({ history }: { history: NonNullable<CatalystEvent['earnings_history']> }) {
  const { beat_rate, avg_surprise_pct, last_quarters } = history
  const color = beat_rate >= 75 ? 'text-emerald-400' : beat_rate >= 50 ? 'text-amber-400' : 'text-red-400'
  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-center gap-3 text-xs">
        <span className={`font-bold ${color}`}>Bate {beat_rate.toFixed(0)}%</span>
        <span className="text-muted-foreground">
          Sorpresa media: <span className={avg_surprise_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            {avg_surprise_pct >= 0 ? '+' : ''}{avg_surprise_pct.toFixed(1)}%
          </span>
        </span>
      </div>
      <div className="flex gap-1">
        {last_quarters.map((q, i) => (
          <div key={i} title={`${q.date}: est ${q.eps_est} vs act ${q.eps_act} (${q.surprise_pct > 0 ? '+' : ''}${q.surprise_pct.toFixed(1)}%)`}
            className={`h-2 w-6 rounded-sm ${q.beat ? 'bg-emerald-500' : 'bg-red-500'}`} />
        ))}
        <span className="text-[0.6rem] text-muted-foreground/50 ml-1 self-end">últimos {last_quarters.length}Q</span>
      </div>
    </div>
  )
}

// ─── Single Event Card ────────────────────────────────────────────────────────

function EventCard({ event }: { event: CatalystEvent }) {
  const [expanded, setExpanded] = useState(false)
  const catCfg = CATEGORY_CONFIG[event.category] ?? CATEGORY_CONFIG.MACRO
  const dirCfg = DIRECTION_CONFIG[event.direction_bias] ?? DIRECTION_CONFIG.UNKNOWN
  const impactCls = IMPACT_CONFIG[event.impact] ?? IMPACT_CONFIG.LOW
  const hasDetail = (event.earnings_history?.last_quarters?.length ?? 0) > 0
    || (event.affected_tickers?.length ?? 0) > 1
    || event.bullish_sectors?.length > 0
    || event.bearish_sectors?.length > 0

  return (
    <div className={`rounded-xl border ${catCfg.border} bg-card/30 backdrop-blur-sm transition-all`}>
      {/* Main row */}
      <div
        className={`flex items-start gap-3 px-4 py-3 ${hasDetail ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetail && setExpanded(v => !v)}
      >
        {/* Date badge */}
        <div className="shrink-0 text-center min-w-[42px]">
          <div className="text-[0.6rem] font-bold uppercase text-muted-foreground/50">
            {new Date(event.date + 'T00:00:00').toLocaleDateString('es-ES', { month: 'short' })}
          </div>
          <div className="text-lg font-extrabold leading-none text-foreground tabular-nums">
            {new Date(event.date + 'T00:00:00').getDate()}
          </div>
          <div className={`text-[0.58rem] font-bold mt-0.5 ${event.days_away <= 3 ? 'text-red-400' : event.days_away <= 7 ? 'text-amber-400' : 'text-muted-foreground/50'}`}>
            {daysLabel(event.days_away)}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`text-[0.65rem] font-bold px-1.5 py-0.5 rounded border ${catCfg.bg} ${catCfg.border} ${catCfg.text}`}>
              {catCfg.icon} {catCfg.label}
            </span>
            <span className={`text-[0.62rem] font-medium px-1.5 py-0.5 rounded border ${impactCls}`}>
              {event.impact}
            </span>
            <span className={`text-[0.62rem] font-medium px-1.5 py-0.5 rounded border ${dirCfg.cls}`}>
              {dirCfg.label}
            </span>
            {event.avg_move_pct != null && event.avg_move_pct > 0 && (
              <span className="text-[0.6rem] text-muted-foreground/50">
                ±{event.avg_move_pct.toFixed(1)}% histórico
              </span>
            )}
          </div>
          <div className="text-sm font-semibold text-foreground truncate">{event.title}</div>
          <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{event.description}</div>
        </div>

        {/* Right side: ticker chip + expand */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          {event.ticker && (
            <span className="font-mono text-xs font-bold text-foreground/80 bg-muted/20 px-2 py-0.5 rounded border border-border/30">
              {event.ticker}
            </span>
          )}
          {hasDetail && (
            <span className="text-muted-foreground/40 mt-1">
              {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </span>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-border/20 mt-1 space-y-3">
          {/* Earnings history */}
          {event.earnings_history && event.earnings_history.last_quarters?.length > 0 && (
            <div>
              <div className="text-[0.6rem] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1">Historial de sorpresas</div>
              <EarningsHistoryBar history={event.earnings_history} />
            </div>
          )}

          {/* Affected tickers */}
          {event.affected_tickers?.length > 1 && (
            <div>
              <div className="text-[0.6rem] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1.5">Tickers afectados</div>
              <div className="flex flex-wrap gap-1">
                {event.affected_tickers.map(t => (
                  <span key={t} className="font-mono text-xs bg-muted/20 border border-border/30 px-1.5 py-0.5 rounded">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Sector impact */}
          {(event.bullish_sectors?.length > 0 || event.bearish_sectors?.length > 0) && (
            <div className="flex gap-4">
              {event.bullish_sectors?.length > 0 && (
                <div>
                  <div className="text-[0.6rem] font-bold uppercase tracking-wider text-emerald-400/50 mb-1">Sectores alcistas</div>
                  <div className="flex flex-wrap gap-1">
                    {event.bullish_sectors.map(s => (
                      <span key={s} className="text-[0.65rem] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {event.bearish_sectors?.length > 0 && (
                <div>
                  <div className="text-[0.6rem] font-bold uppercase tracking-wider text-red-400/50 mb-1">Sectores bajistas</div>
                  <div className="flex flex-wrap gap-1">
                    {event.bearish_sectors.map(s => (
                      <span key={s} className="text-[0.65rem] font-mono text-red-400 bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded">{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Price + market cap for earnings/FDA */}
          {event.current_price && (
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Precio: <strong className="text-foreground">${event.current_price.toFixed(2)}</strong></span>
              {event.eps_estimate && (
                <span>EPS est: <strong className="text-foreground">${event.eps_estimate.toFixed(2)}</strong></span>
              )}
              {event.market_cap && (
                <span>Mcap: <strong className="text-foreground">{event.market_cap >= 1e12 ? `$${(event.market_cap/1e12).toFixed(1)}T` : `$${(event.market_cap/1e9).toFixed(0)}B`}</strong></span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CatalystCalendar() {
  const { data, loading, error } = useApi(() => fetchCatalysts(), [])
  const [filterCategory, setFilterCategory] = useState<string>('ALL')
  const [filterImpact, setFilterImpact] = useState<string>('ALL')

  const events = data?.events ?? []
  const byCategory = data?.by_category ?? {}

  const filtered = useMemo(() => events.filter(e => {
    if (filterCategory !== 'ALL' && e.category !== filterCategory) return false
    if (filterImpact !== 'ALL' && e.impact !== filterImpact) return false
    return true
  }), [events, filterCategory, filterImpact])

  const grouped = useMemo(() => groupByWeek(filtered), [filtered])

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const totalEvents = events.length
  const highImpact = events.filter(e => e.impact === 'HIGH').length
  const thisWeek = events.filter(e => e.days_away <= 7).length
  const earningsCount = byCategory['EARNINGS'] ?? 0

  return (
    <>
      <StaleDataBanner module="catalysts" />
      <PageHeader
        title="Catalyst Calendar"
        subtitle={`Próximos ${data?.horizon_days ?? 90} días · Earnings, Macro, FDA, OpEx y Dividendos`}
      />

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total eventos', value: totalEvents, sub: `${data?.horizon_days ?? 90}d horizonte`, color: '' },
          { label: 'Esta semana', value: thisWeek, sub: 'próximos 7 días', color: thisWeek > 5 ? 'text-red-400' : 'text-amber-400' },
          { label: 'Alto impacto', value: highImpact, sub: 'FOMC, earnings clave', color: 'text-red-400' },
          { label: 'Earnings', value: earningsCount, sub: 'resultados próximos', color: 'text-emerald-400' },
        ].map(({ label, value, sub, color }) => (
          <Card key={label} className="glass glow-border p-5">
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {/* Filter bar */}
      <Card className="glass px-4 py-3 mb-4">
        <div className="flex flex-wrap gap-x-4 gap-y-2 items-center">
          <div className="flex items-center gap-1">
            <span className="filter-label mr-0.5">Tipo</span>
            <button onClick={() => setFilterCategory('ALL')} className={`filter-btn ${filterCategory === 'ALL' ? 'active' : ''}`}>Todos</button>
            {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
              <button key={key} onClick={() => setFilterCategory(key)} className={`filter-btn ${filterCategory === key ? 'active' : ''}`}>
                {cfg.icon} {cfg.label}
                {byCategory[key] ? <span className="ml-1 opacity-60">({byCategory[key]})</span> : null}
              </button>
            ))}
          </div>
          <div className="w-px h-4 bg-border/40 self-center" />
          <div className="flex items-center gap-1">
            <span className="filter-label mr-0.5">Impacto</span>
            {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map(v => (
              <button key={v} onClick={() => setFilterImpact(v)} className={`filter-btn ${filterImpact === v ? 'active' : ''}`}>{v === 'ALL' ? 'Todos' : v}</button>
            ))}
          </div>
          <span className="filter-label ml-auto !normal-case !tracking-normal">{filtered.length} eventos</span>
        </div>
      </Card>

      {/* No data state */}
      {events.length === 0 && (
        <EmptyState
          icon="📅"
          title="Sin datos de catalizadores"
          subtitle="Ejecuta python3 catalyst_scanner.py para generar el calendario"
        />
      )}

      {/* Timeline grouped by week */}
      <div className="space-y-6">
        {grouped.map(({ weekLabel, events: grpEvents }) => (
          <div key={weekLabel}>
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground/50">{weekLabel}</h3>
              <div className="flex-1 h-px bg-border/30" />
              <span className="text-[0.6rem] text-muted-foreground/40">{grpEvents.length} eventos</span>
            </div>
            <div className="space-y-2">
              {grpEvents.map(e => <EventCard key={e.id} event={e} />)}
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && events.length > 0 && (
        <EmptyState icon="🔍" title="Sin resultados" subtitle="Prueba a cambiar los filtros" />
      )}

      {data && (
        <p className="text-center text-[0.62rem] text-muted-foreground/30 mt-6">
          Generado {new Date(data.generated_at).toLocaleDateString('es-ES')} · Fuentes: BLS, Fed, yfinance, FDA.gov
        </p>
      )}
    </>
  )
}
