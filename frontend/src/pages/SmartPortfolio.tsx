import { fetchSmartPortfolio } from '../api/client'
import type { SmartPortfolioPick } from '../api/client'
import { useApi } from '../hooks/useApi'
import AiNarrativeCard from '../components/AiNarrativeCard'
import TickerLogo from '../components/TickerLogo'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Sparkles, ShieldAlert, TrendingUp, Wallet, AlertCircle, CheckCircle2 } from 'lucide-react'

const GRADE_COLOR: Record<string, string> = {
  A: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10',
  B: 'text-blue-400 border-blue-500/40 bg-blue-500/10',
  C: 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10',
}

const REGIME_COLORS: Record<string, string> = {
  CALM:   'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  WATCH:  'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  STRESS: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  ALERT:  'text-red-400 bg-red-500/10 border-red-500/30',
  CRISIS: 'text-red-500 bg-red-500/15 border-red-500/40',
}

function AllocationBar({ pick }: { pick: SmartPortfolioPick }) {
  const grade = pick.conviction_grade || 'C'
  const barColor = grade === 'A' ? '#10b981' : grade === 'B' ? '#3b82f6' : '#eab308'

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(100, pick.allocation_pct * 2)}%`, backgroundColor: barColor }}
        />
      </div>
      <span className="text-xs font-bold tabular-nums" style={{ color: barColor }}>
        {pick.allocation_pct.toFixed(1)}%
      </span>
    </div>
  )
}

function PickRow({ pick, rank }: { pick: SmartPortfolioPick; rank: number }) {
  const gradeCls = GRADE_COLOR[pick.conviction_grade] || GRADE_COLOR['C']

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 border-b border-border/20 last:border-0 hover:bg-muted/5 transition-colors">
      {/* Rank + Ticker */}
      <div className="flex items-center gap-2 min-w-[100px]">
        <span className="text-[0.6rem] text-muted-foreground/50 font-bold w-4">#{rank}</span>
        <TickerLogo ticker={pick.ticker} size="xs" />
        <div>
          <div className="font-mono font-bold text-sm text-primary leading-tight">{pick.ticker}</div>
          <div className="text-[0.6rem] text-muted-foreground/60 truncate max-w-[80px]">{pick.sector}</div>
        </div>
      </div>

      {/* Company */}
      <div className="flex-1 min-w-[120px]">
        <div className="text-xs text-foreground/80 truncate">{pick.company}</div>
        {pick.current_price != null && (
          <div className="text-[0.6rem] text-muted-foreground/60">${pick.current_price.toFixed(2)}</div>
        )}
      </div>

      {/* Grade */}
      <span className={`text-xs font-bold px-2 py-0.5 rounded border ${gradeCls}`}>
        {pick.conviction_grade}
      </span>

      {/* Score */}
      <div className="text-center min-w-[38px]">
        <div className="text-sm font-bold text-foreground">{pick.value_score.toFixed(0)}</div>
        <div className="text-[0.55rem] text-muted-foreground/50">score</div>
      </div>

      {/* Metrics */}
      <div className="flex items-center gap-3 text-xs">
        {pick.analyst_upside_pct != null && (
          <div className="text-center">
            <div className={`font-bold ${pick.analyst_upside_pct >= 15 ? 'text-emerald-400' : 'text-foreground/70'}`}>
              +{pick.analyst_upside_pct.toFixed(0)}%
            </div>
            <div className="text-muted-foreground/50 text-[0.55rem]">upside</div>
          </div>
        )}
        {pick.fcf_yield_pct != null && (
          <div className="text-center">
            <div className={`font-bold ${pick.fcf_yield_pct >= 5 ? 'text-emerald-400' : 'text-foreground/60'}`}>
              {pick.fcf_yield_pct.toFixed(1)}%
            </div>
            <div className="text-muted-foreground/50 text-[0.55rem]">FCF</div>
          </div>
        )}
        {pick.risk_reward_ratio != null && (
          <div className="text-center">
            <div className={`font-bold ${pick.risk_reward_ratio >= 2 ? 'text-emerald-400' : 'text-foreground/60'}`}>
              {pick.risk_reward_ratio.toFixed(1)}x
            </div>
            <div className="text-muted-foreground/50 text-[0.55rem]">R:R</div>
          </div>
        )}
        {pick.days_to_earnings != null && pick.days_to_earnings <= 21 && (
          <div className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded border ${pick.earnings_catalyst ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-orange-400 border-orange-500/30 bg-orange-500/10'}`}>
            {pick.days_to_earnings}d earn
          </div>
        )}
      </div>

      {/* Allocation bar */}
      <AllocationBar pick={pick} />
    </div>
  )
}

export default function SmartPortfolio() {
  const { data, loading, error } = useApi(() => fetchSmartPortfolio(), [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  if (!data) return <ErrorState message="Sin datos de portfolio" />

  const regimeCls = REGIME_COLORS[data.regime_name] || REGIME_COLORS['WATCH']
  const cashPct = data.cash_pct
  const investedPct = data.invested_pct

  // Sector breakdown
  const sectorMap: Record<string, number> = {}
  for (const p of data.picks) {
    sectorMap[p.sector] = (sectorMap[p.sector] || 0) + 1
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={18} className="text-primary" />
            <h1 className="text-2xl font-bold text-foreground">Smart Portfolio</h1>
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${regimeCls}`}>
              {data.regime_name}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Cartera algorítmica construida combinando Macro Radar, VALUE scores, conviction y diversificación sectorial
          </p>
        </div>
        <span className="text-xs text-muted-foreground self-start">{data.date}</span>
      </div>

      {data.portfolio_thesis && (
        <AiNarrativeCard narrative={data.portfolio_thesis} label="Tesis del Portfolio Algorítmico" className="mb-5" />
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="glass border border-primary/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp size={14} className="text-primary" />
              <span className="text-xs text-muted-foreground">Picks</span>
            </div>
            <div className="text-2xl font-bold text-primary">{data.total_picks}</div>
            <div className="text-[0.6rem] text-muted-foreground/60 mt-0.5">posiciones activas</div>
          </CardContent>
        </Card>

        <Card className="glass border border-emerald-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Wallet size={14} className="text-emerald-400" />
              <span className="text-xs text-muted-foreground">Invertido</span>
            </div>
            <div className="text-2xl font-bold text-emerald-400">{investedPct.toFixed(1)}%</div>
            <div className="text-[0.6rem] text-muted-foreground/60 mt-0.5">del portfolio</div>
          </CardContent>
        </Card>

        <Card className="glass border border-yellow-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <ShieldAlert size={14} className="text-yellow-400" />
              <span className="text-xs text-muted-foreground">Cash buffer</span>
            </div>
            <div className="text-2xl font-bold text-yellow-400">{cashPct}%</div>
            <div className="text-[0.6rem] text-muted-foreground/60 mt-0.5">reserva liquidez</div>
          </CardContent>
        </Card>

        <Card className={`glass border ${regimeCls.includes('emerald') ? 'border-emerald-500/20' : regimeCls.includes('yellow') ? 'border-yellow-500/20' : 'border-red-500/20'}`}>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-muted-foreground">R:R mín</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{data.params.require_rr}x</div>
            <div className="text-[0.6rem] text-muted-foreground/60 mt-0.5">requerido ({data.regime_name})</div>
          </CardContent>
        </Card>
      </div>

      {/* Allocation visualization */}
      <Card className="glass border border-border/40">
        <CardContent className="p-4">
          <div className="text-xs font-semibold text-muted-foreground mb-3">Distribución del portfolio</div>
          <div className="flex h-5 rounded-lg overflow-hidden gap-0.5">
            {data.picks.map((p, i) => {
              const colors = ['#6366f1','#10b981','#3b82f6','#f97316','#a855f7','#ec4899','#14b8a6']
              const color = colors[i % colors.length]
              return (
                <div
                  key={p.ticker}
                  className="h-full transition-all flex items-center justify-center overflow-hidden"
                  style={{ width: `${p.allocation_pct}%`, backgroundColor: color, opacity: 0.85 }}
                  title={`${p.ticker}: ${p.allocation_pct.toFixed(1)}%`}
                >
                  {p.allocation_pct > 7 && (
                    <span className="text-[0.55rem] font-bold text-white truncate px-0.5">{p.ticker}</span>
                  )}
                </div>
              )
            })}
            {/* Cash segment */}
            <div
              className="h-full flex items-center justify-center overflow-hidden"
              style={{ width: `${cashPct}%`, backgroundColor: '#64748b', opacity: 0.5 }}
              title={`Cash: ${cashPct}%`}
            >
              {cashPct > 7 && <span className="text-[0.55rem] font-bold text-white px-0.5">CASH</span>}
            </div>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
            {data.picks.map((p, i) => {
              const colors = ['#6366f1','#10b981','#3b82f6','#f97316','#a855f7','#ec4899','#14b8a6']
              const color = colors[i % colors.length]
              return (
                <div key={p.ticker} className="flex items-center gap-1 text-[0.6rem] text-muted-foreground">
                  <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
                  {p.ticker} {p.allocation_pct.toFixed(1)}%
                </div>
              )
            })}
            <div className="flex items-center gap-1 text-[0.6rem] text-muted-foreground">
              <div className="w-2 h-2 rounded-sm bg-slate-500 opacity-50" />
              CASH {cashPct}%
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Picks list */}
      {data.picks.length > 0 ? (
        <Card className="glass border border-border/40">
          <CardContent className="p-0">
            <div className="px-4 py-3 border-b border-border/30">
              <span className="text-xs font-semibold text-muted-foreground">
                {data.total_picks} posiciones · ordenadas por ranking algorítmico
              </span>
            </div>
            {data.picks.map((pick, i) => (
              <PickRow key={pick.ticker} pick={pick} rank={i + 1} />
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card className="glass border border-border/40">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            No se encontraron picks que superen los criterios del régimen {data.regime_name}
          </CardContent>
        </Card>
      )}

      {/* AI Thesis */}
      {data.portfolio_thesis && (
        <Card className="glass border border-primary/20 bg-primary/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles size={14} className="text-primary" />
              <span className="text-xs font-semibold text-primary">Tesis del portfolio (IA)</span>
            </div>
            <p className="text-sm text-foreground/85 leading-relaxed">{data.portfolio_thesis}</p>
          </CardContent>
        </Card>
      )}

      {/* Risk Notes */}
      {data.risk_notes.length > 0 && (
        <Card className="glass border border-border/30">
          <CardContent className="p-4 space-y-2">
            <div className="text-xs font-semibold text-muted-foreground mb-1">Notas de riesgo</div>
            {data.risk_notes.map((note, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <AlertCircle size={12} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                {note}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Methodology footer */}
      <Card className="glass border border-border/30">
        <CardContent className="p-3 space-y-1 text-xs text-muted-foreground">
          <div className="font-semibold text-foreground/70 mb-2">Metodología</div>
          <div className="flex items-start gap-1.5"><CheckCircle2 size={10} className="text-emerald-400 mt-0.5 flex-shrink-0" /> Score mínimo: {data.params.min_score} pts (ajustado al régimen {data.regime_name})</div>
          <div className="flex items-start gap-1.5"><CheckCircle2 size={10} className="text-emerald-400 mt-0.5 flex-shrink-0" /> R:R mínimo: {data.params.require_rr}x | Máx 2 posiciones por sector</div>
          <div className="flex items-start gap-1.5"><CheckCircle2 size={10} className="text-emerald-400 mt-0.5 flex-shrink-0" /> Excluye dividend traps HIGH-risk ({data.trap_tickers_excluded.length > 0 ? data.trap_tickers_excluded.slice(0, 5).join(', ') + (data.trap_tickers_excluded.length > 5 ? '...' : '') : 'ninguno'})</div>
          <div className="flex items-start gap-1.5"><CheckCircle2 size={10} className="text-emerald-400 mt-0.5 flex-shrink-0" /> Ponderación por conviction grade: A +2pts, C -2pts, normalizado al {100 - cashPct}% invertible</div>
        </CardContent>
      </Card>
    </div>
  )
}
