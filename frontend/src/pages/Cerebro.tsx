import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchCerebroInsights, fetchCerebroConvergence, fetchCerebroAlerts, fetchCerebroCalibration,
  fetchCerebroEntrySignals, fetchCerebroExitSignals, fetchCerebroValueTraps, fetchCerebroSmartMoney,
  fetchCerebroInsiderClusters, fetchCerebroDividendSafety, fetchCerebroPiotroski,
  fetchCerebroStressTest, fetchCerebroBriefing,
  type CerebroTier, type CerebroAlert, type EntrySignal,
} from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import AiNarrativeCard from '../components/AiNarrativeCard'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import TickerLogo from '../components/TickerLogo'
import {
  Brain, Crosshair, Bell, SlidersHorizontal, TrendingUp, TrendingDown, Minus, ChevronRight,
  Zap, CheckCircle2, XCircle, Newspaper, Bot, AlertOctagon, ShieldAlert,
  Building2, Users, Wallet, BarChart2, Activity,
} from 'lucide-react'

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

// ── Entry signal helpers ───────────────────────────────────────────────────────

const SIGNAL_STYLES: Record<EntrySignal['signal'], { label: string; border: string; bg: string; badge: string; scoreColor: string }> = {
  STRONG_BUY: { label: '🟢 STRONG BUY', border: 'border-emerald-500/60', bg: 'bg-emerald-500/15', badge: 'bg-emerald-500/25 text-emerald-400 border-emerald-500/40', scoreColor: 'text-emerald-400' },
  BUY:        { label: '🟡 BUY',         border: 'border-amber-500/50',   bg: 'bg-amber-500/10',  badge: 'bg-amber-500/25 text-amber-400 border-amber-500/40',      scoreColor: 'text-amber-400'   },
  MONITOR:    { label: '🔵 MONITOR',     border: 'border-blue-500/30',    bg: 'bg-blue-500/10',   badge: 'bg-blue-500/20 text-blue-400 border-blue-500/30',         scoreColor: 'text-blue-400'    },
  WAIT:       { label: '⚪ WAIT',        border: 'border-border/20',      bg: 'bg-transparent',   badge: 'bg-muted/20 text-muted-foreground border-border/30',      scoreColor: 'text-muted-foreground' },
}

function EntryScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : score >= 30 ? 'bg-blue-500' : 'bg-muted/40'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-muted/20 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="tabular-nums text-sm font-extrabold w-8 text-right">{score}</span>
    </div>
  )
}

function EntrySignalCard({ sig }: Readonly<{ sig: EntrySignal }>) {
  const style = SIGNAL_STYLES[sig.signal]
  const [expanded, setExpanded] = useState(false)
  return (
    <Card className={`glass border ${style.border} ${style.bg} transition-all`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <TickerLogo ticker={sig.ticker} size="sm" className="mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Link to={`/search?q=${sig.ticker}`} className="font-mono font-bold text-primary text-[0.9rem] hover:underline">
                {sig.ticker}
              </Link>
              <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded border ${style.badge}`}>{style.label}</span>
              {sig.conviction_grade && (
                <Badge variant={sig.conviction_grade === 'A' ? 'green' : sig.conviction_grade === 'B' ? 'blue' : 'yellow'} className="text-[0.6rem]">
                  {sig.conviction_grade}
                </Badge>
              )}
              <span className="text-[0.6rem] text-muted-foreground/50 ml-auto">{sig.region} · {sig.days_in_value}d en VALUE</span>
            </div>

            <div className="text-[0.72rem] text-muted-foreground mb-2">{sig.company_name} · {sig.sector}</div>

            {/* Score bar */}
            <div className="mb-2">
              <div className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-1">Entry score</div>
              <EntryScoreBar score={sig.entry_score} />
            </div>

            {/* Key metrics */}
            <div className="flex flex-wrap gap-3 text-[0.72rem] mb-2">
              {sig.value_score != null && <span>Score VALUE: <strong className="text-foreground">{sig.value_score.toFixed(0)}</strong></span>}
              {sig.analyst_upside_pct != null && <span>Upside: <strong className={sig.analyst_upside_pct >= 15 ? 'text-emerald-400' : 'text-foreground'}>{sig.analyst_upside_pct >= 0 ? '+' : ''}{sig.analyst_upside_pct.toFixed(1)}%</strong></span>}
              {sig.fcf_yield_pct != null && <span>FCF: <strong className={sig.fcf_yield_pct >= 5 ? 'text-emerald-400' : 'text-foreground'}>{sig.fcf_yield_pct.toFixed(1)}%</strong></span>}
              {sig.risk_reward_ratio != null && <span>R:R: <strong className={sig.risk_reward_ratio >= 2 ? 'text-emerald-400' : 'text-foreground'}>{sig.risk_reward_ratio.toFixed(1)}x</strong></span>}
              {sig.rsi != null && <span>RSI: <strong className={sig.rsi <= 30 ? 'text-teal-400' : 'text-foreground'}>{sig.rsi.toFixed(0)}</strong></span>}
            </div>

            {/* Signals fired */}
            {sig.signals_fired.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {sig.signals_fired.map(s => (
                  <span key={s} className="flex items-center gap-0.5 text-[0.6rem] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 size={9} /> {s}
                  </span>
                ))}
              </div>
            )}

            {/* Missing signals — toggle */}
            {sig.signals_missing.length > 0 && (
              <button
                onClick={() => setExpanded(e => !e)}
                className="flex items-center gap-1 text-[0.65rem] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
              >
                <XCircle size={10} className="text-red-400/60" />
                {expanded ? 'Ocultar' : `Ver qué falta (${sig.signals_missing.length})`}
                <ChevronRight size={10} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} />
              </button>
            )}
            {expanded && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {sig.signals_missing.map(s => (
                  <span key={s} className="flex items-center gap-0.5 text-[0.6rem] px-1.5 py-0.5 rounded bg-red-500/8 text-red-400/70 border border-red-500/15">
                    <XCircle size={9} /> {s}
                  </span>
                ))}
              </div>
            )}

            {sig.earnings_warning && sig.days_to_earnings != null && (
              <div className="mt-2 text-[0.65rem] text-amber-400 flex items-center gap-1">
                <Bell size={10} /> Earnings en {sig.days_to_earnings}d — riesgo de entrada
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Cerebro() {
  const { data: insights,    loading: loadingI }   = useApi(() => fetchCerebroInsights(), [])
  const { data: convergence, loading: loadingC }   = useApi(() => fetchCerebroConvergence(), [])
  const { data: alertsData,  loading: loadingA }   = useApi(() => fetchCerebroAlerts(), [])
  const { data: calibration, loading: loadingCal } = useApi(() => fetchCerebroCalibration(), [])
  const { data: entryData,   loading: loadingE }   = useApi(() => fetchCerebroEntrySignals(), [])
  const { data: exitData }    = useApi(() => fetchCerebroExitSignals(), [])
  const { data: trapsData }   = useApi(() => fetchCerebroValueTraps(), [])
  const { data: smData }      = useApi(() => fetchCerebroSmartMoney(), [])
  const { data: clustersData }= useApi(() => fetchCerebroInsiderClusters(), [])
  const { data: divData }     = useApi(() => fetchCerebroDividendSafety(), [])
  const { data: piotrData }   = useApi(() => fetchCerebroPiotroski(), [])
  const { data: stressData }  = useApi(() => fetchCerebroStressTest(), [])
  const { data: briefingData }= useApi(() => fetchCerebroBriefing(), [])

  const [activeTab, setActiveTab] = useState<'briefing' | 'entry' | 'convergence' | 'agents' | 'alerts' | 'insights' | 'calibration'>('briefing')
  const [entryFilter, setEntryFilter] = useState<'ACTIONABLE' | 'STRONG_BUY' | 'BUY' | 'MONITOR'>('ACTIONABLE')
  const [focusedIdx, setFocusedIdx] = useState(-1)

  const loading = loadingI && loadingC && loadingA && loadingCal && loadingE
  if (loading) return <Loading />
  const anyError = !insights && !convergence && !alertsData && !entryData
  if (anyError) return <ErrorState message="CEREBRO aún no ha generado datos. Ejecuta cerebro.py primero." />

  const baseline      = insights?.baseline_win_rate_7d ?? 50
  const signals       = convergence?.convergences ?? []
  const alerts        = alertsData?.alerts ?? []
  const entrySignals  = entryData?.signals ?? []
  const filteredEntry = entryFilter === 'ACTIONABLE'
    ? entrySignals.filter(s => s.signal === 'STRONG_BUY' || s.signal === 'BUY')
    : entrySignals.filter(s => s.signal === entryFilter)

  const pagedRef = useRef(filteredEntry)
  pagedRef.current = filteredEntry

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); setFocusedIdx(i => Math.min(i + 1, pagedRef.current.length - 1)) }
      if (e.key === 'k' || e.key === 'ArrowUp')   { e.preventDefault(); setFocusedIdx(i => Math.max(i - 1, 0)) }
      if (e.key === 'Escape') setFocusedIdx(-1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const tabs = [
    { id: 'briefing' as const,    label: 'Briefing',        icon: Newspaper,        count: undefined, highlight: !!briefingData?.narrative },
    { id: 'entry' as const,       label: 'Señales',         icon: Zap,              count: (entryData?.strong_buy ?? 0) + (entryData?.buy ?? 0), highlight: (entryData?.strong_buy ?? 0) > 0 },
    { id: 'convergence' as const, label: 'Convergencias',   icon: Crosshair,        count: convergence?.total_convergences },
    { id: 'agents' as const,      label: 'Agentes IA',      icon: Bot,              count: (exitData?.high_count ?? 0) + (trapsData?.high_count ?? 0), highlight: (exitData?.high_count ?? 0) + (trapsData?.high_count ?? 0) > 0 },
    { id: 'alerts' as const,      label: 'Alertas',         icon: Bell,             count: alertsData?.high_count, highlight: (alertsData?.high_count ?? 0) > 0 },
    { id: 'insights' as const,    label: 'Patrones',        icon: Brain,            count: insights?.total_analyzed },
    { id: 'calibration' as const, label: 'Calibración',     icon: SlidersHorizontal, count: calibration?.total_recommendations },
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
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        {[
          { label: 'Strong Buy hoy',    value: entryData?.strong_buy ?? '—',  color: (entryData?.strong_buy ?? 0) > 0 ? 'text-emerald-400' : 'text-muted-foreground', sub: `${entryData?.buy ?? 0} BUY · ${entryData?.monitor ?? 0} Monitor` },
          { label: 'Señales analizadas',value: insights?.total_analyzed ?? '—', color: 'text-violet-400', sub: 'histórico' },
          { label: 'Win rate base',     value: insights ? `${insights.baseline_win_rate_7d.toFixed(1)}%` : '—', color: insights?.baseline_win_rate_7d != null ? (insights.baseline_win_rate_7d >= 55 ? 'text-emerald-400' : insights.baseline_win_rate_7d >= 45 ? 'text-amber-400' : 'text-red-400') : '', sub: '7d sistema' },
          { label: 'Convergencias hoy', value: convergence?.total_convergences ?? '—', color: 'text-cyan-400', sub: `${convergence?.triple_or_more ?? 0} triples` },
          { label: 'Alertas HIGH',      value: alertsData?.high_count ?? '—', color: (alertsData?.high_count ?? 0) > 0 ? 'text-red-400' : 'text-muted-foreground', sub: `${alertsData?.total ?? 0} total` },
        ].map((s, i) => (
          <Card key={s.label} className="glass p-5 border border-border/40 hover:border-border/60 transition-colors animate-fade-in-up" style={{ animationDelay: `${i * 60}ms` }}>
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
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors active:scale-[0.98] -mb-px ${
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

      {/* ── TAB: Briefing ─────────────────────────────────────────────────────── */}
      {activeTab === 'briefing' && (
        <div className="space-y-4 animate-fade-in-up">
          {briefingData?.narrative ? (
            <AiNarrativeCard narrative={briefingData.narrative} label={`Briefing diario · ${briefingData.generated_at} · Régimen ${briefingData.regime}`} />
          ) : (
            <Card className="glass"><CardContent className="py-8 text-center text-muted-foreground text-sm">Briefing no disponible aún — se genera al final del pipeline.</CardContent></Card>
          )}

          {briefingData?.sections && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {/* Top entries */}
              {briefingData.sections.top_entries.length > 0 && (
                <Card className="glass border-emerald-500/20 hover:border-border/60 animate-fade-in-up" style={{ animationDelay: '60ms' }}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Zap size={13} className="text-emerald-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Entradas hoy</span>
                      <span className="ml-auto text-[0.6rem] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30 font-bold">
                        {briefingData.sections.strong_buy_count} SB · {briefingData.sections.buy_count} BUY
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {briefingData.sections.top_entries.map(([ticker, score]) => (
                        <div key={ticker} className="flex items-center gap-2">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline w-14">{ticker}</Link>
                          <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${score}%` }} />
                          </div>
                          <span className="tabular-nums text-[0.7rem] text-muted-foreground w-6 text-right">{score}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Smart money */}
              {briefingData.sections.smart_money.length > 0 && (
                <Card className="glass border-purple-500/20 hover:border-border/60 animate-fade-in-up" style={{ animationDelay: '120ms' }}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Building2 size={13} className="text-purple-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Smart Money</span>
                    </div>
                    <div className="space-y-1.5">
                      {briefingData.sections.smart_money.map(([ticker, nHF]) => (
                        <div key={ticker} className="flex items-center justify-between">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{ticker}</Link>
                          <span className="text-[0.65rem] text-purple-400">{nHF} HF</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Exits + traps */}
              {(briefingData.sections.exit_warnings.length > 0 || briefingData.sections.traps_warning.length > 0) && (
                <Card className="glass border-red-500/20 hover:border-border/60 animate-fade-in-up" style={{ animationDelay: '180ms' }}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <ShieldAlert size={13} className="text-red-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Vigilar / Salir</span>
                    </div>
                    <div className="space-y-1.5">
                      {briefingData.sections.exit_warnings.map(([ticker, reason]) => (
                        <div key={`exit-${ticker}`} className="flex items-start gap-2">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-red-400 text-[0.8rem] hover:underline w-14 shrink-0">{ticker}</Link>
                          <span className="text-[0.65rem] text-muted-foreground leading-tight">{reason}</span>
                        </div>
                      ))}
                      {briefingData.sections.traps_warning.map(([ticker, score]) => (
                        <div key={`trap-${ticker}`} className="flex items-center justify-between">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-amber-400 text-[0.8rem] hover:underline">{ticker}</Link>
                          <span className="text-[0.65rem] text-amber-400">trampa {score}/10</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Convergences */}
              {briefingData.sections.top_convergences.length > 0 && (
                <Card className="glass border-cyan-500/20 hover:border-border/60 animate-fade-in-up" style={{ animationDelay: '240ms' }}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Crosshair size={13} className="text-cyan-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Convergencias</span>
                    </div>
                    <div className="space-y-1.5">
                      {briefingData.sections.top_convergences.map(([ticker, score]) => (
                        <div key={ticker} className="flex items-center justify-between">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{ticker}</Link>
                          <span className="text-[0.65rem] text-cyan-400">conv {score}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Alerts */}
              {briefingData.sections.high_alerts.length > 0 && (
                <Card className="glass border-amber-500/20 hover:border-border/60 animate-fade-in-up" style={{ animationDelay: '300ms' }}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Bell size={13} className="text-amber-400" />
                      <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Alertas HIGH</span>
                    </div>
                    <div className="space-y-1.5">
                      {briefingData.sections.high_alerts.map(([ticker, type]) => (
                        <div key={`alert-${ticker}-${type}`} className="flex items-center justify-between">
                          <Link to={`/search?q=${ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{ticker}</Link>
                          <span className="text-[0.65rem] text-amber-400">{type}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── TAB: Señales de Entrada ──────────────────────────────────────────── */}
      {activeTab === 'entry' && (
        <div className="space-y-4 animate-fade-in-up">
          {entryData?.narrative && (
            <AiNarrativeCard narrative={entryData.narrative} label="Análisis de entradas de hoy" />
          )}

          {/* Filter buttons */}
          <div className="flex gap-2 flex-wrap">
            {(['ACTIONABLE', 'STRONG_BUY', 'BUY', 'MONITOR'] as const).map(f => {
              const counts: Record<string, number | undefined> = {
                ACTIONABLE: (entryData?.strong_buy ?? 0) + (entryData?.buy ?? 0),
                STRONG_BUY: entryData?.strong_buy,
                BUY: entryData?.buy,
                MONITOR: entryData?.monitor,
              }
              const labels: Record<string, string> = { ACTIONABLE: '⚡ Accionables', STRONG_BUY: '🟢 Strong Buy', BUY: '🟡 Buy', MONITOR: '🔵 Monitor' }
              return (
                <button
                  key={f}
                  onClick={() => setEntryFilter(f)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors active:scale-[0.98] ${
                    entryFilter === f
                      ? 'bg-primary/15 text-primary border-primary/30'
                      : 'bg-muted/10 text-muted-foreground border-border/30 hover:text-foreground'
                  }`}
                >
                  {labels[f]}
                  <span className="text-[0.6rem] opacity-70">{counts[f] ?? 0}</span>
                </button>
              )
            })}
          </div>

          {loadingE ? (
            <div className="space-y-3">{['a','b','c'].map(k => <Card key={k} className="glass h-32 animate-pulse" />)}</div>
          ) : filteredEntry.length === 0 ? (
            <Card className="glass">
              <CardContent className="py-12 text-center text-muted-foreground">
                {entryFilter === 'ACTIONABLE'
                  ? 'No hay señales de entrada claras hoy. Revisa mañana.'
                  : `No hay señales ${entryFilter.replace('_', ' ')} hoy.`}
              </CardContent>
            </Card>
          ) : (
            filteredEntry.map((sig, i) => (
              <div
                key={sig.ticker}
                data-row-idx={i}
                className={`animate-fade-in-up rounded-xl transition-shadow ${focusedIdx === i ? 'ring-2 ring-primary/50' : ''}`}
                style={{ animationDelay: `${i * 60}ms` }}
                onClick={() => setFocusedIdx(i)}
              >
                <EntrySignalCard sig={sig} />
              </div>
            ))
          )}
        </div>
      )}

      {/* ── TAB: Convergencias ─────────────────────────────────────────────────── */}
      {activeTab === 'convergence' && (
        <div className="space-y-4 animate-fade-in-up">
          {signals.length === 0 ? (
            <Card className="glass"><CardContent className="py-12 text-center text-muted-foreground">Sin convergencias detectadas hoy</CardContent></Card>
          ) : (
            signals.map((sig, i) => (
              <Card key={sig.ticker} className={`glass border hover:border-border/60 animate-fade-in-up ${sig.strategy_count >= 3 ? 'border-amber-500/30' : 'border-border/40'}`} style={{ animationDelay: `${i * 60}ms` }}>
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
            <>
              {/* Mobile cards */}
              <div className="sm:hidden space-y-2">
                {alerts.map((alert, i) => (
                  <div key={`mob-${alert.ticker}-${alert.type}-${i}`} className={`p-3 rounded-xl border animate-fade-in-up ${alertColor(alert.severity)}`} style={{ animationDelay: `${i * 60}ms` }}>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="shrink-0">{alertIcon(alert.type)}</div>
                      <Link to={`/search?q=${alert.ticker}`} className="font-mono font-bold text-primary text-sm hover:underline">{alert.ticker}</Link>
                      <span className={`text-[0.55rem] font-bold px-1.5 py-0.5 rounded border ${alert.severity === 'HIGH' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'}`}>{alert.severity}</span>
                    </div>
                    <div className="text-[0.72rem] font-semibold text-foreground/80 mb-0.5">{alert.title}</div>
                    <p className="text-[0.72rem] text-muted-foreground leading-relaxed">{alert.message}</p>
                  </div>
                ))}
              </div>

              {/* Desktop list */}
              <div className="hidden sm:block space-y-2">
                {alerts.map((alert, i) => (
                  <div key={`${alert.ticker}-${alert.type}-${i}`} className={`flex items-start gap-3 p-4 rounded-xl border animate-fade-in-up ${alertColor(alert.severity)}`} style={{ animationDelay: `${i * 60}ms` }}>
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
                ))}
              </div>
            </>
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

      {/* ── TAB: Agentes IA ───────────────────────────────────────────────────── */}
      {activeTab === 'agents' && (
        <div className="space-y-6 animate-fade-in-up">

          {/* Exit Monitor */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <TrendingDown size={14} className="text-red-400" />
              <h3 className="text-sm font-bold text-foreground/80">Exit Monitor</h3>
              {exitData && <span className="text-[0.6rem] text-red-400 bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded font-bold">{exitData.high_count} HIGH · {exitData.total} total</span>}
            </div>
            {exitData?.narrative && <AiNarrativeCard narrative={exitData.narrative} label="" />}
            <div className="space-y-2 mt-2">
              {(exitData?.exits ?? []).slice(0, 6).map(e => (
                <div key={e.ticker} className={`flex items-start gap-3 p-3 rounded-xl border ${e.severity === 'HIGH' ? 'border-red-500/25 bg-red-500/5' : 'border-amber-500/20 bg-amber-500/5'}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <Link to={`/search?q=${e.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{e.ticker}</Link>
                      <span className={`text-[0.55rem] font-bold px-1 py-0.5 rounded border ${e.severity === 'HIGH' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'}`}>{e.severity}</span>
                      {e.current_score != null && <span className="text-[0.65rem] text-muted-foreground ml-auto">Score {e.entry_score.toFixed(0)} → {e.current_score.toFixed(0)}</span>}
                    </div>
                    <p className="text-[0.7rem] text-muted-foreground leading-relaxed">{e.reasons.join(' · ')}</p>
                  </div>
                </div>
              ))}
              {!exitData?.exits?.length && <p className="text-sm text-muted-foreground text-center py-4">Sin señales de salida activas</p>}
            </div>
          </section>

          {/* Value Trap Detector */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <AlertOctagon size={14} className="text-amber-400" />
              <h3 className="text-sm font-bold text-foreground/80">Value Trap Detector</h3>
              {trapsData && <span className="text-[0.6rem] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded font-bold">{trapsData.high_count} HIGH · {trapsData.total} total</span>}
            </div>
            {trapsData?.narrative && <AiNarrativeCard narrative={trapsData.narrative} label="" />}
            <div className="space-y-2 mt-2">
              {(trapsData?.traps ?? []).slice(0, 6).map(t => (
                <div key={t.ticker} className={`p-3 rounded-xl border ${t.severity === 'HIGH' ? 'border-red-500/25 bg-red-500/5' : 'border-amber-500/20 bg-amber-500/5'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Link to={`/search?q=${t.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{t.ticker}</Link>
                    <span className="text-[0.65rem] text-muted-foreground">{t.company_name}</span>
                    <span className="ml-auto text-[0.65rem] text-amber-400">trampa {t.trap_score}/10</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {t.flags.map((f, i) => <span key={i} className="text-[0.6rem] text-muted-foreground/70 bg-muted/10 border border-border/20 px-1.5 py-0.5 rounded">{f}</span>)}
                  </div>
                </div>
              ))}
              {!trapsData?.traps?.length && <p className="text-sm text-muted-foreground text-center py-4">Sin value traps detectadas</p>}
            </div>
          </section>

          {/* Smart Money */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Building2 size={14} className="text-purple-400" />
              <h3 className="text-sm font-bold text-foreground/80">Smart Money Convergence</h3>
              {smData && <span className="text-[0.6rem] text-purple-400 bg-purple-500/10 border border-purple-500/20 px-1.5 py-0.5 rounded font-bold">{smData.total} señales</span>}
            </div>
            {smData?.narrative && <AiNarrativeCard narrative={smData.narrative} label="" />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
              {(smData?.signals ?? []).slice(0, 8).map(s => (
                <div key={s.ticker} className="flex items-center gap-3 p-3 rounded-xl border border-purple-500/20 bg-purple-500/5">
                  <TickerLogo ticker={s.ticker} size="sm" className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Link to={`/search?q=${s.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{s.ticker}</Link>
                      {s.in_value && <span className="text-[0.5rem] bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-1 py-0 rounded font-bold">VALUE</span>}
                    </div>
                    <div className="text-[0.65rem] text-muted-foreground">{s.n_hedge_funds} HF · {s.n_insiders} insiders · conv {s.convergence_score}</div>
                  </div>
                </div>
              ))}
              {!smData?.signals?.length && <p className="text-sm text-muted-foreground text-center py-4 col-span-2">Sin convergencias HF+insiders</p>}
            </div>
          </section>

          {/* Insider Clusters */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Users size={14} className="text-teal-400" />
              <h3 className="text-sm font-bold text-foreground/80">Insider Sector Clusters</h3>
              {clustersData && <span className="text-[0.6rem] text-teal-400 bg-teal-500/10 border border-teal-500/20 px-1.5 py-0.5 rounded font-bold">{clustersData.total} clusters</span>}
            </div>
            {clustersData?.narrative && <AiNarrativeCard narrative={clustersData.narrative} label="" />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
              {(clustersData?.clusters ?? []).map(c => (
                <div key={c.sector} className={`p-3 rounded-xl border ${c.signal === 'STRONG' ? 'border-teal-500/30 bg-teal-500/5' : 'border-border/30 bg-muted/5'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[0.75rem] font-bold text-foreground/80">{c.sector}</span>
                    <span className={`text-[0.55rem] font-bold px-1.5 py-0.5 rounded border ${c.signal === 'STRONG' ? 'bg-teal-500/20 text-teal-400 border-teal-500/30' : 'bg-muted/20 text-muted-foreground border-border/30'}`}>{c.signal}</span>
                  </div>
                  <div className="text-[0.65rem] text-muted-foreground mb-1">{c.ticker_count} empresas · {c.total_purchases} compras · score {c.cluster_score}</div>
                  <div className="flex flex-wrap gap-1">
                    {c.tickers.slice(0, 6).map(t => (
                      <Link key={t} to={`/search?q=${t}`} className="text-[0.6rem] font-mono text-primary hover:underline bg-muted/15 border border-border/20 px-1 py-0.5 rounded">{t}</Link>
                    ))}
                  </div>
                </div>
              ))}
              {!clustersData?.clusters?.length && <p className="text-sm text-muted-foreground text-center py-4 col-span-2">Sin clusters sectoriales de insiders</p>}
            </div>
          </section>

          {/* Dividend Safety */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Wallet size={14} className="text-emerald-400" />
              <h3 className="text-sm font-bold text-foreground/80">Dividend Safety Monitor</h3>
              {divData && <span className="text-[0.6rem] text-red-400 bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded font-bold">{divData.at_risk} AT RISK · {divData.total} total</span>}
            </div>
            {divData?.narrative && <AiNarrativeCard narrative={divData.narrative} label="" />}
            <div className="space-y-2 mt-2">
              {(divData?.dividends ?? []).slice(0, 8).map(d => {
                const ratingStyle = d.rating === 'AT_RISK' ? 'border-red-500/25 bg-red-500/5' : d.rating === 'WATCH' ? 'border-amber-500/20 bg-amber-500/5' : 'border-emerald-500/20 bg-emerald-500/5'
                const ratingBadge = d.rating === 'AT_RISK' ? 'bg-red-500/15 text-red-400 border-red-500/30' : d.rating === 'WATCH' ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                return (
                  <div key={d.ticker} className={`flex items-start gap-3 p-3 rounded-xl border ${ratingStyle}`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <Link to={`/search?q=${d.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{d.ticker}</Link>
                        <span className={`text-[0.55rem] font-bold px-1 py-0.5 rounded border ${ratingBadge}`}>{d.rating}</span>
                        <span className="text-[0.65rem] text-emerald-400 ml-1">yield {d.div_yield.toFixed(1)}%</span>
                        {d.payout_ratio != null && <span className="text-[0.65rem] text-muted-foreground">payout {d.payout_ratio.toFixed(0)}%</span>}
                        <span className="text-[0.65rem] text-muted-foreground ml-auto">safety {d.safety_score}</span>
                      </div>
                      {d.risk_flags.length > 0 && <p className="text-[0.7rem] text-muted-foreground">{d.risk_flags[0]}</p>}
                    </div>
                  </div>
                )
              })}
              {!divData?.dividends?.length && <p className="text-sm text-muted-foreground text-center py-4">Sin tickers con dividendo en VALUE</p>}
            </div>
          </section>

          {/* Piotroski Momentum */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <BarChart2 size={14} className="text-blue-400" />
              <h3 className="text-sm font-bold text-foreground/80">Piotroski Momentum</h3>
              {piotrData && <span className="text-[0.6rem] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.5 rounded font-bold">{piotrData.improving} mejorando · {piotrData.total} analizados</span>}
            </div>
            {piotrData?.narrative && <AiNarrativeCard narrative={piotrData.narrative} label="" />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
              {(piotrData?.candidates ?? []).slice(0, 10).map(c => {
                const trendColor = c.trend === 'IMPROVING' ? 'text-emerald-400' : c.trend === 'SLIGHT_UP' ? 'text-blue-400' : c.trend === 'DETERIORATING' ? 'text-red-400' : c.trend === 'SLIGHT_DOWN' ? 'text-amber-400' : 'text-muted-foreground'
                const trendIcon = c.trend === 'IMPROVING' || c.trend === 'SLIGHT_UP' ? <TrendingUp size={11} /> : c.trend === 'DETERIORATING' || c.trend === 'SLIGHT_DOWN' ? <TrendingDown size={11} /> : <Minus size={11} />
                return (
                  <div key={c.ticker} className="flex items-center gap-3 p-3 rounded-xl border border-border/30 bg-muted/5">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Link to={`/search?q=${c.ticker}`} className="font-mono font-bold text-primary text-[0.8rem] hover:underline">{c.ticker}</Link>
                        <span className={`flex items-center gap-0.5 text-[0.65rem] font-semibold ${trendColor}`}>{trendIcon} {c.trend.replace('_', ' ')}</span>
                      </div>
                      <div className="text-[0.65rem] text-muted-foreground">
                        F-score: {c.piotroski_prev != null ? `${c.piotroski_prev} → ` : ''}<strong className={c.piotroski_current >= 7 ? 'text-emerald-400' : c.piotroski_current <= 3 ? 'text-red-400' : 'text-foreground'}>{c.piotroski_current}/9</strong>
                        {c.delta !== 0 && <span className={c.delta > 0 ? ' text-emerald-400' : ' text-red-400'}> ({c.delta > 0 ? '+' : ''}{c.delta})</span>}
                      </div>
                    </div>
                  </div>
                )
              })}
              {!piotrData?.candidates?.length && <p className="text-sm text-muted-foreground text-center py-4 col-span-2">Sin datos Piotroski destacables</p>}
            </div>
          </section>

          {/* Portfolio Stress Test */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Activity size={14} className="text-pink-400" />
              <h3 className="text-sm font-bold text-foreground/80">Portfolio Stress Test</h3>
              {stressData && <span className="text-[0.6rem] text-foreground/60 bg-muted/15 border border-border/30 px-1.5 py-0.5 rounded font-bold">{stressData.total_positions} posiciones · {stressData.risks.length} riesgos</span>}
            </div>
            {stressData?.narrative && <AiNarrativeCard narrative={stressData.narrative} label="" />}
            <div className="space-y-2 mt-2">
              {(stressData?.risks ?? []).map((r, i) => (
                <div key={i} className={`p-3 rounded-xl border ${r.severity === 'HIGH' ? 'border-red-500/25 bg-red-500/5' : r.severity === 'MEDIUM' ? 'border-amber-500/20 bg-amber-500/5' : 'border-border/30 bg-muted/5'}`}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-[0.55rem] font-bold px-1 py-0.5 rounded border ${r.severity === 'HIGH' ? 'bg-red-500/15 text-red-400 border-red-500/30' : r.severity === 'MEDIUM' ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' : 'bg-muted/15 text-muted-foreground border-border/30'}`}>{r.severity}</span>
                    <span className="text-[0.65rem] font-semibold text-foreground/70">{r.type.replace(/_/g, ' ')}</span>
                  </div>
                  <p className="text-[0.72rem] text-muted-foreground">{r.message}</p>
                </div>
              ))}
              {stressData && (stressData.risks ?? []).length === 0 && (
                <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center text-sm text-emerald-400">
                  Sin riesgos de concentración detectados — cartera bien diversificada
                </div>
              )}
            </div>
            {stressData?.sector_breakdown && stressData.sector_breakdown.length > 0 && (
              <Card className="glass mt-3">
                <CardContent className="p-4">
                  <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Distribución sectorial (últimas 60 días)</div>
                  <div className="space-y-2">
                    {stressData.sector_breakdown.map(s => (
                      <div key={s.sector} className="flex items-center gap-2">
                        <span className="text-[0.7rem] text-muted-foreground w-36 truncate">{s.sector}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                          <div className="h-full rounded-full bg-primary/50" style={{ width: `${s.pct}%` }} />
                        </div>
                        <span className="text-[0.65rem] text-muted-foreground w-10 text-right tabular-nums">{s.pct}%</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </section>

        </div>
      )}
    </>
  )
}
