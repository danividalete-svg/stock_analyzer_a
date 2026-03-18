import { useState, useEffect } from 'react'
import { FlaskConical, Info, ArrowLeftRight } from 'lucide-react'
import Loading from '../components/Loading'
import TickerLogo from '../components/TickerLogo'

// ── Config ─────────────────────────────────────────────────────────────────────

const CSV_BASE = (import.meta.env.VITE_CSV_BASE as string | undefined)
  ?? 'https://tantancansado.github.io/stock_analyzer_a'
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

// ── Types ──────────────────────────────────────────────────────────────────────

interface Signal {
  ticker: string
  company_name: string
  strategy: string
  signal_date: string
  signal_price: number
  value_score: number | null
  sector: string
  return_7d: number | null
  return_14d: number | null
  return_30d: number | null
}

interface MRSetup {
  ticker: string
  company_name: string
  strategy: string
  quality: string
  reversion_score: number
  current_price: number
  target: number
  stop_loss: number
  risk_reward: number
  detected_date: string
  rsi: number | null
  drawdown_pct: number | null
}

// ── CSV parsers ────────────────────────────────────────────────────────────────

function splitCSV(line: string): string[] {
  const result: string[] = []
  let cur = '', inQ = false
  for (const ch of line) {
    if (ch === '"') { inQ = !inQ }
    else if (ch === ',' && !inQ) { result.push(cur); cur = '' }
    else { cur += ch }
  }
  result.push(cur)
  return result
}

function parseSignalsCSV(text: string): Signal[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const headers = splitCSV(lines[0]).map(h => h.trim())
  const idx = (name: string) => headers.indexOf(name)
  const rows = lines.slice(1).map(line => {
    const cols = splitCSV(line)
    const get  = (name: string) => cols[idx(name)]?.trim() ?? ''
    const num  = (name: string) => { const v = parseFloat(get(name)); return isNaN(v) ? null : v }
    return {
      ticker: get('ticker'), company_name: get('company_name'),
      strategy: get('strategy'), signal_date: get('signal_date'),
      signal_price: parseFloat(get('signal_price')) || 0,
      value_score: num('value_score'), sector: get('sector'),
      return_7d: num('return_7d'), return_14d: num('return_14d'), return_30d: num('return_30d'),
    }
  }).filter(s => s.ticker)

  // Deduplicate: one entry per ticker — keep the earliest signal date
  const seen = new Map<string, Signal>()
  for (const s of rows.sort((a,b) => a.signal_date.localeCompare(b.signal_date))) {
    if (!seen.has(s.ticker)) seen.set(s.ticker, s)
  }
  return Array.from(seen.values())
}

function parseMRCSV(text: string): MRSetup[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const headers = splitCSV(lines[0]).map(h => h.trim())
  const idx = (name: string) => headers.indexOf(name)
  return lines.slice(1).map(line => {
    const cols = splitCSV(line)
    const get  = (name: string) => cols[idx(name)]?.trim() ?? ''
    const num  = (name: string) => { const v = parseFloat(get(name)); return isNaN(v) ? null : v }
    return {
      ticker: get('ticker'), company_name: get('company_name'),
      strategy: get('strategy'), quality: get('quality'),
      reversion_score: num('reversion_score') ?? 0,
      current_price: num('current_price') ?? 0,
      target: parseFloat(get('target')) || 0,
      stop_loss: parseFloat(get('stop_loss')) || 0,
      risk_reward: num('risk_reward') ?? 0,
      detected_date: get('detected_date'),
      rsi: num('rsi'), drawdown_pct: num('drawdown_pct'),
    }
  }).filter(s => s.ticker)
}

// ── Helpers ────────────────────────────────────────────────────────────────────

type Period = '7d' | '14d' | '30d'
const PERIODS: { key: Period; label: string }[] = [
  { key: '7d',  label: '+7 días' },
  { key: '14d', label: '+14 días' },
  { key: '30d', label: '+30 días' },
]

function retOf(s: Signal, p: Period) {
  return p === '7d' ? s.return_7d : p === '14d' ? s.return_14d : s.return_30d
}

function pct(v: number | null, d = 1) {
  if (v == null) return null
  return `${v >= 0 ? '+' : ''}${v.toFixed(d)}%`
}

async function fetchCSV(url: string): Promise<string> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.text()
}

function Stats({ signals, period }: { signals: Signal[]; period: Period }) {
  const withData = signals.filter(s => retOf(s, period) != null)
  if (!withData.length) return (
    <div className="glass rounded-2xl p-5 text-center text-sm text-muted-foreground">
      Sin resultados a {period} todavía — se completan automáticamente con el pipeline diario
    </div>
  )
  const rets   = withData.map(s => retOf(s, period)!)
  const wins   = rets.filter(r => r > 0).length
  const avg    = rets.reduce((a, b) => a + b, 0) / rets.length
  const wr     = (wins / rets.length) * 100
  const sorted = [...rets].sort((a,b) => a - b)
  const mid    = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 === 0 ? (sorted[mid-1] + sorted[mid]) / 2 : sorted[mid]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: 'Tickers evaluados', val: String(withData.length), sub: `de ${signals.length} únicos`, color: '' },
        { label: 'Win Rate', val: `${wr.toFixed(1)}%`, sub: `${wins} ganaron · ${withData.length-wins} perdieron`, color: wr >= 50 ? 'text-emerald-400' : 'text-red-400' },
        { label: 'Retorno medio', val: pct(avg, 2)!, sub: `mediana ${pct(median, 2)}`, color: avg >= 0 ? 'text-emerald-400' : 'text-red-400' },
        { label: 'Mejor / Peor', val: `${pct(Math.max(...rets))} / ${pct(Math.min(...rets))}`, sub: '', color: '' },
      ].map(c => (
        <div key={c.label} className="glass rounded-2xl p-4">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-1">{c.label}</div>
          <div className={`text-2xl font-extrabold ${c.color}`}>{c.val}</div>
          {c.sub && <div className="text-[0.66rem] text-muted-foreground mt-0.5">{c.sub}</div>}
        </div>
      ))}
    </div>
  )
}

const STRAT_LABEL: Record<string, string> = {
  VALUE: 'Value US 🇺🇸', EU_VALUE: 'Value EU 🇪🇺', GLOBAL_VALUE: 'Value Global 🌍',
}

// ── Main ───────────────────────────────────────────────────────────────────────

export default function Backtest() {
  const [signals,  setSignals]  = useState<Signal[]>([])
  const [mrSetups, setMrSetups] = useState<MRSetup[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [tab,      setTab]      = useState<'value' | 'mr'>('value')
  const [period,   setPeriod]   = useState<Period>('7d')
  const [strat,    setStrat]    = useState('ALL')
  const [sort,     setSort]     = useState<'date' | 'ret' | 'score'>('ret')

  useEffect(() => {
    const sigUrl    = `${CSV_BASE}/portfolio_tracker/recommendations.csv`
    const mrUrl     = `${CSV_BASE}/mean_reversion_opportunities.csv`
    const usUrl     = `${CSV_BASE}/value_opportunities_filtered.csv`
    const euUrl     = `${CSV_BASE}/european_value_opportunities_filtered.csv`

    const parseTickers = (text: string) =>
      text.trim().split('\n').slice(1).map(l => l.split(',')[0].trim()).filter(Boolean)

    Promise.all([
      fetchCSV(sigUrl).catch(() =>
        fetch(`${API_BASE}/api/portfolio-tracker/signals`)
          .then(r => r.json())
          .then((j: {data?:Record<string,unknown>[]}) =>
            ['ticker,company_name,strategy,signal_date,signal_price,value_score,sector,return_7d,return_14d,return_30d',
             ...(j.data??[]).map(r => [r.ticker,r.company_name,r.strategy,r.signal_date,r.signal_price,r.value_score,r.sector,r.return_7d,r.return_14d,r.return_30d].join(','))
            ].join('\n')
          )
      ),
      fetchCSV(mrUrl).catch(() => ''),
      fetchCSV(usUrl).catch(() => ''),
      fetchCSV(euUrl).catch(() => ''),
    ]).then(([sigText, mrText, usText, euText]) => {
      const allowed = new Set([...parseTickers(usText), ...parseTickers(euText)])
      const all = parseSignalsCSV(sigText)
      setSignals(allowed.size > 0 ? all.filter(s => allowed.has(s.ticker)) : all)
      if (mrText) setMrSetups(parseMRCSV(mrText))
      setLoading(false)
    }).catch(e => { setError(String(e)); setLoading(false) })
  }, [])

  if (loading) return <Loading />
  if (error)   return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold flex items-center gap-2"><FlaskConical size={22} className="text-primary" />Backtest</h1>
      <div className="glass rounded-2xl p-8 text-center text-sm text-muted-foreground">{error}</div>
    </div>
  )

  const strategies = [...new Set(signals.map(s => s.strategy))].sort()
  const filtered   = strat === 'ALL' ? signals : signals.filter(s => s.strategy === strat)
  const sorted = [...filtered].sort((a, b) => {
    if (sort === 'date')  return b.signal_date.localeCompare(a.signal_date)
    if (sort === 'score') return (b.value_score ?? 0) - (a.value_score ?? 0)
    const ra = retOf(a, period), rb = retOf(b, period)
    if (ra == null && rb == null) return 0
    if (ra == null) return 1
    if (rb == null) return -1
    return rb - ra
  })

  const dateRange = signals.length
    ? `${signals.map(s=>s.signal_date).sort()[0]} → ${signals.map(s=>s.signal_date).sort().at(-1)}`
    : ''

  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-2">
          <FlaskConical size={22} className="text-primary" /> Backtest — Señales Reales
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {signals.length} tickers únicos · {dateRange} · resultados forward-looking
        </p>
      </div>

      <div className="flex items-start gap-3 p-3.5 rounded-xl bg-primary/5 border border-primary/20">
        <Info size={13} className="text-primary mt-0.5 shrink-0" />
        <p className="text-xs text-muted-foreground">
          Señales generadas en tiempo real. Deduplicadas por ticker — si el sistema seleccionó el mismo ticker varios días, se muestra solo la primera señal para no inflar el win rate.
        </p>
      </div>

      {/* Main tabs */}
      <div className="flex gap-2 p-1 rounded-xl bg-muted/20 border border-border/30 w-fit">
        <button onClick={() => setTab('value')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${tab === 'value' ? 'bg-background text-primary border border-primary/40 shadow-sm' : 'text-muted-foreground hover:text-foreground border border-transparent'}`}>
          📊 Value ({signals.length})
        </button>
        <button onClick={() => setTab('mr')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${tab === 'mr' ? 'bg-background text-teal-400 border border-teal-500/40 shadow-sm' : 'text-muted-foreground hover:text-foreground border border-transparent'}`}>
          <ArrowLeftRight size={14} /> Mean Reversion ({mrSetups.length})
        </button>
      </div>

      {/* ── VALUE TAB ── */}
      {tab === 'value' && (
        <div className="space-y-4">
          {/* Strategy filter */}
          <div className="flex gap-2 flex-wrap">
            {['ALL', ...strategies].map(s => (
              <button key={s} onClick={() => setStrat(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  strat === s ? 'bg-primary/15 border-primary/30 text-primary' : 'bg-muted/20 border-border/30 text-muted-foreground hover:text-foreground'
                }`}>
                {s === 'ALL' ? `Todas (${signals.length})` : `${STRAT_LABEL[s]??s} (${signals.filter(x=>x.strategy===s).length})`}
              </button>
            ))}
          </div>

          {/* Period tabs */}
          <div className="flex gap-1 p-1 rounded-xl bg-muted/20 border border-border/30 w-fit">
            {PERIODS.map(p => (
              <button key={p.key} onClick={() => setPeriod(p.key)}
                className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  period === p.key ? 'bg-background text-foreground shadow-sm border border-border/40' : 'text-muted-foreground hover:text-foreground'
                }`}>
                {p.label} <span className="text-muted-foreground/50">({filtered.filter(s=>retOf(s,p.key)!=null).length})</span>
              </button>
            ))}
          </div>

          <Stats signals={filtered} period={period} />

          {/* Table */}
          <div className="glass rounded-2xl">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border/30 text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">
              <button onClick={() => setSort('date')} className={`w-16 shrink-0 text-left hover:text-foreground transition-colors ${sort==='date'?'text-primary':''}`}>Fecha ↕</button>
              <span className="w-8 shrink-0" />
              <span className="flex-1 min-w-0">Ticker</span>
              <span className="w-24 shrink-0 hidden md:block">Sector</span>
              <button onClick={() => setSort('score')} className={`w-12 text-right shrink-0 hover:text-foreground transition-colors ${sort==='score'?'text-primary':''}`}>Score ↕</button>
              <span className="w-20 text-right shrink-0">Entrada</span>
              <button onClick={() => setSort('ret')} className={`w-16 text-right shrink-0 hover:text-foreground transition-colors ${sort==='ret'?'text-primary':''}`}>Ret {period} ↕</button>
              <span className="w-14 text-center shrink-0 hidden sm:block">Res.</span>
            </div>
            <div className="divide-y divide-border/10">
              {sorted.map((s, i) => {
                const ret = retOf(s, period)
                return (
                  <div key={i} className={`flex items-center gap-2 px-4 py-2.5 hover:bg-muted/10 transition-colors ${ret == null ? 'opacity-40' : ''}`}>
                    <span className="w-16 shrink-0 text-[0.7rem] text-muted-foreground/60 tabular-nums">{s.signal_date.slice(5)}</span>
                    <div className="w-8 shrink-0"><TickerLogo ticker={s.ticker} size="xs" /></div>
                    <div className="flex-1 min-w-0">
                      <span className="font-mono font-bold text-primary text-[0.85rem]">{s.ticker}</span>
                      {s.company_name && <span className="ml-2 text-[0.72rem] text-muted-foreground truncate hidden sm:inline">{s.company_name}</span>}
                    </div>
                    <span className="w-24 shrink-0 hidden md:block text-[0.7rem] text-muted-foreground truncate">{s.sector}</span>
                    <span className={`w-12 text-right shrink-0 text-[0.78rem] font-bold tabular-nums ${s.value_score != null && s.value_score >= 60 ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                      {s.value_score?.toFixed(0) ?? '—'}
                    </span>
                    <span className="w-20 text-right shrink-0 text-[0.75rem] text-muted-foreground tabular-nums">${s.signal_price.toFixed(2)}</span>
                    <span className={`w-16 text-right shrink-0 font-bold tabular-nums text-[0.85rem] ${ret == null ? 'text-muted-foreground/40' : ret >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {ret == null ? '—' : pct(ret)}
                    </span>
                    <span className="w-14 text-center shrink-0 hidden sm:block">
                      {ret != null
                        ? <span className={`text-[0.62rem] font-bold px-1.5 py-0.5 rounded ${ret > 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>{ret > 0 ? '↑ WIN' : '↓ LOSS'}</span>
                        : <span className="text-[0.62rem] text-muted-foreground/30">pend.</span>
                      }
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── MEAN REVERSION TAB ── */}
      {tab === 'mr' && (
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3.5 rounded-xl bg-teal-500/5 border border-teal-500/20">
            <ArrowLeftRight size={13} className="text-teal-400 mt-0.5 shrink-0" />
            <p className="text-xs text-muted-foreground">
              Setups actuales de Mean Reversion — acciones en sobreventa extrema con potencial de rebote.
              Estas señales no tienen historial de retornos todavía (el tracking empieza a añadirse al pipeline).
            </p>
          </div>

          <div className="glass rounded-2xl">
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border/30 text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">
              <span className="w-8 shrink-0" />
              <span className="flex-1 min-w-0">Ticker</span>
              <span className="w-24 shrink-0 hidden md:block">Estrategia</span>
              <span className="w-12 text-right shrink-0">RSI</span>
              <span className="w-16 text-right shrink-0">Caída</span>
              <span className="w-20 text-right shrink-0">Precio</span>
              <span className="w-20 text-right shrink-0">Target</span>
              <span className="w-16 text-right shrink-0">R:R</span>
              <span className="w-16 text-right shrink-0 hidden sm:block">Score</span>
            </div>
            <div className="divide-y divide-border/10">
              {mrSetups.sort((a,b) => b.reversion_score - a.reversion_score).map((m, i) => (
                <div key={i} className="flex items-center gap-2 px-4 py-2.5 hover:bg-muted/10 transition-colors">
                  <div className="w-8 shrink-0"><TickerLogo ticker={m.ticker} size="xs" /></div>
                  <div className="flex-1 min-w-0">
                    <span className="font-mono font-bold text-teal-400 text-[0.85rem]">{m.ticker}</span>
                    {m.company_name && <span className="ml-2 text-[0.72rem] text-muted-foreground truncate hidden sm:inline">{m.company_name}</span>}
                  </div>
                  <span className="w-24 shrink-0 hidden md:block text-[0.7rem] text-muted-foreground">{m.strategy}</span>
                  <span className={`w-12 text-right shrink-0 text-[0.78rem] font-bold tabular-nums ${(m.rsi??50) < 30 ? 'text-red-400' : (m.rsi??50) < 40 ? 'text-amber-400' : 'text-muted-foreground'}`}>
                    {m.rsi?.toFixed(0) ?? '—'}
                  </span>
                  <span className="w-16 text-right shrink-0 text-[0.78rem] font-bold text-red-400 tabular-nums">
                    {m.drawdown_pct != null ? `${m.drawdown_pct.toFixed(0)}%` : '—'}
                  </span>
                  <span className="w-20 text-right shrink-0 text-[0.78rem] tabular-nums text-muted-foreground">${m.current_price.toFixed(2)}</span>
                  <span className="w-20 text-right shrink-0 text-[0.78rem] tabular-nums text-emerald-400">${m.target.toFixed(2)}</span>
                  <span className={`w-16 text-right shrink-0 text-[0.78rem] font-bold tabular-nums ${m.risk_reward >= 2 ? 'text-emerald-400' : m.risk_reward >= 1 ? 'text-amber-400' : 'text-red-400'}`}>
                    {m.risk_reward.toFixed(1)}x
                  </span>
                  <span className="w-16 text-right shrink-0 hidden sm:block text-[0.78rem] font-bold text-teal-400 tabular-nums">
                    {m.reversion_score.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
