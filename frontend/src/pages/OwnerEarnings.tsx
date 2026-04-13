import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Calculator, ChevronDown, ChevronUp, RefreshCw, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ────────────────────────────────────────────────────────────────────

interface FcfEntry { fcf: number; fcf_per_share: number }
interface PriceTarget { ev_fcf?: number; per?: number; ev_ebitda?: number; average?: number }

interface OeResult {
  ticker: string
  current_price: number | null
  buy_price: number | null
  exit_price: number | null
  exit_year: number | null
  years_to_exit: number | null
  upside_pct: number | null
  safety_margin_pct: number | null
  signal: string
  target_return_pct: number
  median_ev_fcf: number
  ev_fcf_target: number
  per_target: number
  ev_ebitda_target: number
  ntm_fcf_yield_pct: number | null
  ntm_pe: number | null
  ntm_ev_ebitda: number | null
  capex_pct_sales_median: number
  historical_fcf: Record<string, number>
  historical_fcf_per_share: Record<string, number>
  forward_fcf: Record<string, FcfEntry>
  forward_net_debt: Record<string, number>
  price_targets: Record<string, PriceTarget>
  error?: string
}

interface BatchResult {
  target_return_pct: number
  total: number
  results: Array<OeResult & { ticker: string }>
}

// ── Signal helpers ────────────────────────────────────────────────────────────

const SIGNAL_COLORS: Record<string, string> = {
  BUY:        'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  WATCH:      'bg-amber-500/15 text-amber-400 border-amber-500/30',
  HOLD:       'bg-sky-500/15 text-sky-400 border-sky-500/30',
  OVERVALUED: 'bg-red-500/15 text-red-400 border-red-500/30',
  NO_DATA:    'bg-muted/20 text-muted-foreground border-border/30',
}

const SIGNAL_ORDER: Record<string, number> = { BUY: 0, WATCH: 1, HOLD: 2, OVERVALUED: 3, NO_DATA: 4 }

function SignalBadge({ signal }: { signal: string }) {
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md text-[0.65rem] font-bold uppercase tracking-wider border', SIGNAL_COLORS[signal] ?? SIGNAL_COLORS.NO_DATA)}>
      {signal.replace('_', ' ')}
    </span>
  )
}

function fmt(v: number | null | undefined, prefix = '', suffix = '', decimals = 2): string {
  if (v == null) return '—'
  return `${prefix}${v.toFixed(decimals)}${suffix}`
}

function fmtM(v: number | null | undefined): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}B`
  return `$${v.toFixed(0)}M`
}

function upsideColor(pct: number | null) {
  if (pct == null) return 'text-muted-foreground'
  if (pct >= 15) return 'text-emerald-400'
  if (pct >= 0)  return 'text-amber-400'
  if (pct >= -20) return 'text-sky-400'
  return 'text-red-400'
}

// ── Detail view ───────────────────────────────────────────────────────────────

function DetailView({
  data, onBack, onRecalculate,
}: {
  data: OeResult
  onBack: () => void
  onRecalculate: (ret: number) => void
}) {
  const [localReturn, setLocalReturn] = useState(data.target_return_pct)
  const [pending, setPending] = useState(false)

  const histYears = Object.keys(data.historical_fcf).map(Number).sort((a, b) => b - a)
  const fwdYears  = Object.keys(data.forward_fcf).sort()

  const upside = data.upside_pct
  const signal = data.signal

  const handleReturnChange = (v: number) => {
    setLocalReturn(v)
    setPending(v !== data.target_return_pct)
  }

  return (
    <div className="space-y-5">
      {/* Back button */}
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft size={14} />
        Todas las empresas
      </button>

      {/* Hero card */}
      <div className="glass rounded-xl p-5 border border-white/8">
        <div className="flex flex-wrap items-start gap-4 justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-2xl font-bold tracking-tight">{data.ticker}</h2>
              <SignalBadge signal={signal} />
            </div>
            <p className="text-xs text-muted-foreground">
              Precio de compra para <span className="text-foreground font-semibold">{data.target_return_pct}%</span> anual · Salida {data.exit_year ?? '—'}E ({data.years_to_exit ?? '—'} años)
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            {/* Current price */}
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Precio actual</div>
              <div className="text-xl font-bold tabular-nums">{fmt(data.current_price, '$')}</div>
            </div>
            {/* Buy price */}
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Precio de compra</div>
              <div className={cn('text-xl font-bold tabular-nums', signal === 'BUY' ? 'text-emerald-400' : '')}>
                {fmt(data.buy_price, '$')}
              </div>
            </div>
            {/* Upside */}
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Margen seguridad</div>
              <div className={cn('text-xl font-bold tabular-nums', upsideColor(upside))}>
                {upside != null ? `${upside > 0 ? '+' : ''}${upside.toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Progress bar: current price vs buy price */}
        {data.buy_price && data.current_price && data.exit_price && (
          <div className="mt-4">
            <div className="flex justify-between text-[0.65rem] text-muted-foreground mb-1">
              <span>Precio compra ${data.buy_price.toFixed(2)}</span>
              <span>Objetivo ${data.exit_price.toFixed(2)} ({data.exit_year}E)</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/5 overflow-clip relative">
              <div
                className={cn('h-full rounded-full transition-all', signal === 'BUY' ? 'bg-emerald-500' : signal === 'WATCH' ? 'bg-amber-500' : signal === 'HOLD' ? 'bg-sky-500' : 'bg-red-500')}
                style={{ width: `${Math.min(100, Math.max(2, (data.current_price / data.exit_price) * 100))}%` }}
              />
            </div>
          </div>
        )}

        {/* Return slider inline */}
        <div className="mt-4 pt-4 border-t border-white/6 flex items-center gap-4">
          <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 font-semibold shrink-0">Retorno objetivo</span>
          <input
            type="range" min={8} max={25} step={1} value={localReturn}
            onChange={e => handleReturnChange(Number(e.target.value))}
            className="flex-1 accent-cyan-400 h-1"
          />
          <span className="text-sm font-bold tabular-nums w-10 text-right text-cyan-400 shrink-0">{localReturn}%</span>
          {pending && (
            <button
              onClick={() => { setPending(false); onRecalculate(localReturn) }}
              className="px-3 py-1 rounded-md bg-cyan-500 hover:bg-cyan-400 text-black text-xs font-bold transition-colors shrink-0"
            >
              Recalcular
            </button>
          )}
        </div>
      </div>

      {/* Multiples reference row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'EV/FCF mediana', value: fmt(data.median_ev_fcf, '', 'x', 1) },
          { label: 'EV/FCF objetivo', value: fmt(data.ev_fcf_target, '', 'x', 1) },
          { label: 'FCF Yield NTM', value: fmt(data.ntm_fcf_yield_pct, '', '%', 1) },
          { label: 'P/E NTM', value: fmt(data.ntm_pe, '', 'x', 1) },
          { label: 'EV/EBITDA NTM', value: fmt(data.ntm_ev_ebitda, '', 'x', 1) },
          { label: 'CapEx/Ventas med.', value: fmt(data.capex_pct_sales_median, '', '%', 1) },
        ].map(({ label, value }) => (
          <div key={label} className="glass rounded-lg p-3 border border-white/6">
            <div className="text-sm font-bold tabular-nums text-foreground/90">{value}</div>
            <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/50 mt-0.5 leading-tight">{label}</div>
          </div>
        ))}
      </div>

      {/* Tables row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* Historical FCF */}
        <div className="glass rounded-xl border border-white/8 overflow-clip">
          <div className="px-4 py-3 border-b border-white/6">
            <h3 className="text-sm font-semibold">Owner Earnings históricos</h3>
            <p className="text-[0.65rem] text-muted-foreground mt-0.5">FCF = CFO − CapEx mantenimiento (o /est actuals si disponibles)</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/6">
                  <th className="text-left px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">Año</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">FCF ($M)</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">FCF/acción</th>
                </tr>
              </thead>
              <tbody>
                {histYears.map(yr => {
                  const fcf = data.historical_fcf[yr]
                  const ps  = data.historical_fcf_per_share[yr]
                  return (
                    <tr key={yr} className="border-b border-white/4 last:border-0 hover:bg-white/3 transition-colors">
                      <td className="px-4 py-2 font-medium tabular-nums">{yr}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmtM(fcf)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmt(ps, '$')}</td>
                    </tr>
                  )
                })}
                {histYears.length === 0 && (
                  <tr><td colSpan={3} className="px-4 py-6 text-center text-muted-foreground text-sm">Sin datos históricos</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Price targets */}
        <div className="glass rounded-xl border border-white/8 overflow-clip">
          <div className="px-4 py-3 border-b border-white/6">
            <h3 className="text-sm font-semibold">Objetivos de precio por año</h3>
            <p className="text-[0.65rem] text-muted-foreground mt-0.5">
              Precio compra = objetivo_{data.exit_year}E ÷ (1 + {data.target_return_pct}%)^años
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/6">
                  <th className="text-left px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">Año</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">FCF/sh</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">EV/FCF</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">P/E</th>
                  <th className="text-right px-4 py-2 text-[0.65rem] uppercase tracking-widest text-muted-foreground/50 font-semibold">Promedio</th>
                </tr>
              </thead>
              <tbody>
                {fwdYears.map(yr => {
                  const fwd = data.forward_fcf[yr]
                  const pt  = data.price_targets[yr]
                  if (!fwd || !pt) return null
                  const isExit = String(data.exit_year) === yr
                  return (
                    <tr key={yr} className={cn('border-b border-white/4 last:border-0 hover:bg-white/3 transition-colors', isExit && 'bg-cyan-500/5')}>
                      <td className="px-4 py-2 font-medium tabular-nums">
                        {yr}E{isExit && <span className="ml-1 text-[0.6rem] text-cyan-400/70">←</span>}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground/70">{fmt(fwd.fcf_per_share, '$')}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{fmt(pt.ev_fcf, '$')}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground/70">{fmt(pt.per, '$')}</td>
                      <td className={cn('px-4 py-2 text-right tabular-nums font-semibold', isExit ? 'text-cyan-400' : '')}>{fmt(pt.average, '$')}</td>
                    </tr>
                  )
                })}
                {fwdYears.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground text-sm">Sin estimaciones forward</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Batch view ────────────────────────────────────────────────────────────────

type SortKey = 'ticker' | 'upside_pct' | 'current_price' | 'buy_price' | 'median_ev_fcf' | 'ntm_fcf_yield_pct'

function BatchView({
  results,
  onSelect,
  targetReturn,
  onTargetReturnChange,
}: {
  results: OeResult[]
  onSelect: (t: OeResult) => void
  targetReturn: number
  onTargetReturnChange: (v: number) => void
}) {
  const [sortKey, setSortKey] = useState<SortKey>('upside_pct')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [filter, setFilter] = useState('')
  const [signalFilter, setSignalFilter] = useState<string>('ALL')

  const onSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(k); setSortDir('desc') }
  }

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return null
    return sortDir === 'desc' ? <ChevronDown size={11} className="inline ml-0.5" /> : <ChevronUp size={11} className="inline ml-0.5" />
  }

  const filtered = results
    .filter(r => !r.error)
    .filter(r => !filter || r.ticker.includes(filter.toUpperCase()))
    .filter(r => signalFilter === 'ALL' || r.signal === signalFilter)
    .sort((a, b) => {
      if (sortKey === 'ticker') {
        return sortDir === 'asc' ? a.ticker.localeCompare(b.ticker) : b.ticker.localeCompare(a.ticker)
      }
      const av = (a[sortKey] as number | null) ?? (sortDir === 'asc' ? Infinity : -Infinity)
      const bv = (b[sortKey] as number | null) ?? (sortDir === 'asc' ? Infinity : -Infinity)
      return sortDir === 'asc' ? av - bv : bv - av
    })

  const counts = results.reduce<Record<string, number>>((acc, r) => {
    if (!r.error) { acc[r.signal] = (acc[r.signal] ?? 0) + 1 }
    return acc
  }, {})

  const thCls = (k: SortKey) => cn(
    'px-4 py-2.5 text-[0.6rem] uppercase tracking-widest font-semibold text-muted-foreground/50 cursor-pointer select-none whitespace-nowrap hover:text-muted-foreground transition-colors text-right',
    sortKey === k && 'text-primary'
  )

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="glass rounded-xl p-4 border border-white/8 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[160px]">
          <label className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 font-semibold block mb-1.5">
            Retorno anual objetivo
          </label>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={8}
              max={25}
              step={1}
              value={targetReturn}
              onChange={e => onTargetReturnChange(Number(e.target.value))}
              className="flex-1 accent-cyan-400 h-1"
            />
            <span className="text-sm font-bold tabular-nums w-10 text-right text-cyan-400">{targetReturn}%</span>
          </div>
        </div>

        <div className="flex-1 min-w-[140px] max-w-[220px]">
          <label className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 font-semibold block mb-1.5">
            Filtrar ticker
          </label>
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <Input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="MSFT, AAPL…"
              className="pl-7 h-8 text-sm bg-white/4 border-white/10"
            />
          </div>
        </div>

        {/* Signal pills */}
        <div className="flex flex-wrap gap-1.5">
          {(['ALL', 'BUY', 'WATCH', 'HOLD', 'OVERVALUED'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSignalFilter(s)}
              className={cn(
                'px-2.5 py-1 rounded-md text-[0.65rem] font-bold uppercase tracking-wider border transition-all',
                signalFilter === s
                  ? (s === 'ALL' ? 'bg-white/15 text-foreground border-white/20' : SIGNAL_COLORS[s])
                  : 'bg-transparent text-muted-foreground/50 border-border/20 hover:border-border/40 hover:text-muted-foreground'
              )}
            >
              {s === 'ALL' ? `Todas (${results.filter(r => !r.error).length})` : `${s} (${counts[s] ?? 0})`}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="glass rounded-xl border border-white/8 overflow-clip">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/8 bg-white/2">
                <th
                  onClick={() => onSort('ticker')}
                  className={cn(thCls('ticker'), 'text-left')}
                >
                  Ticker <SortIcon k="ticker" />
                </th>
                <th onClick={() => onSort('current_price')} className={thCls('current_price')}>
                  Precio actual <SortIcon k="current_price" />
                </th>
                <th onClick={() => onSort('buy_price')} className={thCls('buy_price')}>
                  Precio compra <SortIcon k="buy_price" />
                </th>
                <th onClick={() => onSort('upside_pct')} className={thCls('upside_pct')}>
                  Margen seg. <SortIcon k="upside_pct" />
                </th>
                <th className="px-4 py-2.5 text-[0.6rem] uppercase tracking-widest font-semibold text-muted-foreground/50 text-right">
                  Señal
                </th>
                <th onClick={() => onSort('median_ev_fcf')} className={thCls('median_ev_fcf')}>
                  EV/FCF med. <SortIcon k="median_ev_fcf" />
                </th>
                <th onClick={() => onSort('ntm_fcf_yield_pct')} className={thCls('ntm_fcf_yield_pct')}>
                  FCF Yield NTM <SortIcon k="ntm_fcf_yield_pct" />
                </th>
                <th className="px-4 py-2.5 text-[0.6rem] uppercase tracking-widest font-semibold text-muted-foreground/50 text-right">
                  Salida
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <tr
                  key={row.ticker}
                  onClick={() => onSelect(row)}
                  className="border-b border-white/4 last:border-0 hover:bg-white/4 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-bold text-foreground tracking-wide">{row.ticker}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{fmt(row.current_price, '$')}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-semibold">{fmt(row.buy_price, '$')}</td>
                  <td className={cn('px-4 py-3 text-right tabular-nums font-bold', upsideColor(row.upside_pct))}>
                    {row.upside_pct != null ? `${row.upside_pct > 0 ? '+' : ''}${row.upside_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <SignalBadge signal={row.signal} />
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground/70">
                    {fmt(row.median_ev_fcf, '', 'x', 1)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground/70">
                    {fmt(row.ntm_fcf_yield_pct, '', '%', 1)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground/50 text-xs">
                    {row.exit_year ?? '—'}E
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">
                    No hay resultados
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OwnerEarnings() {
  const [targetReturn, setTargetReturn] = useState(15)
  const [batchData, setBatchData] = useState<BatchResult | null>(null)
  const [loadingBatch, setLoadingBatch] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [selected, setSelected] = useState<OeResult | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [pendingReturn, setPendingReturn] = useState(15) // slider value before apply

  const fetchBatch = useCallback(async (ret: number) => {
    setLoadingBatch(true)
    setBatchError(null)
    try {
      const res = await api.get<BatchResult>(`/api/owner-earnings-batch?target_return=${ret / 100}`)
      setBatchData(res.data)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error al cargar datos'
      setBatchError(msg)
    } finally {
      setLoadingBatch(false)
    }
  }, [])

  const fetchDetail = useCallback(async (ticker: string, ret: number) => {
    setDetailLoading(true)
    setDetailError(null)
    try {
      const res = await api.get<OeResult>(`/api/owner-earnings/${ticker}?target_return=${ret / 100}`)
      setSelected(res.data)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error al cargar detalle'
      setDetailError(msg)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  // Load batch on mount
  useEffect(() => { fetchBatch(targetReturn) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleApplyReturn = () => {
    setTargetReturn(pendingReturn)
    if (selected) {
      fetchDetail(selected.ticker, pendingReturn)
    } else {
      fetchBatch(pendingReturn)
    }
  }

  const handleSelectTicker = (row: OeResult) => {
    fetchDetail(row.ticker, targetReturn)
    setPendingReturn(targetReturn)
  }

  const handleBack = () => {
    setSelected(null)
    setDetailError(null)
  }

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <Calculator size={18} className="text-cyan-400" />
            <h1 className="text-xl font-bold tracking-tight">Owner Earnings</h1>
          </div>
          <p className="text-xs text-muted-foreground">
            Modelo de valoración Buffett — precio de compra para retorno anual objetivo.
            FCF = CFO − CapEx mantenimiento. Datos TIKR Pro.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={() => selected ? fetchDetail(selected.ticker, targetReturn) : fetchBatch(targetReturn)}
          disabled={loadingBatch || detailLoading}
          className="gap-2 border-white/10 bg-white/4 hover:bg-white/8 text-xs"
        >
          <RefreshCw size={12} className={cn(loadingBatch || detailLoading ? 'animate-spin' : '')} />
          Actualizar
        </Button>
      </div>

      {/* Content */}
      {selected && renderDetail()}
      {!selected && renderBatch()}
    </div>
  )

  function renderDetail() {
    if (detailLoading) return <Loading />
    if (detailError)   return <ErrorState message={detailError} />
    if (!selected)     return null
    return <DetailView data={selected} onBack={handleBack} onRecalculate={ret => fetchDetail(selected.ticker, ret)} />
  }

  function renderBatch() {
    if (loadingBatch) return <Loading />
    if (batchError)   return <ErrorState message={batchError} />
    if (!batchData)   return null
    return (
      <>
        <BatchView
          results={batchData.results}
          onSelect={handleSelectTicker}
          targetReturn={pendingReturn}
          onTargetReturnChange={setPendingReturn}
        />
        {pendingReturn !== targetReturn && (
          <div className="fixed bottom-6 right-6 z-50">
            <Button
              onClick={handleApplyReturn}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-xl shadow-cyan-500/20 gap-2"
            >
              <RefreshCw size={13} />
              Recalcular con {pendingReturn}%
            </Button>
          </div>
        )}
      </>
    )
  }
}
