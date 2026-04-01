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

// ── Recent searches hook (inline) ────────────────────────────────────────────
const RECENT_KEY = 'sa-recent-searches'
const RECENT_MAX = 8

function useRecentSearches() {
  const [recents, setRecents] = useState<string[]>(() => {
    try { return JSON.parse(sessionStorage.getItem(RECENT_KEY) ?? '[]') } catch { return [] }
  })

  const add = (ticker: string) => {
    setRecents(prev => {
      const next = [ticker, ...prev.filter(t => t !== ticker)].slice(0, RECENT_MAX)
      sessionStorage.setItem(RECENT_KEY, JSON.stringify(next))
      return next
    })
  }

  const remove = (ticker: string) => {
    setRecents(prev => {
      const next = prev.filter(t => t !== ticker)
      sessionStorage.setItem(RECENT_KEY, JSON.stringify(next))
      return next
    })
  }

  return { recents, add, remove }
}

type Quality = 'good' | 'warn' | 'bad' | 'neutral'
const qualBg = (q: Quality) =>
  q === 'good' ? 'bg-emerald-500/8 border-emerald-500/20' :
  q === 'bad'  ? 'bg-red-500/8 border-red-500/15' :
  q === 'warn' ? 'bg-amber-500/8 border-amber-500/15' :
                 'bg-muted/12 border-border/20'
const qualText = (q: Quality) =>
  q === 'good' ? 'text-emerald-400' :
  q === 'bad'  ? 'text-red-400' :
  q === 'warn' ? 'text-amber-400' :
                 'text-foreground/70'

function Metric({ label, value, quality = 'neutral' }: { label: string; value: string | null; quality?: Quality }) {
  if (value == null) return null
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${qualBg(quality)}`}>
      <div className={`text-[0.82rem] font-bold tabular-nums leading-tight ${qualText(quality)}`}>{value}</div>
      <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/45 mt-0.5 leading-tight">{label}</div>
    </div>
  )
}

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
  const { recents, add: addRecent, remove: removeRecent } = useRecentSearches()

  // Auto-search if ?q= param on mount
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) doSearch(q)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced autocomplete
  useEffect(() => {
    const t = ticker.trim()
    if (!t) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    const delay = t.length <= 2 ? 500 : 280  // longer delay for short queries (yfinance fallback)
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
    }, delay)
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
      addRecent(t)
      fetchScoreHistory(t).then(r => setScoreHistory(r.data.history)).catch(() => {})
      analyzeTickerAI(t).then(r => setAiNarrative(r.data.narrative)).catch(() => {})
    } catch (e) {
      setError((e as Error).message || 'Error de conexion')
    } finally {
      setLoading(false)
    }
  }, [addRecent])

  const onSearch = () => {
    // If input looks like a company name (has spaces or >6 chars with lowercase),
    // and we have suggestions, auto-select the first one
    const t = ticker.trim()
    if (suggestions.length > 0 && (t.includes(' ') || (t.length > 6 && t !== t.toUpperCase()))) {
      selectSuggestion(suggestions[0])
    } else {
      doSearch(t)
    }
  }

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

  const fmtPct    = (v: number | null, suffix = '%') => v != null ? `${v.toFixed(1)}${suffix}` : null
  const fmtDollar = (v: number | null) => v != null ? `$${v.toFixed(2)}` : null

  const notFound = r != null && !r.current_price && r.source === 'live_yfinance'

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h1 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Buscar Ticker</h1>
        <p className="text-sm text-muted-foreground">Analisis completo de cualquier ticker — datos del pipeline o yfinance live</p>
      </div>

      {/* Search box with autocomplete */}
      <div className="relative mb-6 animate-fade-in-up" style={{ animationDelay: '60ms' }} ref={wrapRef}>
        <div className="flex flex-col sm:flex-row gap-2">
          <Input
            className="flex-1"
            placeholder="Ticker o empresa (ej: Apple, MSFT, SAP.DE)"
            value={ticker}
            onChange={e => setTicker(e.target.value)}
            onKeyDown={onKey}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            autoFocus
          />
          <Button onClick={onSearch} disabled={loading || !ticker.trim()} className="active:scale-[0.98] transition-transform sm:w-auto w-full">
            {loading ? 'Analizando...' : <><Search size={14} className="mr-1.5" />Analizar</>}
          </Button>
        </div>

        {showSuggestions && suggestions.length > 0 && (() => {
          // Deduplicate by company_name — keeps first hit (US ticker, no dot) and drops foreign dupes
          const seen = new Set<string>()
          const deduped = suggestions.filter(s => {
            const key = s.company_name.toLowerCase().trim()
            if (seen.has(key)) return false
            seen.add(key)
            return true
          }).slice(0, 6)
          const KNOWN_SECTORS = new Set(['Technology','Financial Services','Healthcare','Energy','Consumer Cyclical','Consumer Defensive','Industrials','Real Estate','Basic Materials','Communication Services','Utilities'])
          return (
            <ul className="absolute top-full left-0 right-0 mt-1 z-50 bg-background border border-border rounded-lg shadow-xl" style={{ overflow: 'clip' }}>
              {deduped.map((s, i) => (
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
                  {s.sector && KNOWN_SECTORS.has(s.sector) && <Badge variant="blue" className="text-[0.6rem] shrink-0">{s.sector}</Badge>}
                </li>
              ))}
            </ul>
          )
        })()}
      </div>

      {!r && !loading && !error && (
        <div className="mt-6">
          {recents.length > 0 && !ticker.trim() && (
            <div className="mb-6 animate-fade-in-up" style={{ animationDelay: '120ms' }}>
              <p className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold mb-2">Búsquedas recientes</p>
              <div className="flex flex-wrap gap-2">
                {recents.map((t, idx) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1 pl-3 pr-1 py-1 rounded-full border border-border/40 bg-muted/20 text-sm font-mono font-semibold text-primary hover:bg-muted/40 hover:border-border/60 transition-colors animate-fade-in-up active:scale-[0.98]"
                    style={{ animationDelay: `${(idx + 2) * 40}ms` }}
                  >
                    <button
                      type="button"
                      className="hover:text-foreground transition-colors"
                      onClick={() => { setTicker(t); doSearch(t) }}
                    >
                      {t}
                    </button>
                    <button
                      type="button"
                      className="ml-0.5 w-4 h-4 flex items-center justify-center rounded-full text-muted-foreground/50 hover:bg-red-500/20 hover:text-red-400 transition-colors text-[0.6rem] leading-none"
                      title="Eliminar de recientes"
                      onClick={() => removeRecent(t)}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="text-center mt-4">
            <div className="text-5xl mb-4 opacity-20">🔍</div>
            <p className="font-medium text-muted-foreground mb-1">Escribe un ticker o el nombre de la empresa</p>
            <span className="text-xs text-muted-foreground/60">Soporta US (AAPL), EU (SAP.DE, BBVA.MC) y UK (.L)</span>
          </div>
        </div>
      )}

      {loading && <Loading />}
      {error && <ErrorState message={error} />}

      {notFound && (
        <Card className="glass mt-6 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip' }}>
          <CardContent className="py-10 text-center">
            <AlertCircle size={36} strokeWidth={1.5} className="text-muted-foreground mx-auto mb-3" />
            <h4 className="font-semibold mb-1">Ticker no encontrado</h4>
            <p className="text-sm text-muted-foreground mb-4">
              <span className="font-mono font-bold text-primary">"{ss('ticker')}"</span> no tiene datos de mercado disponibles.
            </p>
            <div className="flex gap-2 flex-wrap justify-center">
              {['AAPL', 'MSFT', 'SAP.DE', 'BBVA.MC', 'BP.L'].map(ex => (
                <Button key={ex} variant="outline" size="sm" className="active:scale-[0.98] transition-transform" onClick={() => { setTicker(ex); doSearch(ex) }}>
                  {ex}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {r && !notFound && (
        <Card className="glass animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip' }}>
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
              <div className="mb-6 rounded-xl border border-border/20 bg-muted/5" style={{ overflow: 'clip' }}>
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
              ].map(({ label, key }, index) => (
                <div
                  key={key}
                  className="glass rounded-lg p-3 animate-fade-in-up hover:border-border/60 transition-colors active:scale-[0.98]"
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
                  <div>{sf(key) != null ? <ScoreBar score={sf(key)!} /> : <span className="text-muted-foreground text-xs">—</span>}</div>
                </div>
              ))}
            </div>

            {/* ── Analysis sections — visual metric cards ── */}
            <div className="space-y-5">

              {/* Entry / Exit + Analistas — side by side */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Entry / Exit — price ladder */}
                {(sf('entry_price') != null || sf('stop_loss') != null || sf('target_price') != null) && (
                  <div className="rounded-xl border border-border/30 border-l-2 border-l-primary/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '0ms' }}>
                    <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                      <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Entry / Exit</span>
                    </div>
                    <div className="grid grid-cols-4 gap-1.5 p-3">
                      <Metric label="Entrada" value={fmtDollar(sf('entry_price'))} quality="neutral" />
                      <Metric label="Stop Loss" value={fmtDollar(sf('stop_loss'))} quality="bad" />
                      <Metric label="Target" value={fmtDollar(sf('target_price'))} quality="good" />
                      <Metric label="R:R" value={sf('risk_reward')?.toFixed(1) ?? null}
                        quality={sf('risk_reward') != null ? (sf('risk_reward')! >= 2 ? 'good' : sf('risk_reward')! < 1 ? 'bad' : 'warn') : 'neutral'} />
                    </div>
                  </div>
                )}

                {/* Analistas — consensus card */}
                {(sf('target_price_analyst') != null || sf('analyst_upside_pct') != null) && (
                  <div className="rounded-xl border border-border/30 border-l-2 border-l-emerald-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '60ms' }}>
                    <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                      <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Analistas</span>
                    </div>
                    <div className="p-3 space-y-2">
                      {/* Main consensus */}
                      {sf('target_price_analyst') != null && (
                        <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${sf('analyst_upside_pct') != null && sf('analyst_upside_pct')! >= 0 ? 'bg-emerald-500/8 border-emerald-500/15' : 'bg-red-500/8 border-red-500/15'}`}>
                          <div className="flex-1">
                            <div className="flex items-baseline gap-2">
                              <span className={`text-sm font-bold tabular-nums ${sf('analyst_upside_pct') != null && sf('analyst_upside_pct')! >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {fmtDollar(sf('target_price_analyst'))}
                              </span>
                              {sf('analyst_upside_pct') != null && (
                                <span className={`text-[0.7rem] font-semibold ${sf('analyst_upside_pct')! >= 0 ? 'text-emerald-400/70' : 'text-red-400/70'}`}>
                                  {sf('analyst_upside_pct')! >= 0 ? '+' : ''}{sf('analyst_upside_pct')!.toFixed(1)}%
                                </span>
                              )}
                              {ss('analyst_recommendation') && (
                                <span className={`px-1.5 py-0.5 rounded text-[0.55rem] font-bold uppercase ${
                                  ss('analyst_recommendation')!.toLowerCase().includes('buy') ? 'bg-emerald-500/15 text-emerald-300' :
                                  ss('analyst_recommendation')!.toLowerCase().includes('sell') ? 'bg-red-500/15 text-red-300' :
                                  'bg-amber-500/15 text-amber-300'
                                }`}>{ss('analyst_recommendation')}</span>
                              )}
                            </div>
                            <div className="text-[0.6rem] text-muted-foreground/50 mt-0.5">
                              Consenso {sf('analyst_count') != null ? `${sf('analyst_count')!.toFixed(0)} analistas` : ''}
                            </div>
                          </div>
                        </div>
                      )}
                      {/* DCF row */}
                      <div className="grid grid-cols-2 gap-1.5">
                        <Metric label="DCF Target" value={fmtDollar(sf('target_price_dcf'))}
                          quality={sf('target_price_dcf_upside_pct') != null ? (sf('target_price_dcf_upside_pct')! >= 0 ? 'good' : 'bad') : 'neutral'} />
                        <Metric label="DCF Upside" value={fmtPct(sf('target_price_dcf_upside_pct'))}
                          quality={sf('target_price_dcf_upside_pct') != null ? (sf('target_price_dcf_upside_pct')! >= 20 ? 'good' : sf('target_price_dcf_upside_pct')! < 0 ? 'bad' : 'warn') : 'neutral'} />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Fundamentales + Tecnicos */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border/30 border-l-2 border-l-blue-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '0ms' }}>
                  <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Fundamentales</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 p-3">
                    <Metric label="ROE" value={sf('roe') != null ? `${(sf('roe')! * 100).toFixed(1)}%` : null}
                      quality={sf('roe') != null ? (sf('roe')! >= 0.15 ? 'good' : sf('roe')! < 0 ? 'bad' : 'neutral') : 'neutral'} />
                    <Metric label="ROIC" value={sf('roic_greenblatt') != null ? `${sf('roic_greenblatt')!.toFixed(1)}%` : null}
                      quality={sf('roic_greenblatt') != null ? (sf('roic_greenblatt')! >= 20 ? 'good' : sf('roic_greenblatt')! >= 10 ? 'warn' : 'neutral') : 'neutral'} />
                    <Metric label="EBIT/EV" value={sf('ebit_ev_yield') != null ? `${sf('ebit_ev_yield')!.toFixed(1)}%` : null}
                      quality={sf('ebit_ev_yield') != null && sf('ebit_ev_yield')! >= 8 ? 'good' : 'neutral'} />
                    <Metric label="FCF Yield" value={fmtPct(sf('fcf_yield'))}
                      quality={sf('fcf_yield') != null ? (sf('fcf_yield')! >= 5 ? 'good' : sf('fcf_yield')! < 0 ? 'bad' : 'neutral') : 'neutral'} />
                    <Metric label="Forward P/E" value={sf('forward_pe')?.toFixed(1) ?? null}
                      quality={sf('forward_pe') != null ? (sf('forward_pe')! <= 15 ? 'good' : sf('forward_pe')! > 30 ? 'bad' : 'neutral') : 'neutral'} />
                    <Metric label="PEG" value={sf('peg_ratio')?.toFixed(2) ?? null}
                      quality={sf('peg_ratio') != null ? (sf('peg_ratio')! <= 1 ? 'good' : sf('peg_ratio')! > 2 ? 'bad' : 'neutral') : 'neutral'} />
                    <Metric label="Rev Growth" value={sf('revenue_growth') != null ? `${(sf('revenue_growth')! * 100).toFixed(1)}%` : null}
                      quality={sf('revenue_growth') != null ? (sf('revenue_growth')! > 0 ? 'good' : 'bad') : 'neutral'} />
                    <Metric label="Dividend" value={sf('dividend_yield') != null ? `${sf('dividend_yield')!.toFixed(2)}%` : null}
                      quality={sf('dividend_yield') != null && sf('dividend_yield')! > 0 ? 'good' : 'neutral'} />
                    <Metric label="Buyback" value={r?.buyback_active === true ? 'Activo' : r?.buyback_active === false ? 'No' : null}
                      quality={r?.buyback_active === true ? 'good' : 'neutral'} />
                  </div>
                </div>

                <div className="rounded-xl border border-border/30 border-l-2 border-l-cyan-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '60ms' }}>
                  <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Técnicos</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 p-3">
                    <Metric label="MA Filter" value={r?.ma_passes === true ? 'PASS' : r?.ma_passes === false ? 'FAIL' : null}
                      quality={r?.ma_passes === true ? 'good' : r?.ma_passes === false ? 'bad' : 'neutral'} />
                    <Metric label="A/D Signal" value={ss('ad_signal')}
                      quality={ss('ad_signal')?.includes('ACCUM') ? 'good' : ss('ad_signal')?.includes('DIST') ? 'bad' : 'neutral'} />
                    <Metric label="RS Line" value={sf('rs_line_score')?.toFixed(1) ?? null} />
                    <Metric label="Trend" value={sf('trend_template_score') != null ? `${sf('trend_template_score')}/8` : null}
                      quality={sf('trend_template_score') != null ? (sf('trend_template_score')! >= 7 ? 'good' : sf('trend_template_score')! <= 3 ? 'bad' : 'neutral') : 'neutral'} />
                    <Metric label="52w Prox." value={fmtPct(sf('proximity_to_52w_high'))}
                      quality={sf('proximity_to_52w_high') != null ? (sf('proximity_to_52w_high')! > -10 ? 'good' : sf('proximity_to_52w_high')! < -25 ? 'bad' : 'warn') : 'neutral'} />
                  </div>
                </div>
              </div>

              {/* Earnings + Salud Financiera */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border/30 border-l-2 border-l-amber-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '0ms' }}>
                  <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Earnings</span>
                  </div>
                  <div className="p-3 space-y-2">
                    <div className="grid grid-cols-3 gap-1.5">
                      <Metric label="EPS Growth" value={fmtPct(sf('eps_growth_yoy'))}
                        quality={sf('eps_growth_yoy') != null ? (sf('eps_growth_yoy')! > 0 ? 'good' : 'bad') : 'neutral'} />
                      <Metric label="EPS Accel." value={r?.eps_accelerating != null ? (r.eps_accelerating ? 'Sí' : 'No') : null}
                        quality={r?.eps_accelerating ? 'good' : 'neutral'} />
                      <Metric label="Rev Growth" value={fmtPct(sf('rev_growth_yoy'))}
                        quality={sf('rev_growth_yoy') != null ? (sf('rev_growth_yoy')! > 0 ? 'good' : 'bad') : 'neutral'} />
                      <Metric label="Profit Margin" value={fmtPct(sf('profit_margin_pct'))}
                        quality={sf('profit_margin_pct') != null ? (sf('profit_margin_pct')! >= 15 ? 'good' : sf('profit_margin_pct')! < 5 ? 'bad' : 'neutral') : 'neutral'} />
                      <Metric label="Next Earnings" value={ss('next_earnings')} />
                      <Metric label="Days" value={sf('days_to_earnings')?.toFixed(0) ?? null}
                        quality={sf('days_to_earnings') != null ? (sf('days_to_earnings')! <= 7 ? 'bad' : sf('days_to_earnings')! <= 21 ? 'warn' : 'good') : 'neutral'} />
                    </div>
                    {/* Warning/Catalyst badges */}
                    {(Boolean(r?.earnings_warning) || Boolean(r?.earnings_catalyst)) && (
                      <div className="flex gap-2 flex-wrap">
                        {Boolean(r?.earnings_warning) && (
                          <span className="text-[0.65rem] px-2 py-0.5 rounded-lg border bg-red-500/8 border-red-500/20 text-red-400">⚠ Risky entry</span>
                        )}
                        {Boolean(r?.earnings_catalyst) && (
                          <span className="text-[0.65rem] px-2 py-0.5 rounded-lg border bg-emerald-500/8 border-emerald-500/20 text-emerald-400">🚀 Catalyst</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border/30 border-l-2 border-l-violet-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip', animationDelay: '60ms' }}>
                  <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Salud Financiera</span>
                  </div>
                  <div className="p-3 space-y-2">
                    {/* Piotroski F-Score — visual bar */}
                    {sf('piotroski_score') != null && (() => {
                      const ps = sf('piotroski_score')!
                      const pq: Quality = ps >= 8 ? 'good' : ps <= 2 ? 'bad' : ps >= 6 ? 'warn' : 'neutral'
                      return (
                        <div className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${qualBg(pq)}`}>
                          <div className="flex-1">
                            <div className="flex items-baseline gap-2">
                              <span className={`text-sm font-bold tabular-nums ${qualText(pq)}`}>{ps}/9</span>
                              <span className="text-[0.65rem] text-muted-foreground/60">{ss('piotroski_label')}</span>
                            </div>
                            <div className="flex gap-0.5 mt-1.5">
                              {Array.from({ length: 9 }).map((_, i) => (
                                <div key={i} className={`h-1.5 flex-1 rounded-full ${i < ps ? (pq === 'good' ? 'bg-emerald-400' : pq === 'bad' ? 'bg-red-400' : 'bg-amber-400') : 'bg-muted/30'}`} />
                              ))}
                            </div>
                          </div>
                          <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/40 shrink-0">F-Score</div>
                        </div>
                      )
                    })()}
                    <div className="grid grid-cols-3 gap-1.5">
                      <Metric label="Current Ratio" value={sf('current_ratio')?.toFixed(2) ?? null}
                        quality={sf('current_ratio') != null ? (sf('current_ratio')! >= 1.5 ? 'good' : sf('current_ratio')! < 1 ? 'bad' : 'warn') : 'neutral'} />
                      <Metric label="Debt/Equity" value={sf('debt_to_equity_fund')?.toFixed(2) ?? sf('debt_to_equity')?.toFixed(2) ?? null}
                        quality={(sf('debt_to_equity_fund') ?? sf('debt_to_equity')) != null ? ((sf('debt_to_equity_fund') ?? sf('debt_to_equity'))! <= 0.5 ? 'good' : (sf('debt_to_equity_fund') ?? sf('debt_to_equity'))! > 2 ? 'bad' : 'warn') : 'neutral'} />
                      <Metric label="Op. Margin" value={fmtPct(sf('operating_margin_pct'))}
                        quality={sf('operating_margin_pct') != null ? (sf('operating_margin_pct')! >= 20 ? 'good' : sf('operating_margin_pct')! < 5 ? 'bad' : 'neutral') : 'neutral'} />
                      <Metric label="Int. Coverage" value={sf('interest_coverage')?.toFixed(1) ?? null}
                        quality={sf('interest_coverage') != null ? (sf('interest_coverage')! >= 5 ? 'good' : sf('interest_coverage')! < 2 ? 'bad' : 'warn') : 'neutral'} />
                      <Metric label="FCF/Share" value={sf('fcf_per_share') != null ? `$${sf('fcf_per_share')!.toFixed(2)}` : null}
                        quality={sf('fcf_per_share') != null ? (sf('fcf_per_share')! > 0 ? 'good' : 'bad') : 'neutral'} />
                      <Metric label="Payout" value={fmtPct(sf('payout_ratio'))}
                        quality={sf('payout_ratio') != null ? (sf('payout_ratio')! <= 60 ? 'good' : sf('payout_ratio')! > 90 ? 'bad' : 'warn') : 'neutral'} />
                    </div>
                    {sf('analyst_revision') != null && (
                      <Metric label="Analyst Revision" value={sf('analyst_revision')! > 0 ? `+${sf('analyst_revision')!.toFixed(1)}` : sf('analyst_revision')!.toFixed(1)}
                        quality={sf('analyst_revision')! > 0 ? 'good' : sf('analyst_revision')! < 0 ? 'bad' : 'neutral'} />
                    )}
                  </div>
                </div>
              </div>

              {/* Señales */}
              {(sf('insiders_score') != null || !!r?.insider_recurring || !!r?.options_flow || !!r?.mean_reversion) && (
                <div className="rounded-xl border border-border/30 border-l-2 border-l-purple-500/50 animate-fade-in-up hover:border-border/60 transition-colors" style={{ overflow: 'clip' }}>
                  <div className="px-3 py-1.5 bg-muted/30 border-b border-border/15">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Señales</span>
                  </div>
                  <div className="grid grid-cols-3 md:grid-cols-6 gap-1.5 p-3">
                    <Metric label="Insiders Score" value={sf('insiders_score')?.toFixed(0) ?? null}
                      quality={sf('insiders_score') != null ? (sf('insiders_score')! >= 70 ? 'good' : sf('insiders_score')! <= 30 ? 'bad' : 'neutral') : 'neutral'} />
                    {(r?.insider_recurring as Record<string, unknown>) && (
                      <>
                        <Metric label="Compras" value={String((r.insider_recurring as Record<string, unknown>).purchase_count ?? '—')} quality="neutral" />
                        <Metric label="Confianza" value={String((r.insider_recurring as Record<string, unknown>).confidence_score ?? '—')}
                          quality={Number((r.insider_recurring as Record<string, unknown>).confidence_score ?? 0) >= 70 ? 'good' : 'neutral'} />
                      </>
                    )}
                    {(r?.options_flow as Record<string, unknown>) && (
                      <>
                        <Metric label="Options" value={String((r.options_flow as Record<string, unknown>).sentiment ?? '—')}
                          quality={String((r.options_flow as Record<string, unknown>).sentiment ?? '').toLowerCase().includes('bull') ? 'good' : String((r.options_flow as Record<string, unknown>).sentiment ?? '').toLowerCase().includes('bear') ? 'bad' : 'neutral'} />
                        <Metric label="Flow Score" value={String((r.options_flow as Record<string, unknown>).flow_score ?? '—')} />
                      </>
                    )}
                    {(r?.mean_reversion as Record<string, unknown>) && (
                      <>
                        <Metric label="MR Strategy" value={String((r.mean_reversion as Record<string, unknown>).strategy ?? '—')} />
                        <Metric label="MR Score" value={String((r.mean_reversion as Record<string, unknown>).reversion_score ?? '—')} />
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {aiNarrative && (
              <div className="mt-6">
                <AiNarrativeCard narrative={aiNarrative} label="Evaluación de Convicción IA" />
              </div>
            )}

            {ss('thesis') && (
              <div className="mt-6 pt-5 border-t border-border/50">
                <h4 className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold mb-3">Tesis de Inversion</h4>
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
                    <h4 className="text-xs uppercase tracking-wider text-muted-foreground/60 font-semibold">Historial VALUE Score</h4>
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
