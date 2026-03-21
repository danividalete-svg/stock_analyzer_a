import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchCerebroInsights, fetchCerebroConvergence, fetchCerebroAlerts, fetchCerebroCalibration,
  type CerebroTier, type CerebroAlert,
} from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import AiNarrativeCard from '../components/AiNarrativeCard'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import TickerLogo from '../components/TickerLogo'
import { Brain, Crosshair, Bell, SlidersHorizontal, TrendingUp, TrendingDown, Minus, ChevronRight } from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────

function WrBar({ wr, baseline }: { wr: number; baseline: number }) {
  const color = wr >= baseline + 10 ? 'bg-emerald-500' : wr >= baseline ? 'bg-blue-500' : wr >= baseline - 10 ? 'bg-amber-500' : 'bg-red-500'
  const delta = wr - baseline
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, wr)}%` }} />
      </div>
      <span className="tabular-nums text-[0.75rem] font-bold w-10 text-right">{wr.toFixed(0)}%</span>
      <span className={`tabular-nums text-[0.65rem] w-12 text-right ${delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {delta >= 0 ? '+' : ''}{delta.toFixed(1)}pp
      </span>
    </div>
  )
}

function TierCard({ tier, baseline }: { tier: CerebroTier; baseline: number }) {
  return (
    <div className="rounded-lg border border-border/30 bg-muted/10 px-3 py-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[0.72rem] font-semibold text-foreground/80">{tier.label}</span>
        <span className="text-[0.6rem] text-muted-foreground/60 tabular-nums">n={tier.n}</span>
      </div>
      <WrBar wr={tier.win_rate_7d} baseline={baseline} />
      <div className="text-[0.6rem] text-muted-foreground mt-1 tabular-nums">
        Ret. medio: <span className={tier.avg_return_7d >= 0 ? 'text-emerald-400' : 'text-red-400'}>
          {tier.avg_return_7d >= 0 ? '+' : ''}{tier.avg_return_7d.toFixed(2)}%
        </span>
      </div>
    </div>
  )
}

function alertIcon(type: string) {
  if (type === 'MR_ZONE')         return <TrendingDown size={13} className="text-teal-400" />
  if (type === 'INSIDER_BUYING')  return <TrendingUp size={13} className="text-purple-400" />
  if (type === 'EARNINGS_WARNING') return <Bell size={13} className="text-amber-400" />
  if (type === 'NEW_CONVERGENCE') return <Crosshair size={13} className="text-cyan-400" />
  return <Minus size={13} className="text-muted-foreground" />
}

function alertColor(severity: CerebroAlert['severity']) {
  if (severity === 'HIGH')   return 'border-red-500/25 bg-red-500/5'
  if (severity === 'MEDIUM') return 'border-amber-500/20 bg-amber-500/5'
  return 'border-border/30 bg-muted/5'
}

function strategyBadge(s: string) {
  const styles: Record<string, string> = {
    VALUE:    'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    INSIDERS: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
    MR:       'bg-teal-500/15 text-teal-400 border-teal-500/30',
    OPTIONS:  'bg-pink-500/15 text-pink-400 border-pink-500/30',
    MOMENTUM: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  }
  return (
    <span key={s} className={`text-[0.55rem] font-bold px-1.5 py-0.5 rounded border ${styles[s] ?? 'bg-muted/15 text-muted-foreground border-border/30'}`}>
      {s}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Cerebro() {
  const { data: insights,    loading: loadingI } = useApi(() => fetchCerebroInsights(), [])
  const { data: convergence, loading: loadingC } = useApi(() => fetchCerebroConvergence(), [])
  const { data: alertsData,  loading: loadingA } = useApi(() => fetchCerebroAlerts(), [])
  const { data: calibration, loading: loadingCal } = useApi(() => fetchCerebroCalibration(), [])
  const [activeTab, setActiveTab] = useState<'convergence' | 'insights' | 'alerts' | 'calibration'>('convergence')

  const loading = loadingI && loadingC && loadingA && loadingCal
  if (loading) return <Loading />
  const anyError = !insights && !convergence && !alertsData
  if (anyError) return <ErrorState message="CEREBRO aún no ha generado datos. Ejecuta cerebro.py primero." />

  const baseline = insights?.baseline_win_rate_7d ?? 50
  const signals  = convergence?.convergences ?? []
  const alerts   = alertsData?.alerts ?? []

  const tabs = [
    { id: 'convergence' as const,  label: 'Convergencias',   icon: Crosshair,        count: convergence?.total_convergences },
    { id: 'insights' as const,     label: 'Patrones',         icon: Brain,            count: insights?.total_analyzed },
    { id: 'alerts' as const,       label: 'Alertas',          icon: Bell,             count: alertsData?.high_count, highlight: (alertsData?.high_count ?? 0) > 0 },
    { id: 'calibration' as const,  label: 'Calibración',      icon: SlidersHorizontal, count: calibration?.total_recommendations },
  ]

  return (
    <>
      {/* Header */}
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title flex items-center gap-2">
          <Brain size={22} className="text-violet-400" />
          Cerebro — IA Proactiva
        </h2>
        <p className="text-sm text-muted-foreground">
          Agente autónomo · Aprende de {insights?.total_analyzed ?? '—'} señales históricas · Actualización diaria
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Señales analizadas', value: insights?.total_analyzed ?? '—', color: 'text-violet-400', sub: 'histórico' },
          { label: 'Win rate base',      value: insights ? `${insights.baseline_win_rate_7d.toFixed(1)}%` : '—', color: insights?.baseline_win_rate_7d != null ? (insights.baseline_win_rate_7d >= 55 ? 'text-emerald-400' : insights.baseline_win_rate_7d >= 45 ? 'text-amber-400' : 'text-red-400') : '', sub: '7d sistema' },
          { label: 'Convergencias hoy', value: convergence?.total_convergences ?? '—', color: 'text-cyan-400', sub: `${convergence?.triple_or_more ?? 0} triples` },
          { label: 'Alertas HIGH',       value: alertsData?.high_count ?? '—', color: (alertsData?.high_count ?? 0) > 0 ? 'text-red-400' : 'text-muted-foreground', sub: `${alertsData?.total ?? 0} total` },
        ].map(s => (
          <Card key={s.label} className="glass p-5">
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{s.label}</div>
            <div className={`text-3xl font-extrabold tabular-nums leading-none mb-1 ${s.color}`}>{s.value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{s.sub}</div>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-border/40 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors -mb-px ${
              activeTab === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <tab.icon size={12} />
            {tab.label}
            {tab.count != null && (
              <span className={`text-[0.6rem] px-1.5 py-0.5 rounded-full font-bold ${
                tab.highlight ? 'bg-red-500/20 text-red-400' : 'bg-muted/30 text-muted-foreground'
              }`}>{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── TAB: Convergencias ─────────────────────────────────────────────────── */}
      {activeTab === 'convergence' && (
        <div className="space-y-4 animate-fade-in-up">
          {signals.length === 0 ? (
            <Card className="glass"><CardContent className="py-12 text-center text-muted-foreground">Sin convergencias detectadas hoy</CardContent></Card>
          ) : (
            signals.map(sig => (
              <Card key={sig.ticker} className={`glass border ${sig.strategy_count >= 3 ? 'border-amber-500/30' : 'border-border/40'}`}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <TickerLogo ticker={sig.ticker} size="sm" className="mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <Link to={`/search?q=${sig.ticker}`} className="font-mono font-bold text-primary text-[0.9rem] hover:underline">
                          {sig.ticker}
                        </Link>
                        {sig.strategy_count >= 3 && (
                          <span className="text-[0.55rem] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">TRIPLE</span>
                        )}
                        {sig.strategies.map(s => strategyBadge(s))}
                        {sig.conviction_grade && <Badge variant={sig.conviction_grade === 'A' ? 'green' : sig.conviction_grade === 'B' ? 'blue' : 'yellow'} className="text-[0.6rem]">{sig.conviction_grade}</Badge>}
                      </div>
                      <div className="text-[0.72rem] text-muted-foreground mb-2">{sig.company_name} · {sig.sector}</div>
                      <div className="flex flex-wrap gap-3 text-[0.72rem] mb-2">
                        {sig.value_score != null && <span>Score: <strong className="text-foreground">{sig.value_score.toFixed(0)}</strong></span>}
                        {sig.analyst_upside_pct != null && <span>Upside: <strong className={sig.analyst_upside_pct >= 10 ? 'text-emerald-400' : 'text-foreground'}>{sig.analyst_upside_pct >= 0 ? '+' : ''}{sig.analyst_upside_pct.toFixed(1)}%</strong></span>}
                        {sig.fcf_yield_pct != null && <span>FCF: <strong className={sig.fcf_yield_pct >= 5 ? 'text-emerald-400' : 'text-foreground'}>{sig.fcf_yield_pct.toFixed(1)}%</strong></span>}
                        <span className="ml-auto text-muted-foreground/60">Conv. score: {sig.convergence_score}</span>
                      </div>
                      {sig.analysis && (
                        <p className="text-[0.75rem] text-foreground/70 leading-relaxed border-l-2 border-violet-500/40 pl-2">
                          {sig.analysis}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* ── TAB: Patrones aprendidos ───────────────────────────────────────────── */}
      {activeTab === 'insights' && (
        <div className="space-y-5 animate-fade-in-up">
          {insights?.narrative && (
            <AiNarrativeCard narrative={insights.narrative} label="Lo que el sistema aprendió" />
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Score tiers */}
            <Card className="glass">
              <CardContent className="p-4">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Win rate por score</div>
                <div className="space-y-2">
                  {(insights?.score_tiers ?? []).map(t => <TierCard key={t.label} tier={t} baseline={baseline} />)}
                  {!insights?.score_tiers?.length && <p className="text-sm text-muted-foreground">Sin datos</p>}
                </div>
              </CardContent>
            </Card>

            {/* Regimes */}
            <Card className="glass">
              <CardContent className="p-4">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Win rate por régimen</div>
                <div className="space-y-2">
                  {(insights?.market_regimes ?? []).map(t => <TierCard key={t.label} tier={t} baseline={baseline} />)}
                  {!insights?.market_regimes?.length && <p className="text-sm text-muted-foreground">Sin datos</p>}
                </div>
              </CardContent>
            </Card>

            {/* FCF */}
            <Card className="glass">
              <CardContent className="p-4">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Efecto FCF Yield</div>
                <div className="space-y-2">
                  {(insights?.fcf_tiers ?? []).map(t => <TierCard key={t.label} tier={t} baseline={baseline} />)}
                  {!insights?.fcf_tiers?.length && <p className="text-sm text-muted-foreground">Sin datos</p>}
                </div>
              </CardContent>
            </Card>

            {/* Best combos */}
            <Card className="glass">
              <CardContent className="p-4">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Mejores combinaciones</div>
                <div className="space-y-2">
                  {(insights?.best_combos ?? []).map(t => <TierCard key={t.label} tier={t} baseline={baseline} />)}
                  {!insights?.best_combos?.length && <p className="text-sm text-muted-foreground">Sin datos suficientes aún</p>}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Sectors */}
          {(insights?.sectors ?? []).length > 0 && (
            <Card className="glass">
              <CardContent className="p-4">
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Win rate por sector (top 8)</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {(insights?.sectors ?? []).slice(0, 8).map(t => <TierCard key={t.label} tier={t} baseline={baseline} />)}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ── TAB: Alertas ──────────────────────────────────────────────────────── */}
      {activeTab === 'alerts' && (
        <div className="space-y-2 animate-fade-in-up">
          {alerts.length === 0 ? (
            <Card className="glass"><CardContent className="py-12 text-center text-muted-foreground">Sin alertas activas hoy</CardContent></Card>
          ) : (
            alerts.map((alert, i) => (
              <div key={`${alert.ticker}-${alert.type}-${i}`} className={`flex items-start gap-3 p-4 rounded-xl border ${alertColor(alert.severity)}`}>
                <div className="mt-0.5 shrink-0">{alertIcon(alert.type)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <Link to={`/search?q=${alert.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">
                      {alert.ticker}
                    </Link>
                    <span className={`text-[0.55rem] font-bold px-1.5 py-0.5 rounded border ${
                      alert.severity === 'HIGH'
                        ? 'bg-red-500/15 text-red-400 border-red-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}>{alert.severity}</span>
                    <span className="text-[0.65rem] font-semibold text-foreground/80">{alert.title}</span>
                  </div>
                  <p className="text-[0.72rem] text-muted-foreground leading-relaxed">{alert.message}</p>
                </div>
                <Link to={`/search?q=${alert.ticker}`} className="shrink-0 text-muted-foreground/40 hover:text-muted-foreground mt-0.5">
                  <ChevronRight size={14} />
                </Link>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── TAB: Calibración ─────────────────────────────────────────────────── */}
      {activeTab === 'calibration' && (
        <div className="space-y-4 animate-fade-in-up">
          {calibration?.narrative && (
            <AiNarrativeCard narrative={calibration.narrative} label="Recomendaciones de auto-mejora" />
          )}
          {(calibration?.recommendations ?? []).length === 0 ? (
            <Card className="glass"><CardContent className="py-12 text-center text-muted-foreground">
              Se necesitan más señales completadas para generar recomendaciones.
            </CardContent></Card>
          ) : (
            <Card className="glass">
              <CardContent className="p-4">
                <div className="space-y-3">
                  {(calibration?.recommendations ?? []).map((rec, i) => (
                    <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${
                      rec.type === 'BOOST' ? 'bg-emerald-500/5 border-emerald-500/20' :
                      rec.type === 'REDUCE' ? 'bg-red-500/5 border-red-500/20' :
                      'bg-amber-500/5 border-amber-500/20'
                    }`}>
                      <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded border shrink-0 mt-0.5 ${
                        rec.type === 'BOOST' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                        rec.type === 'REDUCE' ? 'bg-red-500/15 text-red-400 border-red-500/30' :
                        'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      }`}>{rec.type}</span>
                      <div>
                        <div className="text-[0.75rem] font-semibold text-foreground/80 mb-0.5">{rec.factor}</div>
                        <p className="text-[0.72rem] text-muted-foreground leading-relaxed">{rec.insight}</p>
                        <span className="text-[0.6rem] text-muted-foreground/50">n={rec.n} señales</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          {loadingCal && <Loading />}
        </div>
      )}
    </>
  )
}
