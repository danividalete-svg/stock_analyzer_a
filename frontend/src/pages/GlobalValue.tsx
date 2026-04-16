import StaleDataBanner from '../components/StaleDataBanner'
import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchGlobalValueOpportunities, fetchThesis, type ValueOpportunity } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useTechnicalSummaryMap } from '../hooks/useTechnicalSummaryMap'
import type { TechnicalSummary } from '../api/client'

function TechBiasCell({ t }: { t?: TechnicalSummary }) {
  if (!t) return <span className="text-muted-foreground/30 text-xs">—</span>
  const cls = t.bias === 'BULLISH'
    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    : t.bias === 'BEARISH'
    ? 'bg-red-500/15 text-red-400 border-red-500/30'
    : 'bg-muted/20 text-muted-foreground border-border/20'
  const icon = t.bias === 'BULLISH' ? '▲' : t.bias === 'BEARISH' ? '▼' : '—'
  return (
    <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full border ${cls}`}
      title={`+${t.bullish_count} alcistas / -${t.bearish_count} bajistas`}>
      {icon}
    </span>
  )
}
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import ScoreRing from '../components/ScoreRing'
import GradeBadge from '../components/GradeBadge'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import ThesisBody from '../components/ThesisBody'
import CsvDownload from '../components/CsvDownload'
import WatchlistButton from '../components/WatchlistButton'
import InfoTooltip from '../components/InfoTooltip'
import OwnedBadge from '../components/OwnedBadge'

// Extend ValueOpportunity with global-specific fields
type GlobalOpportunity = ValueOpportunity & {
  currency?: string
  market_flag?: string
  market_cape?: number
  roe_pct?: number
  pe_forward?: number
  profit_margin_pct?: number
  revenue_growth_pct?: number
  pct_from_52w_high?: number
  risk_flags?: string
  nasdaq_adr?: string
  ai_verdict?: string
  ai_notes?: string
}

const MARKET_META: Record<string, { flag: string; cape: number; label: string; color: string }> = {
  Brazil:   { flag: '🇧🇷', cape: 9.0,  label: 'Brasil',      color: '#22c55e' },
  Korea:    { flag: '🇰🇷', cape: 21.2, label: 'Corea',       color: '#3b82f6' },
  Japan:    { flag: '🇯🇵', cape: 29.4, label: 'Japón',       color: '#f97316' },
  HongKong: { flag: '🇭🇰', cape: 10.7, label: 'Hong Kong',   color: '#a855f7' },
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  BRL: 'R$', KRW: '₩', JPY: '¥', HKD: 'HK$', USD: '$', EUR: '€',
}

type SortKey = keyof GlobalOpportunity
type SortDir = 'asc' | 'desc'

function ConvictionPanel({ row }: { row: GlobalOpportunity }) {
  const reasons = row.conviction_reasons
    ? row.conviction_reasons.split(' | ').filter(Boolean)
    : []
  if (!reasons.length && row.conviction_score == null) return null
  return (
    <div className="border-t border-border/40 pt-4 mt-4">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Conviction Filter</span>
        {row.conviction_grade && row.conviction_score != null && (
          <span className={`text-xs font-bold px-2 py-0.5 rounded ${row.conviction_grade === 'A' ? 'bg-emerald-500/20 text-emerald-400' : row.conviction_grade === 'B' ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400'}`}>
            {row.conviction_grade} — {row.conviction_score.toFixed(0)}pts
          </span>
        )}
      </div>
      {reasons.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {reasons.map((r, i) => (
            <span key={i} className="text-[0.65rem] px-2 py-0.5 rounded-full bg-white/5 border border-border/50 text-muted-foreground">{r}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function isListo(row: GlobalOpportunity): boolean {
  const grade = (row.conviction_grade ?? '').toUpperCase()
  return (
    (row.value_score ?? 0) >= 65 &&
    ['A', 'B', 'EXCELLENT', 'STRONG'].includes(grade) &&
    !row.earnings_warning
  )
}

export default function GlobalValue() {
  const { data, loading, error } = useApi(() => fetchGlobalValueOpportunities(), [])
  const techMap = useTechnicalSummaryMap()
  const [searchParams, setSearchParams] = useSearchParams()

  const [sortKey, setSortKey] = useState<SortKey>('value_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)
  const [expandedRow, setExpandedRow] = useState<GlobalOpportunity | null>(null)
  const [thesisText, setThesisText] = useState<string>('')
  const [filterMarket, setFilterMarket] = useState<string>(searchParams.get('market') ?? 'ALL')
  const [filterGrade, setFilterGrade] = useState<string>(searchParams.get('grade') ?? 'ALL')
  const [minFcf, setMinFcf] = useState<string>('')
  const [minRr, setMinRr] = useState<string>('')
  const [hideRisky, setHideRisky] = useState<boolean>(true)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1280)

  // Sync filterMarket + filterGrade to URL params (functional form preserves region=global)
  useEffect(() => {
    setSearchParams(p => {
      const n = new URLSearchParams(p)
      filterMarket !== 'ALL' ? n.set('market', filterMarket) : n.delete('market')
      filterGrade !== 'ALL' ? n.set('grade', filterGrade) : n.delete('grade')
      return n
    }, { replace: true })
  }, [filterMarket, filterGrade, setSearchParams])

  // pagedRef must be declared before early returns (React Rules of Hooks)
  const pagedRef = useRef<GlobalOpportunity[]>([])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (e.key === 'Escape') { setFocusedIdx(-1); setExpandedTicker(null); setExpandedRow(null); return }
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        setFocusedIdx(i => {
          const next = Math.min(i + 1, pagedRef.current.length - 1)
          setTimeout(() => document.querySelector(`[data-row-idx="${next}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 0)
          return next
        })
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusedIdx(i => {
          const prev = Math.max(i - 1, 0)
          setTimeout(() => document.querySelector(`[data-row-idx="${prev}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 0)
          return prev
        })
      } else if (e.key === 'Enter') {
        setFocusedIdx(i => {
          if (i >= 0 && pagedRef.current[i]) {
            const row = pagedRef.current[i]
            toggleThesis(row.ticker, row)
          }
          return i
        })
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const rows = (data?.data ?? []) as GlobalOpportunity[]
  const source = data?.source ?? ''

  const filtered = rows.filter(r => {
    if (filterMarket !== 'ALL' && r.market !== filterMarket) return false
    if (filterGrade !== 'ALL' && r.conviction_grade !== filterGrade) return false
    if (minFcf !== '' && (r.fcf_yield_pct == null || r.fcf_yield_pct < Number(minFcf))) return false
    if (minRr !== '' && (r.risk_reward_ratio == null || r.risk_reward_ratio < Number(minRr))) return false
    if (hideRisky && r.ai_verdict === 'RISKY') return false
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey] ?? 0; const bv = b[sortKey] ?? 0
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })
  const paged = sorted.slice(0, 50)
  pagedRef.current = paged

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const toggleThesis = async (ticker: string, row: GlobalOpportunity) => {
    if (expandedTicker === ticker) { setExpandedTicker(null); setExpandedRow(null); return }
    setExpandedTicker(ticker)
    setExpandedRow(row)
    setThesisText('Cargando tesis...')
    try {
      const res = await fetchThesis(ticker)
      const t = res.data.thesis
      const text = !t ? 'Sin tesis disponible'
        : typeof t === 'string' ? t
        : (t as Record<string, string>).thesis_narrative || (t as Record<string, string>).overview || JSON.stringify(t)
      setThesisText(text)
    } catch { setThesisText('Error cargando tesis') }
  }

  const Th = ({ k, label, tooltip }: { k: SortKey; label: string; tooltip?: string }) => (
    <TableHead
      className="cursor-pointer select-none whitespace-nowrap text-[0.68rem] font-semibold uppercase tracking-wider"
      onClick={() => onSort(k)}
    >
      <span className="flex items-center gap-1">
        {label}
        {tooltip && <InfoTooltip text={tooltip} />}
        {sortKey === k && <span className="text-primary">{sortDir === 'desc' ? ' ↓' : ' ↑'}</span>}
      </span>
    </TableHead>
  )

  // Market summary cards
  const marketSummary = Object.entries(MARKET_META).map(([key, meta]) => {
    const mRows = rows.filter(r => r.market === key)
    return { key, meta, count: mRows.length, avgScore: mRows.length ? mRows.reduce((s, r) => s + (r.value_score || 0), 0) / mRows.length : 0 }
  })

  const formatPrice = (row: GlobalOpportunity) => {
    const sym = CURRENCY_SYMBOLS[row.currency ?? ''] ?? ''
    return `${sym}${(row.current_price ?? 0).toLocaleString()}`
  }

  return (
    <>
      <StaleDataBanner module="value_global" />
      <div className="mb-6 animate-fade-in-up flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight mb-1 flex items-center gap-2">
            <span className="gradient-title">VALUE Global</span>
            {source && <Badge variant="outline" className="text-[0.6rem]">{source}</Badge>}
          </h2>
          <p className="text-sm text-muted-foreground">
            Acciones VALUE en mercados globales undervalued — Brasil, Corea, Japón, Hong Kong
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CsvDownload dataset="value-global" />
        </div>
      </div>

      {/* Market CAPE context cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {marketSummary.map(({ key, meta, count, avgScore }) => {
          const isActive = filterMarket === key
          return (
            <button
              key={key}
              onClick={() => setFilterMarket(isActive ? 'ALL' : key)}
              className={`glass p-4 rounded-xl text-left transition-all hover:scale-[1.02] ${isActive ? 'ring-2' : ''}`}
              style={{ '--tw-ring-color': meta.color } as React.CSSProperties}
            >
              <div className="text-2xl mb-1">{meta.flag}</div>
              <div className="text-sm font-bold">{meta.label}</div>
              <div className="text-[0.65rem] text-muted-foreground mt-1">
                CAPE <span className="font-mono font-bold" style={{ color: meta.color }}>{meta.cape}</span>
                {count > 0 && <span className="ml-2">{count} picks · avg {avgScore.toFixed(0)}pts</span>}
                {count === 0 && <span className="ml-2 opacity-50">sin datos aún</span>}
              </div>
            </button>
          )
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        {(['ALL', 'A', 'B', 'C'] as string[]).map(g => (
          <button key={g} onClick={() => setFilterGrade(g)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${filterGrade === g ? 'bg-primary text-primary-foreground border-primary' : 'border-border text-muted-foreground hover:border-primary/50'}`}>
            {g === 'ALL' ? 'Todos' : `Grado ${g}`}
          </button>
        ))}
        <span className="text-muted-foreground text-xs mx-1">|</span>
        <input
          type="number" placeholder="FCF% ≥" value={minFcf}
          onChange={e => setMinFcf(e.target.value)}
          className="w-20 text-xs px-2 py-1 rounded-md border border-border bg-background text-foreground"
        />
        <input
          type="number" placeholder="R:R ≥" value={minRr}
          onChange={e => setMinRr(e.target.value)}
          className="w-20 text-xs px-2 py-1 rounded-md border border-border bg-background text-foreground"
        />
        <button
          onClick={() => setHideRisky(h => !h)}
          className={`text-xs px-3 py-1 rounded-full border transition-colors ${hideRisky ? 'bg-red-500/20 text-red-400 border-red-500/40' : 'border-border text-muted-foreground hover:border-red-500/40'}`}
        >
          {hideRisky ? '🚫 Ocultar RISKY' : 'Mostrar todos'}
        </button>
        <button
          onClick={() => setCompact(v => !v)}
          className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ${compact ? 'border-primary/60 bg-primary/15 text-primary' : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'}`}
        >
          {compact ? '⊟ Compacta' : '⊞ Completa'}
        </button>
        <span className="text-xs text-muted-foreground ml-auto">{filtered.length} resultados</span>
      </div>

      {rows.length === 0 ? (
        <Card className="glass">
          <div className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">🌍</div>
            <p className="font-medium text-muted-foreground">
              Sin datos globales aún — el pipeline ejecutará el scanner en la próxima ejecución diaria
            </p>
            <p className="text-xs text-muted-foreground mt-2 opacity-60">
              También puedes ejecutar <code className="font-mono bg-white/5 px-1 rounded">python3 global_market_scanner.py</code> manualmente
            </p>
          </div>
        </Card>
      ) : (
        <>
          {/* Mobile cards */}
          <div className="sm:hidden space-y-2 mb-2">
            {paged.map((row, i) => {
              const meta = MARKET_META[row.market ?? '']
              const listo = isListo(row)
              return (
                <div
                  key={row.ticker}
                  data-row-idx={i}
                  onClick={() => { setFocusedIdx(i); toggleThesis(row.ticker, row) }}
                  className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform ${focusedIdx === i ? 'ring-1 ring-primary/50' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <ScoreRing score={row.value_score ?? 0} size="sm" />
                      <div>
                        <div className="flex items-center gap-1.5">
                          {meta && <span>{meta.flag}</span>}
                          <span className="font-mono font-bold text-sm text-primary">{row.ticker.replace(/\.(SA|KS|T|HK)$/, '')}</span>
                          <OwnedBadge ticker={row.ticker} />
                          {row.ai_verdict === 'RISKY' && <span className="text-red-400 text-xs">🚫</span>}
                          {listo && <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">✦ LISTO</span>}
                        </div>
                        <span className="text-[0.65rem] text-muted-foreground block">{row.company_name}</span>
                      </div>
                    </div>
                    <div className="text-right flex flex-col items-end gap-1">
                      <GradeBadge grade={row.conviction_grade ?? ''} />
                      {row.analyst_upside_pct != null && (
                        <span className={`text-xs font-semibold tabular-nums ${row.analyst_upside_pct >= 20 ? 'text-emerald-400' : row.analyst_upside_pct >= 0 ? 'text-foreground' : 'text-red-400'}`}>
                          {row.analyst_upside_pct >= 0 ? '+' : ''}{row.analyst_upside_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-3 mt-2.5 text-[0.62rem] text-muted-foreground/60">
                    {row.fcf_yield_pct != null && <span>FCF: {row.fcf_yield_pct.toFixed(1)}%</span>}
                    {row.risk_reward_ratio != null && <span>R:R {row.risk_reward_ratio.toFixed(1)}x</span>}
                    {meta && <span>{meta.label} · {row.currency}</span>}
                  </div>
                  {expandedTicker === row.ticker && (
                    <div className="mt-3 pt-3 border-t border-border/30">
                      {thesisText === 'Cargando tesis...' ? (
                        <p className="text-xs text-muted-foreground italic">{thesisText}</p>
                      ) : thesisText && thesisText !== 'Sin tesis disponible' && thesisText !== 'Error cargando tesis' ? (
                        <ThesisBody text={thesisText} />
                      ) : thesisText ? (
                        <p className="text-xs text-muted-foreground italic">{thesisText}</p>
                      ) : null}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block">
            <Card className="glass animate-fade-in-up">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <Th k="ticker" label="Ticker" />
                    <Th k="company_name" label="Empresa" />
                    <Th k="current_price" label="Precio" />
                    <Th k="value_score" label="Score" tooltip="VALUE score (0-100). Incluye bonus por mercado undervalued." />
                    <TableHead className="text-[0.68rem] font-semibold uppercase tracking-wider">Grade</TableHead>
                    <Th k="sector" label="Sector" />
                    <Th k="analyst_upside_pct" label="Potencial" tooltip="Upside implícito según precio objetivo consenso analistas" />
                    <Th k="fcf_yield_pct" label="FCF%" tooltip="Free Cash Flow Yield = FCF / Market Cap" />
                    <Th k="risk_reward_ratio" label="R:R" tooltip="Risk/Reward = upside / 8% stop loss" />
                    {!compact && <Th k="pe_forward" label="P/E fwd" />}
                    {!compact && <Th k="roe_pct" label="ROE%" />}
                    <Th k="pct_from_52w_high" label="vs Max" tooltip="Distancia al máximo de 52 semanas. Negativo = caído del máximo → posible oportunidad de entrada." />
                    <TableHead className="text-[0.68rem] font-semibold uppercase tracking-wider">Téc</TableHead>
                    <TableHead className="w-8" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paged.map((row, idx) => {
                    const isExpanded = expandedTicker === row.ticker
                    const meta = MARKET_META[row.market ?? '']
                    const listo = isListo(row)
                    const colSpan = compact ? 12 : 14
                    return (
                      <React.Fragment key={row.ticker}>
                        <TableRow
                          data-row-idx={idx}
                          className={`border-border/30 cursor-pointer transition-colors hover:bg-white/3 stagger-${Math.min(idx + 1, 10)} ${isExpanded ? 'bg-white/5' : ''} ${focusedIdx === idx ? 'bg-primary/10 ring-1 ring-inset ring-primary/30' : ''}`}
                          onClick={() => { setFocusedIdx(idx); toggleThesis(row.ticker, row) }}
                        >
                          <TableCell>
                            <div className="flex items-center gap-1.5">
                              {meta && <span title={meta.label}>{meta.flag}</span>}
                              <span className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{row.ticker.replace(/\.(SA|KS|T|HK)$/, '')}</span>
                              <OwnedBadge ticker={row.ticker} />
                              {row.ai_verdict === 'RISKY' && <span title={row.ai_notes} className="text-red-400 text-xs">🚫</span>}
                              {listo && <span className="text-[0.6rem] font-bold px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">✦</span>}
                            </div>
                          </TableCell>
                          <TableCell className="max-w-[160px]">
                            <div className="truncate text-sm font-medium">{row.company_name}</div>
                            {row.market && <div className="text-[0.6rem] text-muted-foreground">{meta?.label} · {row.currency}</div>}
                          </TableCell>
                          <TableCell className="font-mono text-sm tabular-nums">
                            {formatPrice(row)}
                          </TableCell>
                          <TableCell>
                            <ScoreBar score={row.value_score} max={100} />
                          </TableCell>
                          <TableCell>
                            <GradeBadge grade={row.conviction_grade ?? ''} />
                          </TableCell>
                          <TableCell className="text-[0.75rem] text-muted-foreground max-w-[110px]">
                            <span className="truncate block">{row.sector ?? '—'}</span>
                          </TableCell>
                          <TableCell>
                            {row.analyst_upside_pct != null ? (
                              <span className={`font-semibold text-sm tabular-nums ${row.analyst_upside_pct >= 20 ? 'text-emerald-400' : row.analyst_upside_pct >= 0 ? 'text-foreground' : 'text-red-400'}`}>
                                {row.analyst_upside_pct >= 0 ? '+' : ''}{row.analyst_upside_pct.toFixed(1)}%
                              </span>
                            ) : '—'}
                          </TableCell>
                          <TableCell>
                            {row.fcf_yield_pct != null ? (
                              <span className={`font-semibold text-sm tabular-nums ${row.fcf_yield_pct >= 5 ? 'text-emerald-400' : row.fcf_yield_pct >= 0 ? 'text-muted-foreground' : 'text-red-400'}`}>
                                {row.fcf_yield_pct.toFixed(1)}%
                              </span>
                            ) : '—'}
                          </TableCell>
                          <TableCell>
                            {row.risk_reward_ratio != null ? (
                              <span className={`font-semibold text-sm tabular-nums ${row.risk_reward_ratio >= 3 ? 'text-emerald-400' : row.risk_reward_ratio >= 2 ? 'text-foreground' : 'text-muted-foreground'}`}>
                                {row.risk_reward_ratio.toFixed(1)}x
                              </span>
                            ) : '—'}
                          </TableCell>
                          {!compact && (
                            <TableCell className="font-mono text-sm tabular-nums text-muted-foreground">
                              {row.pe_forward != null ? `${row.pe_forward}x` : '—'}
                            </TableCell>
                          )}
                          {!compact && (
                            <TableCell className="font-mono text-sm tabular-nums">
                              {row.roe_pct != null ? (
                                <span className={`${(row.roe_pct ?? 0) >= 15 ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                                  {row.roe_pct}%
                                </span>
                              ) : '—'}
                            </TableCell>
                          )}
                          <TableCell className="font-mono text-sm tabular-nums">
                            {row.pct_from_52w_high != null ? (
                              <span className={`${row.pct_from_52w_high <= -30 ? 'text-emerald-400' : row.pct_from_52w_high <= -15 ? 'text-amber-400' : 'text-muted-foreground'}`}>
                                {row.pct_from_52w_high.toFixed(1)}%
                              </span>
                            ) : '—'}
                          </TableCell>
                          <TableCell>
                            <TechBiasCell t={techMap[row.ticker]} />
                          </TableCell>
                          <TableCell onClick={e => e.stopPropagation()}>
                            <WatchlistButton ticker={row.ticker} />
                          </TableCell>
                        </TableRow>
                        {isExpanded && expandedRow && (
                          <TableRow className="border-border/20 hover:bg-transparent">
                            <TableCell colSpan={colSpan} className="bg-white/2 px-6 pb-5">
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 mb-4">
                                {[
                                  { label: 'Margen Neto', val: expandedRow.profit_margin_pct != null ? `${expandedRow.profit_margin_pct}%` : '—', color: (expandedRow.profit_margin_pct ?? 0) >= 10 ? 'text-emerald-400' : '' },
                                  { label: 'Crec. Ingresos', val: expandedRow.revenue_growth_pct != null ? `+${expandedRow.revenue_growth_pct}%` : '—', color: (expandedRow.revenue_growth_pct ?? 0) >= 5 ? 'text-emerald-400' : '' },
                                  { label: 'Dividendo', val: expandedRow.dividend_yield_pct != null ? `${expandedRow.dividend_yield_pct}%` : '—', color: '' },
                                  { label: 'Analistas', val: expandedRow.analyst_count != null ? String(expandedRow.analyst_count) : '—', color: '' },
                                ].map(({ label, val, color }) => (
                                  <div key={label} className="glass rounded-lg p-3">
                                    <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">{label}</div>
                                    <div className={`text-lg font-extrabold tabular-nums ${color}`}>{val}</div>
                                  </div>
                                ))}
                              </div>
                              {/* US ADR alternative */}
                              {expandedRow.nasdaq_adr && (
                                <div className="flex items-center gap-2 mt-3 mb-1">
                                  <span className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">También en US</span>
                                  <span className="font-mono text-xs font-bold text-blue-400 bg-blue-500/10 border border-blue-500/30 px-2 py-0.5 rounded">
                                    {expandedRow.nasdaq_adr}
                                  </span>
                                  <span className="text-[0.65rem] text-muted-foreground">NYSE/NASDAQ/OTC · cotiza en USD · horario europeo</span>
                                </div>
                              )}
                              {/* Risk flags + AI verdict */}
                              {(expandedRow.risk_flags || expandedRow.ai_verdict) && (
                                <div className="border-t border-border/40 pt-4 mt-4">
                                  <div className="flex items-center gap-3 mb-2 flex-wrap">
                                    <span className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Análisis IA</span>
                                    {expandedRow.ai_verdict && (
                                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${expandedRow.ai_verdict === 'CLEAN' ? 'bg-emerald-500/20 text-emerald-400' : expandedRow.ai_verdict === 'SUSPECT' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'}`}>
                                        {expandedRow.ai_verdict === 'CLEAN' ? '✅ CLEAN' : expandedRow.ai_verdict === 'SUSPECT' ? '⚠️ SUSPECT' : '🚫 RISKY'}
                                      </span>
                                    )}
                                    {expandedRow.ai_notes && (
                                      <span className="text-xs text-muted-foreground italic">{expandedRow.ai_notes}</span>
                                    )}
                                  </div>
                                  {expandedRow.risk_flags && (
                                    <div className="flex flex-wrap gap-1.5">
                                      {expandedRow.risk_flags.split(' | ').filter(Boolean).map((f, i) => (
                                        <span key={i} className="text-[0.65rem] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-400">{f}</span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                              <ConvictionPanel row={expandedRow} />
                              {thesisText && thesisText !== 'Sin tesis disponible' && thesisText !== 'Error cargando tesis' && thesisText !== 'Cargando tesis...' ? (
                                <div className="mt-4">
                                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Tesis de Inversión</div>
                                  <ThesisBody text={thesisText} />
                                </div>
                              ) : thesisText ? (
                                <p className="text-xs text-muted-foreground mt-3 italic">{thesisText}</p>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        )}
                      </React.Fragment>
                    )
                  })}
                </TableBody>
              </Table>
              {sorted.length > 0 && (
                <div className="text-[0.6rem] text-muted-foreground/25 text-right px-3 py-1.5 border-t border-border/10">
                  j / k navegar · Enter abrir · Esc cerrar
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}
