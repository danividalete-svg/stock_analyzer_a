import { useState, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchValueOpportunities, fetchMarketRegime, fetchThesis, fetchMacroRadar, type ValueOpportunity } from '../api/client'
import StaleDataBanner from '../components/StaleDataBanner'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import ScoreRing from '../components/ScoreRing'
import GradeBadge from '../components/GradeBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import CsvDownload from '../components/CsvDownload'
import WatchlistButton from '../components/WatchlistButton'
import PaginationBar from '../components/PaginationBar'
import InfoTooltip from '../components/InfoTooltip'
import ThesisModal from '../components/ThesisModal'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'
import { useTechnicalSummaryMap } from '../hooks/useTechnicalSummaryMap'
import { useCerebroSignals } from '../hooks/useCerebroSignals'
import CerebroBadges from '../components/CerebroBadges'
import type { TechnicalSummary } from '../api/client'
import PageHeader from '../components/PageHeader'

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

type SortKey = keyof ValueOpportunity
type SortDir = 'asc' | 'desc'

export default function ValueUS() {
  const { data, loading, error } = useApi(() => fetchValueOpportunities(), [])
  const { data: regime } = useApi(() => fetchMarketRegime(), [])
  const { data: macroRaw } = useApi(() => fetchMacroRadar(), [])
  const techMap = useTechnicalSummaryMap()
  const cerebro = useCerebroSignals()
  const [sortKey, setSortKey] = useState<SortKey>('value_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedRow, setExpandedRow] = useState<ValueOpportunity | null>(null)
  const [thesisText, setThesisText] = useState<string>('')

  // URL-synced filters
  const [searchParams, setSearchParams] = useSearchParams()

  const filterGrade = searchParams.get('grade') ?? 'ALL'
  const filterSector = searchParams.get('sector') ?? 'ALL'
  const minScore = searchParams.get('score') ?? '55'

  function setFilterGrade(v: string) {
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      v === 'ALL' ? next.delete('grade') : next.set('grade', v)
      return next
    }, { replace: true })
  }
  function setFilterSector(v: string) {
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      v === 'ALL' ? next.delete('sector') : next.set('sector', v)
      return next
    }, { replace: true })
  }
  function setMinScore(v: string) {
    setSearchParams(p => {
      const next = new URLSearchParams(p)
      v === '' || v === '55' ? next.delete('score') : next.set('score', v)
      return next
    }, { replace: true })
  }

  // Local-only filters (not URL-synced)
  const [minFcf, setMinFcf] = useState<string>('')
  const [minRr, setMinRr] = useState<string>('')
  const [hideEarnings, setHideEarnings] = useState(false)
  const [hideTraps, setHideTraps] = useState(true)
  const [hideExits, setHideExits] = useState(true)
  const [onlyOwned, setOnlyOwned] = useState(false)
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1280)
  const { isOwned, positions: myPos } = usePersonalPortfolio()
  const [page, setPage] = useState(1)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const PAGE_SIZE = 50

  const currentThesisTicker = useRef<string | null>(null)
  // pagedRef must be declared before early returns (React Rules of Hooks)
  const pagedRef = useRef<ValueOpportunity[]>([])

  useEffect(() => { setPage(1); setFocusedIdx(-1) }, [filterGrade, filterSector, minScore, minFcf, minRr, hideEarnings, hideTraps, hideExits, onlyOwned])

  // Keyboard navigation — j/k/Enter/Escape
  // useRef para evitar stale closures (paged se recalcula cada render)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (e.key === 'Escape') { setFocusedIdx(-1); return }
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
          if (i >= 0 && pagedRef.current[i]) toggleThesis(pagedRef.current[i].ticker, pagedRef.current[i])
          return i
        })
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const rows = data?.data ?? []
  const source = data?.source ?? ''

  // Unique sectors for filter pills
  const sectors = ['ALL', ...Array.from(new Set(rows.map(r => r.sector).filter(Boolean) as string[])).sort()]

  // Apply filters then sort
  const filtered = rows.filter(r => {
    if (filterGrade !== 'ALL' && r.conviction_grade !== filterGrade) return false
    if (filterSector !== 'ALL' && r.sector !== filterSector) return false
    if (minScore !== '' && (r.value_score == null || r.value_score < Number(minScore))) return false
    if (minFcf !== '' && (r.fcf_yield_pct == null || r.fcf_yield_pct < Number(minFcf))) return false
    if (minRr !== '' && (r.risk_reward_ratio == null || r.risk_reward_ratio < Number(minRr))) return false
    if (hideEarnings && r.earnings_warning) return false
    if (hideTraps && cerebro.trapMap[r.ticker]?.severity === 'HIGH') return false
    if (hideExits && (cerebro.exitMap[r.ticker] || r.cerebro_signal === 'EXIT')) return false
    if (onlyOwned && !isOwned(r.ticker)) return false
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE)
  const paged = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  pagedRef.current = paged

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const toggleThesis = async (ticker: string, row: ValueOpportunity) => {
    currentThesisTicker.current = ticker
    setExpandedRow(row)
    setThesisText('Cargando tesis...')
    try {
      const res = await fetchThesis(ticker)
      if (currentThesisTicker.current !== ticker) return // stale response
      const t = res.data.thesis
      const text = !t ? 'Sin tesis disponible'
        : typeof t === 'string' ? t
        : (t as Record<string, string>).thesis_narrative || (t as Record<string, string>).overview || JSON.stringify(t)
      setThesisText(text)
    } catch { if (currentThesisTicker.current === ticker) setThesisText('Error cargando tesis') }
  }

  const thCls = (key: SortKey) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const usRegime = regime?.us as Record<string, string> | undefined
  const regimeLabel = usRegime?.regime || usRegime?.market_regime || ''
  const regimeRec = usRegime?.recommendation || ''

  const avgScore = filtered.length ? filtered.reduce((s, r) => s + (r.value_score || 0), 0) / filtered.length : 0
  const gradeA = filtered.filter(r => r.conviction_grade === 'A').length
  const gradeB = filtered.filter(r => r.conviction_grade === 'B').length
  const bestUpside = Math.max(...filtered.map(r => r.analyst_upside_pct || 0), 0)

  const sectorCounts: Record<string, number> = {}
  sorted.forEach(d => { const s = d.sector || 'Unknown'; sectorCounts[s] = (sectorCounts[s] || 0) + 1 })
  const concentrated = Object.entries(sectorCounts).filter(([, c]) => c >= 3)

  const hiddenByTraps = hideTraps ? Object.values(cerebro.trapMap).filter(t => t.severity === 'HIGH').length : 0
  const hiddenByExits = hideExits ? rows.filter(r => cerebro.exitMap[r.ticker] || r.cerebro_signal === 'EXIT').length : 0
  const hasActiveFilters = filterGrade !== 'ALL' || filterSector !== 'ALL' || minScore !== '55' || minFcf !== '' || minRr !== '' || hideEarnings || hideTraps || hideExits || onlyOwned
  const resetFilters = () => {
    setSearchParams({}, { replace: true })
    setMinFcf(''); setMinRr(''); setHideEarnings(false); setHideTraps(false); setHideExits(false); setOnlyOwned(false)
  }

  const fmtFcf = (v?: number) => {
    if (v == null) return <span className="text-muted-foreground">—</span>
    const cls = v >= 5 ? 'text-emerald-400' : v >= 3 ? 'text-amber-400' : v < 0 ? 'text-red-400' : ''
    return <span className={cls}>{v.toFixed(1)}%</span>
  }
  const fmtRR = (v?: number) => {
    if (v == null) return <span className="text-muted-foreground">—</span>
    const cls = v >= 2 ? 'text-emerald-400' : v >= 1 ? 'text-amber-400' : 'text-red-400'
    return <span className={cls}>{v.toFixed(1)}</span>
  }
  const fmtDivBB = (d: ValueOpportunity) => {
    const parts: string[] = []
    if (d.dividend_yield_pct != null && d.dividend_yield_pct > 0) parts.push(`${d.dividend_yield_pct.toFixed(1)}%`)
    if (d.buyback_active) parts.push('BB')
    return parts.length
      ? <span className="text-emerald-400">{parts.join('+')}</span>
      : <span className="text-muted-foreground">—</span>
  }
  const fmtEarn = (d: ValueOpportunity) => {
    if (d.days_to_earnings == null) return <span className="text-muted-foreground">—</span>
    const cls = d.days_to_earnings <= 7 ? 'text-red-400' : d.days_to_earnings <= 21 ? 'text-amber-400' : 'text-emerald-400'
    return <span className={cls}>{d.days_to_earnings}d</span>
  }

  return (
    <>
      <StaleDataBanner module="value_us" />
      <PageHeader
        title={<>
          VALUE US
          {regimeLabel && (
            <Badge variant={regimeLabel.includes('UP') ? 'green' : regimeLabel.includes('CORR') ? 'red' : 'yellow'} className="ml-2 align-middle text-xs">
              {regimeLabel}
            </Badge>
          )}
          {source && <span className="ml-2 align-middle text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground/50 border border-border/40 rounded px-1.5 py-0.5">{source}</span>}
        </>}
        subtitle={<>
          Oportunidades VALUE — fundamentales, FCF, dividendos, conviction filter
          {regimeRec && <> · <strong className="text-foreground">{regimeRec}</strong></>}
        </>}
      >
        <CsvDownload dataset="value-us" label="CSV" />
        <CsvDownload dataset="value-us-full" label="CSV Full" />
      </PageHeader>

      {/* Macro Risk Overlay */}
      {(() => {
        const macro = macroRaw as { regime?: { name: string; color: string; description: string }; composite_score?: number; max_score?: number } | null
        const rname = macro?.regime?.name
        if (!rname || !['STRESS', 'ALERT', 'CRISIS'].includes(rname)) return null
        const cfg = {
          STRESS: { bg: 'border-yellow-500/30 bg-yellow-500/8', text: 'text-yellow-400', msg: 'Estrés moderado detectado. Reduce tamaño de posición y prioriza picks con mayor margen de seguridad.' },
          ALERT:  { bg: 'border-orange-500/30 bg-orange-500/8', text: 'text-orange-400', msg: 'Alerta macro elevada. Considera posiciones más pequeñas, stop loss más ajustados y diversificación.' },
          CRISIS: { bg: 'border-red-500/40 bg-red-500/10',     text: 'text-red-400',    msg: 'Régimen de crisis potencial. Capital preservation mode — evitar nuevas entradas agresivas.' },
        }[rname]!
        return (
          <div className={`mb-5 flex items-start gap-3 px-4 py-3 rounded-lg border ${cfg.bg}`}>
            <span className={`text-lg shrink-0`}>⚠️</span>
            <div>
              <span className={`text-xs font-bold uppercase tracking-wider ${cfg.text}`}>
                Macro Radar: {rname} ({macro.composite_score?.toFixed(1)}/{macro.max_score})
              </span>
              <p className="text-xs text-muted-foreground mt-0.5">{cfg.msg}</p>
            </div>
            <Link to="/macro-radar" className={`ml-auto shrink-0 text-[0.65rem] font-semibold ${cfg.text} hover:underline`}>
              Ver detalle →
            </Link>
          </div>
        )
      })()}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Oportunidades', value: rows.length, sub: 'tickers analizados', idx: 1 },
          { label: 'Score Medio', value: avgScore.toFixed(1), sub: 'de 100 puntos', color: avgScore >= 50 ? 'text-emerald-400' : 'text-amber-400', idx: 2 },
          { label: 'Grado A+B', value: gradeA + gradeB, sub: `${gradeA} A, ${gradeB} B`, color: 'text-emerald-400', idx: 3 },
          { label: 'Mejor Upside', value: `+${bestUpside.toFixed(0)}%`, sub: 'potencial analistas', color: 'text-emerald-400', idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass glow-border p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {concentrated.length > 0 && (
        <Card className="glass mb-4 px-5 py-3 border-amber-500/30">
          <span className="text-amber-400 text-sm font-medium">
            Concentración sectorial: {concentrated.map(([s, c]) => `${s} (${c})`).join(', ')}
          </span>
        </Card>
      )}

      {/* Filter Bar */}
      <Card className="glass px-4 py-3 mb-3 animate-fade-in-up">
        <div className="flex flex-wrap gap-x-4 gap-y-2 items-center">

          {/* Min Score */}
          <div className="flex items-center gap-1">
            <span className="filter-label mr-0.5">Score≥</span>
            {[['ALL', ''], ['50+', '50'], ['55+', '55'], ['60+', '60'], ['65+', '65']].map(([label, val]) => (
              <button key={val} onClick={() => setMinScore(val)} className={`filter-btn ${minScore === val ? 'active' : ''}`}>{label}</button>
            ))}
          </div>

          <div className="w-px h-4 bg-border/40 self-center" />

          {/* Grade */}
          <div className="flex items-center gap-1">
            <span className="filter-label mr-0.5">Grado</span>
            {['ALL', 'A', 'B', 'C'].map(g => (
              <button key={g} onClick={() => setFilterGrade(g)} className={`filter-btn ${filterGrade === g ? 'active' : ''}`}>{g}</button>
            ))}
          </div>

          {/* Sector */}
          {sectors.length > 2 && (
            <>
              <div className="w-px h-4 bg-border/40 self-center" />
              <div className="flex items-center gap-1 flex-wrap max-w-[400px]">
                <span className="filter-label mr-0.5">Sector</span>
                {sectors.slice(0, 7).map(s => (
                  <button key={s} onClick={() => setFilterSector(s)} className={`filter-btn ${filterSector === s ? 'active' : ''}`}>
                    {s === 'ALL' ? 'Todos' : s}
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="w-px h-4 bg-border/40 self-center" />

          {/* FCF% min */}
          <div className="flex items-center gap-1.5">
            <span className="filter-label">FCF%≥</span>
            <input type="number" value={minFcf} onChange={e => setMinFcf(e.target.value)} placeholder="0" className="filter-input" />
          </div>

          {/* R:R min */}
          <div className="flex items-center gap-1.5">
            <span className="filter-label">R:R≥</span>
            <input type="number" value={minRr} onChange={e => setMinRr(e.target.value)} placeholder="0" className="filter-input" />
          </div>

          <div className="w-px h-4 bg-border/40 self-center" />

          {/* Cerebro IA filters */}
          <button onClick={() => setHideTraps(v => !v)} className={`filter-btn ${hideTraps ? 'active-red' : ''}`}
            title="Ocultar tickers marcados como value trap HIGH por Cerebro IA">
            {hideTraps && hiddenByTraps > 0 ? `⚠ TRAP (${hiddenByTraps})` : '⚠ TRAP'}
          </button>
          <button onClick={() => setHideExits(v => !v)} className={`filter-btn ${hideExits ? 'active-red' : ''}`}
            title="Ocultar tickers con señal de salida HIGH por Cerebro IA">
            {hideExits && hiddenByExits > 0 ? `⬆ EXIT (${hiddenByExits})` : '⬆ EXIT'}
          </button>
          <button onClick={() => setHideEarnings(v => !v)} className={`filter-btn ${hideEarnings ? 'active-amber' : ''}`}>
            Earn &lt;7d
          </button>

          {myPos.length > 0 && (
            <button onClick={() => setOnlyOwned(v => !v)} className={`filter-btn ${onlyOwned ? 'active' : ''}`}>
              En cartera
            </button>
          )}

          {/* Compact toggle */}
          <button onClick={() => setCompact(v => !v)} className={`filter-btn ${compact ? 'active' : ''}`}
            title="Alternar entre vista compacta y completa">
            {compact ? '⊟ Compacta' : '⊞ Completa'}
          </button>

          {/* Reset + count — pushed to the right */}
          <div className="flex items-center gap-3 ml-auto">
            {hasActiveFilters && (
              <button onClick={resetFilters} className="text-xs text-muted-foreground/50 hover:text-foreground underline underline-offset-2 transition-colors">
                Limpiar
              </button>
            )}
            <span className="filter-label !normal-case !tracking-normal">
              {filtered.length !== rows.length ? `${filtered.length} / ${rows.length}` : `${rows.length} picks`}
            </span>
          </div>
        </div>
      </Card>

      {/* Mobile card view */}
      <div className="sm:hidden space-y-2.5 mb-2">
        {paged.map((d, i) => {
          const isReady =
            (d.value_score ?? 0) >= 65 &&
            ['A', 'B', 'EXCELLENT', 'STRONG'].includes((d.conviction_grade ?? '').toUpperCase()) &&
            !d.earnings_warning &&
            (d.days_to_earnings == null || d.days_to_earnings > 7) &&
            d.cerebro_signal !== 'EXIT' &&
            d.cerebro_signal !== 'TRAP'
          const hasTrap   = !!cerebro.trapMap[d.ticker]
          const hasExit   = !!(cerebro.exitMap[d.ticker] || d.cerebro_signal === 'EXIT')
          const hasSM     = !!cerebro.smMap[d.ticker]
          const hasSqueeze = !!cerebro.squeezeMap[d.ticker]
          return (
            <div
              key={d.ticker}
              onClick={() => { setFocusedIdx(i); toggleThesis(d.ticker, d) }}
              className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform border ${hasTrap ? 'border-red-500/30' : hasExit ? 'border-amber-500/30' : 'border-white/5'}`}
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {/* Row 1: logo + ticker + grade + upside */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-3 min-w-0">
                  <ScoreRing score={d.value_score ?? 0} size="sm" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono font-extrabold text-base leading-tight">{d.ticker}</span>
                      {isReady && (
                        <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">✦ LISTO</span>
                      )}
                      <OwnedBadge ticker={d.ticker} />
                    </div>
                    <span className="text-xs text-muted-foreground truncate max-w-[160px] block mt-0.5">{d.company_name}</span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <GradeBadge grade={d.conviction_grade} score={d.conviction_score} />
                  {d.analyst_upside_pct != null && (
                    <div className={`text-sm font-bold mt-1 ${d.analyst_upside_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {d.analyst_upside_pct > 0 ? '+' : ''}{d.analyst_upside_pct.toFixed(0)}%
                    </div>
                  )}
                  <div className="text-[0.65rem] text-muted-foreground/50 mt-0.5">${d.current_price?.toFixed(2)}</div>
                </div>
              </div>

              {/* Row 2: Cerebro signals */}
              {(hasTrap || hasExit || hasSM || hasSqueeze || d.earnings_warning) && (
                <div className="flex flex-wrap gap-1.5 mt-2.5">
                  {hasTrap && (
                    <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/25">
                      ⚠ TRAP
                    </span>
                  )}
                  {hasExit && (
                    <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25">
                      ↑ EXIT
                    </span>
                  )}
                  {hasSM && (
                    <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400 border border-violet-500/25">
                      🐋 SMART $
                    </span>
                  )}
                  {hasSqueeze && (
                    <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/25">
                      💥 SQUEEZE
                    </span>
                  )}
                  {d.earnings_warning && (
                    <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/25">
                      📅 EARNINGS
                    </span>
                  )}
                </div>
              )}

              {/* Row 3: Entry / Stop / Target */}
              {(d.entry_price || d.stop_loss || d.target_price) && (
                <div className="flex gap-3 mt-2.5 text-xs font-mono">
                  {d.entry_price && <span className="text-cyan-400">E ${d.entry_price.toFixed(2)}</span>}
                  {d.stop_loss && <span className="text-red-400/80">SL ${d.stop_loss.toFixed(2)}</span>}
                  {d.target_price && <span className="text-emerald-400/80">TP ${d.target_price.toFixed(2)}</span>}
                </div>
              )}

              {/* Row 4: FCF / R:R / Sector */}
              <div className="flex gap-3 mt-2 text-xs text-muted-foreground/70">
                {d.fcf_yield_pct != null && <span>FCF {d.fcf_yield_pct.toFixed(1)}%</span>}
                {d.risk_reward_ratio != null && <span>R:R {d.risk_reward_ratio.toFixed(1)}x</span>}
                {d.sector && <span className="truncate">{d.sector}</span>}
              </div>
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
              <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
              <TableHead className={compact ? 'hidden' : `hidden sm:table-cell ${thCls('company_name')}`} onClick={() => onSort('company_name')}>Empresa</TableHead>
              <TableHead className={compact ? 'hidden' : `hidden sm:table-cell ${thCls('current_price')}`} onClick={() => onSort('current_price')}>Precio</TableHead>
              <TableHead className={thCls('value_score')} onClick={() => onSort('value_score')}>
                Score
                <InfoTooltip
                  text="Score VALUE propio (0-100): fundamentales 40pts, insiders 15pts, institucionales 15pts, opciones 10pts, ML 5pts, sector/reversion 20pts. Bonificaciones por FCF, dividendo, recompras y R:R."
                  align="left"
                />
              </TableHead>
              <TableHead>
                Grade
                <InfoTooltip
                  text={
                    <span>
                      Grado de convicción del filtro IA:<br />
                      <span className="text-emerald-400">A</span> — alta convicción (pocas alertas, múltiples positivos)<br />
                      <span className="text-blue-400">B</span> — convicción moderada<br />
                      <span className="text-amber-400">C</span> — baja convicción (revisar antes de entrar)
                    </span>
                  }
                />
              </TableHead>
              <TableHead className={compact ? 'hidden' : `hidden md:table-cell ${thCls('sector')}`} onClick={() => onSort('sector')}>Sector</TableHead>
              <TableHead className={thCls('analyst_upside_pct')} onClick={() => onSort('analyst_upside_pct')}>
                Objetivo
                <InfoTooltip text="Upside según precio objetivo de analistas = (precio objetivo − precio actual) / precio actual. Negativo = analistas ven el valor sobrevalorado." />
              </TableHead>
              <TableHead className={`hidden sm:table-cell ${thCls('fcf_yield_pct')}`} onClick={() => onSort('fcf_yield_pct')}>
                FCF%
                <InfoTooltip text="FCF Yield = Free Cash Flow / Market Cap. ≥5% excelente (verde), 3-5% bueno (ámbar), <0% negativo (rojo). Indica cuánto cash genera la empresa respecto a su valor de mercado." />
              </TableHead>
              <TableHead className={compact ? 'hidden' : thCls('risk_reward_ratio')} onClick={() => onSort('risk_reward_ratio')}>
                R:R
                <InfoTooltip text="Risk:Reward = upside analista / 8% stop loss estándar. ≥3 excelente (verde), ≥2 bueno, <1 desfavorable (rojo). Mide si el potencial de ganancia justifica el riesgo." />
              </TableHead>
              <TableHead className={compact ? 'hidden' : 'hidden sm:table-cell'}>
                Div/BB
                <InfoTooltip text="Dividend yield del ticker. 'BB' indica que la empresa está recomprando acciones propias activamente (buyback), lo que también retorna capital al accionista." />
              </TableHead>
              <TableHead className={thCls('days_to_earnings')} onClick={() => onSort('days_to_earnings')}>
                Earn
                <InfoTooltip
                  text="Días hasta próximos resultados trimestrales. Rojo ≤7d — entrada muy arriesgada (gap post-earnings). Ámbar ≤21d — precaución. Verde >21d — zona segura."
                  align="right"
                />
              </TableHead>
              <TableHead className={compact ? 'hidden' : 'hidden sm:table-cell'}>
                Téc
                <InfoTooltip text="Sesgo técnico detectado automáticamente: indicadores de tendencia, RSI, MACD, Bollinger y velas. ▲ Alcista · ▼ Bajista · — Neutro." align="right" />
              </TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paged.map((d, i) => {
            const isReady =
              (d.value_score ?? 0) >= 65 &&
              ['A', 'B', 'EXCELLENT', 'STRONG'].includes((d.conviction_grade ?? '').toUpperCase()) &&
              !d.earnings_warning &&
              (d.days_to_earnings == null || d.days_to_earnings > 7) &&
              d.cerebro_signal !== 'EXIT' &&
              d.cerebro_signal !== 'TRAP'
            return (
              <TableRow
                key={d.ticker}
                data-row-idx={i}
                className={`cursor-pointer transition-colors ${i === focusedIdx ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                onClick={() => { setFocusedIdx(i); toggleThesis(d.ticker, d) }}
              >
                  <TableCell className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">
                    <div className="flex items-center gap-2">
                      <TickerLogo ticker={d.ticker} size="sm" />
                      <div className="flex items-center gap-1.5">
                        {d.ticker}
                        {isReady && (
                          <span
                            title="Todos los filtros pasan — setup listo para operar"
                            className="inline-flex items-center gap-0.5 text-[0.6rem] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 tracking-wide"
                          >
                            ✦ LISTO
                          </span>
                        )}
                        <OwnedBadge ticker={d.ticker} />
                        {d.magic_formula_rank != null && d.magic_formula_rank <= 50 && (
                          <span
                            className="text-[0.55rem] font-bold px-1 py-0.5 rounded bg-violet-500/15 text-violet-400 border border-violet-500/25"
                            title={`Magic Formula (Greenblatt) rank #${d.magic_formula_rank} — EBIT/EV yield ${d.ebit_ev_yield != null ? d.ebit_ev_yield.toFixed(1) + '%' : '—'} · ROIC ${d.roic_greenblatt != null ? d.roic_greenblatt.toFixed(1) + '%' : '—'}`}
                          >
                            MF #{d.magic_formula_rank}
                          </span>
                        )}
                        {d.proximity_to_52w_high != null && d.proximity_to_52w_high > -5 && (
                          <span className="text-[0.55rem] font-bold px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/25" title={`A ${Math.abs(d.proximity_to_52w_high).toFixed(1)}% del máximo 52 semanas — posible entrada en techo`}>
                            TECHO
                          </span>
                        )}
                        {(d.hedge_fund_count ?? 0) >= 1 && (
                          <span
                            className={`text-[0.55rem] font-bold px-1 py-0.5 rounded border ${(d.hedge_fund_count ?? 0) >= 2 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25' : 'bg-muted/20 text-muted-foreground border-border/30'}`}
                            title={d.hedge_fund_names || `${d.hedge_fund_count} hedge fund(s) en posición`}
                          >
                            {d.hedge_fund_count ?? 1} {(d.hedge_fund_count ?? 1) === 1 ? 'FONDO' : 'FONDOS'}
                          </span>
                        )}
                      </div>
                      <CerebroBadges
                        entryInfo={cerebro.entryMap[d.ticker]}
                        trapInfo={cerebro.trapMap[d.ticker]}
                        smInfo={cerebro.smMap[d.ticker]}
                        exitInfo={cerebro.exitMap[d.ticker]}
                        divInfo={cerebro.divMap[d.ticker]}
                        piotrInfo={cerebro.piotrMap[d.ticker]}
                        squeezeInfo={cerebro.squeezeMap[d.ticker]}
                        decayInfo={cerebro.decayMap[d.ticker]}
                        sectorInfo={cerebro.sectorMap[d.ticker]}
                      />
                    </div>
                  </TableCell>
                  <TableCell className={compact ? 'hidden' : 'hidden sm:table-cell max-w-[160px] truncate text-muted-foreground text-[0.76rem]'}>{d.company_name}</TableCell>
                  <TableCell className={compact ? 'hidden' : 'hidden sm:table-cell tabular-nums'}>${d.current_price?.toFixed(2)}</TableCell>
                  <TableCell><ScoreBar score={d.value_score} /></TableCell>
                  <TableCell><GradeBadge grade={d.conviction_grade} score={d.conviction_score} /></TableCell>
                  <TableCell className={compact ? 'hidden' : 'hidden md:table-cell max-w-[120px] truncate text-muted-foreground text-[0.76rem]'}>{d.sector}</TableCell>
                  <TableCell className="tabular-nums">
                    {d.target_price_analyst ? `$${d.target_price_analyst.toFixed(0)}` : '—'}
                    {d.analyst_upside_pct != null && (
                      <span className={`ml-1.5 text-xs font-semibold ${d.analyst_upside_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {d.analyst_upside_pct > 0 ? '+' : ''}{d.analyst_upside_pct.toFixed(0)}%
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">{fmtFcf(d.fcf_yield_pct)}</TableCell>
                  <TableCell className={compact ? 'hidden' : ''}>{fmtRR(d.risk_reward_ratio)}</TableCell>
                  <TableCell className={compact ? 'hidden' : 'hidden sm:table-cell'}>{fmtDivBB(d)}</TableCell>
                  <TableCell>{fmtEarn(d)}</TableCell>
                  <TableCell className={compact ? 'hidden' : 'hidden sm:table-cell'}>
                    <TechBiasCell t={techMap[d.ticker]} />
                  </TableCell>
                  <TableCell>
                    <WatchlistButton ticker={d.ticker} company_name={d.company_name} sector={d.sector} current_price={d.current_price} value_score={d.value_score} conviction_grade={d.conviction_grade} analyst_upside_pct={d.analyst_upside_pct} fcf_yield_pct={d.fcf_yield_pct} />
                  </TableCell>
              </TableRow>
            )
          })}
          </TableBody>
        </Table>
        {sorted.length === 0 && (
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">💎</div>
            <p className="font-medium text-muted-foreground">
              {rows.length === 0 ? 'Sin oportunidades VALUE en este momento' : 'Sin resultados con los filtros aplicados'}
            </p>
          </CardContent>
        )}
        {sorted.length > 0 && (
          <div className="hidden sm:block text-[0.6rem] text-muted-foreground/25 text-right px-3 py-1.5 border-t border-border/10">
            j / k navegar · Enter ver tesis · Esc cerrar
          </div>
        )}
      </Card>
      </div>

      <PaginationBar page={page} totalPages={totalPages} onPage={setPage} />

      {expandedRow && (
        <ThesisModal
          row={expandedRow}
          thesisText={thesisText}
          onClose={() => setExpandedRow(null)}
        />
      )}
    </>
  )
}
