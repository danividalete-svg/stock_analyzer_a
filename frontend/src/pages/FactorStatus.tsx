import { fetchFactorStatus, type FactorDetail } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Gem, TrendingUp, Shield, Users, Building2, Zap, Info } from 'lucide-react'

// ── Config per factor ─────────────────────────────────────────────────────────

const FACTOR_CONFIG: Record<string, {
  label: string
  icon: React.ElementType
  color: string
  description: string
  investor: string
}> = {
  value:       { label: 'VALUE',       icon: Gem,        color: '#10b981', description: 'EV/EBIT, FCF Yield, P/Book', investor: 'Buffett / Graham' },
  quality:     { label: 'QUALITY',     icon: Shield,     color: '#3b82f6', description: 'Piotroski F-Score, ROIC',    investor: 'Piotroski / Greenblatt' },
  momentum:    { label: 'MOMENTUM',    icon: TrendingUp, color: '#f97316', description: 'VCP, Stage 2, RS Line',      investor: 'Minervini / Druckenmiller' },
  insider:     { label: 'INSIDER',     icon: Users,      color: '#8b5cf6', description: 'Cluster buying, recurrentes', investor: 'Lynch / Academic research' },
  smart_money: { label: 'SMART MONEY', icon: Building2,  color: '#f59e0b', description: '13F SEC — Buffett, Ackman, Klarman', investor: 'Hedge funds tier-1' },
}

const STATUS_STYLE: Record<string, { badge: string; bar: string; label: string }> = {
  ATTRACTIVE:  { badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', bar: 'bg-emerald-500', label: 'Atractivo' },
  STRONG:      { badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', bar: 'bg-emerald-500', label: 'Fuerte' },
  BULL:        { badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', bar: 'bg-emerald-500', label: 'Alcista' },
  BULLISH:     { badge: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', bar: 'bg-emerald-500', label: 'Alcista' },
  NEUTRAL:     { badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',       bar: 'bg-amber-500',   label: 'Neutral' },
  MIXED:       { badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',       bar: 'bg-amber-500',   label: 'Mixto' },
  MODERATE:    { badge: 'bg-amber-500/20 text-amber-400 border-amber-500/30',       bar: 'bg-amber-500',   label: 'Moderado' },
  EXPENSIVE:   { badge: 'bg-red-500/20 text-red-400 border-red-500/30',             bar: 'bg-red-500',     label: 'Caro' },
  WEAK:        { badge: 'bg-red-500/20 text-red-400 border-red-500/30',             bar: 'bg-red-500',     label: 'Débil' },
  BEAR:        { badge: 'bg-red-500/20 text-red-400 border-red-500/30',             bar: 'bg-red-500',     label: 'Bajista' },
  QUIET:       { badge: 'bg-slate-500/20 text-slate-400 border-slate-500/30',       bar: 'bg-slate-500',   label: 'Sin señal' },
  SPARSE:      { badge: 'bg-slate-500/20 text-slate-400 border-slate-500/30',       bar: 'bg-slate-500',   label: 'Disperso' },
}

const ALIGNMENT_STYLE: Record<string, { cls: string; label: string }> = {
  FULL_ALIGNMENT: { cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30', label: 'Alineación total' },
  GOOD:           { cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30', label: 'Condiciones buenas' },
  MIXED:          { cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30',       label: 'Señales mixtas' },
  CAUTIOUS:       { cls: 'text-orange-400 bg-orange-500/10 border-orange-500/30',    label: 'Cauteloso' },
  HOSTILE:        { cls: 'text-red-400 bg-red-500/10 border-red-500/30',             label: 'Entorno adverso' },
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatRow({ label, value, highlight }: { label: string; value: string | null; highlight?: boolean }) {
  if (value == null) return null
  return (
    <div className="flex justify-between items-center py-1 border-b border-border/10 last:border-0">
      <span className="text-[0.65rem] text-muted-foreground">{label}</span>
      <span className={`text-[0.65rem] font-semibold tabular-nums ${highlight ? 'text-foreground' : 'text-muted-foreground/80'}`}>{value}</span>
    </div>
  )
}

function ScoreRing({ score, color }: { score: number; color: string }) {
  const r = 20, c = 2 * Math.PI * r
  const fill = (score / 100) * c
  return (
    <svg width="56" height="56" viewBox="0 0 56 56" className="flex-shrink-0">
      <circle cx="28" cy="28" r={r} fill="none" stroke="currentColor" strokeWidth="3.5" className="text-muted/20" />
      <circle
        cx="28" cy="28" r={r} fill="none"
        stroke={color} strokeWidth="3.5"
        strokeDasharray={`${fill} ${c}`}
        strokeLinecap="round"
        transform="rotate(-90 28 28)"
      />
      <text x="28" y="33" textAnchor="middle" fontSize="12" fontWeight="700" fill={color}>{score}</text>
    </svg>
  )
}

function FactorCard({ factorKey, factor, staggerIdx }: { factorKey: string; factor: FactorDetail; staggerIdx?: number }) {
  const cfg = FACTOR_CONFIG[factorKey]
  if (!cfg) return null
  const st = STATUS_STYLE[factor.status] ?? STATUS_STYLE['QUIET']
  const staggerCls = staggerIdx ? `stagger-${staggerIdx} animate-fade-in-up` : ''

  const extraStats: Array<{ label: string; value: string | null }> = []
  if (factorKey === 'value') {
    if (factor.opportunities != null)  extraStats.push({ label: 'Oportunidades activas', value: `${factor.opportunities}` })
    if (factor.grade_a != null)        extraStats.push({ label: 'Grado A', value: `${factor.grade_a}` })
    if (factor.avg_upside_pct != null) extraStats.push({ label: 'Upside medio analistas', value: `+${factor.avg_upside_pct}%` })
    if (factor.avg_fcf_yield != null)  extraStats.push({ label: 'FCF Yield medio', value: `${factor.avg_fcf_yield}%` })
  }
  if (factorKey === 'quality') {
    if (factor.avg_piotroski != null)  extraStats.push({ label: 'F-Score medio', value: `${factor.avg_piotroski}/9` })
    if (factor.pct_strong != null)     extraStats.push({ label: 'F≥8 (STRONG)', value: `${factor.pct_strong}%` })
    if (factor.pct_weak != null)       extraStats.push({ label: 'F≤2 (value traps)', value: `${factor.pct_weak}%` })
    if (factor.avg_roic_pct != null)   extraStats.push({ label: 'ROIC medio', value: `${factor.avg_roic_pct}%` })
  }
  if (factorKey === 'momentum') {
    if (factor.opportunities != null)  extraStats.push({ label: 'Setups VCP activos', value: `${factor.opportunities}` })
    if (factor.market_regime)          extraStats.push({ label: 'Régimen mercado', value: factor.market_regime })
    if (factor.avg_score != null)      extraStats.push({ label: 'Score momentum medio', value: `${factor.avg_score}` })
  }
  if (factorKey === 'insider') {
    if (factor.active_signals != null) extraStats.push({ label: 'Señales activas', value: `${factor.active_signals}` })
    if (factor.cluster_buying != null) extraStats.push({ label: 'Cluster buys', value: `${factor.cluster_buying}` })
    if (factor.high_confidence != null)extraStats.push({ label: 'Alta convicción (≥70)', value: `${factor.high_confidence}` })
  }
  if (factorKey === 'smart_money') {
    if (factor.total_positions != null)  extraStats.push({ label: 'Posiciones 13F', value: `${factor.total_positions}` })
    if (factor.consensus_2plus != null)  extraStats.push({ label: '2+ fondos coinciden', value: `${factor.consensus_2plus}` })
    if (factor.consensus_3plus != null)  extraStats.push({ label: '3+ fondos coinciden', value: `${factor.consensus_3plus}` })
    if (factor.funds_tracked != null)    extraStats.push({ label: 'Fondos rastreados', value: `${factor.funds_tracked}` })
  }

  return (
    <Card className={`glass flex flex-col hover:border-border/60 transition-colors ${staggerCls}`}>
      <CardContent className="p-4 flex flex-col gap-3 h-full">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${cfg.color}18` }}>
              <cfg.icon size={14} style={{ color: cfg.color }} />
            </div>
            <div>
              <div className="text-xs font-bold tracking-wider" style={{ color: cfg.color }}>{cfg.label}</div>
              <div className="text-[0.6rem] text-muted-foreground/60">{cfg.description}</div>
            </div>
          </div>
          <ScoreRing score={factor.score} color={cfg.color} />
        </div>

        {/* Status badge */}
        <span className={`self-start text-[0.6rem] font-bold px-2 py-0.5 rounded-full border ${st.badge}`}>
          {st.label}
        </span>

        {/* Score bar */}
        <div className="h-1 rounded-full bg-muted/20 overflow-hidden">
          <div className={`h-full rounded-full transition-all ${st.bar}`} style={{ width: `${factor.score}%` }} />
        </div>

        {/* Stats */}
        {extraStats.length > 0 && (
          <div className="flex-1">
            {extraStats.map(s => <StatRow key={s.label} label={s.label} value={s.value} />)}
          </div>
        )}

        {/* Interpretation */}
        {factor.interpretation && (
          <p className="text-[0.65rem] text-muted-foreground/70 leading-relaxed border-t border-border/20 pt-2">
            {factor.interpretation}
          </p>
        )}

        {/* Academic edge */}
        {factor.academic_edge && (
          <div className="flex items-start gap-1.5 mt-auto">
            <Info size={10} className="text-muted-foreground/40 mt-0.5 flex-shrink-0" />
            <span className="text-[0.58rem] text-muted-foreground/40 italic">{factor.academic_edge}</span>
          </div>
        )}

        {/* Investor reference */}
        <div className="text-[0.58rem] text-muted-foreground/30 uppercase tracking-widest">
          {cfg.investor}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function FactorStatus() {
  const { data, loading, error } = useApi(() => fetchFactorStatus(), [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  if (!data) return <ErrorState message="Sin datos de factores disponibles" />

  const align = ALIGNMENT_STYLE[data.factor_alignment] ?? ALIGNMENT_STYLE['MIXED']
  const genAt = data.generated_at ? new Date(data.generated_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'

  const factorOrder = ['value', 'quality', 'momentum', 'insider', 'smart_money']

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="animate-fade-in-up">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2 gradient-title">
          <Zap size={22} className="text-primary" />
          Factor Status
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Estado actual de los 5 factores académicamente probados · Fama-French + AQR · {genAt}
        </p>
      </div>

      {/* Combined score + alignment hero card */}
      <div className={`rounded-xl border p-5 animate-fade-in-up ${align.cls}`}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest opacity-60 mb-1">Alineación de Factores</div>
            <div className="text-2xl font-bold">{align.label}</div>
            <p className="text-sm opacity-70 mt-1 leading-relaxed max-w-md">{data.recommendation}</p>
          </div>
          <div className="flex items-end gap-4">
            <div className="text-center">
              <div className="text-4xl font-black tabular-nums">{data.combined_score}</div>
              <div className="text-[0.6rem] uppercase tracking-widest opacity-60 mt-0.5">Score global</div>
            </div>
          </div>
        </div>
      </div>

      {/* Value–Momentum AQR insight */}
      {data.value_momentum_note && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-lg border border-primary/20 bg-primary/5 text-xs text-primary/80">
          <Info size={13} className="mt-0.5 flex-shrink-0 text-primary" />
          <span><strong className="text-primary">AQR:</strong> {data.value_momentum_note}</span>
        </div>
      )}

      {/* Factor grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5 animate-fade-in-up">
        {factorOrder.map((key, idx) => {
          const factor = data.factors[key as keyof typeof data.factors]
          if (!factor) return null
          return <FactorCard key={key} factorKey={key} factor={factor} staggerIdx={idx + 1} />
        })}
      </div>

      {/* Academic footnote */}
      <div className="text-[0.62rem] text-muted-foreground/30 leading-relaxed border-t border-border/20 pt-4">
        Basado en: Fama & French (1992) Value + Size, Jegadeesh & Titman (1993) Momentum, Piotroski (2000) F-Score,
        Asness et al. AQR (2013) Value + Momentum Everywhere, Frazzini & Pedersen (2014) Betting Against Beta (Low Vol).
        Los scores son relativos al universo actual del sistema, no absolutos.
      </div>
    </div>
  )
}
