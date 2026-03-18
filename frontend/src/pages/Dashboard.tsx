import { Link } from 'react-router-dom'
import {
  fetchMarketRegime, fetchValueOpportunities, fetchEUValueOpportunities,
  fetchPortfolioTracker, fetchRecurringInsiders, fetchOptionsFlow, fetchMeanReversion,
  fetchMacroRadar, fetchDailyBriefing,
  type ValueOpportunity, type InsiderData, type PortfolioSummary,
} from '../api/client'
import AiNarrativeCard from '../components/AiNarrativeCard'
import { useApi } from '../hooks/useApi'
import { useCountUp } from '../hooks/useCountUp'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import GradeBadge from '../components/GradeBadge'
import InfoTooltip from '../components/InfoTooltip'
import TickerLogo from '../components/TickerLogo'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, ChevronRight, Radar, Wallet, Zap } from 'lucide-react'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'

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

  const { positions: myPositions } = usePersonalPortfolio()
  const myTickers = new Set(myPositions.map(p => p.ticker.toUpperCase()))

  const pf = (portfolio as PortfolioSummary) ?? {}
  const overall = pf.overall as Record<string, { count: number; win_rate: number; avg_return: number }> | undefined

  const topUS = (valueUS?.data ?? []).slice(0, 5)
  const topEU = (valueEU?.data ?? []).slice(0, 5)

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

  const winRate7d = overall?.['7d']
  const totalSignals = pf.total_signals ?? 0
  const activeSignals = pf.active_signals ?? totalSignals

  function winRateColor() {
    if (winRate7d?.win_rate == null) return 'text-muted-foreground'
    if (winRate7d.win_rate >= 55) return 'text-emerald-400'
    if (winRate7d.win_rate >= 45) return 'text-amber-400'
    return 'text-red-400'
  }

  const signalsNum = activeSignals > 0 ? activeSignals : totalSignals > 0 ? totalSignals : null

  return (
    <>
      {/* Header */}
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Dashboard</h2>
        <p className="text-sm text-muted-foreground">
          Resumen ejecutivo · Actualización diaria automática
        </p>
      </div>

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
          label="Win Rate 7d"
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

      {/* Top VALUE Picks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <TopPicksTable title="Top VALUE US" rows={topUS} to="/value" loading={loadingUS} />
        <TopPicksTable title="Top VALUE EU" rows={topEU} to="/value-eu" loading={loadingEU} />
      </div>

      {/* Signals Radar: Macro + Insiders + Options + Mean Reversion */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MacroRadarMini data={macroRaw} loading={loadingMacro} />
        <InsidersMini data={insiders?.data} loading={loadingInsiders} />
        <OptionsFlowMini data={optionsRaw} loading={loadingOptions} />
        <MeanReversionMini data={mrRaw} loading={loadingMR} />
      </div>

      {/* Quick Nav Cards */}
      <div>
        <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-3 px-1">
          Ir a
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {[
            { to: '/value',          label: 'VALUE US',      color: 'text-emerald-400' },
            { to: '/value-eu',       label: 'VALUE EU',      color: 'text-blue-400' },
            { to: '/insiders',       label: 'Insiders',      color: 'text-purple-400' },
            { to: '/options',        label: 'Options',       color: 'text-pink-400' },
            { to: '/portfolio',      label: 'Portfolio',     color: 'text-green-400' },
            { to: '/datos',          label: 'Datos & CSV',   color: 'text-slate-400' },
          ].map(nav => (
            <Link
              key={nav.to}
              to={nav.to}
              className="flex items-center justify-between px-3.5 py-2.5 rounded-lg border border-border/40 bg-white/3 hover:bg-white/6 hover:border-border/60 transition-colors group"
            >
              <span className={`text-xs font-semibold ${nav.color}`}>{nav.label}</span>
              <ChevronRight size={12} className="text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
            </Link>
          ))}
        </div>
      </div>
    </>
  )
}
