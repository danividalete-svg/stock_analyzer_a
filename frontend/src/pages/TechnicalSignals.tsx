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

function BiasBadge({ bias }: { bias: string }) {
  if (bias === 'BULLISH')
    return <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">ALCISTA</span>
  if (bias === 'BEARISH')
    return <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500/15 text-red-400 border border-red-500/30">BAJISTA</span>
  return <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-muted/40 text-muted-foreground border border-border/40">NEUTRO</span>
}

function DirectionPill({ dir, tf }: { dir: string; tf: string }) {
  const isBull = dir === 'BULLISH'
  const isBear = dir === 'BEARISH'
  const tfLabel = tf === 'WEEKLY' ? 'W' : 'D'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
      isBull ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25' :
      isBear ? 'bg-red-500/10 text-red-400 border-red-500/25' :
      'bg-muted/30 text-muted-foreground border-border/30'
    }`}>
      {isBull ? '▲' : isBear ? '▼' : '—'} {tfLabel}
    </span>
  )
}

function SignalRow({ sig }: { sig: TechnicalSignal }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-border/20 last:border-0">
      <DirectionPill dir={sig.direction} tf={sig.timeframe} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-foreground">{sig.signal_name}</span>
          <span className={`flex gap-0.5 ${sig.direction === 'BULLISH' ? 'text-emerald-400' : sig.direction === 'BEARISH' ? 'text-red-400' : 'text-muted-foreground'}`}>
            {STRENGTH_DOTS(sig.strength)}
          </span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{sig.description}</p>
      </div>
      <span className="text-xs text-muted-foreground/60 whitespace-nowrap shrink-0">
        {sig.days_ago === 0 ? 'hoy' : sig.days_ago === 1 ? 'ayer' : `${sig.days_ago}d`}
      </span>
    </div>
  )
}

function TickerCard({ row, signals }: { row: TechnicalSummary; signals: TechnicalSignal[] }) {
  const [open, setOpen] = useState(false)

  const dailySignals = signals.filter(s => s.timeframe === 'DAILY')
  const weeklySignals = signals.filter(s => s.timeframe === 'WEEKLY')
  const sortedAll = [...signals].sort((a, b) => {
    if (a.days_ago !== b.days_ago) return a.days_ago - b.days_ago
    return b.strength - a.strength
  })

  return (
    <Card className="bg-card/40 border-border/30 hover:border-border/60 transition-colors">
      <CardContent className="p-4">
        {/* Header row */}
        <div
          className="flex items-center gap-3 cursor-pointer"
          onClick={() => setOpen(o => !o)}
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
        </div>

        {/* Top signals preview (collapsed) */}
        {!open && signals.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {sortedAll.slice(0, 4).map((s, i) => (
              <DirectionPill key={i} dir={s.direction} tf={s.timeframe} />
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
                  {dailySignals
                    .sort((a, b) => a.days_ago - b.days_ago || b.strength - a.strength)
                    .map((s, i) => <SignalRow key={i} sig={s} />)}
                </div>
              </div>
            )}
            {weeklySignals.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Semanal ({weeklySignals.length})
                </div>
                <div className="divide-y divide-border/20">
                  {weeklySignals
                    .sort((a, b) => a.days_ago - b.days_ago || b.strength - a.strength)
                    .map((s, i) => <SignalRow key={i} sig={s} />)}
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

  const [biasFilter, setBiasFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'>('ALL')
  const [sourceFilter, setSourceFilter] = useState<string>('ALL')
  const [tfFilter, setTfFilter] = useState<'ALL' | 'DAILY' | 'WEEKLY'>('ALL')
  const [strengthFilter, setStrengthFilter] = useState<number>(1)

  // All hooks must be called unconditionally — before any early returns
  const { signals = [], summary = [] } = (data as { signals: TechnicalSignal[]; summary: TechnicalSummary[] }) ?? {}

  const sources = ['ALL', ...Array.from(new Set(summary.map(r => r.source))).filter(Boolean)]

  const filteredSummary = useMemo(() => {
    return summary.filter(row => {
      if (biasFilter !== 'ALL' && row.bias !== biasFilter) return false
      if (sourceFilter !== 'ALL' && row.source !== sourceFilter) return false
      return true
    }).sort((a, b) => {
      if (a.bias === 'BULLISH' && b.bias !== 'BULLISH') return -1
      if (b.bias === 'BULLISH' && a.bias !== 'BULLISH') return 1
      return b.net_score - a.net_score
    })
  }, [summary, biasFilter, sourceFilter])

  const getSignals = (ticker: string) => {
    return signals.filter(s =>
      s.ticker === ticker &&
      (tfFilter === 'ALL' || s.timeframe === tfFilter) &&
      s.strength >= strengthFilter
    )
  }

  // Stats
  const bullishCount = summary.filter(r => r.bias === 'BULLISH').length
  const bearishCount = summary.filter(r => r.bias === 'BEARISH').length
  const neutralCount = summary.filter(r => r.bias === 'NEUTRAL').length
  const portfolioTickers = summary.filter(r => r.source === 'portfolio')
  const portfolioBullish = portfolioTickers.filter(r => r.bias === 'BULLISH').length
  const generatedAt = summary[0]?.generated_at ?? ''

  if (loading) return <Loading />
  if (error) return (
    <ErrorState message={
      error.includes('not available')
        ? 'Los datos técnicos se generan una vez al día. Estarán disponibles después del próximo ciclo de análisis.'
        : error
    } />
  )

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity size={20} className="text-primary" />
            <h1 className="text-2xl font-bold">Señales Técnicas</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Detección automática de patrones técnicos — cartera activa + oportunidades value
          </p>
          {generatedAt && (
            <p className="text-xs text-muted-foreground/50 mt-1">Actualizado: {generatedAt}</p>
          )}
        </div>

        {/* Stats summary */}
        <div className="flex gap-3 flex-wrap">
          <div className="glass-panel px-3 py-2 rounded-lg text-center">
            <div className="text-lg font-bold text-emerald-400">{bullishCount}</div>
            <div className="text-xs text-muted-foreground">Alcistas</div>
          </div>
          <div className="glass-panel px-3 py-2 rounded-lg text-center">
            <div className="text-lg font-bold text-red-400">{bearishCount}</div>
            <div className="text-xs text-muted-foreground">Bajistas</div>
          </div>
          <div className="glass-panel px-3 py-2 rounded-lg text-center">
            <div className="text-lg font-bold text-muted-foreground">{neutralCount}</div>
            <div className="text-xs text-muted-foreground">Neutros</div>
          </div>
          {portfolioTickers.length > 0 && (
            <div className="glass-panel px-3 py-2 rounded-lg text-center">
              <div className="text-lg font-bold text-primary">{portfolioBullish}/{portfolioTickers.length}</div>
              <div className="text-xs text-muted-foreground">Cartera ↑</div>
            </div>
          )}
        </div>
      </div>

      {/* Portfolio alert if any are bearish */}
      {portfolioTickers.some(r => r.bias === 'BEARISH') && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/25 text-sm">
          <TrendingDown size={16} className="text-red-400 shrink-0 mt-0.5" />
          <span className="text-red-300">
            <strong>{portfolioTickers.filter(r => r.bias === 'BEARISH').length} posición(es) de cartera</strong> muestran sesgo bajista técnico —{' '}
            {portfolioTickers.filter(r => r.bias === 'BEARISH').map(r => r.ticker).join(', ')}
          </span>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {/* Bias filter */}
        <div className="flex rounded-lg bg-muted/20 border border-border/30 p-1 gap-1">
          {(['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const).map(b => (
            <button
              key={b}
              onClick={() => setBiasFilter(b)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all border ${
                biasFilter === b
                  ? b === 'BULLISH' ? 'bg-background text-emerald-400 border-emerald-500/40 shadow-sm'
                    : b === 'BEARISH' ? 'bg-background text-red-400 border-red-500/40 shadow-sm'
                    : 'bg-background text-foreground border-border/40 shadow-sm'
                  : 'text-muted-foreground hover:text-foreground border-transparent'
              }`}
            >
              {b === 'ALL' ? 'Todos' : b === 'BULLISH' ? '▲ Alcistas' : b === 'BEARISH' ? '▼ Bajistas' : '— Neutros'}
            </button>
          ))}
        </div>

        {/* Source filter */}
        <div className="flex rounded-lg bg-muted/20 border border-border/30 p-1 gap-1">
          {sources.map(s => (
            <button
              key={s}
              onClick={() => setSourceFilter(s)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all border ${
                sourceFilter === s
                  ? 'bg-background text-foreground border-border/40 shadow-sm'
                  : 'text-muted-foreground hover:text-foreground border-transparent'
              }`}
            >
              {s === 'ALL' ? 'Todas las fuentes' : SOURCE_LABELS[s] ?? s}
            </button>
          ))}
        </div>

        {/* Timeframe filter */}
        <div className="flex rounded-lg bg-muted/20 border border-border/30 p-1 gap-1">
          {(['ALL', 'DAILY', 'WEEKLY'] as const).map(tf => (
            <button
              key={tf}
              onClick={() => setTfFilter(tf)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all border ${
                tfFilter === tf
                  ? 'bg-background text-foreground border-border/40 shadow-sm'
                  : 'text-muted-foreground hover:text-foreground border-transparent'
              }`}
            >
              {tf === 'ALL' ? 'D+W' : tf === 'DAILY' ? 'Diario' : 'Semanal'}
            </button>
          ))}
        </div>

        {/* Min strength filter */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/20 border border-border/30">
          <span className="text-xs text-muted-foreground">Fuerza mín:</span>
          {[1, 2, 3].map(s => (
            <button
              key={s}
              onClick={() => setStrengthFilter(s)}
              className={`w-5 h-5 rounded-full text-xs font-bold transition-all ${
                strengthFilter === s ? 'bg-primary text-primary-foreground' : 'bg-muted/40 text-muted-foreground hover:bg-muted/60'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Results count */}
      <div className="text-sm text-muted-foreground">
        Mostrando <strong className="text-foreground">{filteredSummary.length}</strong> tickers
        {biasFilter !== 'ALL' && ` · ${biasFilter === 'BULLISH' ? 'alcistas' : biasFilter === 'BEARISH' ? 'bajistas' : 'neutros'}`}
        {sourceFilter !== 'ALL' && ` · ${SOURCE_LABELS[sourceFilter] ?? sourceFilter}`}
      </div>

      {/* Cards */}
      {filteredSummary.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No hay tickers con los filtros seleccionados.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredSummary.map(row => {
            const rowSignals = getSignals(row.ticker)
            if (rowSignals.length === 0 && strengthFilter > 1) return null
            return (
              <TickerCard key={row.ticker} row={row} signals={rowSignals} />
            )
          })}
        </div>
      )}
    </div>
  )
}
