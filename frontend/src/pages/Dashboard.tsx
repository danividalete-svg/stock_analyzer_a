import React, { useMemo } from 'react'
import { Link } from 'react-router-dom'
import StaleDataBanner from '../components/StaleDataBanner'
import {
  fetchMarketRegime, fetchValueOpportunities, fetchEUValueOpportunities,
  fetchPortfolioTracker, fetchRecurringInsiders, fetchOptionsFlow, fetchMeanReversion,
  fetchMacroRadar, fetchDailyBriefing, fetchMarketBreadth, fetchCerebroConvergence, fetchCerebroAlerts,
  fetchCerebroEntrySignals, fetchCerebroDailyPlan, fetchLivePrices, fetchPortfolioNews,
  type ValueOpportunity, type InsiderData, type PortfolioSummary, type BreadthData, type CerebroAlert,
  type DailyPlan, type DailyPlanAction, type MacroPlay, type LivePricesData, type PortfolioNewsItem,
} from '../api/client'
import AiNarrativeCard from '../components/AiNarrativeCard'

import { useApi } from '../hooks/useApi'
import { useCountUp } from '../hooks/useCountUp'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import GradeBadge from '../components/GradeBadge'
import ScoreRing from '../components/ScoreRing'
import InfoTooltip from '../components/InfoTooltip'
import TickerLogo from '../components/TickerLogo'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, ChevronRight, Radar, Wallet, Zap, Crosshair, BarChart3, Brain, Target, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import { useWatchlist } from '../hooks/useWatchlist'

// ── helpers ─────────────────────────────────────────────────────────────────

function fmt(n: number | undefined | null, dec = 1) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toFixed(dec)
}

function pct(n: number | undefined | null) {
  if (n == null || Number.isNaN(n)) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

const REGIME_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  BULL:       { bg: 'bg-emerald-500/10 border-emerald-500/20', text: 'text-emerald-400', icon: <TrendingUp size={14} />, label: 'ALCISTA' },
  BEAR:       { bg: 'bg-red-500/10 border-red-500/20',         text: 'text-red-400',     icon: <TrendingDown size={14} />, label: 'BAJISTA' },
  CORRECTION: { bg: 'bg-amber-500/10 border-amber-500/20',     text: 'text-amber-400',   icon: <TrendingDown size={14} />, label: 'CORRECCIÓN' },
  NEUTRAL:    { bg: 'bg-blue-500/10 border-blue-500/20',       text: 'text-blue-400',    icon: <Minus size={14} />, label: 'NEUTRAL' },
  RECOVERY:   { bg: 'bg-sky-500/10 border-sky-500/20',         text: 'text-sky-400',     icon: <TrendingUp size={14} />, label: 'RECUPERACIÓN' },
}

function regimeStyle(regime: string | undefined) {
  if (!regime) return REGIME_STYLES.NEUTRAL
  const upper = regime.toUpperCase()
  return (
    REGIME_STYLES[upper] ??
    REGIME_STYLES[Object.keys(REGIME_STYLES).find(k => upper.includes(k)) ?? ''] ??
    REGIME_STYLES.NEUTRAL
  )
}

// ── sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, color = 'text-foreground', loading = false,
  countTo, countDecimals = 0, countSuffix = '',
}: {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  color?: string
  loading?: boolean
  countTo?: number
  countDecimals?: number
  countSuffix?: string
}) {
  const counted = useCountUp(countTo ?? null, 700, countDecimals)
  const displayValue = countTo != null
    ? `${counted.toFixed(countDecimals)}${countSuffix}`
    : value

  if (loading) return (
    <Card className="glass p-5">
      <Skeleton className="h-2.5 w-1/2 mb-4" />
      <Skeleton className="h-8 w-2/5 mb-3" />
      <Skeleton className="h-2.5 w-3/5" />
    </Card>
  )
  return (
    <Card className="glass glow-border p-5">
      <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
      <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color}`}>{displayValue}</div>
      {sub && <div className="text-[0.66rem] text-muted-foreground">{sub}</div>}
    </Card>
  )
}

function RegimeCard({ label, data, loading }: { label: string; data: Record<string, unknown> | undefined; loading: boolean }) {
  if (loading) return (
    <Card className="glass p-5">
      <Skeleton className="h-2.5 w-1/3 mb-4" />
      <Skeleton className="h-6 w-1/2 mb-3" />
      <Skeleton className="h-2.5 w-3/4" />
    </Card>
  )
  const regime = data?.regime as string | undefined
  const s = regimeStyle(regime)
  const spy = data?.spy_price ?? data?.eurostoxx_price ?? data?.index_price
  const vs200 = data?.spy_vs_200ma ?? data?.index_vs_200ma

  return (
    <Card className={`glass p-5 border ${s.bg}`}>
      <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
      <div className={`flex items-center gap-2 ${s.text} mb-2`}>
        {s.icon}
        <span className="text-xl font-extrabold tracking-tight">{s.label}</span>
        <InfoTooltip
          text={
            <span>
              Régimen de mercado detectado:<br />
              <span className="text-emerald-400">ALCISTA</span> — tendencia sana, operar largo<br />
              <span className="text-sky-400">RECUPERACIÓN</span> — rebote desde mínimos, precaución<br />
              <span className="text-blue-400">NEUTRAL</span> — sin tendencia clara, selectivo<br />
              <span className="text-amber-400">CORRECCIÓN</span> — caída &gt;5% desde máximos, reducir exposición<br />
              <span className="text-red-400">BAJISTA</span> — tendencia bajista, evitar nuevas entradas
            </span>
          }
          side="bottom"
        />
      </div>
      <div className="text-[0.66rem] text-muted-foreground space-y-0.5">
        {spy != null && <div>Precio: <span className="text-foreground">${Number(spy).toFixed(2)}</span></div>}
        {vs200 != null && (
          <div>vs 200MA: <span className={Number(vs200) >= 0 ? 'text-emerald-400' : 'text-red-400'}>{pct(Number(vs200))}</span></div>
        )}
        {data?.market_score != null && (
          <div>Score: <span className="text-foreground">{Number(data.market_score).toFixed(0)}/100</span></div>
        )}
      </div>
    </Card>
  )
}

function upsideColor(upside: number) {
  if (upside >= 15) return 'text-emerald-400'
  if (upside < 0) return 'text-red-400'
  return 'text-foreground'
}

function UpsideCell({ upside }: { upside: number }) {
  return <div className={`text-[0.65rem] tabular-nums ${upsideColor(upside)}`}>{pct(upside)}</div>
}

function TopPicksTable({
  title, rows, to, loading
}: {
  title: string; rows: ValueOpportunity[]; to: string; loading: boolean
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{title}</span>
        <Link to={to} className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver todos <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass">
        {loading ? (
          <div className="divide-y divide-border/30">
            {['a','b','c','d','e'].map((k) => (
              <div key={k} className="px-4 py-3 flex items-center gap-3">
                <Skeleton className="h-3.5 w-12" />
                <Skeleton className="h-3 flex-1" />
                <Skeleton className="h-3 w-8" />
                <Skeleton className="h-3 w-10" />
              </div>
            ))}
          </div>
        ) : rows.length === 0 ? (
          <CardContent className="py-8 text-center text-sm text-muted-foreground">Sin datos</CardContent>
        ) : (
          <div className="divide-y divide-border/30">
            {rows.map((r) => (
              <div key={r.ticker} className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/3 transition-colors">
                <TickerLogo ticker={r.ticker} size="md" className="flex-shrink-0" />
                <div className="w-[4rem] shrink-0">
                  <div className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{r.ticker}</div>
                  {r.conviction_grade && (
                    <GradeBadge grade={r.conviction_grade} score={r.conviction_score} />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[0.72rem] text-muted-foreground truncate">{r.company_name || r.sector || ''}</div>
                  {r.sector && r.company_name && (
                    <div className="text-[0.6rem] text-muted-foreground/50 truncate">{r.sector}</div>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[0.75rem] font-bold text-foreground tabular-nums">
                    {fmt(r.value_score, 0)}
                    <span className="text-muted-foreground/50 font-normal text-[0.6rem]">pts</span>
                  </div>
                  {r.analyst_upside_pct != null && (
                    <UpsideCell upside={r.analyst_upside_pct} />
                  )}
                </div>
                {r.earnings_warning && (
                  <span title="Earnings próximos">
                    <AlertTriangle size={11} className="text-amber-400 shrink-0" />
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function InsidersMini({ data, loading }: { data: InsiderData[] | undefined; loading: boolean }) {
  const top = data?.slice(0, 4) ?? []
  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Top Insiders</span>
        <Link to="/insiders" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver todos <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass">
        {loading ? (
          <div className="divide-y divide-border/30">
            {['a','b','c','d'].map((k) => (
              <div key={k} className="px-4 py-2.5 flex items-center gap-3">
                <Skeleton className="h-3.5 w-10" />
                <Skeleton className="h-3 flex-1" />
                <Skeleton className="h-3 w-8" />
              </div>
            ))}
          </div>
        ) : top.length === 0 ? (
          <CardContent className="py-6 text-center text-sm text-muted-foreground">Sin datos</CardContent>
        ) : (
          <div className="divide-y divide-border/30">
            {top.map((r) => {
              const ri = r as unknown as Record<string, unknown>
              const name = ri.company_name ?? ri.company ?? r.ticker
              const isEU = ri.market === 'EU' || r.confidence_label != null
              return (
                <div key={r.ticker} className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/3 transition-colors">
                  <div className="w-[3.5rem] shrink-0">
                    <div className="font-mono font-bold text-primary text-[0.8rem]">{r.ticker}</div>
                    <div className="text-[0.58rem] text-muted-foreground/50">{isEU ? 'EU' : 'US'}</div>
                  </div>
                  <div className="flex-1 min-w-0 text-[0.72rem] text-muted-foreground truncate">
                    {String(name ?? r.ticker)}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-[0.72rem] text-foreground">{r.purchase_count}×</div>
                    <div className="text-[0.6rem] text-muted-foreground/60">{r.unique_insiders} dir.</div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}

function OptionsFlowMini({ data, loading }: { data: unknown; loading: boolean }) {
  const rows = (data as { data?: Array<{ sentiment: string; flow_score: number }> } | null)?.data ?? []
  const bullish = rows.filter(r => (r.sentiment ?? '').toLowerCase().includes('bull')).length
  const bearish = rows.filter(r => (r.sentiment ?? '').toLowerCase().includes('bear')).length
  const total = rows.length

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Options Flow</span>
        <Link to="/options" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver todos <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ) : total === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-2">Sin datos</p>
        ) : (
          <>
            <div className="flex items-center gap-4 mb-3">
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">Bullish</div>
                <div className="text-2xl font-extrabold text-emerald-400 tabular-nums">{bullish}</div>
              </div>
              <div className="h-10 w-px bg-border/50" />
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">Bearish</div>
                <div className="text-2xl font-extrabold text-red-400 tabular-nums">{bearish}</div>
              </div>
              <div className="h-10 w-px bg-border/50" />
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">Total</div>
                <div className="text-2xl font-extrabold tabular-nums">{total}</div>
              </div>
            </div>
            {total > 0 && (
              <div className="relative h-1.5 rounded-full overflow-hidden bg-red-500/30">
                <div
                  className="absolute inset-y-0 left-0 bg-emerald-500/70 rounded-full"
                  style={{ width: `${Math.round((bullish / total) * 100)}%` }}
                />
              </div>
            )}
            <div className="text-[0.6rem] text-muted-foreground mt-1.5 text-right">
              {total > 0 ? `${Math.round((bullish / total) * 100)}% alcista` : ''}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

interface MacroSignal { score: number; label: string; interpretation: string }
interface MacroData {
  regime: { name: string; color: string; description: string }
  composite_score: number
  max_score: number
  signals: Record<string, MacroSignal>
  signal_order: string[]
}

const MACRO_REGIME_BG: Record<string, string> = {
  CALM:   'bg-emerald-500/10 border-emerald-500/25',
  WATCH:  'bg-lime-500/10 border-lime-500/25',
  STRESS: 'bg-yellow-500/10 border-yellow-500/25',
  ALERT:  'bg-orange-500/10 border-orange-500/25',
  CRISIS: 'bg-red-500/10 border-red-500/25',
}
const MACRO_REGIME_TEXT: Record<string, string> = {
  CALM: 'text-emerald-400', WATCH: 'text-lime-400', STRESS: 'text-yellow-400',
  ALERT: 'text-orange-400', CRISIS: 'text-red-400',
}

function MacroRadarMini({ data, loading }: { data: unknown; loading: boolean }) {
  const macro = data as MacroData | null

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Radar size={11} /> Macro Radar
        </span>
        <Link to="/macro-radar" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver detalle <ChevronRight size={11} />
        </Link>
      </div>
      <Card className={`glass border ${macro ? (MACRO_REGIME_BG[macro.regime?.name] ?? 'border-border/40') : 'border-border/40'} p-4`}>
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        ) : !macro ? (
          <p className="text-sm text-muted-foreground text-center py-2">Sin datos</p>
        ) : (
          <>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: macro.regime?.color }} />
                <span className={`text-base font-extrabold ${MACRO_REGIME_TEXT[macro.regime?.name] ?? 'text-foreground'}`}>
                  {macro.regime?.name}
                </span>
              </div>
              <span className="text-[0.65rem] text-muted-foreground tabular-nums">
                {macro.composite_score > 0 ? '+' : ''}{macro.composite_score.toFixed(1)} / {macro.max_score}
              </span>
            </div>

            {/* Composite gauge */}
            <div className="h-1.5 w-full rounded-full bg-muted/30 overflow-hidden mb-2">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${((macro.composite_score + macro.max_score) / (2 * macro.max_score)) * 100}%`,
                  backgroundColor: macro.regime?.color,
                }}
              />
            </div>

            {/* Worst 3 signals */}
            <div className="space-y-1">
              {(macro.signal_order ?? Object.keys(macro.signals))
                .map(k => ({ k, s: macro.signals[k] }))
                .filter(x => x.s)
                .sort((a, b) => (a.s.score ?? 0) - (b.s.score ?? 0))
                .slice(0, 3)
                .map(({ k, s }) => (
                  <div key={k} className="flex items-center justify-between">
                    <span className="text-[0.62rem] text-muted-foreground truncate">{s.label}</span>
                    <span className={`text-[0.62rem] font-bold tabular-nums shrink-0 ml-2 ${s.score < -1 ? 'text-red-400' : s.score < 0 ? 'text-orange-400' : 'text-emerald-400'}`}>
                      {s.score > 0 ? '+' : ''}{s.score.toFixed(1)}
                    </span>
                  </div>
                ))}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

function MeanReversionMini({ data, loading }: { data: unknown; loading: boolean }) {
  const rows = (data as { data?: Array<{ quality: string; reversion_score: number }> } | null)?.data ?? []
  const high = rows.filter(r => (r.quality ?? '').toUpperCase() === 'HIGH').length
  const total = rows.length

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Mean Reversion</span>
        <Link to="/mean-reversion" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver todos <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-6 w-1/2" />
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div>
              <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">Setups</div>
              <div className="text-2xl font-extrabold tabular-nums">{total || '—'}</div>
            </div>
            {high > 0 && (
              <>
                <div className="h-10 w-px bg-border/50" />
                <div>
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">Alta Calidad</div>
                  <div className="text-2xl font-extrabold text-teal-400 tabular-nums">{high}</div>
                </div>
              </>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

const STRATEGY_TAG: Record<string, string> = {
  VALUE: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  INSIDERS: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  MOMENTUM: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
}
function strategyTag(s: string) {
  return STRATEGY_TAG[s.toUpperCase()] ?? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
}

function ConvergenciaMini({ loading, data }: {
  loading: boolean
  data: { convergences: Array<{ ticker: string; strategies: string[]; strategy_count: number; convergence_score: number; conviction_grade?: string; streak_days?: number; analysis?: string | null }> } | null
}) {
  const items = data?.convergences ?? []
  const sorted = [...items].sort((a, b) => b.convergence_score - a.convergence_score).slice(0, 6)

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Crosshair size={11} /> Convergencia
        </span>
        <Link to="/cerebro" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          {!loading && <span className="mr-0.5">{items.length} tickers</span>}
          <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">{['a','b','c'].map(k => <Skeleton key={k} className="h-4 w-full" />)}</div>
        ) : sorted.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-1">Sin convergencias</p>
        ) : (
          <div className="space-y-2">
            {sorted.map(item => (
              <div key={item.ticker} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 shrink-0">
                  <Link to={`/search?q=${item.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">
                    {item.ticker}
                  </Link>
                  {(item.streak_days ?? 0) >= 3 && (
                    <span className="text-[0.5rem] font-bold px-1 py-0 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30" title={`${item.streak_days} días consecutivos`}>
                      🔥{item.streak_days}d
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-0.5 justify-end">
                  {item.strategy_count >= 3 && (
                    <span className="text-[0.5rem] font-bold px-1 py-0 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">TRIPLE</span>
                  )}
                  {item.strategies.map(s => (
                    <span key={s} className={`text-[0.5rem] font-bold px-1 py-0 rounded border ${strategyTag(s)}`}>{s}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function alertSeverityStyle(severity: string) {
  if (severity === 'HIGH') return 'text-red-400 bg-red-500/10 border-red-500/30'
  if (severity === 'MEDIUM') return 'text-amber-400 bg-amber-500/10 border-amber-500/30'
  return 'text-blue-400 bg-blue-500/10 border-blue-500/30'
}

function WatchlistAlertsMini({ alerts, watchlistTickers, loading }: {
  alerts: CerebroAlert[] | undefined
  watchlistTickers: Set<string>
  loading: boolean
}) {
  const filtered = (alerts ?? [])
    .filter(a => watchlistTickers.has(a.ticker.toUpperCase()))
    .sort((a, b) => {
      const sev = { HIGH: 0, MEDIUM: 1, LOW: 2 }
      return (sev[a.severity] ?? 2) - (sev[b.severity] ?? 2)
    })
    .slice(0, 5)

  if (!loading && watchlistTickers.size === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Brain size={11} /> Alertas Watchlist
        </span>
        <Link to="/cerebro" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Ver todas <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">{['a','b','c'].map(k => <Skeleton key={k} className="h-4 w-full" />)}</div>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-1">Sin alertas para tu watchlist</p>
        ) : (
          <div className="space-y-1.5">
            {filtered.map((a, i) => (
              <div key={i} className={`flex items-start gap-2 px-2 py-1.5 rounded-md border ${alertSeverityStyle(a.severity)}`}>
                <span className="text-[0.55rem] font-bold uppercase mt-0.5 shrink-0">{a.severity}</span>
                <div className="flex-1 min-w-0">
                  <span className="font-mono font-bold text-[0.75rem] mr-1">{a.ticker}</span>
                  <span className="text-[0.68rem]">{a.title}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function BreadthMini({ data, loading }: { data: { us: BreadthData; eu: BreadthData } | undefined; loading: boolean }) {
  const us = data?.us
  const eu = data?.eu

  function BreadthRow({ label, pct, n, total }: { label: string; pct?: number; n?: number; total: number }) {
    if (pct == null) return null
    const color = pct >= 50 ? 'bg-emerald-500' : pct >= 30 ? 'bg-amber-500' : 'bg-red-500'
    return (
      <div>
        <div className="flex justify-between text-[0.6rem] mb-0.5">
          <span className="text-muted-foreground">{label}</span>
          <span className="tabular-nums font-semibold">{n ?? 0}/{total} <span className="text-muted-foreground/60">({pct}%)</span></span>
        </div>
        <div className="h-1 w-full rounded-full bg-muted/30 overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <BarChart3 size={11} /> Breadth
        </span>
        <Link to="/industry-groups" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          Grupos <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-3">{['a','b'].map(k => <div key={k}><Skeleton className="h-2 w-full mb-1" /><Skeleton className="h-1 w-full" /></div>)}</div>
        ) : !us ? (
          <p className="text-sm text-muted-foreground text-center py-1">Sin datos</p>
        ) : (
          <div className="space-y-2.5">
            <div className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-1">US · {us.total} tickers</div>
            <BreadthRow label="En tendencia alcista" pct={us.trend_pass_pct} n={us.trend_pass} total={us.total} />
            <BreadthRow label="Upside positivo" pct={us.positive_upside_pct} n={us.positive_upside} total={us.total} />
            {eu && eu.total > 0 && (
              <>
                <div className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground/50 mt-2 mb-1">EU · {eu.total} tickers</div>
                <BreadthRow label="En tendencia alcista" pct={eu.trend_pass_pct} n={eu.trend_pass} total={eu.total} />
                <BreadthRow label="Upside positivo" pct={eu.positive_upside_pct} n={eu.positive_upside} total={eu.total} />
              </>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

const ENTRY_SIGNAL_COLOR: Record<string, string> = {
  STRONG_BUY: 'text-emerald-400',
  BUY:        'text-amber-400',
  MONITOR:    'text-blue-400',
  WAIT:       'text-muted-foreground',
}
const ENTRY_SIGNAL_LABEL: Record<string, string> = {
  STRONG_BUY: '🟢 STRONG BUY', BUY: '🟡 BUY', MONITOR: '🔵 MONITOR', WAIT: '⚪ WAIT',
}

function EntrySignalsMini({ data, loading }: {
  data: { strong_buy: number; buy: number; signals: Array<{ ticker: string; signal: string; entry_score: number; signals_fired: string[]; signals_missing: string[] }> } | null
  loading: boolean
}) {
  const top = (data?.signals ?? []).filter(s => s.signal !== 'WAIT').slice(0, 4)

  return (
    <div>
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Zap size={11} /> Señales de Entrada
        </span>
        <Link to="/cerebro" className="flex items-center gap-1 text-[0.65rem] text-muted-foreground hover:text-foreground transition-colors">
          {!loading && <span className="mr-0.5">{(data?.strong_buy ?? 0) + (data?.buy ?? 0)} activas</span>}
          <ChevronRight size={11} />
        </Link>
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">{['a','b','c','d'].map(k => <Skeleton key={k} className="h-4 w-full" />)}</div>
        ) : top.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-1">Sin señales claras hoy</p>
        ) : (
          <div className="space-y-2">
            {top.map(s => (
              <div key={s.ticker} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 shrink-0">
                  <Link to={`/search?q=${s.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{s.ticker}</Link>
                  <span className={`text-[0.58rem] font-bold tabular-nums ${ENTRY_SIGNAL_COLOR[s.signal]}`}>{ENTRY_SIGNAL_LABEL[s.signal]}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <div className="w-14 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${s.entry_score >= 75 ? 'bg-emerald-500' : s.entry_score >= 50 ? 'bg-amber-500' : 'bg-blue-500'}`}
                      style={{ width: `${s.entry_score}%` }}
                    />
                  </div>
                  <span className="text-[0.65rem] tabular-nums font-bold text-muted-foreground">{s.entry_score}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

// ── LivePricesBar ─────────────────────────────────────────────────────────────

const LIVE_ORDER = ['vix', 'spy', 'oil', 'gold', 'tnx', 'tyx', 'dxy'] as const

function useLivePrices(intervalMs = 60_000) {
  const [data, setData]           = React.useState<LivePricesData | null>(null)
  const [loading, setLoading]     = React.useState(true)
  const [lastUpdate, setLastUpdate] = React.useState<Date | null>(null)
  const [secsAgo, setSecsAgo]     = React.useState(0)

  React.useEffect(() => {
    let cancelled = false
    const doFetch = async () => {
      try {
        const res = await fetchLivePrices()
        if (!cancelled) { setData(res.data); setLastUpdate(new Date()); setSecsAgo(0) }
      } catch { /* silent */ } finally {
        if (!cancelled) setLoading(false)
      }
    }
    doFetch()
    const fetchId = setInterval(doFetch, intervalMs)
    const tickId  = setInterval(() => setSecsAgo(s => s + 1), 1000)
    return () => { cancelled = true; clearInterval(fetchId); clearInterval(tickId) }
  }, [intervalMs])

  return { data, loading, lastUpdate, secsAgo }
}

function LivePriceItem({ id, price }: { id: string; price: { label: string; kind: string; current: number | null; change_pct: number | null } }) {
  const chg = price.change_pct ?? 0
  const isRate = price.kind === 'rate'

  // VIX: green <20, yellow 20-25, red >25
  const vixColor = id === 'vix'
    ? (price.current ?? 0) > 25 ? 'text-red-400' : (price.current ?? 0) > 20 ? 'text-amber-400' : 'text-emerald-400'
    : null

  const chgColor = vixColor ?? (
    isRate
      ? chg > 0.03 ? 'text-red-400' : chg < -0.03 ? 'text-emerald-400' : 'text-muted-foreground'
      : chg >= 0.5 ? 'text-emerald-400' : chg <= -0.5 ? 'text-red-400' : 'text-muted-foreground'
  )

  const fmtVal = () => {
    if (price.current == null) return '—'
    if (id === 'vix') return price.current.toFixed(1)
    if (price.kind === 'rate') return `${price.current.toFixed(2)}%`
    return price.current.toFixed(2)
  }

  return (
    <div className="flex items-center gap-1.5 px-2.5 border-r border-border/20 last:border-0">
      <span className="text-[0.62rem] text-muted-foreground/60 hidden sm:inline">{price.label}</span>
      <span className={`font-mono font-bold text-[0.75rem] tabular-nums ${chgColor}`}>{fmtVal()}</span>
      {price.change_pct != null && (
        <span className={`text-[0.6rem] tabular-nums ${chgColor}`}>
          {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
        </span>
      )}
    </div>
  )
}

function LivePricesBar() {
  const { data, loading, secsAgo } = useLivePrices(60_000)

  if (loading) return (
    <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg border border-border/20 bg-muted/5 animate-pulse h-9" />
  )
  if (!data) return null

  const isOpen   = data.market_open
  const freshness = secsAgo < 90 ? 'text-emerald-400' : secsAgo < 180 ? 'text-amber-400' : 'text-muted-foreground/40'

  return (
    <div className="flex items-center gap-0 mb-4 rounded-lg border border-border/20 bg-muted/5 overflow-x-auto scrollbar-none animate-fade-in-up">
      {/* Status pill */}
      <div className="flex items-center gap-1.5 px-3 py-2 border-r border-border/20 shrink-0">
        <span className={`w-1.5 h-1.5 rounded-full ${isOpen ? 'bg-emerald-400 animate-pulse' : 'bg-muted-foreground/30'}`} />
        <span className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground/60">
          {isOpen ? 'Live' : 'Closed'}
        </span>
      </div>

      {/* Prices */}
      {LIVE_ORDER.map(id => {
        const p = data.prices[id]
        if (!p) return null
        return <LivePriceItem key={id} id={id} price={p} />
      })}

      {/* Freshness */}
      <div className={`ml-auto px-3 text-[0.58rem] tabular-nums shrink-0 ${freshness}`}>
        {secsAgo < 5 ? 'ahora' : `${secsAgo}s`}
      </div>
    </div>
  )
}

// ── DailyPlanCard ────────────────────────────────────────────────────────────

const SESGO_STYLES: Record<string, { border: string; text: string; bg: string; badge: string }> = {
  ALCISTA:     { border: 'border-l-emerald-500',  text: 'text-emerald-400',  bg: 'bg-emerald-500/8',  badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  BAJISTA:     { border: 'border-l-red-500',       text: 'text-red-400',      bg: 'bg-red-500/8',      badge: 'bg-red-500/20 text-red-300 border-red-500/40' },
  DEFENSIVO:   { border: 'border-l-amber-500',     text: 'text-amber-400',    bg: 'bg-amber-500/8',    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  OPORTUNIDAD: { border: 'border-l-cyan-500',      text: 'text-cyan-400',     bg: 'bg-cyan-500/8',     badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' },
  NEUTRO:      { border: 'border-l-blue-500',      text: 'text-blue-400',     bg: 'bg-blue-500/8',     badge: 'bg-blue-500/20 text-blue-300 border-blue-500/40' },
}

const ACCION_STYLES: Record<string, string> = {
  COMPRAR:  'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  VENDER:   'bg-red-500/20 text-red-300 border-red-500/40',
  REDUCIR:  'bg-orange-500/20 text-orange-300 border-orange-500/40',
  ESPERAR:  'bg-blue-500/20 text-blue-300 border-blue-500/40',
  VIGILAR:  'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  CUBRIR:   'bg-amber-500/20 text-amber-300 border-amber-500/40',
}

function ActionRow({ action, idx }: { action: DailyPlanAction; idx: number }) {
  const accionKey = (action.accion ?? '').toUpperCase()
  const badgeStyle = ACCION_STYLES[accionKey] ?? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-border/15 last:border-0">
      <div className="shrink-0 w-5 h-5 rounded-full bg-muted/20 flex items-center justify-center text-[0.6rem] font-bold text-muted-foreground mt-0.5">
        {idx + 1}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={`text-[0.62rem] font-bold px-1.5 py-0.5 rounded border ${badgeStyle}`}>
            {action.accion}
          </span>
          <span className="font-mono font-bold text-primary text-[0.82rem] tracking-wide">{action.instrumento}</span>
          {action.size_hint && (
            <span className="text-[0.58rem] px-1.5 py-0.5 rounded bg-muted/20 text-muted-foreground border border-border/30">
              {action.size_hint}
            </span>
          )}
        </div>
        <div className="text-[0.72rem] text-foreground/80 mb-0.5">{action.razon}</div>
        {action.catalizador && (
          <div className="text-[0.65rem] text-muted-foreground/70">
            <span className="text-muted-foreground/50">Catalizador:</span> {action.catalizador}
          </div>
        )}
        {action.invalidacion && (
          <div className="text-[0.62rem] text-muted-foreground/50 mt-0.5">
            <span className="text-red-400/50">Invalida si:</span> {action.invalidacion}
          </div>
        )}
      </div>
    </div>
  )
}

function MacroPlayRow({ play }: { play: MacroPlay }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-border/10 last:border-0">
      <div className="shrink-0 mt-0.5">
        <div className="font-mono font-bold text-[0.78rem] text-primary">{play.instrument}</div>
        {play.direction && (
          <div className="text-[0.6rem] text-muted-foreground/60">{play.direction}</div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[0.7rem] text-foreground/80">{play.thesis}</div>
        <div className="text-[0.62rem] text-muted-foreground/50 mt-0.5">{play.timeframe} · {play.risk}</div>
        {play.eu_alternative && (
          <div className="mt-1 flex items-center gap-1">
            <span className="text-[0.55rem] font-bold uppercase tracking-wide text-blue-400/70 border border-blue-400/30 px-1 py-px rounded">EU</span>
            {play.eu_alternative.ticker ? (
              <span className="text-[0.62rem] font-mono text-blue-300/80">{play.eu_alternative.ticker}</span>
            ) : null}
            <span className="text-[0.58rem] text-muted-foreground/40 truncate">{play.eu_alternative.available}</span>
          </div>
        )}
      </div>
      <div className="shrink-0 text-right">
        <div className="text-[0.72rem] font-bold tabular-nums text-foreground">{play.score}</div>
        <div className="w-10 h-1 rounded-full bg-muted/20 mt-1 overflow-hidden">
          <div
            className={`h-full rounded-full ${play.score >= 80 ? 'bg-emerald-500' : play.score >= 65 ? 'bg-amber-500' : 'bg-blue-500'}`}
            style={{ width: `${play.score}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function DailyPlanCard({ data, loading }: { data: DailyPlan | null | undefined; loading: boolean }) {
  const [showMacroPlays, setShowMacroPlays] = React.useState(true)

  if (loading) {
    return (
      <Card className="glass border-l-4 border-l-primary/40 p-5 mb-5">
        <div className="flex items-center gap-3 mb-4">
          <Skeleton className="h-5 w-5 rounded" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-5 w-16 ml-auto rounded-full" />
        </div>
        <Skeleton className="h-3 w-full mb-2" />
        <Skeleton className="h-3 w-4/5 mb-4" />
        <div className="space-y-3">
          {['a','b','c'].map(k => <Skeleton key={k} className="h-12 w-full" />)}
        </div>
      </Card>
    )
  }

  if (!data) return null

  const sesgoKey = (data.sesgo ?? 'NEUTRO').toUpperCase()
  const ss = SESGO_STYLES[sesgoKey] ?? SESGO_STYLES.NEUTRO

  return (
    <Card className={`glass border-l-4 ${ss.border} ${ss.bg} p-5 mb-5 animate-fade-in-up`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2.5">
          <Target size={16} className={ss.text} />
          <span className="text-[0.7rem] font-bold uppercase tracking-widest text-muted-foreground">
            Plan del Día — Cerebro IA
          </span>
          <span className="text-[0.6rem] text-muted-foreground/50">{data.generated_at}</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {data.ai_powered && (
            <span className="flex items-center gap-1 text-[0.58rem] font-bold px-1.5 py-0.5 rounded border bg-purple-500/15 text-purple-300 border-purple-500/30">
              <Sparkles size={9} /> AI
            </span>
          )}
          <span className="text-[0.6rem] px-1.5 py-0.5 rounded bg-muted/20 text-muted-foreground border border-border/30 tabular-nums">
            Confianza {data.confianza}%
          </span>
          <span className={`text-[0.7rem] font-extrabold px-2.5 py-1 rounded border ${ss.badge}`}>
            {data.sesgo}
          </span>
        </div>
      </div>

      {/* Situacion */}
      {data.situacion && (
        <div className={`text-[0.85rem] font-semibold mb-1 ${ss.text}`}>{data.situacion}</div>
      )}

      {/* Narrativa */}
      {data.narrativa && (
        <div className="text-[0.72rem] text-muted-foreground/80 mb-4 leading-relaxed">{data.narrativa}</div>
      )}

      <div className="h-px bg-border/20 mb-4" />

      {/* Acciones Inmediatas */}
      {(data.acciones_inmediatas?.length ?? 0) > 0 && (
        <div className="mb-4">
          <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">
            Acciones Inmediatas
          </div>
          <div>
            {data.acciones_inmediatas.map((action, i) => (
              <ActionRow key={i} action={action} idx={i} />
            ))}
          </div>
        </div>
      )}

      {/* Macro Plays */}
      {(data.macro_plays?.length ?? 0) > 0 && (
        <div className="mb-4">
          <button
            onClick={() => setShowMacroPlays(prev => !prev)}
            className="flex items-center gap-2 text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground mb-2 hover:text-foreground transition-colors w-full text-left"
          >
            Macro Plays ({data.macro_plays.length})
            {showMacroPlays ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {data.macro_plays_commentary && (
              <span className="font-normal normal-case tracking-normal text-muted-foreground/60 ml-1 flex-1 text-left">
                — {data.macro_plays_commentary}
              </span>
            )}
          </button>
          {showMacroPlays && (
            <div>
              {data.macro_plays.map((play, i) => (
                <MacroPlayRow key={i} play={play} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* VALUE en este entorno + Evitar */}
      <div className="flex gap-4 mb-4 flex-wrap">
        {(data.value_en_entorno?.length ?? 0) > 0 && (
          <div className="flex-1 min-w-0">
            <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">
              VALUE en este entorno
            </div>
            {data.value_en_entorno_razon && (
              <div className="text-[0.62rem] text-muted-foreground/60 mb-2">{data.value_en_entorno_razon}</div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {data.value_en_entorno.map(v => (
                <Link
                  key={v.ticker}
                  to={`/search?q=${v.ticker}`}
                  className="flex items-center gap-1.5 px-2 py-1 rounded border border-border/30 bg-muted/10 hover:bg-muted/20 transition-colors"
                >
                  <span className="font-mono font-bold text-primary text-[0.78rem]">{v.ticker}</span>
                  {v.grade && (
                    <span className="text-[0.55rem] font-bold px-1 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                      {v.grade}
                    </span>
                  )}
                  <span className="text-[0.62rem] text-muted-foreground/60">{v.score}pts</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {(data.evitar?.length ?? 0) > 0 && (
          <div className="shrink-0">
            <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">
              Evitar
            </div>
            <div className="flex flex-wrap gap-1.5">
              {data.evitar.map(e => (
                <span
                  key={e.ticker}
                  title={e.razon}
                  className="font-mono font-bold text-[0.75rem] px-2 py-0.5 rounded border bg-red-500/10 text-red-400 border-red-500/25 cursor-help"
                >
                  {e.ticker}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Agenda */}
      {(data.agenda_semana?.length ?? 0) > 0 && (
        <div className="mb-3">
          <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">
            Agenda
          </div>
          <div className="flex flex-wrap gap-2">
            {data.agenda_semana.slice(0, 4).map((ev, i) => (
              <div key={i} className={`flex items-center gap-1.5 px-2 py-1 rounded border text-[0.65rem] ${
                ev.impacto === 'ALTO'
                  ? 'border-red-500/25 bg-red-500/8 text-red-300'
                  : ev.impacto === 'MEDIO'
                  ? 'border-amber-500/25 bg-amber-500/8 text-amber-300'
                  : 'border-blue-500/20 bg-blue-500/8 text-blue-300'
              }`}>
                <span className="font-mono text-muted-foreground/60">{ev.fecha}</span>
                <span className="font-semibold">{ev.evento}</span>
                <span className="text-[0.55rem] font-bold opacity-70">[{ev.impacto}]</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Frase del día */}
      {data.frase_del_dia && (
        <div className="pt-2 border-t border-border/15">
          <p className="text-[0.68rem] italic text-muted-foreground/60">{data.frase_del_dia}</p>
        </div>
      )}
    </Card>
  )
}

// ── Portfolio News Widget ─────────────────────────────────────────────────────

function PortfolioNewsWidget({ data, loading }: { data: any; loading: boolean }) {
  const items: PortfolioNewsItem[] = data?.items ?? []
  const important = items.filter((i: PortfolioNewsItem) => i.importance === 'ALTA' || i.importance === 'MEDIA').slice(0, 8)
  const tickers: string[] = data?.tickers ?? []
  const scanTime: string = data?.scan_time ?? ''
  const scanDate: string = data?.scan_date ?? ''

  return (
    <Card className="glass border border-border/50 animate-fade-in-up">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-base">📰</span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Noticias de Cartera
          </span>
          {tickers.length > 0 && (
            <span className="text-[0.6rem] text-muted-foreground/40 ml-1">
              {tickers.join(' · ')}
            </span>
          )}
          {scanDate && (
            <span className="ml-auto text-[0.58rem] text-muted-foreground/30">
              {scanDate} {scanTime}
            </span>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-8 w-full" />)}
          </div>
        ) : important.length === 0 ? (
          <div className="text-center py-4">
            <p className="text-xs text-muted-foreground/40">Sin noticias relevantes en las últimas 48h</p>
            {tickers.length === 0 && (
              <p className="text-[0.65rem] text-muted-foreground/30 mt-1">
                Edita <code className="font-mono">docs/portfolio_watch.json</code> con tus tickers
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {important.map((item: PortfolioNewsItem) => {
              const isHigh = item.importance === 'ALTA'
              return (
                <div
                  key={item.id}
                  className={`rounded-lg border px-3 py-2 ${
                    isHigh
                      ? 'bg-red-500/6 border-red-500/20'
                      : 'bg-muted/6 border-border/20'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[0.7rem] mt-px shrink-0">
                      {isHigh ? '🔴' : '📌'}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-[0.6rem] font-black font-mono ${isHigh ? 'text-red-400' : 'text-primary'}`}>
                          {item.ticker}
                        </span>
                        <span className="text-[0.58rem] text-muted-foreground/40">
                          {item.source}{item.time_ago ? ` · ${item.time_ago}` : ''}
                        </span>
                      </div>
                      {item.url ? (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[0.68rem] text-foreground/85 leading-snug hover:text-primary transition-colors line-clamp-2"
                        >
                          {item.title}
                        </a>
                      ) : (
                        <p className="text-[0.68rem] text-foreground/85 leading-snug line-clamp-2">
                          {item.title}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="mt-3 pt-2 border-t border-border/10 flex justify-between items-center">
          <span className="text-[0.58rem] text-muted-foreground/30">
            {data?.alta_count ?? 0} alta · {data?.media_count ?? 0} media
          </span>
          <Link to="/my-portfolio" className="text-[0.65rem] text-primary/60 hover:text-primary transition-colors">
            Ver cartera →
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: regime, loading: loadingRegime } = useApi(() => fetchMarketRegime(), [])
  const { data: valueUS, loading: loadingUS } = useApi(() => fetchValueOpportunities(), [])
  const { data: valueEU, loading: loadingEU } = useApi(() => fetchEUValueOpportunities(), [])
  const { data: portfolio } = useApi(() => fetchPortfolioTracker(), [])
  const { data: insiders, loading: loadingInsiders } = useApi(() => fetchRecurringInsiders(), [])
  const { data: optionsRaw, loading: loadingOptions } = useApi(() => fetchOptionsFlow(), [])
  const { data: mrRaw, loading: loadingMR } = useApi(() => fetchMeanReversion(), [])
  const { data: macroRaw, loading: loadingMacro } = useApi(() => fetchMacroRadar(), [])
  const { data: briefingRaw } = useApi(() => fetchDailyBriefing(), [])
  const { data: breadthRaw, loading: loadingBreadth } = useApi(() => fetchMarketBreadth(), [])
  const { data: cerebroConv, loading: loadingConv } = useApi(() => fetchCerebroConvergence(), [])
  const { data: cerebroAlertsRaw, loading: loadingAlerts } = useApi(() => fetchCerebroAlerts(), [])
  const { data: cerebroEntry, loading: loadingEntry } = useApi(() => fetchCerebroEntrySignals(), [])
  const { data: dailyPlanRaw, loading: loadingDailyPlan } = useApi(() => fetchCerebroDailyPlan(), [])
  const { data: portfolioNewsRaw, loading: loadingPortfolioNews } = useApi(() => fetchPortfolioNews(), [])

  const { positions: myPositions } = usePersonalPortfolio()
  const { entries: watchlistEntries } = useWatchlist()
  const watchlistTickers = new Set(watchlistEntries.map(e => e.ticker.toUpperCase()))
  const myTickers = new Set(myPositions.map(p => p.ticker.toUpperCase()))

  const pf = (portfolio as PortfolioSummary) ?? {}
  const overall = pf.overall as Record<string, { count: number; win_rate: number; avg_return: number }> | undefined

  const topUS = [...(valueUS?.data ?? [])].sort((a, b) => (b.value_score ?? 0) - (a.value_score ?? 0)).slice(0, 5)
  const topEU = [...(valueEU?.data ?? [])].sort((a, b) => (b.value_score ?? 0) - (a.value_score ?? 0)).slice(0, 5)

  const bestPick = useMemo(() => {
    const rows = valueUS?.data ?? []
    return rows
      .filter((r) =>
        (r.value_score ?? 0) >= 65 &&
        ['A', 'B', 'EXCELLENT', 'STRONG'].includes((r.conviction_grade ?? '').toUpperCase()) &&
        !r.earnings_warning &&
        (r.days_to_earnings == null || r.days_to_earnings > 7) &&
        r.cerebro_signal !== 'EXIT' &&
        r.cerebro_signal !== 'TRAP'
      )
      .sort((a, b) => (b.value_score ?? 0) - (a.value_score ?? 0))[0] ?? null
  }, [valueUS])

  // ── Portfolio Action Items ─────────────────────────────────────────
  const actionItems: { icon: React.ReactNode; text: string; color: string; link: string }[] = []
  if (myTickers.size > 0) {
    // Earnings warnings for owned tickers
    const allValue = [...(valueUS?.data ?? []), ...(valueEU?.data ?? [])]
    for (const r of allValue) {
      if (myTickers.has(r.ticker) && r.earnings_warning && r.days_to_earnings != null) {
        actionItems.push({
          icon: <AlertTriangle size={11} />,
          text: `${r.ticker} — earnings en ${r.days_to_earnings}d, evita añadir`,
          color: 'text-amber-400',
          link: '/earnings',
        })
      }
    }
    // Insiders buying/selling owned tickers
    const insiderData = (insiders?.data ?? []) as InsiderData[]
    for (const ins of insiderData) {
      if (myTickers.has(ins.ticker)) {
        actionItems.push({
          icon: <Zap size={11} />,
          text: `${ins.ticker} — ${ins.purchase_count} compras insider (${ins.unique_insiders} directivos)`,
          color: 'text-purple-400',
          link: '/insiders',
        })
      }
    }
    // Mean reversion bounce on owned tickers
    const mrData = (mrRaw as { data?: { ticker: string }[] })?.data ?? []
    for (const mr of mrData) {
      if (myTickers.has(mr.ticker)) {
        actionItems.push({
          icon: <TrendingUp size={11} />,
          text: `${mr.ticker} — en zona oversold, oportunidad de añadir`,
          color: 'text-cyan-400',
          link: '/mean-reversion',
        })
      }
    }
  }

  // Earnings warnings from both lists
  const earningsWarnings = [
    ...(valueUS?.data ?? []).filter(r => r.earnings_warning),
    ...(valueEU?.data ?? []).filter(r => r.earnings_warning),
  ].slice(0, 6)

  const usRegime = regime?.us as Record<string, unknown> | undefined
  const euRegime = regime?.eu as Record<string, unknown> | undefined

  const conviction = (pf as Record<string, unknown>).conviction as Record<string, { count: number; win_rate: number; avg_return: number }> | undefined
  const winRate7d = conviction?.['7d']?.count ? conviction['7d'] : overall?.['7d']
  const winRateIsConviction = !!conviction?.['7d']?.count
  const totalSignals = pf.total_signals ?? 0
  const activeSignals = pf.active_signals ?? totalSignals

  function winRateColor() {
    if (winRate7d?.win_rate == null) return 'text-muted-foreground'
    if (winRate7d.win_rate >= 55) return 'text-emerald-400'
    if (winRate7d.win_rate >= 45) return 'text-amber-400'
    return 'text-red-400'
  }

  const signalsNum = activeSignals > 0 ? activeSignals : totalSignals > 0 ? totalSignals : null

  const macroDate = (macroRaw as { date?: string } | null)?.date ?? null

  return (
    <>
      {/* Header */}
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Resumen ejecutivo · Actualización diaria automática
        </p>
      </div>

      <StaleDataBanner dataDate={macroDate} />

      {/* Live prices bar — real-time, polls every 60s */}
      <LivePricesBar />

      {/* Daily Plan — most prominent feature, shown first */}
      <DailyPlanCard data={dailyPlanRaw} loading={loadingDailyPlan} />

      {/* Cerebro IA — acceso rápido */}
      {(() => {
        const entryCount = (cerebroEntry?.strong_buy ?? 0) + (cerebroEntry?.buy ?? 0)
        const convCount = cerebroConv?.convergences?.length ?? 0
        const alertCount = cerebroAlertsRaw?.alerts?.length ?? 0
        return (
          <div className="mb-5 animate-fade-in-up">
            <Link
              to="/cerebro"
              className="flex items-center gap-4 glass rounded-xl p-4 border border-primary/20 hover:border-primary/40 transition-colors group"
            >
              <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/20 shrink-0">
                <Brain size={18} className="text-purple-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-[0.72rem] font-bold uppercase tracking-widest text-foreground/80">Cerebro IA</span>
                  {!loadingEntry && !loadingConv && (entryCount > 0 || convCount > 0) && (
                    <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">
                      {entryCount > 0 ? `${entryCount} señales` : `${convCount} convergencias`}
                    </span>
                  )}
                  {!loadingAlerts && alertCount > 0 && (
                    <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-400 font-bold">
                      {alertCount} alertas
                    </span>
                  )}
                </div>
                <p className="text-[0.7rem] text-muted-foreground/60">
                  Agente IA que analiza convergencia de señales y genera alertas automáticas
                </p>
              </div>
              <ChevronRight size={14} className="text-muted-foreground/40 group-hover:text-primary transition-colors shrink-0" />
            </Link>
          </div>
        )
      })()}

      {/* Earnings Warning Banner */}
      {earningsWarnings.length > 0 && (
        <div className="mb-5 animate-fade-in-up">
          <div className="flex items-start gap-3 px-4 py-3 rounded-lg border border-amber-500/30 bg-amber-500/8">
            <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">Earnings próximos</span>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {earningsWarnings.map(r => (
                  <span key={r.ticker} className="text-[0.7rem] font-mono font-bold text-amber-300 px-2 py-0.5 rounded bg-amber-500/15">
                    {r.ticker}
                    {r.days_to_earnings != null && r.days_to_earnings <= 7 && (
                      <span className="ml-1 font-normal text-amber-400/70">{r.days_to_earnings}d</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Portfolio Action Items */}
      {actionItems.length > 0 && (
        <div className="mb-5 animate-fade-in-up">
          <Card className="glass border border-primary/20">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Wallet size={14} className="text-primary" />
                <span className="text-[0.62rem] font-bold uppercase tracking-widest text-primary/70">Acciones pendientes · Mi Cartera</span>
                <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">{actionItems.length}</span>
              </div>
              <div className="space-y-1.5">
                {actionItems.slice(0, 8).map((item, i) => (
                  <Link
                    key={i}
                    to={item.link}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/10 border border-border/20 hover:bg-muted/20 hover:border-border/40 transition-colors group"
                  >
                    <span className={item.color}>{item.icon}</span>
                    <span className="text-[0.75rem] text-foreground/80 flex-1">{item.text}</span>
                    <ChevronRight size={11} className="text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Daily AI Briefing */}
      {briefingRaw?.narrative && (
        <div className="mb-5 animate-fade-in-up">
          <AiNarrativeCard
            narrative={briefingRaw.narrative}
            label={`Briefing del día · ${briefingRaw.date ?? ''} · Régimen ${briefingRaw.macro_regime ?? ''}`}
          />
        </div>
      )}

      {/* Market Regime + Portfolio Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <RegimeCard label="Mercado US" data={usRegime} loading={loadingRegime} />
        <RegimeCard label="Mercado EU" data={euRegime} loading={loadingRegime} />
        <StatCard
          label={winRateIsConviction ? 'Win Rate 7d (≥55pts)' : 'Win Rate 7d (base)'}
          value={winRate7d?.win_rate != null ? `${winRate7d.win_rate.toFixed(1)}%` : '—'}
          countTo={winRate7d?.win_rate ?? undefined}
          countDecimals={1}
          countSuffix="%"
          sub={winRate7d ? (
            <span>
              Avg <span className={winRate7d.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                {pct(winRate7d.avg_return)}
              </span> · {winRate7d.count} señales
            </span>
          ) : 'Sin datos de retorno aún'}
          color={winRateColor()}
          loading={false}
        />
        <StatCard
          label="Señales Activas"
          value={signalsNum ?? '—'}
          countTo={signalsNum ?? undefined}
          sub={totalSignals > 0 ? `${totalSignals} señales totales` : 'Sin datos de portfolio'}
          loading={false}
        />
      </div>

      {/* Setup del día — hero card */}
      {bestPick && (
        <Link to="/value" className="block mb-6 group">
          <div className="glass rounded-2xl overflow-clip border border-emerald-500/25 animate-fade-in-up transition-all duration-200 group-hover:border-emerald-500/50 group-hover:bg-emerald-500/6">
            {/* Thin accent top bar */}
            <div className="h-0.5 bg-gradient-to-r from-emerald-500/60 via-emerald-400/80 to-emerald-500/20" />
            <div className="p-5">
              {/* Header row */}
              <div className="flex items-center justify-between mb-4">
                <span className="text-[0.58rem] font-bold tracking-[0.18em] text-emerald-400/60 uppercase">
                  Setup del día
                </span>
                <span className="inline-flex items-center gap-1 text-[0.58rem] font-bold text-emerald-400/80 tracking-wide">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LISTO
                </span>
              </div>
              {/* Main content */}
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-3xl font-black tracking-tight text-foreground group-hover:text-emerald-400 transition-colors">
                    {bestPick.ticker}
                  </div>
                  <div className="text-xs text-muted-foreground/70 mt-0.5 truncate">{bestPick.company_name}</div>
                  {/* Metrics row */}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
                    {bestPick.analyst_upside_pct != null && (
                      <div>
                        <div className="text-[0.58rem] text-muted-foreground/40 uppercase tracking-wider">Upside</div>
                        <div className="text-sm font-bold text-emerald-400">+{bestPick.analyst_upside_pct.toFixed(0)}%</div>
                      </div>
                    )}
                    {bestPick.fcf_yield_pct != null && (
                      <div>
                        <div className="text-[0.58rem] text-muted-foreground/40 uppercase tracking-wider">FCF Yield</div>
                        <div className="text-sm font-semibold text-foreground/80">{bestPick.fcf_yield_pct.toFixed(1)}%</div>
                      </div>
                    )}
                    {bestPick.risk_reward_ratio != null && (
                      <div>
                        <div className="text-[0.58rem] text-muted-foreground/40 uppercase tracking-wider">R:R</div>
                        <div className="text-sm font-semibold text-foreground/80">{bestPick.risk_reward_ratio.toFixed(1)}x</div>
                      </div>
                    )}
                    {bestPick.sector && (
                      <div>
                        <div className="text-[0.58rem] text-muted-foreground/40 uppercase tracking-wider">Sector</div>
                        <div className="text-xs text-muted-foreground/70 truncate max-w-[100px]">{bestPick.sector}</div>
                      </div>
                    )}
                  </div>
                </div>
                {/* Score ring */}
                <div className="flex-shrink-0">
                  <ScoreRing score={bestPick.value_score ?? 0} size="lg" />
                </div>
              </div>
            </div>
          </div>
        </Link>
      )}

      {/* Top VALUE Picks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <TopPicksTable title="Top VALUE US" rows={topUS} to="/value" loading={loadingUS} />
        <TopPicksTable title="Top VALUE EU" rows={topEU} to="/value-eu" loading={loadingEU} />
      </div>

      {/* Signals Radar: Macro + Insiders + Options + Mean Reversion */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MacroRadarMini data={macroRaw} loading={loadingMacro} />
        <InsidersMini data={insiders?.data} loading={loadingInsiders} />
        <OptionsFlowMini data={optionsRaw} loading={loadingOptions} />
        <MeanReversionMini data={mrRaw} loading={loadingMR} />
      </div>

      {/* Cerebro widgets: Entradas + Convergencia + Breadth + Watchlist Alerts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <EntrySignalsMini data={cerebroEntry} loading={loadingEntry} />
        <ConvergenciaMini loading={loadingConv} data={cerebroConv} />
        <BreadthMini data={breadthRaw ?? undefined} loading={loadingBreadth} />
        <WatchlistAlertsMini
          alerts={cerebroAlertsRaw?.alerts}
          watchlistTickers={watchlistTickers}
          loading={loadingAlerts}
        />
      </div>

      {/* Portfolio News */}
      <div className="mb-6">
        <PortfolioNewsWidget data={portfolioNewsRaw} loading={loadingPortfolioNews} />
      </div>

    </>
  )
}
