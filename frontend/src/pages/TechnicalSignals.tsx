import { useState, useMemo, useCallback, useEffect } from 'react'
import { TrendingDown, ChevronDown, ChevronRight, Activity, Wallet } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
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

  const dailySignals = signals.filter(s => s.timeframe === 'DAILY').toSorted(sigSortFn)
  const weeklySignals = signals.filter(s => s.timeframe === 'WEEKLY').toSorted(sigSortFn)
  const sortedAll = signals.toSorted(sigSortFn)

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

function SignalStrengthDots({ strength }: Readonly<{ strength: number }>) {
  return (
    <span className="flex gap-0.5 text-emerald-400">
      {Array.from({ length: 3 }, (_, j) => (
        <span key={j} className={`inline-block w-1 h-1 rounded-full ${j < strength ? 'bg-emerald-400' : 'bg-emerald-400/20'}`} />
      ))}
    </span>
  )
}

type BiasFilter = 'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'

function biasBtnCls(b: BiasFilter, active: boolean): string {
  if (!active) return 'text-muted-foreground hover:text-foreground border-transparent'
  if (b === 'BULLISH') return 'bg-background text-emerald-400 border-emerald-500/40 shadow-sm'
  if (b === 'BEARISH') return 'bg-background text-red-400 border-red-500/40 shadow-sm'
  return 'bg-background text-foreground border-border/40 shadow-sm'
}

function biasBtnLabel(b: BiasFilter): string {
  if (b === 'BULLISH') return '▲ Alcistas'
  if (b === 'BEARISH') return '▼ Bajistas'
  if (b === 'NEUTRAL') return '— Neutros'
  return 'Todos'
}

function biasResultLabel(b: BiasFilter): string {
  if (b === 'BULLISH') return 'alcistas'
  if (b === 'BEARISH') return 'bajistas'
  if (b === 'NEUTRAL') return 'neutros'
  return ''
}

function tfLabel(tf: 'ALL' | 'DAILY' | 'WEEKLY'): string {
  if (tf === 'DAILY') return 'Diario'
  if (tf === 'WEEKLY') return 'Semanal'
  return 'D+W'
}

export default function TechnicalSignals() {
  const { data, loading, error } = useApi(() => fetchTechnicalSignals().then(d => ({ data: d })), [])
  const { isOwned, positions: myPositions } = usePersonalPortfolio()

  const [biasFilter, setBiasFilter] = useState<BiasFilter>('ALL')
  const [sourceFilter, setSourceFilter] = useState<string>('ALL')
  const [tfFilter, setTfFilter] = useState<'ALL' | 'DAILY' | 'WEEKLY'>('ALL')
  const [strengthFilter, setStrengthFilter] = useState<number>(1)
  const [onlyMyPortfolio, setOnlyMyPortfolio] = useState(false)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  // All hooks must be called unconditionally — before any early returns
  const { signals = [], summary = [] } = (data as { signals: TechnicalSignal[]; summary: TechnicalSummary[] }) ?? {}

  const sources = ['ALL', ...Array.from(new Set(summary.map(r => r.source))).filter(Boolean)]

  const filteredSummary = useMemo(() => {
    return summary.filter(row => {
      if (biasFilter !== 'ALL' && row.bias !== biasFilter) return false
      if (sourceFilter !== 'ALL' && row.source !== sourceFilter) return false
      if (onlyMyPortfolio && !isOwned(row.ticker)) return false
      return true
    }).sort((a, b) => {
      if (a.bias === 'BULLISH' && b.bias !== 'BULLISH') return -1
      if (b.bias === 'BULLISH' && a.bias !== 'BULLISH') return 1
      return b.net_score - a.net_score
    })
  }, [summary, biasFilter, sourceFilter, onlyMyPortfolio, isOwned])

  useEffect(() => { setPage(1) }, [biasFilter, sourceFilter, onlyMyPortfolio, tfFilter, strengthFilter])

  const totalPages = Math.ceil(filteredSummary.length / PAGE_SIZE)
  const pagedSummary = filteredSummary.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const goToPage = useCallback((p: number) => {
    setPage(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  // O(N) pre-build once per filter change — O(1) lookup per card
  const signalsMap = useMemo(() => {
    const map = new Map<string, TechnicalSignal[]>()
    for (const s of signals) {
      if (tfFilter !== 'ALL' && s.timeframe !== tfFilter) continue
      if (s.strength < strengthFilter) continue
      const arr = map.get(s.ticker)
      if (arr) arr.push(s)
      else map.set(s.ticker, [s])
    }
    return map
  }, [signals, tfFilter, strengthFilter])

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
            <h1 className="text-2xl font-bold gradient-title">Señales Técnicas</h1>
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

      {/* ── Entradas Destacadas ─────────────────────────────────────────── */}
      {(() => {
        const top = summary
          .filter(r => r.bias === 'BULLISH' && r.bullish_count >= 2)
          .sort((a, b) => b.net_score - a.net_score)
          .slice(0, 6)
        if (top.length === 0) return null
        return (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[0.6rem] font-bold uppercase tracking-widest text-emerald-400">⚡ Entradas Destacadas</span>
              <span className="text-[0.6rem] text-muted-foreground/50">— alcistas con ≥2 señales confirmadas</span>
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
              {top.map(row => {
                const topSig = signals
                  .filter(s => s.ticker === row.ticker && s.direction === 'BULLISH')
                  .sort((a, b) => b.strength - a.strength)
                  .slice(0, 2)
                const inPortfolio = row.source === 'portfolio'
                return (
                  <div
                    key={row.ticker}
                    className="glass flex-shrink-0 w-52 rounded-xl p-3 border border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-500/40 transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <TickerLogo ticker={row.ticker} size="xs" />
                      <span className="font-mono font-bold text-sm text-foreground">{row.ticker}</span>
                      {inPortfolio && (
                        <span className="text-[0.55rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary border border-primary/25 font-bold ml-auto">
                          EN CARTERA
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/25">
                        +{row.bullish_count} ALCISTAS
                      </span>
                      <span className="text-[0.6rem] text-muted-foreground/50">{SOURCE_LABELS[row.source] ?? row.source}</span>
                    </div>
                    <div className="space-y-1">
                      {topSig.map((s) => (
                        <div key={`${s.signal_name}-${s.timeframe}`} className="flex items-center gap-1.5">
                          <SignalStrengthDots strength={s.strength} />
                          <span className="text-[0.68rem] text-foreground/70 truncate">{s.signal_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {/* Bias filter */}
        <div className="flex rounded-lg bg-muted/20 border border-border/30 p-1 gap-1">
          {(['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const).map(b => (
            <button
              key={b}
              onClick={() => setBiasFilter(b)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all border ${biasBtnCls(b, biasFilter === b)}`}
            >
              {biasBtnLabel(b)}
            </button>
          ))}
        </div>

        {/* Source filter */}
        <div className="flex flex-wrap gap-1.5">
          {sources.map(s => (
            <button
              key={s}
              onClick={() => setSourceFilter(s)}
              className={`text-[0.68rem] px-2.5 py-0.5 rounded-full border transition-colors ${
                sourceFilter === s
                  ? 'border-primary/60 bg-primary/15 text-primary'
                  : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'
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
              {tfLabel(tf)}
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

        {/* My portfolio filter */}
        {myPositions.length > 0 && (
          <button
            onClick={() => setOnlyMyPortfolio(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
              onlyMyPortfolio
                ? 'bg-primary/20 border-primary/50 text-primary'
                : 'bg-muted/20 border-border/30 text-muted-foreground hover:text-foreground hover:border-border/60'
            }`}
          >
            <Wallet size={12} />
            Mi Cartera
          </button>
        )}
      </div>

      {/* Results count */}
      <div className="text-sm text-muted-foreground">
        Mostrando <strong className="text-foreground">{filteredSummary.length}</strong> tickers
        {biasFilter !== 'ALL' && ` · ${biasResultLabel(biasFilter)}`}
        {sourceFilter !== 'ALL' && ` · ${SOURCE_LABELS[sourceFilter] ?? sourceFilter}`}
        {totalPages > 1 && ` · pág. ${page}/${totalPages}`}
      </div>

      {/* Cards */}
      {filteredSummary.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No hay tickers con los filtros seleccionados.
        </div>
      ) : (
        <div className="space-y-3 animate-fade-in-up">
          {pagedSummary.map(row => {
            const rowSignals = signalsMap.get(row.ticker) ?? []
            if (rowSignals.length === 0 && strengthFilter > 1) return null
            return (
              <TickerCard key={row.ticker} row={row} signals={rowSignals} />
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page === 1}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-border/40 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            ← Anterior
          </button>
          <div className="flex gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
              <button
                key={p}
                onClick={() => goToPage(p)}
                className={`w-8 h-8 rounded-lg text-xs font-bold transition-all border ${
                  p === page
                    ? 'bg-primary/20 border-primary/50 text-primary'
                    : 'border-border/30 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          <button
            onClick={() => goToPage(page + 1)}
            disabled={page === totalPages}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-border/40 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Siguiente →
          </button>
        </div>
      )}
    </div>
  )
}
