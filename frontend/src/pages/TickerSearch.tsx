import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { analyzeTicker, analyzeTickerAI, searchTickers, fetchScoreHistory } from '../api/client'
import type { SearchResult, ScoreHistoryPoint } from '../api/client'
import AiNarrativeCard from '../components/AiNarrativeCard'
import PriceChart from '../components/PriceChart'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import { Search, AlertCircle } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export default function TickerSearch() {
  const [searchParams] = useSearchParams()
  const [ticker, setTicker] = useState(() => searchParams.get('q') ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [suggestions, setSuggestions] = useState<SearchResult[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const [scoreHistory, setScoreHistory] = useState<ScoreHistoryPoint[]>([])
  const [aiNarrative, setAiNarrative] = useState<string | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Auto-search if ?q= param on mount
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) doSearch(q)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced autocomplete
  useEffect(() => {
    const t = ticker.trim()
    if (t.length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    const timer = setTimeout(async () => {
      try {
        const res = await searchTickers(t)
        const items = res.data?.results || []
        setSuggestions(items)
        setShowSuggestions(items.length > 0)
        setActiveIdx(-1)
      } catch {
        setSuggestions([])
      }
    }, 280)
    return () => clearTimeout(timer)
  }, [ticker])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const doSearch = useCallback(async (sym: string) => {
    const t = sym.trim().toUpperCase()
    if (!t) return
    setShowSuggestions(false)
    setLoading(true)
    setError(null)
    setResult(null)
    setScoreHistory([])
    setAiNarrative(null)
    try {
      const res = await analyzeTicker(t)
      setResult(res.data as Record<string, unknown>)
      fetchScoreHistory(t).then(r => setScoreHistory(r.data.history)).catch(() => {})
      analyzeTickerAI(t).then(r => setAiNarrative(r.data.narrative)).catch(() => {})
    } catch (e) {
      setError((e as Error).message || 'Error de conexion')
    } finally {
      setLoading(false)
    }
  }, [])

  const onSearch = () => doSearch(ticker)

  const selectSuggestion = (s: SearchResult) => {
    setTicker(s.ticker)
    setSuggestions([])
    setShowSuggestions(false)
    doSearch(s.ticker)
  }

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') { setShowSuggestions(false); return }
    if (e.key === 'Enter') {
      if (showSuggestions && activeIdx >= 0 && suggestions[activeIdx]) {
        selectSuggestion(suggestions[activeIdx])
      } else {
        onSearch()
      }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx(i => Math.min(i + 1, suggestions.length - 1))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, -1))
    }
  }

  const r = result
  const sf = (key: string) => {
    const v = r?.[key]
    if (v == null) return null
    return Number(v)
  }
  const ss = (key: string) => r?.[key] != null ? String(r[key]) : null

  const Row = ({ label, value, cls }: { label: string; value: string | null; cls?: string }) => (
    <div className="flex items-center justify-between py-1.5 border-b border-border/20 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn('text-xs font-medium tabular-nums', cls)}>{value ?? '—'}</span>
    </div>
  )

  const fmtPct    = (v: number | null, suffix = '%') => v != null ? `${v.toFixed(1)}${suffix}` : null
  const fmtDollar = (v: number | null) => v != null ? `$${v.toFixed(2)}` : null
  const colorPct  = (v: number | null) => v == null ? '' : v >= 0 ? 'text-emerald-400' : 'text-red-400'

  const notFound = r != null && !r.current_price && r.source === 'live_yfinance'

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Buscar Ticker</h2>
        <p className="text-sm text-muted-foreground">Analisis completo de cualquier ticker — datos del pipeline o yfinance live</p>
      </div>

      {/* Search box with autocomplete */}
      <div className="relative mb-6" ref={wrapRef}>
        <div className="flex gap-2">
          <Input
            className="flex-1 font-mono uppercase"
            placeholder="Ticker o empresa (ej: Apple, MSFT, SAP.DE)"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={onKey}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            autoFocus
          />
          <Button onClick={onSearch} disabled={loading || !ticker.trim()}>
            {loading ? 'Analizando...' : <><Search size={14} className="mr-1.5" />Analizar</>}
          </Button>
        </div>

        {showSuggestions && suggestions.length > 0 && (
          <ul className="absolute top-full left-0 right-0 mt-1 z-50 bg-card border border-border rounded-lg shadow-xl overflow-hidden">
            {suggestions.map((s, i) => (
              <li
                key={s.ticker}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors',
                  i === activeIdx ? 'bg-primary/10' : 'hover:bg-muted/50'
                )}
                onMouseDown={() => selectSuggestion(s)}
                onMouseEnter={() => setActiveIdx(i)}
              >
                <span className="font-mono font-bold text-primary text-sm w-20 shrink-0">{s.ticker}</span>
                <span className="text-sm text-muted-foreground truncate flex-1">{s.company_name}</span>
                {s.sector && <Badge variant="blue" className="text-[0.6rem] shrink-0">{s.sector}</Badge>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {!r && !loading && !error && (
        <div className="text-center mt-10">
          <div className="text-5xl mb-4 opacity-20">🔍</div>
          <p className="font-medium text-muted-foreground mb-1">Escribe un ticker o el nombre de la empresa</p>
          <span className="text-xs text-muted-foreground/60">Soporta US (AAPL), EU (SAP.DE, BBVA.MC) y UK (.L)</span>
        </div>
      )}

      {loading && <Loading />}
      {error && <ErrorState message={error} />}

      {notFound && (
        <Card className="glass mt-6">
          <CardContent className="py-10 text-center">
            <AlertCircle size={36} strokeWidth={1.5} className="text-muted-foreground mx-auto mb-3" />
            <h4 className="font-semibold mb-1">Ticker no encontrado</h4>
            <p className="text-sm text-muted-foreground mb-4">
              <span className="font-mono font-bold text-primary">"{ss('ticker')}"</span> no tiene datos de mercado disponibles.
            </p>
            <div className="flex gap-2 flex-wrap justify-center">
              {['AAPL', 'MSFT', 'SAP.DE', 'BBVA.MC', 'BP.L'].map(ex => (
                <Button key={ex} variant="outline" size="sm" onClick={() => { setTicker(ex); doSearch(ex) }}>
                  {ex}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {r && !notFound && (
        <Card className="glass animate-fade-in-up">
          <CardContent className="p-6">
            {/* Header */}
            <div className="flex items-start justify-between mb-6 gap-4">
              <div>
                <h3 className="text-xl font-extrabold tracking-tight flex items-baseline gap-2 flex-wrap">
                  <span className="font-mono text-primary text-2xl">{ss('ticker')}</span>
                  <span className="text-muted-foreground font-normal text-base">{ss('company_name')}</span>
                </h3>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {ss('source') && <Badge variant="gray">{ss('source')}</Badge>}
                  {ss('sector_name') && <Badge variant="blue">{ss('sector_name')}</Badge>}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-3xl font-extrabold tracking-tight tabular-nums">{fmtDollar(sf('current_price')) ?? '—'}</div>
                {ss('tier_emoji') && (
                  <Badge variant="blue" className="mt-1 text-xs">
                    {ss('tier_emoji')} {ss('tier_label')}
                  </Badge>
                )}
              </div>
            </div>

            {/* Price chart */}
            {ss('ticker') && (
              <div className="mb-6 rounded-xl overflow-hidden border border-border/20 bg-muted/5">
                <PriceChart ticker={ss('ticker')!} height={180} />
              </div>
            )}

            {/* Score mini-grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              {[
                { label: 'Final Score', key: 'final_score' },
                { label: 'VCP', key: 'vcp_score' },
                { label: 'ML', key: 'ml_score' },
                { label: 'Fundamental', key: 'fund_score' },
              ].map(({ label, key }) => (
                <div key={key} className="glass rounded-lg p-3">
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
                  <div>{sf(key) != null ? <ScoreBar score={sf(key)!} /> : <span className="text-muted-foreground text-xs">—</span>}</div>
                </div>
              ))}
            </div>

            {/* Analysis sections */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-5">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Entry / Exit</h4>
                <Row label="Entry"     value={fmtDollar(sf('entry_price'))} />
                <Row label="Stop Loss" value={fmtDollar(sf('stop_loss'))} cls="text-red-400" />
                <Row label="Target"    value={fmtDollar(sf('target_price'))} cls="text-emerald-400" />
                <Row label="R:R"       value={sf('risk_reward')?.toFixed(1) ?? null} cls={sf('risk_reward') != null && sf('risk_reward')! >= 2 ? 'text-emerald-400' : sf('risk_reward') != null && sf('risk_reward')! < 1 ? 'text-red-400' : ''} />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Analistas</h4>
                <Row label="Target"        value={fmtDollar(sf('target_price_analyst'))} />
                <Row label="Upside"        value={fmtPct(sf('analyst_upside_pct'))} cls={colorPct(sf('analyst_upside_pct'))} />
                <Row label="Recomendacion" value={ss('analyst_recommendation')} />
                <Row label="Analistas"     value={sf('analyst_count')?.toFixed(0) ?? null} />
                <Row label="DCF Target"    value={fmtDollar(sf('target_price_dcf'))} />
                <Row label="DCF Upside"    value={fmtPct(sf('target_price_dcf_upside_pct'))} cls={colorPct(sf('target_price_dcf_upside_pct'))} />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Fundamentales</h4>
                <Row label="ROE"         value={sf('roe') != null ? `${(sf('roe')! * 100).toFixed(1)}%` : null} cls={sf('roe') != null ? (sf('roe')! > 0 ? 'text-emerald-400' : 'text-red-400') : ''} />
                <Row label="ROIC"        value={sf('roic_greenblatt') != null ? `${sf('roic_greenblatt')!.toFixed(1)}%` : null} cls={sf('roic_greenblatt') != null && sf('roic_greenblatt')! >= 20 ? 'text-emerald-400' : sf('roic_greenblatt') != null && sf('roic_greenblatt')! >= 10 ? 'text-amber-400' : ''} />
                <Row label="EBIT/EV"     value={sf('ebit_ev_yield') != null ? `${sf('ebit_ev_yield')!.toFixed(1)}%` : null} cls={sf('ebit_ev_yield') != null && sf('ebit_ev_yield')! >= 8 ? 'text-emerald-400' : ''} />
                <Row label="FCF Yield"   value={fmtPct(sf('fcf_yield'))} cls={sf('fcf_yield') != null && sf('fcf_yield')! >= 5 ? 'text-emerald-400' : ''} />
                <Row label="Forward P/E" value={sf('forward_pe')?.toFixed(1) ?? null} />
                <Row label="PEG"         value={sf('peg_ratio')?.toFixed(2) ?? null} cls={sf('peg_ratio') != null && sf('peg_ratio')! <= 1 ? 'text-emerald-400' : ''} />
                <Row label="Rev Growth"  value={sf('revenue_growth') != null ? `${(sf('revenue_growth')! * 100).toFixed(1)}%` : null} cls={colorPct(sf('revenue_growth'))} />
                <Row label="Dividend"    value={sf('dividend_yield') != null ? `${sf('dividend_yield')!.toFixed(2)}%` : null} cls={sf('dividend_yield') != null && sf('dividend_yield')! > 0 ? 'text-emerald-400' : ''} />
                <Row label="Buyback"     value={r?.buyback_active != null ? (r.buyback_active ? 'Si' : 'No') : null} cls={r?.buyback_active ? 'text-emerald-400' : ''} />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Tecnicos</h4>
                <Row label="MA Filter"     value={r?.ma_passes != null ? (r.ma_passes ? 'PASS' : 'FAIL') : null} cls={r?.ma_passes ? 'text-emerald-400' : 'text-red-400'} />
                <Row label="A/D Signal"    value={ss('ad_signal')} cls={ss('ad_signal')?.includes('ACCUM') ? 'text-emerald-400' : ss('ad_signal')?.includes('DIST') ? 'text-red-400' : ''} />
                <Row label="RS Line"       value={sf('rs_line_score')?.toFixed(1) ?? null} />
                <Row label="Trend"         value={sf('trend_template_score') != null ? `${sf('trend_template_score')}/8` : null} cls={sf('trend_template_score') != null && sf('trend_template_score')! >= 7 ? 'text-emerald-400' : ''} />
                <Row label="52w Proximity" value={fmtPct(sf('proximity_to_52w_high'))} cls={sf('proximity_to_52w_high') != null && sf('proximity_to_52w_high')! > -10 ? 'text-emerald-400' : ''} />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Earnings</h4>
                <Row label="EPS Growth YoY"   value={fmtPct(sf('eps_growth_yoy'))} cls={colorPct(sf('eps_growth_yoy'))} />
                <Row label="EPS Accelerating" value={r?.eps_accelerating != null ? (r.eps_accelerating ? 'Si' : 'No') : null} cls={r?.eps_accelerating ? 'text-emerald-400' : ''} />
                <Row label="Rev Growth YoY"   value={fmtPct(sf('rev_growth_yoy'))} cls={colorPct(sf('rev_growth_yoy'))} />
                <Row label="Profit Margin"    value={fmtPct(sf('profit_margin_pct'))} cls={sf('profit_margin_pct') != null && sf('profit_margin_pct')! >= 15 ? 'text-emerald-400' : ''} />
                <Row label="Next Earnings"    value={ss('next_earnings')} />
                <Row label="Days to Earnings" value={sf('days_to_earnings')?.toFixed(0) ?? null} cls={sf('days_to_earnings') != null && sf('days_to_earnings')! <= 7 ? 'text-red-400' : sf('days_to_earnings') != null && sf('days_to_earnings')! <= 21 ? 'text-amber-400' : ''} />
                {r?.earnings_warning != null && (
                  <Row label="Earnings Warning" value={r.earnings_warning ? '⚠ Risky entry' : 'OK'} cls={r.earnings_warning ? 'text-amber-400' : 'text-emerald-400'} />
                )}
                {r?.earnings_catalyst != null && (
                  <Row label="Earnings Catalyst" value={r.earnings_catalyst ? '🚀 Upcoming catalyst' : '—'} cls={r.earnings_catalyst ? 'text-emerald-400' : ''} />
                )}
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Salud Financiera</h4>
                {/* Piotroski F-Score — proven +13.4% annual alpha */}
                {sf('piotroski_score') != null && (
                  <div className="flex items-center justify-between py-1.5 border-b border-border/20">
                    <span className="text-xs text-muted-foreground">Piotroski F-Score</span>
                    <span className={`text-xs font-bold tabular-nums ${sf('piotroski_score')! >= 8 ? 'text-emerald-400' : sf('piotroski_score')! <= 2 ? 'text-red-400' : 'text-amber-400'}`}>
                      {sf('piotroski_score')}/9 — {ss('piotroski_label')}
                    </span>
                  </div>
                )}
                <Row label="Current Ratio"     value={sf('current_ratio')?.toFixed(2) ?? null} cls={sf('current_ratio') != null && sf('current_ratio')! >= 1.5 ? 'text-emerald-400' : sf('current_ratio') != null && sf('current_ratio')! < 1 ? 'text-red-400' : ''} />
                <Row label="Debt/Equity"       value={sf('debt_to_equity_fund')?.toFixed(2) ?? sf('debt_to_equity')?.toFixed(2) ?? null} cls={sf('debt_to_equity_fund') != null && sf('debt_to_equity_fund')! > 2 ? 'text-red-400' : ''} />
                <Row label="Operating Margin"  value={fmtPct(sf('operating_margin_pct'))} cls={sf('operating_margin_pct') != null && sf('operating_margin_pct')! >= 20 ? 'text-emerald-400' : ''} />
                <Row label="Interest Coverage" value={sf('interest_coverage')?.toFixed(1) ?? null} cls={sf('interest_coverage') != null && sf('interest_coverage')! >= 5 ? 'text-emerald-400' : sf('interest_coverage') != null && sf('interest_coverage')! < 2 ? 'text-red-400' : ''} />
                <Row label="FCF per Share"     value={sf('fcf_per_share') != null ? `$${sf('fcf_per_share')!.toFixed(2)}` : null} cls={sf('fcf_per_share') != null && sf('fcf_per_share')! > 0 ? 'text-emerald-400' : sf('fcf_per_share') != null && sf('fcf_per_share')! < 0 ? 'text-red-400' : ''} />
                <Row label="Payout Ratio"      value={fmtPct(sf('payout_ratio'))} />
                <Row label="Analyst Revision"  value={sf('analyst_revision') != null ? (sf('analyst_revision')! > 0 ? `+${sf('analyst_revision')!.toFixed(1)}` : sf('analyst_revision')!.toFixed(1)) : null} cls={sf('analyst_revision') != null && sf('analyst_revision')! > 0 ? 'text-emerald-400' : sf('analyst_revision') != null && sf('analyst_revision')! < 0 ? 'text-red-400' : ''} />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Señales</h4>
                <Row label="Insiders Score" value={sf('insiders_score')?.toFixed(0) ?? null} />
                {(r?.insider_recurring as Record<string, unknown>) && (
                  <>
                    <Row label="Insider Compras"   value={String((r.insider_recurring as Record<string, unknown>).purchase_count ?? '—')} />
                    <Row label="Insider Confianza" value={String((r.insider_recurring as Record<string, unknown>).confidence_score ?? '—')} />
                  </>
                )}
                {(r?.options_flow as Record<string, unknown>) && (
                  <>
                    <Row label="Options Sentiment" value={String((r.options_flow as Record<string, unknown>).sentiment ?? '—')} />
                    <Row label="Options Score"     value={String((r.options_flow as Record<string, unknown>).flow_score ?? '—')} />
                  </>
                )}
                {(r?.mean_reversion as Record<string, unknown>) && (
                  <>
                    <Row label="MR Strategy" value={String((r.mean_reversion as Record<string, unknown>).strategy ?? '—')} />
                    <Row label="MR Score"    value={String((r.mean_reversion as Record<string, unknown>).reversion_score ?? '—')} />
                  </>
                )}
              </div>
            </div>

            {aiNarrative && (
              <div className="mt-6">
                <AiNarrativeCard narrative={aiNarrative} label="Evaluación de Convicción IA" />
              </div>
            )}

            {ss('thesis') && (
              <div className="mt-6 pt-5 border-t border-border/50">
                <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-3">Tesis de Inversion</h4>
                <p className="text-sm text-muted-foreground leading-relaxed">{ss('thesis')}</p>
              </div>
            )}

            {scoreHistory.length >= 2 && (() => {
              const W = 300, H = 48
              const scores = scoreHistory.map(p => p.score)
              const min = Math.min(...scores), max = Math.max(...scores)
              const range = max - min || 10
              const xs = scoreHistory.map((_, i) => (i / (scoreHistory.length - 1)) * W)
              const ys = scoreHistory.map(p => H - ((p.score - min) / range) * (H - 10) - 5)
              const path = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ')
              const area = path + ` L${W},${H} L0,${H} Z`
              const last = scoreHistory[scoreHistory.length - 1]
              const trend = last.score - scoreHistory[0].score
              const color = trend >= 0 ? '#10b981' : '#ef4444'
              return (
                <div className="mt-6 pt-5 border-t border-border/50">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Historial VALUE Score</h4>
                    <span className={`text-xs font-semibold tabular-nums ${trend >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {trend >= 0 ? '+' : ''}{trend.toFixed(1)} pts · {scoreHistory.length} sesiones
                    </span>
                  </div>
                  <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-12" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity="0.25" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <path d={area} fill="url(#sparkGrad)" />
                    <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
                    <circle cx={xs.at(-1)!.toFixed(1)} cy={ys.at(-1)!.toFixed(1)} r="3" fill={color} />
                  </svg>
                  <div className="flex justify-between text-[0.6rem] text-muted-foreground/50 mt-1 tabular-nums">
                    <span>{scoreHistory[0].date.slice(5)} · {scoreHistory[0].score.toFixed(0)}</span>
                    <span>{last.date.slice(5)} · {last.score.toFixed(0)}</span>
                  </div>
                </div>
              )
            })()}
          </CardContent>
        </Card>
      )}
    </>
  )
}
