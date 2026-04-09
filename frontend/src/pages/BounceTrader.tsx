import { useState, useMemo } from 'react'
import { fetchMeanReversion } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import StaleDataBanner from '../components/StaleDataBanner'
import TickerLogo from '../components/TickerLogo'
import { AlertTriangle, TrendingDown, Zap } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface BounceSetup {
  ticker: string
  company_name: string
  strategy: string
  current_price: number
  rsi: number
  rsi_tier?: 'EXTREMO' | 'ALTO' | 'MEDIO'
  drawdown_pct: number
  support_level: number
  distance_to_support_pct: number
  volume_ratio: number
  reversion_score: number
  bounce_target?: number
  bounce_usd?: number
  bounce_pct?: number
  stop_loss: number
  stop_pct?: number
  risk_reward: number
  bounce_confidence?: number
  bounce_signals?: string[]
  consecutive_down_days?: number
  bb_pct_b?: number
  below_bb?: boolean
  stoch_k?: number
  volume_drying?: boolean
  // Advanced signals
  rsi_weekly?: number | null
  weekly_oversold?: boolean
  cum_rsi2?: number | null
  connors_signal?: boolean
  atr14?: number
  hammer_candle?: boolean
  engulfing_candle?: boolean
  obv_divergence?: boolean
  market_regime?: string
  market_ok?: boolean | null
  days_to_earnings?: number | null
  earnings_warning?: boolean
  detected_date: string
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function tierColor(tier?: string) {
  if (tier === 'EXTREMO') return { dot: 'bg-red-400', text: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' }
  if (tier === 'ALTO')    return { dot: 'bg-orange-400', text: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30' }
  return { dot: 'bg-amber-400', text: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' }
}

function confidenceBar(score?: number) {
  const pct = Math.min(100, score ?? 0)
  const color = pct >= 60 ? 'bg-emerald-400' : pct >= 35 ? 'bg-amber-400' : 'bg-red-400'
  const label = pct >= 60 ? 'Alta' : pct >= 35 ? 'Media' : 'Baja'
  return { pct, color, label }
}

// ─── Card ─────────────────────────────────────────────────────────────────────

function BounceCard({ s }: { s: BounceSetup }) {
  const tc = tierColor(s.rsi_tier)
  const conf = confidenceBar(s.bounce_confidence)
  const bounceUsd = s.bounce_usd ?? (s.bounce_target ? s.bounce_target - s.current_price : null)
  const bouncePct = s.bounce_pct ?? (bounceUsd != null ? (bounceUsd / s.current_price * 100) : null)
  const stopPct   = s.stop_pct ?? ((s.stop_loss / s.current_price - 1) * 100)
  const rr        = s.risk_reward > 0 ? s.risk_reward : null

  return (
    <div className="glass rounded-2xl border border-border/20 hover:border-primary/30 transition-all p-4 flex flex-col gap-3">

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <TickerLogo ticker={s.ticker} size="sm" />
          <div className="min-w-0">
            <div className="font-mono font-extrabold text-foreground text-base leading-tight tracking-wide">{s.ticker}</div>
            <div className="text-[0.65rem] text-muted-foreground/60 truncate">{s.company_name}</div>
          </div>
        </div>
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[0.65rem] font-bold shrink-0 ${tc.bg}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${tc.dot}`} />
          <span className={tc.text}>RSI {s.rsi?.toFixed(1)} · {s.rsi_tier ?? 'MEDIO'}</span>
        </div>
      </div>

      {/* Earnings warning */}
      {s.earnings_warning && (
        <div className="flex items-center gap-1.5 text-[0.65rem] text-amber-400 bg-amber-500/8 border border-amber-500/20 rounded-lg px-2.5 py-1.5">
          <AlertTriangle size={11} />
          <span>Earnings en {s.days_to_earnings}d — riesgo elevado</span>
        </div>
      )}

      {/* Main numbers */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-muted/10 rounded-xl p-2.5 text-center">
          <div className="text-[0.58rem] font-bold uppercase tracking-wider text-muted-foreground/40 mb-1">Entrada</div>
          <div className="text-sm font-extrabold text-foreground tabular-nums">${s.current_price.toFixed(2)}</div>
        </div>
        <div className="bg-emerald-500/8 border border-emerald-500/20 rounded-xl p-2.5 text-center">
          <div className="text-[0.58rem] font-bold uppercase tracking-wider text-emerald-400/50 mb-1">Rebote</div>
          <div className="text-sm font-extrabold text-emerald-400 tabular-nums">
            {bounceUsd != null ? `+$${bounceUsd.toFixed(2)}` : '—'}
          </div>
          {bouncePct != null && (
            <div className="text-[0.6rem] text-emerald-400/60">+{bouncePct.toFixed(1)}%</div>
          )}
        </div>
        <div className="bg-red-500/8 border border-red-500/20 rounded-xl p-2.5 text-center">
          <div className="text-[0.58rem] font-bold uppercase tracking-wider text-red-400/50 mb-1">Stop</div>
          <div className="text-sm font-extrabold text-red-400 tabular-nums">${s.stop_loss.toFixed(2)}</div>
          <div className="text-[0.6rem] text-red-400/60">{stopPct.toFixed(1)}%</div>
        </div>
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-[0.65rem] text-muted-foreground/60">
        <span>R:R <strong className={`${rr && rr >= 2 ? 'text-emerald-400' : rr && rr >= 1 ? 'text-amber-400' : 'text-muted-foreground'}`}>{rr ? `${rr.toFixed(1)}:1` : '—'}</strong></span>
        <span>Vol <strong className={s.volume_ratio >= 1.5 ? 'text-cyan-400' : 'text-muted-foreground'}>{s.volume_ratio.toFixed(1)}x</strong></span>
        <span>Caída <strong className="text-foreground">{s.drawdown_pct.toFixed(0)}%</strong></span>
        {s.consecutive_down_days != null && s.consecutive_down_days >= 2 && (
          <span className="flex items-center gap-0.5 text-red-400/70">
            <TrendingDown size={10} />
            {s.consecutive_down_days}d seguidos
          </span>
        )}
      </div>

      {/* Bounce confidence bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[0.58rem] font-bold uppercase tracking-wider text-muted-foreground/40">Confianza rebote</span>
          <span className={`text-[0.6rem] font-bold ${conf.color.replace('bg-', 'text-')}`}>{conf.label} {conf.pct}%</span>
        </div>
        <div className="h-1 bg-muted/20 rounded-full overflow-clip">
          <div className={`h-full rounded-full transition-all ${conf.color}`} style={{ width: `${conf.pct}%` }} />
        </div>
        {(s.bounce_signals?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {s.bounce_signals!.map(sig => (
              <span key={sig} className="text-[0.58rem] px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary/70">{sig}</span>
            ))}
          </div>
        )}
      </div>

      {/* Indicators row */}
      <div className="grid grid-cols-4 gap-1.5 text-[0.58rem] text-center">
        {s.stoch_k != null && (
          <div className={`rounded-lg px-1.5 py-1 border ${s.stoch_k < 20 ? 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400' : 'bg-muted/10 border-border/20 text-muted-foreground/50'}`}>
            <div className="font-bold uppercase tracking-wider mb-0.5">Stoch</div>
            <div className="font-extrabold">{s.stoch_k.toFixed(0)}</div>
          </div>
        )}
        {s.bb_pct_b != null && (
          <div className={`rounded-lg px-1.5 py-1 border ${s.below_bb ? 'bg-purple-500/8 border-purple-500/20 text-purple-400' : 'bg-muted/10 border-border/20 text-muted-foreground/50'}`}>
            <div className="font-bold uppercase tracking-wider mb-0.5">BB%</div>
            <div className="font-extrabold">{s.bb_pct_b.toFixed(0)}</div>
          </div>
        )}
        {s.rsi_weekly != null && (
          <div className={`rounded-lg px-1.5 py-1 border ${s.weekly_oversold ? 'bg-orange-500/8 border-orange-500/20 text-orange-400' : 'bg-muted/10 border-border/20 text-muted-foreground/50'}`}>
            <div className="font-bold uppercase tracking-wider mb-0.5">RSI W</div>
            <div className="font-extrabold">{s.rsi_weekly.toFixed(0)}</div>
          </div>
        )}
        {s.cum_rsi2 != null && (
          <div className={`rounded-lg px-1.5 py-1 border ${s.connors_signal ? 'bg-cyan-500/8 border-cyan-500/20 text-cyan-400' : 'bg-muted/10 border-border/20 text-muted-foreground/50'}`}>
            <div className="font-bold uppercase tracking-wider mb-0.5">CRsi2</div>
            <div className="font-extrabold">{s.cum_rsi2.toFixed(0)}</div>
          </div>
        )}
      </div>

      {/* Market regime + candle pattern */}
      {(s.market_regime || s.hammer_candle || s.engulfing_candle || s.obv_divergence) && (
        <div className="flex flex-wrap gap-1">
          {s.market_regime && (
            <span className={`text-[0.58rem] px-1.5 py-0.5 rounded border font-medium ${s.market_ok ? 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400/80' : s.market_ok === false ? 'bg-red-500/8 border-red-500/20 text-red-400/80' : 'bg-muted/10 border-border/20 text-muted-foreground/50'}`}>
              {s.market_ok ? '✓' : '⚠'} {s.market_regime}
            </span>
          )}
          {s.hammer_candle && <span className="text-[0.58rem] px-1.5 py-0.5 rounded border bg-amber-500/8 border-amber-500/20 text-amber-400">🔨 Hammer</span>}
          {s.engulfing_candle && <span className="text-[0.58rem] px-1.5 py-0.5 rounded border bg-emerald-500/8 border-emerald-500/20 text-emerald-400">📈 Engulfing</span>}
          {s.obv_divergence && <span className="text-[0.58rem] px-1.5 py-0.5 rounded border bg-blue-500/8 border-blue-500/20 text-blue-400">↗ OBV div.</span>}
        </div>
      )}
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

type TierFilter = 'ALL' | 'EXTREMO' | 'ALTO' | 'MEDIO'

export default function BounceTrader() {
  const { data: raw, loading, error } = useApi(() => fetchMeanReversion(), [])
  const [tierFilter, setTierFilter] = useState<TierFilter>('ALL')
  const [hideEarnings, setHideEarnings] = useState(true)

  const allSetups: BounceSetup[] = useMemo(() => {
    const ops: BounceSetup[] = Array.isArray(raw?.opportunities) ? raw.opportunities : []
    return ops.filter(s =>
      s.strategy === 'Oversold Bounce' &&
      s.rsi != null && s.rsi < 30 &&
      (s.distance_to_support_pct == null || s.distance_to_support_pct >= -10)
    )
  }, [raw])

  const setups = useMemo(() => {
    let s = allSetups
    if (tierFilter !== 'ALL') s = s.filter(x => x.rsi_tier === tierFilter)
    if (hideEarnings) s = s.filter(x => !x.earnings_warning)
    return [...s].sort((a, b) => (a.rsi ?? 99) - (b.rsi ?? 99))
  }, [allSetups, tierFilter, hideEarnings])

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const scanDate = (raw as Record<string, unknown>)?.scan_date as string | undefined
  const extremos = allSetups.filter(s => s.rsi_tier === 'EXTREMO').length
  const altos    = allSetups.filter(s => s.rsi_tier === 'ALTO').length
  const withEarn = allSetups.filter(s => s.earnings_warning).length

  return (
    <>
      <StaleDataBanner module="mean_reversion" />

      {/* Header */}
      <div className="mb-6 animate-fade-in-up">
        <div className="flex items-start justify-between gap-4 mb-1">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight gradient-title flex items-center gap-2">
              <Zap size={20} className="text-orange-400" />
              Bounce Trader
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Rebotes técnicos de 1–3 días · Oversold extremo + confirmación multi-indicador
              {scanDate && <span className="text-muted-foreground/40 ml-2">· Scan {scanDate}</span>}
            </p>
          </div>
        </div>

        {/* Summary pills */}
        <div className="flex flex-wrap gap-2 mt-3">
          <div className="flex items-center gap-1.5 text-[0.7rem] px-3 py-1.5 rounded-lg bg-red-500/8 border border-red-500/20 text-red-400">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            <span className="font-bold">{extremos}</span> EXTREMO (RSI &lt;20)
          </div>
          <div className="flex items-center gap-1.5 text-[0.7rem] px-3 py-1.5 rounded-lg bg-orange-500/8 border border-orange-500/20 text-orange-400">
            <span className="w-1.5 h-1.5 rounded-full bg-orange-400" />
            <span className="font-bold">{altos}</span> ALTO (RSI 20–25)
          </div>
          {withEarn > 0 && (
            <div className="flex items-center gap-1.5 text-[0.7rem] px-3 py-1.5 rounded-lg bg-amber-500/8 border border-amber-500/20 text-amber-400">
              <AlertTriangle size={11} />
              <span className="font-bold">{withEarn}</span> con earnings próximos
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        {(['ALL', 'EXTREMO', 'ALTO', 'MEDIO'] as TierFilter[]).map(t => {
          const count = t === 'ALL' ? allSetups.length : allSetups.filter(s => s.rsi_tier === t).length
          return (
            <button
              key={t}
              onClick={() => setTierFilter(t)}
              className={`text-[0.68rem] font-bold px-3 py-1.5 rounded-lg border transition-colors ${
                tierFilter === t
                  ? 'bg-primary/20 border-primary/50 text-primary'
                  : 'bg-muted/10 border-border/30 text-muted-foreground hover:border-border/60 hover:text-foreground'
              }`}
            >
              {t === 'ALL' ? 'Todos' : t} ({count})
            </button>
          )
        })}
        <div className="ml-auto">
          <button
            onClick={() => setHideEarnings(v => !v)}
            className={`text-[0.68rem] font-bold px-3 py-1.5 rounded-lg border transition-colors ${
              hideEarnings
                ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                : 'bg-muted/10 border-border/30 text-muted-foreground hover:border-border/60'
            }`}
          >
            {hideEarnings ? '⚠ Ocultar earnings' : 'Mostrar earnings'}
          </button>
        </div>
      </div>

      {/* Cards grid */}
      {setups.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground/50">
          <div className="text-4xl mb-3 opacity-20">📊</div>
          <div className="text-sm">No hay setups de rebote válidos hoy</div>
          <div className="text-xs mt-1 opacity-60">Espera a que el mercado genere nuevas oportunidades oversold</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {setups.map(s => <BounceCard key={s.ticker} s={s} />)}
        </div>
      )}
    </>
  )
}
