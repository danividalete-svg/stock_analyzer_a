import { useEffect, useState } from 'react'
import { X, TrendingUp, AlertTriangle, Copy, Check, ExternalLink, Shield, Award } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import GradeBadge from './GradeBadge'
import ThesisBody from './ThesisBody'
import TickerLogo from './TickerLogo'
import PriceChart from './PriceChart'
import type { ValueOpportunity, TechnicalSignal } from '../api/client'
import { useTechnicalSignals } from '../hooks/useTechnicalSignals'

// ── Technical signals panel ───────────────────────────────────────────────────

function TechnicalPanel({ ticker }: { ticker: string }) {
  const { signals, summary, loading } = useTechnicalSignals(ticker)

  if (loading) return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground/50 py-2">
      <div className="w-3 h-3 border-2 border-muted-foreground/30 border-t-primary rounded-full animate-spin" />
      Cargando señales...
    </div>
  )

  if (!summary && signals.length === 0) return null

  const bullish = signals.filter((s: TechnicalSignal) => s.direction === 'BULLISH')
  const bearish = signals.filter((s: TechnicalSignal) => s.direction === 'BEARISH')
  const top = [...signals]
    .sort((a: TechnicalSignal, b: TechnicalSignal) => a.days_ago - b.days_ago || b.strength - a.strength)
    .slice(0, 5)

  const biasColor = summary?.bias === 'BULLISH' ? 'text-emerald-400' : summary?.bias === 'BEARISH' ? 'text-red-400' : 'text-muted-foreground'
  const biasBg = summary?.bias === 'BULLISH' ? 'bg-emerald-500/15 border-emerald-500/30' : summary?.bias === 'BEARISH' ? 'bg-red-500/15 border-red-500/30' : 'bg-muted/30 border-border/30'
  const biasLabel = summary?.bias === 'BULLISH' ? 'ALCISTA' : summary?.bias === 'BEARISH' ? 'BAJISTA' : 'NEUTRO'

  return (
    <div>
      <div className="flex items-center gap-2.5 mb-3 flex-wrap">
        <h4 className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Señales Técnicas</h4>
        <span className={`text-[0.65rem] font-bold px-2 py-0.5 rounded-full border ${biasBg} ${biasColor}`}>
          {biasLabel}
        </span>
        <span className="text-[0.65rem] text-emerald-400 font-medium">+{bullish.length} alcistas</span>
        <span className="text-[0.65rem] text-red-400 font-medium">−{bearish.length} bajistas</span>
      </div>
      <div className="space-y-1">
        {top.map((s: TechnicalSignal, i: number) => (
          <div key={i} className="flex items-center gap-2 py-1 px-2 rounded-lg bg-muted/20 hover:bg-muted/30 transition-colors">
            <span className={`shrink-0 text-[0.55rem] font-bold w-8 text-center py-0.5 rounded border ${
              s.direction === 'BULLISH' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25' :
              s.direction === 'BEARISH' ? 'bg-red-500/10 text-red-400 border-red-500/25' :
              'bg-muted/20 text-muted-foreground border-border/20'
            }`}>
              {s.direction === 'BULLISH' ? '▲' : s.direction === 'BEARISH' ? '▼' : '—'}{s.timeframe === 'WEEKLY' ? 'W' : 'D'}
            </span>
            <span className="text-xs text-foreground/80 flex-1">{s.signal_name}</span>
            <span className="text-[0.6rem] text-muted-foreground/50 tabular-nums shrink-0">
              {s.days_ago === 0 ? 'hoy' : s.days_ago === 1 ? 'ayer' : `${s.days_ago}d`}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Conviction panel ──────────────────────────────────────────────────────────

function ConvictionPanel({ row }: { row: ValueOpportunity }) {
  const reasons = row.conviction_reasons
    ? row.conviction_reasons.split(' | ').filter(Boolean)
    : []
  const pos   = row.conviction_positives ?? 0
  const flags = row.conviction_red_flags ?? 0
  const score = row.conviction_score
  const grade = row.conviction_grade

  if (!reasons.length && score == null) return null

  return (
    <div>
      <div className="flex items-center gap-2.5 mb-3 flex-wrap">
        <h4 className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Award size={11} className="text-primary" />
          Conviction IA
        </h4>
        {grade && score != null && (
          <span className={`text-xs font-bold px-2.5 py-0.5 rounded-lg ${
            grade === 'A' || grade === 'A+' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25' :
            grade === 'B' ? 'bg-blue-500/15 text-blue-400 border border-blue-500/25' :
            'bg-amber-500/15 text-amber-400 border border-amber-500/25'
          }`}>
            {grade} — {score.toFixed(0)}pts
          </span>
        )}
      </div>

      {/* Score bar */}
      <div className="flex items-center gap-4 mb-3">
        <div className="flex items-center gap-2 flex-1">
          <span className="text-[0.6rem] text-emerald-400 font-semibold shrink-0">+{pos}</span>
          <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-hidden flex">
            {pos > 0 && <div className="h-full bg-emerald-500/60 rounded-full" style={{ width: `${(pos / (pos + flags || 1)) * 100}%` }} />}
            {flags > 0 && <div className="h-full bg-red-500/60 rounded-full" style={{ width: `${(flags / (pos + flags || 1)) * 100}%` }} />}
          </div>
          <span className="text-[0.6rem] text-red-400 font-semibold shrink-0">{flags}</span>
        </div>
      </div>

      {reasons.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {reasons.map((r, i) => {
            const isPositive = /alta|strong|crecimiento|sólid|excelente|seguro|activo|buyback|favorable/i.test(r)
            const isNegative = /riesgo|alerta|bajo|débil|negativo|warning|alto endeud/i.test(r)
            return (
              <span key={i} className={`text-[0.62rem] px-2 py-0.5 rounded-lg border ${
                isPositive ? 'bg-emerald-500/8 border-emerald-500/20 text-emerald-400/80' :
                isNegative ? 'bg-red-500/8 border-red-500/20 text-red-400/80' :
                'bg-muted/20 border-border/40 text-muted-foreground/70'
              }`}>
                {r}
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Metric chip ───────────────────────────────────────────────────────────────

function Chip({ label, value, color }: { label: string; value: string; color?: string }) {
  const bg =
    color?.includes('emerald') ? 'bg-emerald-500/8 border-emerald-500/20' :
    color?.includes('red')     ? 'bg-red-500/8 border-red-500/15'         :
    color?.includes('amber')   ? 'bg-amber-500/8 border-amber-500/15'     :
    color?.includes('purple')  ? 'bg-purple-500/8 border-purple-500/15'   :
    color?.includes('primary') ? 'bg-primary/8 border-primary/20'         :
                                 'bg-muted/20 border-border/20'
  return (
    <div className={`flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg border min-w-[56px] ${bg}`}>
      <span className="text-[0.5rem] font-bold uppercase tracking-widest text-muted-foreground/40 leading-none">{label}</span>
      <span className={`text-[0.82rem] font-bold tabular-nums leading-none ${color ?? 'text-foreground/70'}`}>{value}</span>
    </div>
  )
}

// ── Main modal ────────────────────────────────────────────────────────────────

interface Props {
  row: ValueOpportunity
  thesisText: string
  onClose: () => void
  currency?: string
}

export default function ThesisModal({ row, thesisText, onClose, currency = '$' }: Props) {
  const [copied, setCopied] = useState(false)

  const copyTicker = () => {
    navigator.clipboard.writeText(row.ticker).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const upside = row.analyst_upside_pct
  const rr     = row.risk_reward_ratio
  const fcf    = row.fcf_yield_pct
  const earn   = row.days_to_earnings
  const price  = row.current_price

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="fixed z-50 bottom-0 left-0 right-0 sm:inset-0 sm:flex sm:items-center sm:justify-center sm:p-4"
        role="dialog"
        aria-modal="true"
      >
        <div className="relative w-full sm:max-w-4xl bg-[hsl(var(--card))] border border-border/50 shadow-2xl rounded-t-2xl sm:rounded-2xl flex flex-col max-h-[92dvh] sm:max-h-[90dvh] modal-enter overflow-hidden">
          {/* Top accent */}
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-primary/50 via-primary to-purple-500/50 z-10" />

          {/* Handle (mobile) */}
          <div className="sm:hidden flex justify-center pt-3 pb-1 flex-shrink-0">
            <div className="w-10 h-1 rounded-full bg-muted-foreground/25" />
          </div>

          {/* ── Header ── */}
          <div className="flex items-start justify-between gap-4 px-5 lg:px-6 pt-4 pb-3 flex-shrink-0">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2.5 flex-wrap mb-1">
                <TickerLogo ticker={row.ticker} size="md" />
                <span className="font-mono font-extrabold text-primary text-2xl tracking-tight">{row.ticker}</span>
                <GradeBadge grade={row.conviction_grade} score={row.conviction_score} />
                {row.earnings_warning && (
                  <Badge variant="yellow" className="text-[0.6rem] gap-1">
                    <AlertTriangle size={10} strokeWidth={2} /> Earnings
                  </Badge>
                )}
                {row.proximity_to_52w_high != null && row.proximity_to_52w_high > -5 && (
                  <Badge variant="green" className="text-[0.58rem]">52w High</Badge>
                )}
              </div>
              <p className="text-sm text-foreground/60">{row.company_name}</p>
              {row.sector && <p className="text-[0.68rem] text-muted-foreground/40">{row.sector}</p>}
            </div>
            <div className="flex items-start gap-1.5 shrink-0">
              {price != null && (
                <div className="text-right mr-2">
                  <div className="text-2xl font-extrabold tabular-nums tracking-tight">{currency}{price.toFixed(2)}</div>
                  {upside != null && (
                    <div className={`text-xs font-semibold tabular-nums flex items-center gap-1 justify-end ${upside >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      <TrendingUp size={11} />
                      {upside >= 0 ? '+' : ''}{upside.toFixed(1)}%
                    </div>
                  )}
                </div>
              )}
              <button onClick={copyTicker} className="p-1.5 rounded-lg text-muted-foreground/50 hover:bg-muted/40 hover:text-foreground transition-colors" title="Copiar ticker">
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
              </button>
              <a href={`https://www.tradingview.com/chart/?symbol=${row.ticker}`} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded-lg text-muted-foreground/50 hover:bg-muted/40 hover:text-foreground transition-colors" title="TradingView">
                <ExternalLink size={14} />
              </a>
              <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground/50 hover:bg-muted/40 hover:text-foreground transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* ── Entry / Stop / Target ── */}
          {(row.entry_price != null || row.stop_loss != null || row.target_price != null) && (
            <div className="flex gap-2 px-5 lg:px-6 pb-3 flex-shrink-0">
              {row.entry_price != null && (
                <div className="flex-1 px-3 py-2 rounded-lg bg-primary/6 border border-primary/15">
                  <div className="text-[0.5rem] font-bold uppercase tracking-widest text-primary/40 mb-0.5">Entrada</div>
                  <div className="font-extrabold text-[0.95rem] tabular-nums text-primary leading-none">{currency}{row.entry_price.toFixed(2)}</div>
                </div>
              )}
              {row.stop_loss != null && (
                <div className="flex-1 px-3 py-2 rounded-lg bg-red-500/6 border border-red-500/15">
                  <div className="text-[0.5rem] font-bold uppercase tracking-widest text-red-400/40 mb-0.5">Stop Loss</div>
                  <div className="font-extrabold text-[0.95rem] tabular-nums text-red-400 leading-none">{currency}{row.stop_loss.toFixed(2)}</div>
                </div>
              )}
              {row.target_price != null && (
                <div className="flex-1 px-3 py-2 rounded-lg bg-emerald-500/6 border border-emerald-500/15">
                  <div className="text-[0.5rem] font-bold uppercase tracking-widest text-emerald-400/40 mb-0.5">Objetivo</div>
                  <div className="font-extrabold text-[0.95rem] tabular-nums text-emerald-400 leading-none">{currency}{row.target_price.toFixed(2)}</div>
                </div>
              )}
            </div>
          )}

          {/* ── Metrics strip ── */}
          <div className="flex gap-1.5 px-5 lg:px-6 pb-3 overflow-x-auto flex-shrink-0 scrollbar-hide">
            <Chip label="Score" value={row.value_score.toFixed(0)} color="text-primary" />
            {row.piotroski_score != null && (
              <Chip label="F-Score" value={`${row.piotroski_score}/9`} color={row.piotroski_score >= 8 ? 'text-emerald-400' : row.piotroski_score <= 2 ? 'text-red-400' : 'text-amber-400'} />
            )}
            {row.magic_formula_rank != null && (
              <Chip label="MF Rank" value={`#${row.magic_formula_rank}`} color="text-purple-400" />
            )}
            {row.peg_ratio != null && (
              <Chip label="PEG" value={row.peg_ratio.toFixed(2)} color={row.peg_ratio < 1 ? 'text-emerald-400' : row.peg_ratio < 2 ? 'text-amber-400' : 'text-red-400'} />
            )}
            {rr != null && (
              <Chip label="R:R" value={rr.toFixed(1)} color={rr >= 2 ? 'text-emerald-400' : rr >= 1 ? 'text-amber-400' : 'text-red-400'} />
            )}
            {fcf != null && (
              <Chip label="FCF%" value={`${fcf.toFixed(1)}%`} color={fcf >= 5 ? 'text-emerald-400' : fcf >= 3 ? 'text-amber-400' : fcf < 0 ? 'text-red-400' : ''} />
            )}
            {row.roic_greenblatt != null && (
              <Chip label="ROIC" value={`${row.roic_greenblatt.toFixed(0)}%`} color={row.roic_greenblatt >= 20 ? 'text-emerald-400' : row.roic_greenblatt >= 10 ? 'text-amber-400' : ''} />
            )}
            {row.dividend_yield_pct != null && row.dividend_yield_pct > 0 && (
              <Chip label="Div" value={`${row.dividend_yield_pct.toFixed(1)}%`} color="text-emerald-400" />
            )}
            {row.buyback_active && <Chip label="Buyback" value="Activo" color="text-emerald-400" />}
            {(row.hedge_fund_count ?? 0) >= 1 && (
              <Chip label="Smart $" value={`${row.hedge_fund_count}`} color={(row.hedge_fund_count ?? 0) >= 2 ? 'text-amber-400' : ''} />
            )}
            {earn != null && (
              <Chip label="Earnings" value={`${earn}d`} color={earn <= 7 ? 'text-red-400' : earn <= 21 ? 'text-amber-400' : 'text-emerald-400'} />
            )}
            {row.target_price_analyst != null && (
              <Chip label="Target" value={`${currency}${row.target_price_analyst.toFixed(0)}`} />
            )}
            {row.analyst_count != null && (
              <Chip label="Analistas" value={String(row.analyst_count)} />
            )}
          </div>

          {/* ── Scrollable content — 2 columns on desktop ── */}
          <div className="flex-1 overflow-y-auto min-h-0 border-t border-border/30">
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-0 lg:gap-0 lg:divide-x lg:divide-border/20">

              {/* Left column: Chart + Technicals + Conviction (2/5) */}
              <div className="lg:col-span-2 px-5 lg:px-5 py-4 space-y-5 lg:border-r-0">
                {/* Mini chart */}
                <div className="rounded-xl overflow-hidden border border-border/15 bg-muted/5">
                  <PriceChart ticker={row.ticker} height={140} />
                </div>

                {/* Technical Signals */}
                <TechnicalPanel ticker={row.ticker} />

                {/* Conviction */}
                <ConvictionPanel row={row} />

                {/* Quick health summary */}
                {(row.roe_pct != null || row.profit_margin_pct != null || row.revenue_growth_pct != null) && (
                  <div>
                    <h4 className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2 flex items-center gap-1.5">
                      <Shield size={11} className="text-emerald-400" />
                      Salud Financiera
                    </h4>
                    <div className="grid grid-cols-3 gap-2">
                      {row.roe_pct != null && (
                        <div className="text-center py-2 px-1 rounded-lg bg-muted/15 border border-border/15">
                          <div className={`text-sm font-bold tabular-nums ${row.roe_pct >= 15 ? 'text-emerald-400' : row.roe_pct < 0 ? 'text-red-400' : 'text-foreground/60'}`}>
                            {row.roe_pct.toFixed(1)}%
                          </div>
                          <div className="text-[0.5rem] text-muted-foreground/40 font-medium uppercase">ROE</div>
                        </div>
                      )}
                      {row.profit_margin_pct != null && (
                        <div className="text-center py-2 px-1 rounded-lg bg-muted/15 border border-border/15">
                          <div className={`text-sm font-bold tabular-nums ${row.profit_margin_pct >= 15 ? 'text-emerald-400' : row.profit_margin_pct < 0 ? 'text-red-400' : 'text-foreground/60'}`}>
                            {row.profit_margin_pct.toFixed(1)}%
                          </div>
                          <div className="text-[0.5rem] text-muted-foreground/40 font-medium uppercase">Margen</div>
                        </div>
                      )}
                      {row.revenue_growth_pct != null && (
                        <div className="text-center py-2 px-1 rounded-lg bg-muted/15 border border-border/15">
                          <div className={`text-sm font-bold tabular-nums ${row.revenue_growth_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {row.revenue_growth_pct >= 0 ? '+' : ''}{row.revenue_growth_pct.toFixed(1)}%
                          </div>
                          <div className="text-[0.5rem] text-muted-foreground/40 font-medium uppercase">Revenue</div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Right column: Thesis (3/5) */}
              <div className="lg:col-span-3 px-5 lg:px-5 py-4 lg:border-t-0 border-t border-border/20">
                <h4 className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-3">Tesis de Inversión</h4>
                <ThesisBody text={thesisText} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
