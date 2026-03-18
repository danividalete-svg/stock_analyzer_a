import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { SlidersHorizontal, TrendingUp, TrendingDown, ExternalLink } from 'lucide-react'
import {
  fetchValueOpportunities,
  fetchEUValueOpportunities,
  fetchGlobalValueOpportunities,
  type ValueOpportunity,
} from '../api/client'
import Loading from '../components/Loading'
import GradeBadge from '../components/GradeBadge'
import ScoreBar from '../components/ScoreBar'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'

// ── Types ─────────────────────────────────────────────────────────────────────

type Row = ValueOpportunity & { _market: 'US' | 'EU' | 'GLOBAL' }
type SortKey = keyof Row
type SortDir  = 'asc' | 'desc'

const MARKET_FLAG: Record<string, string> = { US: '🇺🇸', EU: '🇪🇺', GLOBAL: '🌍' }

// ── Helpers ───────────────────────────────────────────────────────────────────

const pct  = (v: number | null | undefined) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '—'
const x    = (v: number | null | undefined) => v != null ? `${v.toFixed(1)}x`  : '—'
const n1   = (v: number | null | undefined) => v != null ? v.toFixed(1)        : '—'

// ── Column config ─────────────────────────────────────────────────────────────

interface Col { key: SortKey; label: string; fmt: (r: Row) => string; cls?: (r: Row) => string }

const COLS: Col[] = [
  { key: 'value_score',        label: 'Score',   fmt: r => n1(r.value_score),              cls: () => '' },
  { key: 'current_price',      label: 'Precio',  fmt: r => r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—' },
  { key: 'analyst_upside_pct', label: 'Upside',  fmt: r => pct(r.analyst_upside_pct),      cls: r => (r.analyst_upside_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400' },
  { key: 'fcf_yield_pct',      label: 'FCF%',    fmt: r => pct(r.fcf_yield_pct),           cls: r => (r.fcf_yield_pct ?? 0) >= 5 ? 'text-emerald-400' : '' },
  { key: 'risk_reward_ratio',  label: 'R:R',     fmt: r => x(r.risk_reward_ratio),         cls: r => (r.risk_reward_ratio ?? 0) >= 2 ? 'text-emerald-400' : '' },
  { key: 'piotroski_score',    label: 'Piotroski',fmt: r => r.piotroski_score != null ? `${r.piotroski_score}/9` : '—', cls: r => (r.piotroski_score ?? 0) >= 6 ? 'text-emerald-400' : (r.piotroski_score ?? 9) <= 3 ? 'text-red-400' : '' },
  { key: 'ebit_ev_yield',      label: 'EBIT/EV', fmt: r => pct(r.ebit_ev_yield) },
  { key: 'dividend_yield_pct', label: 'Div%',    fmt: r => r.dividend_yield_pct ? pct(r.dividend_yield_pct) : '—' },
]

// ── Sorter header ─────────────────────────────────────────────────────────────

function TH({ label, col, sortKey, sortDir, onSort }: {
  label: string; col: SortKey; sortKey: SortKey; sortDir: SortDir; onSort: (k: SortKey) => void
}) {
  const active = sortKey === col
  return (
    <th
      className="px-3 py-2.5 text-left text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground cursor-pointer hover:text-foreground transition-colors whitespace-nowrap select-none"
      onClick={() => onSort(col)}
    >
      {label}
      {active && <span className="ml-1 opacity-60">{sortDir === 'desc' ? '↓' : '↑'}</span>}
    </th>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Screener() {
  const navigate = useNavigate()

  const [rows,    setRows]    = useState<Row[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  // Filters
  const [market,      setMarket]      = useState<string>('ALL')
  const [grade,       setGrade]       = useState<string>('ALL')
  const [sector,      setSector]      = useState<string>('ALL')
  const [minFcf,      setMinFcf]      = useState('')
  const [minUpside,   setMinUpside]   = useState('')
  const [minScore,    setMinScore]    = useState('')
  const [hideEarn,    setHideEarn]    = useState(false)

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>('value_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Load all markets
  useEffect(() => {
    Promise.all([
      fetchValueOpportunities(),
      fetchEUValueOpportunities(),
      fetchGlobalValueOpportunities(),
    ]).then(([us, eu, gl]) => {
      const all: Row[] = [
        ...(us.data.data  ?? []).map(r => ({ ...r, _market: 'US'     as const })),
        ...(eu.data.data  ?? []).map(r => ({ ...r, _market: 'EU'     as const })),
        ...(gl.data.data  ?? []).map(r => ({ ...r, _market: 'GLOBAL' as const })),
      ]
      setRows(all)
      setLoading(false)
    }).catch(e => {
      setError(e.message || 'Error cargando datos')
      setLoading(false)
    })
  }, [])

  const sectors = useMemo(() =>
    ['ALL', ...Array.from(new Set(rows.map(r => r.sector).filter(Boolean) as string[])).sort()],
    [rows]
  )

  const filtered = useMemo(() => {
    return rows.filter(r => {
      if (market !== 'ALL' && r._market !== market) return false
      if (grade  !== 'ALL' && r.conviction_grade !== grade) return false
      if (sector !== 'ALL' && r.sector !== sector) return false
      if (minFcf    !== '' && (r.fcf_yield_pct == null || r.fcf_yield_pct < Number(minFcf))) return false
      if (minUpside !== '' && (r.analyst_upside_pct == null || r.analyst_upside_pct < Number(minUpside))) return false
      if (minScore  !== '' && (r.value_score == null || r.value_score < Number(minScore))) return false
      if (hideEarn && r.earnings_warning) return false
      return true
    })
  }, [rows, market, grade, sector, minFcf, minUpside, minScore, hideEarn])

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = (a[sortKey] as number) ?? 0
      const bv = (b[sortKey] as number) ?? 0
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [filtered, sortKey, sortDir])

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const resetFilters = () => {
    setMarket('ALL'); setGrade('ALL'); setSector('ALL')
    setMinFcf(''); setMinUpside(''); setMinScore(''); setHideEarn(false)
  }

  if (loading) return <Loading />
  if (error)   return <div className="text-red-400 text-sm p-4">{error}</div>

  const hasFilters = market !== 'ALL' || grade !== 'ALL' || sector !== 'ALL' || minFcf || minUpside || minScore || hideEarn

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-2">
          <SlidersHorizontal size={22} className="text-primary" />
          Screener
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Filtra entre {rows.length} acciones VALUE (US + EU + Global) por cualquier métrica.
        </p>
      </div>

      {/* Filter bar */}
      <div className="glass rounded-2xl p-4 space-y-3">
        <div className="flex flex-wrap gap-2 items-end">
          {/* Market */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground">Mercado</label>
            <div className="flex gap-1">
              {['ALL', 'US', 'EU', 'GLOBAL'].map(m => (
                <button
                  key={m}
                  onClick={() => setMarket(m)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors border ${
                    market === m
                      ? 'bg-primary/15 border-primary/30 text-primary'
                      : 'bg-muted/20 border-border/30 text-muted-foreground hover:bg-muted/40'
                  }`}
                >
                  {m === 'ALL' ? 'Todos' : MARKET_FLAG[m]}
                </button>
              ))}
            </div>
          </div>

          {/* Grade */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground">Grade</label>
            <div className="flex gap-1">
              {['ALL', 'A+', 'A', 'B'].map(g => (
                <button
                  key={g}
                  onClick={() => setGrade(g)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors border ${
                    grade === g
                      ? 'bg-primary/15 border-primary/30 text-primary'
                      : 'bg-muted/20 border-border/30 text-muted-foreground hover:bg-muted/40'
                  }`}
                >
                  {g === 'ALL' ? 'Todos' : g}
                </button>
              ))}
            </div>
          </div>

          {/* Sector */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground">Sector</label>
            <select
              value={sector}
              onChange={e => setSector(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-muted/30 border border-border/40 text-xs text-foreground focus:outline-none focus:border-primary/50 max-w-[160px]"
            >
              {sectors.map(s => <option key={s} value={s}>{s === 'ALL' ? 'Todos' : s}</option>)}
            </select>
          </div>

          {/* Numeric filters */}
          {[
            { label: 'FCF% ≥', val: minFcf,    set: setMinFcf,    placeholder: '5' },
            { label: 'Upside ≥', val: minUpside, set: setMinUpside, placeholder: '15' },
            { label: 'Score ≥',  val: minScore,  set: setMinScore,  placeholder: '60' },
          ].map(({ label, val, set, placeholder }) => (
            <div key={label} className="flex flex-col gap-1">
              <label className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground">{label}</label>
              <input
                value={val}
                onChange={e => set(e.target.value)}
                placeholder={placeholder}
                type="number"
                className="w-20 px-3 py-1.5 rounded-lg bg-muted/30 border border-border/40 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
              />
            </div>
          ))}

          {/* Hide earnings */}
          <div className="flex flex-col gap-1">
            <label className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground">Earnings</label>
            <button
              onClick={() => setHideEarn(e => !e)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors border ${
                hideEarn
                  ? 'bg-amber-500/15 border-amber-500/30 text-amber-400'
                  : 'bg-muted/20 border-border/30 text-muted-foreground hover:bg-muted/40'
              }`}
            >
              Ocultar riesgo
            </button>
          </div>

          {/* Reset */}
          {hasFilters && (
            <button
              onClick={resetFilters}
              className="self-end px-3 py-1.5 rounded-lg text-xs font-semibold text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors border border-border/30"
            >
              Limpiar
            </button>
          )}
        </div>

        {/* Results count */}
        <div className="text-[0.65rem] text-muted-foreground/60 font-semibold uppercase tracking-widest">
          {sorted.length} resultado{sorted.length !== 1 ? 's' : ''}
          {hasFilters && ` de ${rows.length}`}
        </div>
      </div>

      {/* Table */}
      {sorted.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <SlidersHorizontal size={36} className="mx-auto text-muted-foreground/30 mb-4" />
          <p className="text-foreground font-semibold mb-1">Sin resultados</p>
          <p className="text-sm text-muted-foreground">Ajusta los filtros.</p>
        </div>
      ) : (
        <div className="glass rounded-2xl">
          <div style={{ overflowX: 'clip', overflowY: 'visible' }}>
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20">
                  <th className="px-3 py-2.5 text-left text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground whitespace-nowrap w-8">#</th>
                  <TH label="Ticker"    col="ticker"           sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <TH label="Empresa"   col="company_name"     sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
                  <th className="px-3 py-2.5 text-left text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground">Grade</th>
                  {COLS.map(c => <TH key={c.key as string} label={c.label} col={c.key} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />)}
                </tr>
              </thead>
              <tbody>
                {sorted.map((row, i) => (
                  <tr
                    key={`${row.ticker}-${row._market}`}
                    className="border-b border-border/10 hover:bg-muted/10 cursor-pointer transition-colors"
                    onClick={() => navigate(`/search?q=${row.ticker}`)}
                  >
                    <td className="px-3 py-2.5 text-[0.65rem] text-muted-foreground/50 tabular-nums">{i + 1}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <TickerLogo ticker={row.ticker} size="xs" />
                        <span className="font-mono font-extrabold text-sm text-primary">{row.ticker}</span>
                        <span className="text-[0.6rem]">{MARKET_FLAG[row._market]}</span>
                        <OwnedBadge ticker={row.ticker} />
                        {row.earnings_warning && (
                          <span className="text-[0.58rem] px-1 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400">⚡ earn</span>
                        )}
                        {row.buyback_active && (
                          <span className="text-[0.58rem] px-1 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">BB</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground max-w-[160px] truncate">
                      {row.company_name}
                    </td>
                    <td className="px-3 py-2.5">
                      <GradeBadge grade={row.conviction_grade} />
                    </td>
                    {COLS.map(c => {
                      const val  = row[c.key] as number | null
                      const isUp = c.key === 'analyst_upside_pct' && val != null && val > 0
                      const isDn = c.key === 'analyst_upside_pct' && val != null && val < 0
                      return (
                        <td key={c.key as string} className="px-3 py-2.5">
                          <span className={`text-sm tabular-nums font-medium flex items-center gap-0.5 ${c.cls ? c.cls(row) : 'text-foreground/80'}`}>
                            {isUp && <TrendingUp size={10} />}
                            {isDn && <TrendingDown size={10} />}
                            {c.key === 'value_score'
                              ? <span className="flex items-center gap-2"><ScoreBar score={val ?? 0} /><span className="text-xs">{c.fmt(row)}</span></span>
                              : c.fmt(row)
                            }
                          </span>
                        </td>
                      )
                    })}
                    <td className="px-3 py-2.5">
                      <ExternalLink size={11} className="text-muted-foreground/30" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
