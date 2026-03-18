import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { GitCompare, Plus, X, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { searchTickers, type SearchResult } from '../api/client'
import TickerLogo from '../components/TickerLogo'

const API_BASE = import.meta.env.VITE_API_URL || ''

// ── Types ─────────────────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type TickerData = Record<string, any>

interface Metric {
  key: string
  label: string
  format: (v: number | null) => string
  color?: (v: number | null, all: (number | null)[]) => string
  section?: string
}

// ── Metric definitions ────────────────────────────────────────────────────────

const good = (v: number | null, all: (number | null)[]) => {
  const vals = all.filter((x): x is number => x != null)
  if (vals.length < 2 || v == null) return ''
  return v === Math.max(...vals) ? 'text-emerald-400' : v === Math.min(...vals) ? 'text-red-400' : ''
}
const bad = (v: number | null, all: (number | null)[]) => {
  const vals = all.filter((x): x is number => x != null)
  if (vals.length < 2 || v == null) return ''
  return v === Math.min(...vals) ? 'text-emerald-400' : v === Math.max(...vals) ? 'text-red-400' : ''
}

const pct = (v: number | null) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '—'
const x   = (v: number | null) => v != null ? `${v.toFixed(1)}x` : '—'
const p2  = (v: number | null) => v != null ? `$${v.toFixed(2)}` : '—'
const p0  = (v: number | null) => v != null ? `$${v.toFixed(0)}` : '—'
const n1  = (v: number | null) => v != null ? v.toFixed(1) : '—'
const n0  = (v: number | null) => v != null ? v.toFixed(0) : '—'

const METRICS: Metric[] = [
  // Valoración
  { key: 'current_price',       label: 'Precio actual',       format: p2,           section: 'Valoración' },
  { key: 'target_price_analyst',label: 'Target analistas',    format: p0 },
  { key: 'analyst_upside_pct',  label: 'Upside analistas',    format: pct,          color: good },
  { key: 'analyst_recommendation', label: 'Rec. analistas',   format: v => String(v ?? '—') },
  { key: 'analyst_count',       label: 'Nº analistas',        format: n0 },
  { key: 'target_price_dcf',    label: 'Target DCF',          format: p0 },
  { key: 'target_price_dcf_upside_pct', label: 'Upside DCF', format: pct,           color: good },
  // Múltiplos
  { key: 'forward_pe',          label: 'P/E forward',         format: x,            color: bad,  section: 'Múltiplos' },
  { key: 'peg_ratio',           label: 'PEG',                 format: n1,           color: bad },
  { key: 'ebit_ev_yield',       label: 'EBIT/EV yield',       format: pct,          color: good },
  // Calidad
  { key: 'fcf_yield',           label: 'FCF Yield',           format: pct,          color: good, section: 'Calidad' },
  { key: 'roe',                 label: 'ROE',                 format: pct,          color: good },
  { key: 'revenue_growth',      label: 'Crecimiento revenue', format: pct,          color: good },
  { key: 'roic_greenblatt',     label: 'ROIC',                format: pct,          color: good },
  { key: 'operating_margin_pct',label: 'Margen operativo',    format: pct,          color: good },
  { key: 'profit_margin_pct',   label: 'Margen neto',         format: pct,          color: good },
  { key: 'interest_coverage',   label: 'Cobertura intereses', format: n1,           color: good },
  // Scores
  { key: 'final_score',         label: 'Score final',         format: n1,           color: good, section: 'Scores' },
  { key: 'fund_score',          label: 'Score fundamental',   format: n1,           color: good },
  { key: 'piotroski_score',     label: 'Piotroski F-Score',   format: v => v != null ? `${n0(v)}/9` : '—', color: good },
  { key: 'insiders_score',      label: 'Score insiders',      format: n1,           color: good },
  // Dividendo
  { key: 'dividend_yield',      label: 'Div. yield',          format: pct,          color: good, section: 'Dividendo' },
  { key: 'payout_ratio',        label: 'Payout ratio',        format: pct,          color: bad },
  // Riesgo
  { key: 'days_to_earnings',    label: 'Días a earnings',     format: n0,           color: bad,  section: 'Riesgo' },
  { key: 'short_percent_float', label: 'Short % float',       format: pct,          color: bad },
  { key: 'proximity_to_52w_high', label: 'Distancia 52w high', format: pct,         color: good },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function getVal(data: TickerData, key: string): number | string | null {
  const v = data[key]
  if (v == null || (typeof v === 'number' && isNaN(v))) return null
  return v
}

function getNum(data: TickerData, key: string): number | null {
  const v = getVal(data, key)
  return typeof v === 'number' ? v : null
}

// ── Cell ─────────────────────────────────────────────────────────────────────

function Cell({ metric, data, allData }: { metric: Metric; data: TickerData; allData: TickerData[] }) {
  const raw  = getVal(data, metric.key)
  const num  = typeof raw === 'number' ? raw : null
  const nums = allData.map(d => getNum(d, metric.key))
  const cls  = metric.color ? metric.color(num, nums) : ''
  const text = raw != null ? metric.format(raw as number) : '—'

  const isUpside = metric.key === 'analyst_upside_pct' || metric.key === 'target_price_dcf_upside_pct'
  const isGrowth = metric.key === 'revenue_growth' || metric.key === 'roe' || metric.key === 'roic_greenblatt'

  return (
    <td className="px-4 py-2.5 text-center text-sm tabular-nums">
      <span className={`font-semibold ${cls || 'text-foreground/80'} flex items-center justify-center gap-1`}>
        {(isUpside || isGrowth) && num != null && (
          num > 0 ? <TrendingUp size={11} /> : num < 0 ? <TrendingDown size={11} /> : <Minus size={11} />
        )}
        {text}
      </span>
    </td>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function Comparador() {
  const [input, setInput]     = useState('')
  const [tickers, setTickers] = useState<string[]>([])
  const [results, setResults] = useState<Record<string, TickerData>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [errors, setErrors]   = useState<Record<string, string>>({})
  const [suggestions, setSuggestions] = useState<SearchResult[]>([])
  const [showSugg, setShowSugg] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Debounced autocomplete
  useEffect(() => {
    const q = input.trim()
    if (!q) { setSuggestions([]); setShowSugg(false); return }
    const delay = q.length <= 2 ? 500 : 280
    const timer = setTimeout(async () => {
      try {
        const res = await searchTickers(q)
        const items = res.data?.results || []
        setSuggestions(items)
        setShowSugg(items.length > 0)
        setActiveIdx(-1)
      } catch { setSuggestions([]) }
    }, delay)
    return () => clearTimeout(timer)
  }, [input])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setShowSugg(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const addTickerBySymbol = async (sym: string) => {
    const t = sym.trim().toUpperCase()
    if (!t || tickers.includes(t) || tickers.length >= 4) return
    setInput('')
    setSuggestions([])
    setShowSugg(false)
    setTickers(prev => [...prev, t])
    setLoading(prev => ({ ...prev, [t]: true }))
    setErrors(prev => { const e = { ...prev }; delete e[t]; return e })
    try {
      const resp = await axios.get(`${API_BASE}/api/analyze/${t}`)
      setResults(prev => ({ ...prev, [t]: resp.data }))
    } catch {
      setErrors(prev => ({ ...prev, [t]: 'No se pudo cargar' }))
    } finally {
      setLoading(prev => ({ ...prev, [t]: false }))
    }
  }

  const addTicker = async () => {
    const t = input.trim()
    // If input looks like a company name, auto-select first suggestion
    if (suggestions.length > 0 && (t.includes(' ') || (t.length > 6 && t !== t.toUpperCase()))) {
      addTickerBySymbol(suggestions[0].ticker)
      return
    }
    addTickerBySymbol(t)
  }

  const remove = (t: string) => {
    setTickers(prev => prev.filter(x => x !== t))
    setResults(prev => { const r = { ...prev }; delete r[t]; return r })
    setErrors(prev => { const e = { ...prev }; delete e[t]; return e })
  }

  const loadedTickers = tickers.filter(t => results[t] && !errors[t])
  const allData = loadedTickers.map(t => results[t])

  // Group metrics by section
  const sections: { title: string; metrics: Metric[] }[] = []
  let current: { title: string; metrics: Metric[] } | null = null
  for (const m of METRICS) {
    if (m.section) {
      current = { title: m.section, metrics: [m] }
      sections.push(current)
    } else if (current) {
      current.metrics.push(m)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-2">
          <GitCompare size={22} className="text-primary" />
          Comparador de Acciones
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Compara hasta 4 tickers en paralelo con métricas clave. Verde = mejor, rojo = peor.
        </p>
      </div>

      {/* Input */}
      <div className="glass rounded-2xl p-5">
        <div className="flex gap-2 flex-wrap items-center">
          {tickers.map(t => (
            <div key={t} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted/30 border border-border/40 text-sm">
              {loading[t] ? (
                <Loader2 size={12} className="animate-spin text-muted-foreground" />
              ) : errors[t] ? (
                <X size={12} className="text-red-400" />
              ) : (
                <TickerLogo ticker={t} size="xs" />
              )}
              <span className={`font-mono font-bold ${errors[t] ? 'text-red-400' : 'text-foreground'}`}>{t}</span>
              <button onClick={() => remove(t)} className="ml-1 text-muted-foreground hover:text-red-400 transition-colors">
                <X size={12} />
              </button>
            </div>
          ))}
          {tickers.length < 4 && (
            <div className="relative" ref={wrapRef}>
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Escape') { setShowSugg(false); return }
                    if (e.key === 'Enter') {
                      if (showSugg && activeIdx >= 0 && suggestions[activeIdx]) {
                        addTickerBySymbol(suggestions[activeIdx].ticker)
                      } else {
                        addTicker()
                      }
                      return
                    }
                    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, suggestions.length - 1)) }
                    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, -1)) }
                  }}
                  onFocus={() => suggestions.length > 0 && setShowSugg(true)}
                  placeholder="AAPL o Apple..."
                  className="w-40 px-3 py-1.5 rounded-lg bg-muted/30 border border-border/40 text-sm font-bold text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
                />
                <button
                  onClick={addTicker}
                  disabled={!input.trim()}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  <Plus size={13} />
                  Añadir
                </button>
              </div>
              {showSugg && suggestions.length > 0 && (
                <ul className="absolute top-full left-0 mt-1 z-50 w-72 bg-card border border-border rounded-lg shadow-xl overflow-hidden">
                  {suggestions.map((s, i) => (
                    <li
                      key={s.ticker}
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors text-sm ${i === activeIdx ? 'bg-primary/10' : 'hover:bg-muted/50'}`}
                      onMouseDown={() => addTickerBySymbol(s.ticker)}
                      onMouseEnter={() => setActiveIdx(i)}
                    >
                      <span className="font-mono font-bold text-primary w-16 shrink-0">{s.ticker}</span>
                      <span className="text-muted-foreground truncate">{s.company_name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Empty state */}
      {tickers.length === 0 && (
        <div className="glass rounded-2xl p-12 text-center">
          <GitCompare size={40} className="mx-auto text-muted-foreground/30 mb-4" />
          <p className="text-foreground font-semibold mb-1">Añade al menos 2 tickers</p>
          <p className="text-sm text-muted-foreground">Escribe un ticker y pulsa Enter o "Añadir"</p>
        </div>
      )}

      {/* Comparison table */}
      {loadedTickers.length >= 1 && (
        <div className="glass rounded-2xl">
          <div style={{ overflowX: 'clip', overflowY: 'visible' }}>
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/30 bg-muted/20">
                  <th className="px-4 py-3 text-left text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground w-40">
                    Métrica
                  </th>
                  {loadedTickers.map(t => {
                    const d = results[t]
                    return (
                      <th key={t} className="px-4 py-3 text-center">
                        <div className="flex flex-col items-center gap-1">
                          <div className="flex items-center gap-1.5">
                            <TickerLogo ticker={t} size="xs" />
                            <span className="font-mono font-extrabold text-primary">{t}</span>
                          </div>
                          {d?.company_name && d.company_name !== t && (
                            <span className="text-[0.62rem] text-muted-foreground truncate max-w-[120px]">{d.company_name}</span>
                          )}
                          {d?.sector_name && (
                            <span className="text-[0.58rem] px-1.5 py-0.5 rounded bg-muted/40 border border-border/30 text-muted-foreground/60 uppercase tracking-wide">
                              {d.sector_name}
                            </span>
                          )}
                        </div>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {sections.map(section => (
                  <>
                    <tr key={`section-${section.title}`} className="bg-muted/10">
                      <td colSpan={loadedTickers.length + 1} className="px-4 py-1.5 text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground/50">
                        {section.title}
                      </td>
                    </tr>
                    {section.metrics.map((metric, mi) => {
                      // Skip metric if all values are null
                      const hasAny = loadedTickers.some(t => getVal(results[t], metric.key) != null)
                      if (!hasAny) return null
                      return (
                        <tr key={metric.key} className={`border-b border-border/10 ${mi % 2 === 0 ? '' : 'bg-muted/5'}`}>
                          <td className="px-4 py-2.5 text-[0.72rem] text-muted-foreground font-medium whitespace-nowrap">
                            {metric.label}
                          </td>
                          {loadedTickers.map(t => (
                            <Cell key={t} metric={metric} data={results[t]} allData={allData} />
                          ))}
                        </tr>
                      )
                    })}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
