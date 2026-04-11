import { useMemo, useState } from 'react'
import { TrendingDown, ChevronDown, ChevronRight, Activity } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import TickerLogo from '../components/TickerLogo'
import { fetchTechnicalSignals, type TechnicalSignal, type TechnicalSummary } from '../api/client'
import { Card, CardContent } from '@/components/ui/card'
import StaleDataBanner from '../components/StaleDataBanner'

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

  const toggle = () => setOpen((o: boolean) => !o)

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

  const { signals = [], summary = [] } = (data as { signals: TechnicalSignal[]; summary: TechnicalSummary[] }) ?? {}

  // Portfolio positions — all, sorted bearish first
  const portfolioAll = useMemo(() => summary
    .filter(r => r.source === 'portfolio')
    .sort((a, b) => {
      if (a.bias === b.bias) return b.net_score - a.net_score
      return a.bias === 'BEARISH' ? -1 : 1
    })
  , [summary])

  // Entry opportunities: bullish non-portfolio setups with ≥3 confirmed signals, top 10
  const entryOpps = useMemo(() => summary
    .filter(r => r.source !== 'portfolio' && r.bias === 'BULLISH' && r.bullish_count >= 3)
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
  const bearishCount = portfolioAll.filter(r => r.bias === 'BEARISH').length

  if (loading) return <Loading />
  if (error) return (
    <ErrorState message={
      error.includes('not available')
        ? 'Los datos técnicos se generan una vez al día. Disponibles tras el próximo ciclo de análisis.'
        : error
    } />
  )

  return (
    <div className="space-y-6 max-w-4xl">
      <StaleDataBanner module="technical" />

      {/* Header */}
      <div className="mb-2 animate-fade-in-up">
        <h1 className="text-2xl font-extrabold tracking-tight gradient-title mb-1 flex items-center gap-2">
          <Activity size={20} className="text-primary" />
          Señales Técnicas
        </h1>
        <p className="text-sm text-muted-foreground">
          Estado técnico de tu cartera + mejores oportunidades de entrada
          {generatedAt && <span className="ml-2 text-muted-foreground/40">· {generatedAt}</span>}
        </p>
      </div>

      {/* ── Mi Cartera ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Mi Cartera</h2>
          {bearishCount > 0 && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 text-xs font-bold">
              <TrendingDown size={11} />
              {bearishCount} bajista{bearishCount > 1 ? 's' : ''}
            </span>
          )}
        </div>

        {portfolioAll.length === 0 ? (
          <div className="text-sm text-muted-foreground/50 py-6 text-center border border-border/20 rounded-lg">
            No hay posiciones en cartera con datos técnicos. Añade tickers en "Mi Cartera".
          </div>
        ) : (
          <div className="space-y-2">
            {portfolioAll.map(row => (
              <TickerCard key={row.ticker} row={row} signals={signalsMap.get(row.ticker) ?? []} />
            ))}
          </div>
        )}
      </div>

      {/* ── Oportunidades de Entrada ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-bold uppercase tracking-widest text-muted-foreground">Mejores Entradas</h2>
          <span className="text-xs text-muted-foreground/50">≥3 señales alcistas · top 10</span>
        </div>

        {entryOpps.length === 0 ? (
          <div className="text-sm text-muted-foreground/50 py-6 text-center border border-border/20 rounded-lg">
            Sin setups con ≥3 señales alcistas confirmadas ahora mismo.
          </div>
        ) : (
          <div className="space-y-2">
            {entryOpps.map(row => (
              <TickerCard key={row.ticker} row={row} signals={signalsMap.get(row.ticker) ?? []} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
