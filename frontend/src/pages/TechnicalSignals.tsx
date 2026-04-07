import { useState, useMemo } from 'react'
import { TrendingDown, ChevronDown, ChevronRight, Activity } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import TickerLogo from '../components/TickerLogo'
import { fetchTechnicalSignals, type TechnicalSignal, type TechnicalSummary } from '../api/client'
import { Card, CardContent } from '@/components/ui/card'

const SOURCE_LABELS: Record<string, string> = {
  portfolio: 'Cartera',
  value_us: 'Value 🇺🇸',
  value_eu: 'Value 🇪🇺',
  value_global: 'Value 🌍',
}

const STRENGTH_DOTS = (s: number) =>
  Array.from({ length: 3 }, (_, i) => (
    <span key={i} className={`inline-block w-1.5 h-1.5 rounded-full ${i < s ? 'bg-current' : 'bg-current/20'}`} />
  ))

function biasBadgeCls(bias: string): string {
  if (bias === 'BULLISH') return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
  if (bias === 'BEARISH') return 'bg-red-500/15 text-red-400 border-red-500/30'
  return 'bg-muted/40 text-muted-foreground border-border/40'
}
function biasLabel(bias: string): string {
  if (bias === 'BULLISH') return 'ALCISTA'
  if (bias === 'BEARISH') return 'BAJISTA'
  return 'NEUTRO'
}

function BiasBadge({ bias }: Readonly<{ bias: string }>) {
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${biasBadgeCls(bias)}`}>{biasLabel(bias)}</span>
}

function directionPillCls(dir: string): string {
  if (dir === 'BULLISH') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
  if (dir === 'BEARISH') return 'bg-red-500/10 text-red-400 border-red-500/25'
  return 'bg-muted/30 text-muted-foreground border-border/30'
}
function directionArrow(dir: string): string {
  if (dir === 'BULLISH') return '▲'
  if (dir === 'BEARISH') return '▼'
  return '—'
}

function DirectionPill({ dir, tf }: Readonly<{ dir: string; tf: string }>) {
  const tfLabel = tf === 'WEEKLY' ? 'W' : 'D'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${directionPillCls(dir)}`}>
      {directionArrow(dir)} {tfLabel}
    </span>
  )
}

function signalStrengthCls(direction: string): string {
  if (direction === 'BULLISH') return 'text-emerald-400'
  if (direction === 'BEARISH') return 'text-red-400'
  return 'text-muted-foreground'
}
function daysAgoLabel(days: number): string {
  if (days === 0) return 'hoy'
  if (days === 1) return 'ayer'
  return `${days}d`
}

function SignalRow({ sig }: Readonly<{ sig: TechnicalSignal }>) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-border/20 last:border-0">
      <DirectionPill dir={sig.direction} tf={sig.timeframe} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">{sig.signal_name}</span>
          <span className={`flex gap-0.5 ${signalStrengthCls(sig.direction)}`}>
            {STRENGTH_DOTS(sig.strength)}
          </span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{sig.description}</p>
      </div>
      <span className="text-xs text-muted-foreground/60 whitespace-nowrap shrink-0">
        {daysAgoLabel(sig.days_ago)}
      </span>
    </div>
  )
}

const sigSortFn = (a: TechnicalSignal, b: TechnicalSignal) =>
  a.days_ago !== b.days_ago ? a.days_ago - b.days_ago : b.strength - a.strength

function TickerCard({ row, signals }: Readonly<{ row: TechnicalSummary; signals: TechnicalSignal[] }>) {
  const [open, setOpen] = useState(false)

  const dailySignals = [...signals.filter((s: TechnicalSignal) => s.timeframe === 'DAILY')].sort(sigSortFn)
  const weeklySignals = [...signals.filter((s: TechnicalSignal) => s.timeframe === 'WEEKLY')].sort(sigSortFn)
  const sortedAll = [...signals].sort(sigSortFn)

  const toggle = () => setOpen(o => !o)

  return (
    <Card className="bg-card/40 border-border/30 hover:border-border/60 transition-colors">
      <CardContent className="p-4">
        {/* Header row */}
        <button
          type="button"
          className="flex items-center gap-3 w-full text-left active:scale-[0.98] transition-transform"
          onClick={toggle}
        >
          <TickerLogo ticker={row.ticker} size="sm" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-base text-foreground">{row.ticker}</span>
              <BiasBadge bias={row.bias} />
              <span className="text-xs text-muted-foreground/60 hidden sm:block truncate max-w-[140px]">{row.company_name}</span>
            </div>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-emerald-400 font-medium">+{row.bullish_count} alcistas</span>
              <span className="text-xs text-red-400 font-medium">−{row.bearish_count} bajistas</span>
              {row.sector && <span className="text-xs text-muted-foreground/50">{row.sector}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs px-2 py-0.5 rounded bg-muted/30 text-muted-foreground">
              {SOURCE_LABELS[row.source] ?? row.source}
            </span>
            {open
              ? <ChevronDown size={16} className="text-muted-foreground" />
              : <ChevronRight size={16} className="text-muted-foreground" />
            }
          </div>
        </button>

        {/* Top signals preview (collapsed) */}
        {!open && signals.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {sortedAll.slice(0, 4).map((s) => (
              <DirectionPill key={`${s.signal_name}-${s.timeframe}-${s.days_ago}`} dir={s.direction} tf={s.timeframe} />
            ))}
            {signals.length > 4 && (
              <span className="text-xs text-muted-foreground/50 self-center">+{signals.length - 4} más</span>
            )}
            {sortedAll[0] && (
              <span className="text-xs text-muted-foreground/70 ml-1 self-center">{sortedAll[0].signal_name}</span>
            )}
          </div>
        )}

        {/* Expanded detail */}
        {open && (
          <div className="mt-4 space-y-4">
            {dailySignals.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Diario ({dailySignals.length})
                </div>
                <div className="divide-y divide-border/20">
                  {dailySignals.map((s) => <SignalRow key={`${s.signal_name}-${s.days_ago}`} sig={s} />)}
                </div>
              </div>
            )}
            {weeklySignals.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Semanal ({weeklySignals.length})
                </div>
                <div className="divide-y divide-border/20">
                  {weeklySignals.map((s) => <SignalRow key={`${s.signal_name}-${s.days_ago}`} sig={s} />)}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function TechnicalSignals() {
  const { data, loading, error } = useApi(() => fetchTechnicalSignals().then(d => ({ data: d })), [])
  const [showBearish, setShowBearish] = useState(false)

  const { signals = [], summary = [] } = (data as { signals: TechnicalSignal[]; summary: TechnicalSummary[] }) ?? {}

  // Señales accionables: BULLISH con ≥3 señales alcistas confirmadas, ordenadas por net_score
  const actionable = useMemo(() => summary
    .filter(r => r.bias === 'BULLISH' && r.bullish_count >= 3)
    .sort((a, b) => b.net_score - a.net_score)
  , [summary])

  // Alertas de cartera: posiciones con sesgo bajista
  const portfolioBearish = useMemo(() =>
    summary.filter(r => r.source === 'portfolio' && r.bias === 'BEARISH')
  , [summary])

  // Cortos técnicos: BEARISH con ≥3 señales bajistas
  const bearishSetups = useMemo(() => summary
    .filter(r => r.bias === 'BEARISH' && r.bearish_count >= 3)
    .sort((a, b) => b.net_score - a.net_score)
    .slice(0, 10)
  , [summary])

  const signalsMap = useMemo(() => {
    const map = new Map<string, TechnicalSignal[]>()
    for (const s of signals) {
      const arr = map.get(s.ticker)
      if (arr) arr.push(s)
      else map.set(s.ticker, [s])
    }
    return map
  }, [signals])

  const generatedAt = summary[0]?.generated_at ?? ''

  if (loading) return <Loading />
  if (error) return (
    <ErrorState message={
      error.includes('not available')
        ? 'Los datos técnicos se generan una vez al día. Disponibles tras el próximo ciclo de análisis.'
        : error
    } />
  )

  const displayed = showBearish ? bearishSetups : actionable

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Header */}
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight gradient-title mb-1 flex items-center gap-2">
            <Activity size={20} className="text-primary" />
            Señales Técnicas
          </h1>
          <p className="text-sm text-muted-foreground">
            Entradas con ≥3 señales alcistas confirmadas · {actionable.length} setups hoy
            {generatedAt && <span className="ml-2 text-muted-foreground/40">· {generatedAt}</span>}
          </p>
        </div>
        <div className="flex gap-2 shrink-0 mt-1">
          <button onClick={() => setShowBearish(false)} className={`filter-btn ${!showBearish ? 'active' : ''}`}>
            ▲ Alcistas ({actionable.length})
          </button>
          <button onClick={() => setShowBearish(true)} className={`filter-btn ${showBearish ? 'active-red' : ''}`}>
            ▼ Bajistas ({bearishSetups.length})
          </button>
        </div>
      </div>

      {/* Alerta posiciones en cartera */}
      {portfolioBearish.length > 0 && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/25 text-sm">
          <TrendingDown size={16} className="text-red-400 shrink-0 mt-0.5" />
          <span className="text-red-300">
            <strong>{portfolioBearish.length} posición{portfolioBearish.length > 1 ? 'es' : ''} en cartera</strong> con sesgo bajista —{' '}
            {portfolioBearish.map(r => r.ticker).join(', ')}
          </span>
        </div>
      )}

      {/* Cards */}
      {displayed.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          No hay setups {showBearish ? 'bajistas' : 'alcistas'} con ≥3 señales confirmadas hoy.
        </div>
      ) : (
        <div className="space-y-2.5 animate-fade-in-up">
          {displayed.map(row => {
            const rowSignals = signalsMap.get(row.ticker) ?? []
            return <TickerCard key={row.ticker} row={row} signals={rowSignals} />
          })}
        </div>
      )}

      {/* Footer: cuántos más hay */}
      {!showBearish && summary.filter(r => r.bias === 'BULLISH').length > actionable.length && (
        <p className="text-center text-xs text-muted-foreground/40 pt-2">
          {summary.filter(r => r.bias === 'BULLISH').length - actionable.length} tickers alcistas adicionales con &lt;3 señales — no mostrados
        </p>
      )}
    </div>
  )
}
