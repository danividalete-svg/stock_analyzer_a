import { fetchMacroRadar, fetchMacroRadarHistory, fetchEconomicCalendar } from '../api/client'
import type { EconEvent } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import StaleDataBanner from '../components/StaleDataBanner'

interface SignalData {
  label: string
  description: string
  score: number
  current?: number | null
  percentile?: number
  change_5d?: number
  change_20d?: number
  pct_from_200?: number
  interpretation: string
}

interface HistoricalAnalog {
  id: string
  name: string
  date: string
  duration_days: number
  similarity: number
  outcome: { spy_30d: number; spy_90d: number; spy_180d: number; description: string }
  key_difference: string
  closest_signals: string[]
  diverging_signals: string[]
}

interface SystemicRisk {
  id: string
  name: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  color: string
  description: string
  implication: string
}

interface IndexBreakout {
  index: string
  index_name: string
  ma_key: string
  ma_label: string
  current_price: number
  ma_value: number
  pct_from_ma: number
  direction: 'ABOVE' | 'BELOW'
  fresh_cross: boolean
  days_since_cross: number
  signal: 'BEARISH_BREAK' | 'BULLISH_BREAK' | 'ABOVE' | 'BELOW'
}

interface MacroData {
  timestamp: string
  date: string
  regime: { name: string; color: string; description: string }
  composite_score: number
  composite_pct: number
  max_score: number
  signals: Record<string, SignalData>
  signal_order: string[]
  ai_narrative?: string | null
  errors?: string[]
  historical_analogs?: HistoricalAnalog[]
  systemic_risks?: SystemicRisk[]
  index_breakouts?: IndexBreakout[]
}

const SIGNAL_ICONS: Record<string, string> = {
  vix:            '⚡',
  yield_curve:    '📈',
  credit:         '💳',
  copper_gold:    '🔩',
  gold_spy:       '🥇',
  oil:            '🛢',
  defense:        '🛡',
  dollar:         '💵',
  yen:            '🇯🇵',
  breadth:        '📊',
  skew:           '🎯',
  vvix:           '🌀',
  regional_banks: '🏦',
  small_cap:      '🔬',
  real_yields:    '📉',
}

function scoreToColor(score: number): string {
  if (score >= 1.5)  return 'text-emerald-400'
  if (score >= 0.5)  return 'text-green-400'
  if (score >= -0.5) return 'text-yellow-400'
  if (score >= -1.5) return 'text-orange-400'
  return 'text-red-400'
}

function scoreToBg(score: number): string {
  if (score >= 1.5)  return 'bg-emerald-500/10 border-emerald-500/20'
  if (score >= 0.5)  return 'bg-green-500/10 border-green-500/20'
  if (score >= -0.5) return 'bg-yellow-500/10 border-yellow-500/20'
  if (score >= -1.5) return 'bg-orange-500/10 border-orange-500/20'
  return 'bg-red-500/10 border-red-500/20'
}

function scoreToLabel(score: number): string {
  if (score >= 1.5)  return 'Positivo'
  if (score >= 0.5)  return 'Neutro+'
  if (score >= -0.5) return 'Neutro'
  if (score >= -1.5) return 'Precaución'
  return 'Alerta'
}

function regimeBadgeVariant(name: string): string {
  const map: Record<string, string> = {
    CALM:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    WATCH:  'bg-lime-500/15 text-lime-400 border-lime-500/30',
    STRESS: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    ALERT:  'bg-orange-500/15 text-orange-400 border-orange-500/30',
    CRISIS: 'bg-red-500/15 text-red-400 border-red-500/30',
  }
  return map[name] ?? 'bg-muted/20 text-muted-foreground border-border'
}

function ScoreGauge({ score, max }: { score: number; max: number }) {
  // score range: -max to +max → normalize to 0-100
  const pct = ((score + max) / (2 * max)) * 100
  const color = score >= 6 ? '#10b981' : score >= 0 ? '#84cc16' : score >= -6 ? '#f59e0b' : score >= -12 ? '#f97316' : '#ef4444'
  return (
    <div className="relative w-full">
      <div className="flex justify-between text-[0.65rem] text-muted-foreground mb-1">
        <span>Crisis</span>
        <span>Neutro</span>
        <span>Calma</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted/30" style={{ overflow: 'clip' }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between text-[0.65rem] text-muted-foreground mt-1">
        <span>{-max}</span>
        <span className="font-bold" style={{ color }}>{score.toFixed(1)}</span>
        <span>+{max}</span>
      </div>
    </div>
  )
}

function SignalCard({ id, signal, stagger }: { id: string; signal: SignalData; stagger?: number }) {
  const icon = SIGNAL_ICONS[id] ?? '📌'
  const score = signal.score ?? 0
  const staggerClass = stagger != null && stagger <= 8 ? `stagger-${stagger}` : 'animate-fade-in-up'

  return (
    <Card className={`glass border ${scoreToBg(score)} hover:border-border/60 transition-colors ${staggerClass}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg">{icon}</span>
            <span className="text-xs font-semibold text-foreground leading-tight">{signal.label}</span>
          </div>
          <div className={`text-xs font-bold px-1.5 py-0.5 rounded ${scoreToColor(score)}`}>
            {score >= 0 ? '+' : ''}{score.toFixed(1)}
          </div>
        </div>

        {/* Score bar */}
        <div className="mb-2">
          <div className="h-1.5 w-full rounded-full bg-muted/30" style={{ overflow: 'clip' }}>
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${((score + 2) / 4) * 100}%`,
                backgroundColor: score >= 1 ? '#10b981' : score >= 0 ? '#84cc16' : score >= -1 ? '#f97316' : '#ef4444',
              }}
            />
          </div>
        </div>

        <p className="text-[0.7rem] text-muted-foreground leading-snug mb-1.5">
          {signal.interpretation || '—'}
        </p>

        <div className="flex items-center justify-between">
          {signal.percentile != null && (
            <span className="text-[0.62rem] text-muted-foreground/70">
              p{signal.percentile.toFixed(0)} vs 1yr
            </span>
          )}
          <span className={`text-[0.65rem] font-medium ${scoreToColor(score)}`}>
            {scoreToLabel(score)}
          </span>
        </div>

        {signal.change_5d != null && (
          <div className="mt-1 text-[0.62rem] text-muted-foreground/60">
            5d: <span className={signal.change_5d >= 0 ? 'text-green-400' : 'text-red-400'}>
              {signal.change_5d >= 0 ? '+' : ''}{signal.change_5d.toFixed(1)}%
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface HistoryPoint {
  date: string
  composite_score: number
  regime: string
  regime_color: string
}

const REGIME_COLORS: Record<string, string> = {
  CALM: '#10b981', WATCH: '#84cc16', STRESS: '#f59e0b', ALERT: '#f97316', CRISIS: '#ef4444',
}

function HistoryChart({ points, maxScore }: { points: HistoryPoint[]; maxScore: number }) {
  if (points.length < 2) {
    return (
      <div className="flex items-center justify-center h-24 text-xs text-muted-foreground/60">
        Historial en construcción — disponible tras varios días de pipeline
      </div>
    )
  }

  const W = 600, H = 100, PAD = { t: 8, b: 20, l: 28, r: 8 }
  const innerW = W - PAD.l - PAD.r
  const innerH = H - PAD.t - PAD.b

  const xScale = (i: number) => PAD.l + (i / (points.length - 1)) * innerW
  const yScale = (v: number) => PAD.t + ((maxScore - v) / (2 * maxScore)) * innerH

  const y0 = yScale(0)

  // Build polyline path
  const pts = points.map((p, i) => `${xScale(i)},${yScale(p.composite_score)}`).join(' ')

  // X-axis date labels: show first, middle, last
  const labelIdxs = [0, Math.floor(points.length / 2), points.length - 1]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 100 }}>
      {/* Zero line */}
      <line x1={PAD.l} y1={y0} x2={W - PAD.r} y2={y0} stroke="currentColor" strokeOpacity="0.15" strokeDasharray="3,3" />

      {/* Danger zone shading (below 0) */}
      <rect x={PAD.l} y={y0} width={innerW} height={innerH - (y0 - PAD.t)} fill="#ef4444" fillOpacity="0.04" />

      {/* Area fill */}
      <polyline
        points={[
          `${xScale(0)},${y0}`,
          ...points.map((p, i) => `${xScale(i)},${yScale(p.composite_score)}`),
          `${xScale(points.length - 1)},${y0}`,
        ].join(' ')}
        fill={points[points.length - 1].composite_score >= 0 ? '#10b981' : '#f97316'}
        fillOpacity="0.08"
      />

      {/* Line */}
      <polyline points={pts} fill="none" stroke={REGIME_COLORS[points[points.length - 1].regime] ?? '#6366f1'} strokeWidth="1.5" strokeLinejoin="round" />

      {/* Dots (colored by regime) */}
      {points.map((p, i) => (
        <circle
          key={i}
          cx={xScale(i)}
          cy={yScale(p.composite_score)}
          r={points.length > 20 ? 1.5 : 2.5}
          fill={REGIME_COLORS[p.regime] ?? '#94a3b8'}
        />
      ))}

      {/* X-axis labels */}
      {labelIdxs.map(i => (
        <text key={i} x={xScale(i)} y={H - 4} textAnchor="middle" fontSize="7" fill="currentColor" fillOpacity="0.4">
          {points[i].date.slice(5)}
        </text>
      ))}

      {/* Y-axis labels */}
      <text x={PAD.l - 2} y={PAD.t + 4} textAnchor="end" fontSize="7" fill="currentColor" fillOpacity="0.4">+{maxScore}</text>
      <text x={PAD.l - 2} y={y0 + 3} textAnchor="end" fontSize="7" fill="currentColor" fillOpacity="0.4">0</text>
      <text x={PAD.l - 2} y={H - PAD.b + 2} textAnchor="end" fontSize="7" fill="currentColor" fillOpacity="0.4">-{maxScore}</text>
    </svg>
  )
}

const INDEX_FLAGS: Record<string, string> = {
  QQQ: '🇺🇸', SPY: '🇺🇸', IWM: '🇺🇸', DIA: '🇺🇸', EWG: '🇩🇪', EEM: '🌍',
}

const MA_IMPORTANCE: Record<string, number> = {
  ma10m: 4, ma20m: 3, ma200d: 2, ma50d: 1,
}

function IndexBreakoutsPanel({ breakouts }: { breakouts: IndexBreakout[] }) {
  const fresh   = breakouts.filter(b => b.fresh_cross)
  const bearish = fresh.filter(b => b.signal === 'BEARISH_BREAK')
  const bullish = fresh.filter(b => b.signal === 'BULLISH_BREAK')
  const below   = breakouts.filter(b => !b.fresh_cross && b.signal === 'BELOW')
  const above   = breakouts.filter(b => !b.fresh_cross && b.signal === 'ABOVE')

  const sorted = [
    ...bearish.sort((a,b) => (MA_IMPORTANCE[b.ma_key]??0) - (MA_IMPORTANCE[a.ma_key]??0)),
    ...bullish.sort((a,b) => (MA_IMPORTANCE[b.ma_key]??0) - (MA_IMPORTANCE[a.ma_key]??0)),
    ...below.sort((a,b) => a.pct_from_ma - b.pct_from_ma),
    ...above.sort((a,b) => b.pct_from_ma - a.pct_from_ma),
  ]

  if (sorted.length === 0) return null

  return (
    <Card className="glass border border-border/50 animate-fade-in-up">
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-base">📡</span>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Roturas de Índices — Medias Clave
          </p>
          {fresh.length > 0 && (
            <span className={`ml-auto text-[0.6rem] font-bold px-2 py-0.5 rounded-full border ${
              bearish.length > 0
                ? 'bg-red-500/15 text-red-400 border-red-500/30'
                : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
            }`}>
              {bearish.length > 0 ? `${bearish.length} rotura bajista${bearish.length > 1 ? 's' : ''}` : `${bullish.length} rotura alcista${bullish.length > 1 ? 's' : ''}`}
            </span>
          )}
        </div>
        <p className="text-[0.65rem] text-muted-foreground/60 mb-4">
          Cruces de MA50d, MA200d, MA10mes y MA20mes en Nasdaq, S&P, Russell, DAX y mercados emergentes
        </p>

        {/* Fresh crosses — prominently highlighted */}
        {fresh.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[0.6rem] font-black uppercase tracking-[0.15em] text-muted-foreground/50">Roturas recientes</span>
              <div className="flex-1 h-px bg-border/20" />
              <span className="text-[0.6rem] text-muted-foreground/40">últimos 5 días</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[...bearish, ...bullish].map((b, idx) => {
                const isBearish = b.signal === 'BEARISH_BREAK'
                return (
                  <div
                    key={`${b.index}-${b.ma_key}`}
                    className={`rounded-xl border p-3 animate-fade-in-up ${
                      isBearish
                        ? 'bg-red-500/8 border-red-500/35'
                        : 'bg-emerald-500/8 border-emerald-500/30'
                    }`}
                    style={{ animationDelay: `${idx * 60}ms` }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span>{INDEX_FLAGS[b.index] ?? '📊'}</span>
                        <span className="font-mono font-black text-sm text-foreground">{b.index}</span>
                        <span className={`text-[0.6rem] font-bold px-1.5 py-0.5 rounded border ${
                          isBearish
                            ? 'bg-red-500/15 text-red-400 border-red-500/20'
                            : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
                        }`}>{b.ma_label}</span>
                      </div>
                      <span className={`text-lg ${isBearish ? 'text-red-400' : 'text-emerald-400'}`}>
                        {isBearish ? '↓' : '↑'}
                      </span>
                    </div>

                    <div className="text-[0.68rem] text-foreground/80 font-semibold mb-1">
                      {b.index_name.split('(')[0].trim()}
                      {isBearish ? ' ha roto a la baja' : ' ha recuperado'} la <span className="font-black">{b.ma_label}</span>
                    </div>

                    <div className="grid grid-cols-3 gap-1.5 mt-2">
                      <div className="text-center rounded bg-muted/15 px-1.5 py-1">
                        <div className="text-[0.55rem] text-muted-foreground/50 mb-0.5">Precio</div>
                        <div className="text-[0.7rem] font-bold tabular-nums">${b.current_price.toFixed(2)}</div>
                      </div>
                      <div className={`text-center rounded px-1.5 py-1 ${isBearish ? 'bg-red-500/8' : 'bg-emerald-500/8'}`}>
                        <div className="text-[0.55rem] text-muted-foreground/50 mb-0.5">Media</div>
                        <div className="text-[0.7rem] font-bold tabular-nums">${b.ma_value.toFixed(2)}</div>
                      </div>
                      <div className="text-center rounded bg-muted/15 px-1.5 py-1">
                        <div className="text-[0.55rem] text-muted-foreground/50 mb-0.5">Distancia</div>
                        <div className={`text-[0.7rem] font-black tabular-nums ${isBearish ? 'text-red-400' : 'text-emerald-400'}`}>
                          {b.pct_from_ma >= 0 ? '+' : ''}{b.pct_from_ma.toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    {b.days_since_cross < 999 && (
                      <div className="mt-2 text-[0.6rem] text-muted-foreground/50 text-right">
                        cruce hace {b.days_since_cross}d
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Status table for all monitored MAs */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[0.6rem] font-black uppercase tracking-[0.15em] text-muted-foreground/50">Estado actual</span>
            <div className="flex-1 h-px bg-border/20" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[460px] text-[0.68rem]">
              <thead>
                <tr className="border-b border-border/20">
                  <th className="text-left font-medium text-muted-foreground/60 pb-1.5 pr-2">Índice</th>
                  <th className="text-center font-medium text-muted-foreground/60 pb-1.5 px-1">MA50d</th>
                  <th className="text-center font-medium text-muted-foreground/60 pb-1.5 px-1">MA200d</th>
                  <th className="text-center font-medium text-muted-foreground/60 pb-1.5 px-1">MA10m</th>
                  <th className="text-center font-medium text-muted-foreground/60 pb-1.5 pl-1">MA20m</th>
                </tr>
              </thead>
              <tbody>
                {['QQQ','SPY','IWM','DIA','EWG','EEM'].map(ticker => {
                  const row: Record<string, IndexBreakout | undefined> = {}
                  breakouts.filter(b => b.index === ticker).forEach(b => { row[b.ma_key] = b })

                  if (Object.keys(row).length === 0) return null
                  const any = Object.values(row)[0]!

                  return (
                    <tr key={ticker} className="border-b border-border/10 last:border-0">
                      <td className="py-1.5 pr-2 font-mono font-bold text-foreground">
                        {INDEX_FLAGS[ticker] ?? '📊'} {ticker}
                        <span className="ml-1 font-normal text-muted-foreground/50 text-[0.6rem]">${any.current_price.toFixed(1)}</span>
                      </td>
                      {['ma50d','ma200d','ma10m','ma20m'].map(maKey => {
                        const b = row[maKey]
                        if (!b) return <td key={maKey} className="text-center px-1 py-1.5 text-muted-foreground/30">—</td>
                        const isBearishBreak = b.signal === 'BEARISH_BREAK'
                        const isBullishBreak = b.signal === 'BULLISH_BREAK'
                        const isAbove = b.direction === 'ABOVE'
                        return (
                          <td key={maKey} className="text-center px-1 py-1.5">
                            <span className={`inline-flex flex-col items-center gap-0.5`}>
                              <span className={`text-[0.65rem] font-black ${
                                isBearishBreak ? 'text-red-400 animate-pulse' :
                                isBullishBreak ? 'text-emerald-400 animate-pulse' :
                                isAbove ? 'text-emerald-400/70' : 'text-red-400/70'
                              }`}>
                                {isBearishBreak ? '↓BREAK' : isBullishBreak ? '↑BREAK' : isAbove ? '▲' : '▼'}
                              </span>
                              <span className={`text-[0.55rem] tabular-nums ${
                                b.pct_from_ma >= 0 ? 'text-emerald-400/60' : 'text-red-400/60'
                              }`}>
                                {b.pct_from_ma >= 0 ? '+' : ''}{b.pct_from_ma.toFixed(1)}%
                              </span>
                            </span>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

const SEVERITY_CONFIG: Record<string, { bg: string; text: string; label: string; icon: string }> = {
  CRITICAL: { bg: 'border-red-500/40 bg-red-500/10',      text: 'text-red-400',    label: 'CRÍTICO', icon: '🔴' },
  HIGH:     { bg: 'border-orange-500/30 bg-orange-500/8', text: 'text-orange-400', label: 'ALTO',    icon: '🟠' },
  MEDIUM:   { bg: 'border-amber-500/25 bg-amber-500/6',   text: 'text-yellow-400', label: 'MEDIO',   icon: '🟡' },
  LOW:      { bg: 'border-emerald-500/20 bg-emerald-500/5', text: 'text-emerald-400', label: 'BAJO', icon: '🔵' },
}

function SystemicRisksPanel({ risks }: { risks: SystemicRisk[] }) {
  const hasRealRisks = risks.some(r => r.id !== 'none')
  return (
    <Card className="glass border border-border/50 animate-fade-in-up">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-base">⚠️</span>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Riesgos Sistémicos Activos
          </p>
          {hasRealRisks && (
            <span className="ml-auto text-[0.6rem] font-bold px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/30">
              {risks.filter(r => r.id !== 'none').length} detectados
            </span>
          )}
        </div>
        <div className="space-y-3">
          {risks.map(risk => {
            const cfg = SEVERITY_CONFIG[risk.severity] ?? SEVERITY_CONFIG.MEDIUM
            return (
              <div key={risk.id} className={`rounded-lg border p-3 ${cfg.bg}`}>
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">{cfg.icon}</span>
                    <span className={`text-sm font-bold ${cfg.text}`}>{risk.name}</span>
                  </div>
                  <span className={`text-[0.58rem] font-bold px-1.5 py-0.5 rounded border ${cfg.bg} ${cfg.text} shrink-0`}>
                    {cfg.label}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-snug mb-2">{risk.description}</p>
                <div className="flex items-start gap-1.5">
                  <span className="text-[0.65rem] text-muted-foreground/50 shrink-0 mt-px">→</span>
                  <p className="text-[0.7rem] text-foreground/70 leading-snug italic">{risk.implication}</p>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function ReturnBadge({ value }: { value: number }) {
  const color = value > 0 ? 'text-emerald-400' : value < 0 ? 'text-red-400' : 'text-muted-foreground'
  return (
    <span className={`text-xs font-bold ${color}`}>
      {value > 0 ? '+' : ''}{value}%
    </span>
  )
}

function HistoricalAnalogsPanel({ analogs }: { analogs: HistoricalAnalog[] }) {
  return (
    <Card className="glass border border-border/50 animate-fade-in-up">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-base">🕰️</span>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Analogías Históricas
          </p>
        </div>
        <p className="text-[0.65rem] text-muted-foreground/60 mb-4">
          Episodios cuyo patrón de señales macro más se parece al entorno actual
        </p>
        {/* Horizontal scroll on mobile */}
        <div className="overflow-x-auto -mx-1 px-1">
          <div className="space-y-4 min-w-0">
            {analogs.map((analog, idx) => (
              <div
                key={analog.id}
                className="border border-border/30 rounded-lg p-3 bg-muted/5 active:scale-[0.98] transition-transform cursor-default"
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[0.6rem] text-muted-foreground/50 font-bold">#{idx + 1}</span>
                      <span className="text-sm font-bold text-foreground">{analog.name}</span>
                      <span className="text-[0.65rem] text-muted-foreground/60">{analog.date}</span>
                    </div>
                  </div>
                  {/* Similarity meter */}
                  <div className="text-right shrink-0">
                    <div
                      className="text-xs font-bold"
                      style={{ color: analog.similarity > 75 ? '#f97316' : analog.similarity > 60 ? '#f59e0b' : '#94a3b8' }}
                    >
                      {analog.similarity.toFixed(0)}%
                    </div>
                    <div className="text-[0.55rem] text-muted-foreground/50">similitud</div>
                  </div>
                </div>

                {/* Similarity bar */}
                <div className="h-1 w-full rounded-full bg-muted/30 mb-3" style={{ overflow: 'clip' }}>
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${analog.similarity}%`,
                      backgroundColor: analog.similarity > 75 ? '#f97316' : analog.similarity > 60 ? '#f59e0b' : '#94a3b8',
                    }}
                  />
                </div>

                {/* Outcome returns — color-coded */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  {[
                    { label: 'SPY 30d', value: analog.outcome.spy_30d },
                    { label: 'SPY 90d', value: analog.outcome.spy_90d },
                    { label: 'SPY 180d', value: analog.outcome.spy_180d },
                  ].map(o => (
                    <div key={o.label} className="text-center p-1.5 rounded bg-muted/10 border border-border/20">
                      <ReturnBadge value={o.value} />
                      <div className="text-[0.55rem] text-muted-foreground/50 mt-0.5">{o.label}</div>
                    </div>
                  ))}
                </div>

                {/* Description */}
                <p className="text-[0.68rem] text-muted-foreground/80 leading-snug mb-1.5">
                  {analog.outcome.description}
                </p>

                {/* Key difference */}
                <div className="flex items-start gap-1.5">
                  <span className="text-[0.65rem] text-blue-400/60 shrink-0 mt-px font-bold">≠</span>
                  <p className="text-[0.65rem] text-muted-foreground/60 leading-snug italic">{analog.key_difference}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-[0.6rem] text-muted-foreground/40 mt-3">
          * Similitud calculada sobre 9 señales clave. Los retornos son históricos, no predicciones.
        </p>
      </CardContent>
    </Card>
  )
}

export default function MacroRadar() {
  const { data, loading, error } = useApi<MacroData>(() => fetchMacroRadar(), [])
  const { data: historyData } = useApi(() => fetchMacroRadarHistory(), [])
  const { data: econData } = useApi(() => fetchEconomicCalendar(), [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  if (!data || !data.regime) return <ErrorState message="Sin datos de radar macro" />

  const { regime, composite_score, max_score, signals, signal_order, ai_narrative, date, errors, historical_analogs, systemic_risks, index_breakouts } = data

  const orderedSignals = (signal_order || Object.keys(signals)).filter(k => signals[k])

  const classicSignals = orderedSignals.filter(k => !['skew','vvix','regional_banks','small_cap','real_yields'].includes(k))
  const smartSignals   = orderedSignals.filter(k =>  ['skew','vvix','regional_banks','small_cap','real_yields'].includes(k))

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <StaleDataBanner dataDate={date} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold gradient-title mb-1">Macro Radar</h1>
          <p className="text-sm text-muted-foreground">
            Sistema de alerta temprana — detecta cambios de régimen antes de que ocurran
          </p>
        </div>
        <div className="text-right flex flex-col items-end gap-2">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-bold ${regimeBadgeVariant(regime.name)}`}
          >
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: regime.color }} />
            {regime.name}
          </span>
          <span className="text-xs text-muted-foreground">{date}</span>
        </div>
      </div>

      {/* Hero regime card */}
      <Card className="glass border border-border/50 animate-fade-in-up">
        <CardContent className="p-5 flex flex-col md:flex-row gap-6">
          {/* Left: regime info + narrative */}
          <div className="flex-1 space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: regime.color }} />
              <span className="text-3xl font-black text-foreground">{regime.name}</span>
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-bold ${regimeBadgeVariant(regime.name)}`}
              >
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: regime.color }} />
                {regime.name}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">{regime.description}</p>
            {ai_narrative && (
              <div className="mt-3 p-3 rounded-lg bg-muted/20 border border-border/30">
                <p className="text-xs font-semibold text-primary mb-1">Análisis IA</p>
                <p className="text-sm text-foreground/90 leading-relaxed">{ai_narrative}</p>
              </div>
            )}
          </div>
          {/* Right: score gauge + counts */}
          <div className="md:w-64 flex flex-col justify-center gap-2">
            <p className="text-xs text-muted-foreground font-medium">Puntuación compuesta</p>
            <ScoreGauge score={composite_score} max={max_score} />
            <div className="grid grid-cols-3 gap-1 mt-1">
              {[
                { label: 'Positivas', count: orderedSignals.filter(k => signals[k]?.score > 0).length, color: 'text-green-400' },
                { label: 'Neutras',   count: orderedSignals.filter(k => signals[k]?.score === 0).length, color: 'text-yellow-400' },
                { label: 'Negativas', count: orderedSignals.filter(k => signals[k]?.score < 0).length, color: 'text-red-400' },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <div className={`text-lg font-bold ${s.color}`}>{s.count}</div>
                  <div className="text-[0.62rem] text-muted-foreground">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* History chart */}
      <Card className="glass border border-border/40">
        <CardContent className="p-4">
          <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider">
            Evolución del régimen (últimos {historyData?.history?.length ?? 0} días)
          </p>
          <HistoryChart
            points={historyData?.history ?? []}
            maxScore={max_score}
          />
        </CardContent>
      </Card>

      {/* Index breakouts */}
      {index_breakouts && index_breakouts.length > 0 && (
        <IndexBreakoutsPanel breakouts={index_breakouts} />
      )}

      {/* Systemic risks */}
      {systemic_risks && systemic_risks.length > 0 && (
        <SystemicRisksPanel risks={systemic_risks} />
      )}

      {/* Historical analogs */}
      {historical_analogs && historical_analogs.length > 0 && (
        <HistoricalAnalogsPanel analogs={historical_analogs} />
      )}

      {/* Upcoming macro events — horizontal scrollable pill strip */}
      {econData && econData.events.length > 0 && (
        <Card className="glass border border-border/40">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider">
              Próximos eventos macroeconómicos
            </p>
            <div className="overflow-x-auto -mx-1 pb-1">
              <div className="flex gap-2 min-w-0 flex-nowrap px-1">
                {econData.events.slice(0, 10).map((ev: EconEvent) => {
                  const daysUntil = Math.ceil((new Date(ev.date).getTime() - Date.now()) / 86400000)
                  const typeConfig: Record<string, { color: string; bg: string; label: string }> = {
                    FED:      { color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20',       label: 'FED' },
                    CPI:      { color: 'text-orange-400',  bg: 'bg-orange-500/10 border-orange-500/20', label: 'CPI' },
                    PCE:      { color: 'text-yellow-400',  bg: 'bg-yellow-500/10 border-yellow-500/20', label: 'PCE' },
                    JOBS:     { color: 'text-blue-400',    bg: 'bg-blue-500/10 border-blue-500/20',     label: 'NFP' },
                    EARNINGS: { color: 'text-purple-400',  bg: 'bg-purple-500/10 border-purple-500/20', label: 'EARN' },
                  }
                  const cfg = typeConfig[ev.type] ?? { color: 'text-muted-foreground', bg: 'bg-muted/10 border-border/20', label: ev.type }
                  const urgencyColor = daysUntil <= 3 ? 'text-red-400' : daysUntil <= 7 ? 'text-orange-400' : 'text-muted-foreground/60'
                  return (
                    <div
                      key={ev.date + ev.event}
                      className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs whitespace-nowrap ${cfg.bg} ${cfg.color}`}
                    >
                      <span className="font-bold">{cfg.label}</span>
                      <span className="text-foreground/70">{ev.event}</span>
                      <span className={`font-semibold ${urgencyColor}`}>
                        {daysUntil <= 0 ? 'Hoy' : `${daysUntil}d`}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Signal grid */}
      <div className="space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wider">
            Señales clásicas
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {classicSignals.map((key, idx) => (
              <SignalCard key={key} id={key} signal={signals[key]} stagger={idx + 1} />
            ))}
          </div>
        </div>
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground mb-1 uppercase tracking-wider">
            Smart Money — señales que el retail ignora
          </h2>
          <p className="text-xs text-muted-foreground/60 mb-3">
            SKEW, VVIX, bancos regionales, small caps y yields reales — indicadores de posicionamiento institucional
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {smartSignals.map((key, idx) => (
              <SignalCard key={key} id={key} signal={signals[key]} stagger={idx + 1} />
            ))}
          </div>
        </div>
      </div>

      {/* Data errors */}
      {errors && errors.length > 0 && (
        <div className="text-xs text-muted-foreground/60 text-right">
          Señales sin datos: {errors.join(', ')}
        </div>
      )}

      {/* Legend */}
      <Card className="glass border border-border/30">
        <CardContent className="p-4">
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">Guía de regímenes</p>
          <div className="flex flex-wrap gap-3">
            {[
              { name: 'CALM',   color: '#10b981', desc: 'Favorable' },
              { name: 'WATCH',  color: '#84cc16', desc: 'Vigilancia' },
              { name: 'STRESS', color: '#f59e0b', desc: 'Estrés moderado' },
              { name: 'ALERT',  color: '#f97316', desc: 'Alerta elevada' },
              { name: 'CRISIS', color: '#ef4444', desc: 'Capital protection' },
            ].map(r => (
              <div key={r.name} className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: r.color }} />
                <span className="text-xs font-bold" style={{ color: r.color }}>{r.name}</span>
                <span className="text-xs text-muted-foreground">— {r.desc}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
