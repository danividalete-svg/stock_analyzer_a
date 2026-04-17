import { useState, useEffect, useCallback, useMemo } from 'react'
import api, { fetchOwnerEarningsBatch } from '../api/client'
import Loading, { ErrorState } from '../components/Loading'
import TickerLogo from '../components/TickerLogo'
import PaginationBar from '../components/PaginationBar'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table'
import { ArrowLeft, Calculator, ChevronDown, ChevronUp, RefreshCw, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { nlValuation } from '@/lib/nl'

// ── Types ────────────────────────────────────────────────────────────────────

interface FcfEntry { fcf: number; fcf_per_share: number; ebit_per_share?: number | null; projected?: boolean }
interface PriceTarget { ev_fcf?: number; per?: number; ev_ebitda?: number; ev_ebit?: number; average?: number }
interface FcfBreakdownRow {
  revenue?: number | null
  ebitda?: number | null; ebitda_margin?: number | null
  dna?: number | null
  ebit?: number | null; ebit_margin?: number | null
  interest?: number | null; interest_src?: string
  income_tax?: number | null; tax_src?: string
  pre_tax_income?: number | null
  net_income?: number | null; net_margin?: number | null
  delta_wc?: number | null; wc_src?: string
  cfo?: number | null
  capex?: number | null; capex_maint?: number | null
  template_fcf?: number | null
  owner_earnings?: number | null
  source?: string
}

interface ForwardEstimate { eps_norm?: number | null; ebitda?: number | null; revenue?: number | null; ebit?: number | null }

interface OeResult {
  ticker: string
  company_name?: string
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
  da_pct_sales_median?: number
  historical_fcf: Record<string, number>
  historical_fcf_per_share: Record<string, number>
  historical_multiples: Record<string, { price?: number; mc?: number; ev?: number; ev_fcf?: number; ev_ebitda?: number; ev_ebit?: number; pe?: number; fcf_yield?: number }>
  fcf_breakdown: Record<string, FcfBreakdownRow>
  forward_fcf: Record<string, FcfEntry>
  forward_net_debt: Record<string, number>
  forward_shares: Record<string, number>
  forward_estimates: Record<string, ForwardEstimate>
  price_targets: Record<string, PriceTarget>
  error?: string
}

// ── Local price-target recomputation (mirrors owner_earnings.py logic) ────────

interface ComputedTargets {
  priceTargets: Record<string, PriceTarget>
  exitPrice: number | null
  buyPrice: number | null
  upsidePct: number | null
  signal: string
}

function recompute(
  data: OeResult,
  evFcfT: number,
  perT: number,
  evEbitdaT: number,
  evEbitT: number,
  ebitFracOfEbitda: number,
  returnT: number,
): ComputedTargets {
  const fwdYears = Object.keys(data.forward_fcf).sort()
  if (fwdYears.length === 0) return { priceTargets: {}, exitPrice: null, buyPrice: null, upsidePct: null, signal: 'NO_DATA' }

  const priceTargets: Record<string, PriceTarget> = {}

  for (const yr of fwdYears) {
    const fwd = data.forward_fcf[yr]
    const nd  = data.forward_net_debt[yr] ?? 0
    const sh  = data.forward_shares?.[yr] ?? 1
    const est = data.forward_estimates?.[yr] ?? {}
    const ndPs = sh > 0 ? nd / sh : 0
    const targets: PriceTarget = {}

    const evFcfPrice = fwd.fcf_per_share * evFcfT - ndPs
    if (evFcfPrice > 0) targets.ev_fcf = Math.round(evFcfPrice * 100) / 100

    const eps = est.eps_norm
    if (eps && eps > 0) targets.per = Math.round(eps * perT * 100) / 100

    const ebitda = est.ebitda
    if (ebitda && sh > 0) {
      const mc = ebitda * evEbitdaT - nd
      if (mc > 0) targets.ev_ebitda = Math.round(mc / sh * 100) / 100
    }

    // EV/EBIT — use fwd model ebit_per_share if available; else derive from EBITDA × ebitFrac
    const ebitPs = fwd.ebit_per_share != null
      ? fwd.ebit_per_share
      : (ebitda && sh > 0 && ebitFracOfEbitda > 0 ? ebitda * ebitFracOfEbitda / sh : null)
    if (ebitPs && ebitPs > 0) {
      const evEbitPrice = ebitPs * evEbitT - ndPs
      if (evEbitPrice > 0) targets.ev_ebit = Math.round(evEbitPrice * 100) / 100
    }

    const valid = Object.values(targets).filter((v): v is number => v != null && v > 0)
    if (valid.length) targets.average = Math.round(valid.reduce((a, b) => a + b, 0) / valid.length * 100) / 100

    priceTargets[yr] = targets
  }

  const exitYr = fwdYears[fwdYears.length - 1]
  const exitP  = priceTargets[exitYr]?.ev_fcf ?? priceTargets[exitYr]?.average ?? null
  const yearsToExit = Math.max(1, Math.min(parseInt(exitYr) - (data.exit_year! - data.years_to_exit!), 10))
  const buyP = exitP && exitP > 0 ? Math.round(exitP / Math.pow(1 + returnT / 100, yearsToExit) * 100) / 100 : null

  const upside = buyP && data.current_price && data.current_price > 0
    ? Math.round((buyP / data.current_price - 1) * 1000) / 10
    : null

  const sig = upside == null ? 'NO_DATA' : upside >= 15 ? 'BUY' : upside >= 0 ? 'WATCH' : upside >= -15 ? 'HOLD' : 'OVERVALUED'

  return { priceTargets, exitPrice: exitP, buyPrice: buyP, upsidePct: upside, signal: sig }
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
void SIGNAL_ORDER // used by sort in BatchView via sortKey comparators

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

// ── Stepper input with TIKR reference ─────────────────────────────────────────

function StepperInput({
  label, value, onChange, tikrRef, suffix = 'x', step = 0.5, min = 1, max = 100,
}: {
  label: string; value: number; onChange: (v: number) => void
  tikrRef?: number | null; suffix?: string; step?: number; min?: number; max?: number
}) {
  const dec = step < 1 ? 1 : 0
  const clamp = (v: number) => Math.max(min, Math.min(max, parseFloat(v.toFixed(dec))))
  const adj = (delta: number) => onChange(clamp(parseFloat((value + delta).toFixed(dec))))
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[0.55rem] uppercase tracking-widest text-muted-foreground/50 font-semibold leading-none">{label}</span>
      {tikrRef != null && (
        <span className="text-[0.5rem] text-muted-foreground/35 leading-none">
          TIKR: <span className="font-mono text-muted-foreground/55">{tikrRef.toFixed(dec)}{suffix}</span>
        </span>
      )}
      <div className="flex items-center gap-0.5 mt-0.5">
        <button onClick={() => adj(-step)}
          className="w-5 h-5 rounded bg-white/5 hover:bg-amber-500/15 border border-white/10 hover:border-amber-500/30 text-muted-foreground hover:text-amber-400 flex items-center justify-center text-[0.6rem] transition-colors">▼</button>
        <span className="w-14 text-center font-bold tabular-nums text-sm text-amber-400">{value.toFixed(dec)}{suffix}</span>
        <button onClick={() => adj(+step)}
          className="w-5 h-5 rounded bg-white/5 hover:bg-amber-500/15 border border-white/10 hover:border-amber-500/30 text-muted-foreground hover:text-amber-400 flex items-center justify-center text-[0.6rem] transition-colors">▲</button>
      </div>
    </div>
  )
}

// ── Orange editable cell (forward assumptions) ─────────────────────────────────

function OrangeCell({
  value, onChange, suffix = '%', step = 0.5, min = -50, max = 100,
}: {
  value: number; onChange: (v: number) => void
  suffix?: string; step?: number; min?: number; max?: number
}) {
  const dec = step < 1 ? 1 : 0
  const clamp = (v: number) => Math.max(min, Math.min(max, parseFloat(v.toFixed(dec))))
  const adj = (delta: number) => onChange(clamp(parseFloat((value + delta).toFixed(dec))))
  return (
    <div className="flex items-center justify-center gap-0.5">
      <button onClick={() => adj(-step)}
        className="w-4 h-4 rounded bg-orange-500/10 hover:bg-orange-500/25 border border-orange-500/20 text-orange-400/60 hover:text-orange-400 flex items-center justify-center text-[0.5rem] transition-colors">▼</button>
      <span className="w-12 text-center font-bold tabular-nums text-[0.72rem] text-orange-400">{value.toFixed(dec)}{suffix}</span>
      <button onClick={() => adj(+step)}
        className="w-4 h-4 rounded bg-orange-500/10 hover:bg-orange-500/25 border border-orange-500/20 text-orange-400/60 hover:text-orange-400 flex items-center justify-center text-[0.5rem] transition-colors">▲</button>
    </div>
  )
}

// ── Forward model helpers ──────────────────────────────────────────────────────

interface FwdYearInput {
  rev_growth_pct: number
  ebit_margin_pct: number
  tax_rate_pct: number
  capex_pct: number  // single median applied all years; user can override per-year
  wc_pct: number
  interest_m: number
}

function _arrMedian(nums: number[]): number {
  if (!nums.length) return 0
  const s = [...nums].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

// Inicializa los inputs del modelo propio igual que la plantilla:
//   - Revenue growth %: por año desde TIKR (estimaciones consenso)
//   - EBIT margin %: por año desde TIKR
//   - Tax rate %: MEDIANA HISTÓRICA (no derivación algebraica) — igual que plantilla celdas L17:P17
//   - CapEx %: mediana histórica única aplicada todos los años — igual que plantilla celda L22
//   - WC %: 0 por defecto — igual que plantilla celda L23
//   - Interest $M: mediana histórica — igual que plantilla
// El FCF calculado diferirá del TIKR non-GAAP — esto es correcto e intencional (igual que la plantilla).
function initFwdInputs(data: OeResult, fwdYears: string[]): Record<string, FwdYearInput> {
  const sortedYrs = [...fwdYears].sort()

  // Historical data — últimos 5 años
  const brows = Object.entries(data.fcf_breakdown ?? {})
    .sort(([a], [b]) => a.localeCompare(b)).slice(-5).map(([, b]) => b).filter(Boolean)

  // Mediana histórica interest
  const medInterest = _arrMedian(brows.filter(b => b.interest != null).map(b => b.interest as number)) || 0

  // CapEx: mediana histórica única (= plantilla celda L22)
  const capexPct = data.capex_pct_sales_median || 5

  // Tax rate: mediana histórica |income_tax| / max(1, ebit - interest)
  // = plantilla celdas L17:P17 por defecto ~ 24% para muchas empresas
  const taxRates = brows
    .filter(b => b.income_tax != null && b.ebit != null)
    .map(b => {
      const preTax = Math.max(1, (b.ebit as number) - (b.interest ?? 0))
      return Math.abs(b.income_tax as number) / preTax * 100
    })
    .filter(r => r >= 0 && r <= 60)
  const medTaxRate = taxRates.length > 0 ? Math.round(_arrMedian(taxRates) * 10) / 10 : 21

  // Last historical revenue for first-year growth calc
  const histRevs = brows.filter(b => b.revenue != null && (b.revenue as number) > 0).map(b => b.revenue as number)
  const lastHistRev = histRevs.length > 0 ? histRevs[histRevs.length - 1] : null

  const result: Record<string, FwdYearInput> = {}
  for (let i = 0; i < sortedYrs.length; i++) {
    const yr = sortedYrs[i]
    const est = data.forward_estimates?.[yr] ?? {}

    // Revenue growth from TIKR consensus
    const curRev = est.revenue ?? null
    const prevRev = i === 0 ? lastHistRev : (data.forward_estimates?.[sortedYrs[i - 1]]?.revenue ?? null)
    const revGrowth = curRev && prevRev && prevRev > 0
      ? Math.round((curRev / prevRev - 1) * 1000) / 10
      : 10

    // EBIT margin from TIKR consensus
    const ebitMargin = est.ebit != null && curRev && curRev > 0
      ? Math.round(est.ebit / curRev * 1000) / 10
      : 20

    result[yr] = {
      rev_growth_pct: revGrowth,
      ebit_margin_pct: ebitMargin,
      tax_rate_pct: medTaxRate,   // mediana histórica, igual para todos los años (= plantilla default)
      capex_pct: Math.round(capexPct * 10) / 10,  // mediana única (= plantilla celda L22)
      wc_pct: 0,                  // 0 por defecto (= plantilla celda L23)
      interest_m: Math.round(medInterest),
    }
  }
  return result
}

// computeFwdFromModel — sigue la lógica exacta de la plantilla:
//   - D&A forward = prev_DA × (1 + rev_growth%)  [plantilla hoja IS fila 8: =K8*(1+L4)]
//     NO un % fijo de ventas — crece proporcionalmente con el revenue
//   - daLastHist: último D&A histórico ($M) como punto de partida de la cadena
function computeFwdFromModel(
  data: OeResult,
  inputs: Record<string, FwdYearInput>,
  daLastHist: number,
): Record<string, FcfEntry> {
  const histYears = Object.keys(data.fcf_breakdown ?? {}).sort()
  const lastHist = histYears[histYears.length - 1]
  const lastRev = data.fcf_breakdown?.[lastHist]?.revenue ?? 0
  const fwdYears = Object.keys(inputs).sort()
  const result: Record<string, FcfEntry> = {}
  let prevRev = lastRev
  let prevDA  = daLastHist   // D&A crece con revenue igual que en la plantilla
  for (const yr of fwdYears) {
    const inp = inputs[yr]
    const shares = (data.forward_shares?.[yr] ?? 1)
    const rev = prevRev * (1 + inp.rev_growth_pct / 100)
    const ebit = rev * inp.ebit_margin_pct / 100
    // D&A: prev_DA × (1 + rev_growth%) — fórmula plantilla hoja 1.IS fila 8
    const da = prevDA * (1 + inp.rev_growth_pct / 100)
    const ebitda = ebit + da
    const capex = rev * inp.capex_pct / 100
    const deltaWc = -(rev - prevRev) * inp.wc_pct / 100
    const preTax = Math.max(0, ebit - inp.interest_m)
    const tax = preTax * inp.tax_rate_pct / 100
    const fcf = ebitda - capex - inp.interest_m - tax + deltaWc
    result[yr] = {
      fcf: Math.round(fcf * 10) / 10,
      fcf_per_share: shares > 0 ? Math.round(fcf / shares * 100) / 100 : 0,
      ebit_per_share: shares > 0 ? Math.round(ebit / shares * 100) / 100 : 0,
      projected: true,
    }
    prevRev = rev
    prevDA  = da
  }
  return result
}

// ── Detail view ───────────────────────────────────────────────────────────────

function DetailView({
  data, onBack, onRecalculate,
}: {
  data: OeResult
  onBack: () => void
  onRecalculate: (ret: number) => void
}) {
  const [evFcfT,   setEvFcfT]   = useState(data.ev_fcf_target)
  const [perT,     setPerT]     = useState(data.per_target)
  const [evEbT,    setEvEbT]    = useState(data.ev_ebitda_target)
  const [evEbitT,  setEvEbitT]  = useState(25)
  const [returnT,  setReturnT]  = useState(data.target_return_pct)
  const [apiPending, setApiPending] = useState(false)
  const [fwdMode, setFwdMode] = useState(false)
  const [activeTab, setActiveTab] = useState<'is' | 'fcf' | 'ratios' | 'valoracion' | 'detalle'>('is')
  const [fwdInputs, setFwdInputs] = useState<Record<string, FwdYearInput>>(() =>
    initFwdInputs(data, Object.keys(data.forward_fcf ?? {}).sort())
  )

  const setFwdField = (yr: string, field: keyof FwdYearInput, val: number) =>
    setFwdInputs(prev => ({ ...prev, [yr]: { ...prev[yr], [field]: val } }))

  // daLastHist: último D&A histórico en $M — punto de partida para la cadena D&A×(1+g) de la plantilla
  // ebitFracOfEbitda: para derivar EV/EBIT price target en recompute()
  const { daLastHist, ebitFracOfEbitda } = useMemo(() => {
    const brows = Object.entries(data.fcf_breakdown ?? {})
      .sort(([a], [b]) => a.localeCompare(b)).map(([, b]) => b).filter(Boolean)
    // Último D&A disponible (dna = EBITDA - EBIT en el breakdown)
    const daVals = brows.filter(b => b.dna != null && (b.dna as number) > 0)
    const lastDa = daVals.length > 0 ? (daVals[daVals.length - 1].dna as number) : 0
    // Si no hay dna en el breakdown, estimar desde da_pct_sales_median × último revenue
    const lastHistYear = Object.keys(data.fcf_breakdown ?? {}).sort().slice(-1)[0]
    const lastRev = data.fcf_breakdown?.[lastHistYear]?.revenue ?? 0
    const daFallback = lastRev > 0 && data.da_pct_sales_median
      ? lastRev * data.da_pct_sales_median / 100
      : 0
    const daLast = lastDa > 0 ? lastDa : daFallback

    const last5 = brows.slice(-5)
    const frac = _arrMedian(
      last5.filter(b => b.ebitda && b.ebit && (b.ebitda as number) !== 0)
        .map(b => (b.ebit as number) / (b.ebitda as number))
    ) || 0.6
    return { daLastHist: daLast, ebitFracOfEbitda: frac }
  }, [data.fcf_breakdown, data.da_pct_sales_median])

  // When in fwdMode, replace consensus FCF with locally-computed FCF
  const activeData = fwdMode
    ? { ...data, forward_fcf: computeFwdFromModel(data, fwdInputs, daLastHist) }
    : data

  // All price targets and buy price recomputed locally on every param change
  const computed = recompute(activeData, evFcfT, perT, evEbT, evEbitT, ebitFracOfEbitda, returnT)

  const bdownYears  = Object.keys(data.fcf_breakdown ?? {}).map(Number).sort((a, b) => b - a)
  const fwdYears    = Object.keys(data.forward_fcf).sort()
  const isProjected = fwdYears.length > 0 && data.forward_fcf[fwdYears[0]]?.projected === true

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
              <TickerLogo ticker={data.ticker} size="md" />
              <h2 className="text-2xl font-bold tracking-tight">{data.ticker}</h2>
              {data.company_name && <span className="text-sm text-muted-foreground truncate max-w-xs">{data.company_name}</span>}
              <SignalBadge signal={computed.signal} />
            </div>
            <p className="text-xs text-muted-foreground">
              Precio compra para <span className="text-foreground font-semibold">{returnT}%</span> anual · Salida {data.exit_year ?? '—'}E ({data.years_to_exit ?? '—'} años)
              {isProjected && <span className="ml-2 text-[0.6rem] text-amber-400/70 border border-amber-400/20 rounded px-1.5 py-0.5">estimaciones proyectadas ~</span>}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Precio actual</div>
              <div className="text-xl font-bold tabular-nums">{fmt(data.current_price, '$')}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Precio de compra</div>
              <div className={cn('text-xl font-bold tabular-nums', computed.signal === 'BUY' ? 'text-emerald-400' : '')}>
                {fmt(computed.buyPrice, '$')}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground uppercase tracking-widest mb-0.5">Margen seguridad</div>
              <div className={cn('text-xl font-bold tabular-nums', upsideColor(computed.upsidePct))}>
                {computed.upsidePct != null ? `${computed.upsidePct > 0 ? '+' : ''}${computed.upsidePct.toFixed(1)}%` : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {computed.buyPrice && data.current_price && computed.exitPrice && (
          <div className="mt-4">
            <div className="flex justify-between text-[0.65rem] text-muted-foreground mb-1">
              <span>Compra ${computed.buyPrice.toFixed(2)}</span>
              <span>Objetivo ${computed.exitPrice.toFixed(2)} ({data.exit_year}E)</span>
            </div>
            <div className="h-1.5 rounded-full bg-white/5 overflow-clip">
              <div
                className={cn('h-full rounded-full transition-all', computed.signal === 'BUY' ? 'bg-emerald-500' : computed.signal === 'WATCH' ? 'bg-amber-500' : computed.signal === 'HOLD' ? 'bg-sky-500' : 'bg-red-500')}
                style={{ width: `${Math.min(100, Math.max(2, (data.current_price / computed.exitPrice) * 100))}%` }}
              />
            </div>
          </div>
        )}

        {/* NL valuation narrative */}
        <p className="mt-3 text-[0.73rem] leading-relaxed text-muted-foreground/75 italic">
          {nlValuation({
            ticker:          data.ticker,
            current_price:   data.current_price ?? 0,
            intrinsic_value: computed.buyPrice,
            upside_pct:      computed.upsidePct,
            ev_fcf:          evFcfT,
            fcf_yield_pct:   data.ntm_fcf_yield_pct,
          })}
        </p>

        {/* Parameters — retorno + múltiplos de valoración */}
        <div className="mt-4 pt-4 border-t border-white/6 space-y-3">
          {/* Return slider */}
          <div className="flex items-center gap-3">
            <span className="text-[0.55rem] uppercase tracking-widest text-muted-foreground/50 font-semibold shrink-0">Retorno objetivo</span>
            <input type="range" min={8} max={25} step={1} value={returnT}
              onChange={e => setReturnT(Number(e.target.value))}
              className="flex-1 accent-cyan-400 h-1" />
            <span className="text-sm font-bold tabular-nums w-9 text-right text-cyan-400 shrink-0">{returnT}%</span>
            {returnT !== data.target_return_pct && !apiPending && (
              <button onClick={() => { setApiPending(true); onRecalculate(returnT) }}
                className="px-2.5 py-1 rounded-md bg-white/8 hover:bg-white/12 border border-white/10 text-xs text-muted-foreground transition-colors shrink-0">
                Actualizar FCF →
              </button>
            )}
          </div>

          {/* Múltiplos de valoración — stepper con referencia TIKR */}
          <div>
            <p className="text-[0.55rem] uppercase tracking-widest text-muted-foreground/40 font-semibold mb-2">
              Múltiplos de valoración objetivo
              <span className="ml-2 text-[0.5rem] text-muted-foreground/30 normal-case tracking-normal">(TIKR = mediana histórica / consenso NTM)</span>
            </p>
            <div className="flex flex-wrap gap-5">
              <StepperInput label="EV/FCF"   value={evFcfT}  onChange={setEvFcfT}
                tikrRef={data.median_ev_fcf} suffix="x" step={0.5} min={5} max={80} />
              <StepperInput label="P/E"      value={perT}    onChange={setPerT}
                tikrRef={data.ntm_pe}        suffix="x" step={0.5} min={5} max={80} />
              <StepperInput label="EV/EBITDA" value={evEbT}  onChange={setEvEbT}
                tikrRef={data.ntm_ev_ebitda} suffix="x" step={0.5} min={3} max={50} />
              <StepperInput label="EV/EBIT"  value={evEbitT} onChange={setEvEbitT}
                suffix="x" step={0.5} min={3} max={80} />
            </div>
          </div>
        </div>
      </div>

      {/* Forward Model — orange editable assumptions */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <p className="text-xs font-semibold">Modelo forward</p>
          {/* Toggle: two explicit options, always visible */}
          <div className="flex rounded-md border border-border/30 overflow-clip text-[0.65rem] font-semibold">
            <button
              onClick={() => setFwdMode(false)}
              className={cn(
                'px-3 py-1 transition-colors',
                !fwdMode
                  ? 'bg-white/10 text-foreground'
                  : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-white/5'
              )}
            >
              Consenso TIKR
            </button>
            <button
              onClick={() => setFwdMode(true)}
              className={cn(
                'px-3 py-1 border-l border-border/30 transition-colors',
                fwdMode
                  ? 'bg-orange-500/20 text-orange-400'
                  : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-white/5'
              )}
            >
              Modelo propio
            </button>
          </div>
          {fwdMode && (
            <button onClick={() => setFwdInputs(initFwdInputs(data, Object.keys(data.forward_fcf ?? {}).sort()))}
              className="text-[0.6rem] text-muted-foreground/40 hover:text-muted-foreground transition-colors">
              ↺ reset
            </button>
          )}
          {fwdMode && (
            <span className="text-[0.6rem] text-orange-400/50 ml-auto">
              Casillas naranjas = supuestos editables
            </span>
          )}
        </div>

        {/* Consenso TIKR — read-only table of underlying data */}
        {!fwdMode && fwdYears.length > 0 && (
          <Card className={cn('overflow-clip', isProjected ? 'border border-amber-500/20 bg-amber-500/3' : 'border border-border/20')}>
            {isProjected && (
              <div className="px-3 py-2 border-b border-amber-500/20 text-[0.65rem] text-amber-400/80 flex items-center gap-2">
                <span className="font-bold">~ PROYECTADO</span>
                <span className="text-muted-foreground/60">Sin estimaciones de analistas en TIKR — FCF proyectado desde NTM × CAGR histórico. Datos pueden diferir del consenso real.</span>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-[0.7rem]">
                <thead>
                  <tr className="border-b border-border/20">
                    <th className="text-left px-3 py-2 text-muted-foreground/50 font-semibold uppercase tracking-wider w-36">Consenso TIKR</th>
                    {fwdYears.map(yr => (
                      <th key={yr} className="px-2 py-2 text-center text-muted-foreground/60 font-semibold">{yr}E</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/15">
                  {fwdYears.some(yr => data.forward_estimates?.[yr]?.revenue != null) && (
                    <tr className="hover:bg-white/2">
                      <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Revenue ($M)</td>
                      {fwdYears.map((yr, i) => {
                        const cur = data.forward_estimates?.[yr]?.revenue
                        const prev = i > 0 ? data.forward_estimates?.[fwdYears[i-1]]?.revenue : null
                        const growth = cur && prev && prev > 0 ? (cur / prev - 1) * 100 : null
                        return (
                          <td key={yr} className="px-2 py-1.5 text-center">
                            {cur != null
                              ? <span className="font-mono">{(cur / 1000).toFixed(1)}B{growth != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/50">{growth > 0 ? '+' : ''}{growth.toFixed(0)}%</span>}</span>
                              : <span className="text-muted-foreground/30">—</span>}
                          </td>
                        )
                      })}
                    </tr>
                  )}
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">EBITDA ($M)</td>
                    {fwdYears.map((yr, i) => {
                      const est = data.forward_estimates?.[yr]
                      const prev = i > 0 ? data.forward_estimates?.[fwdYears[i-1]]?.ebitda : null
                      const cur = est?.ebitda
                      const growth = cur && prev && prev > 0 ? (cur / prev - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center">
                          {cur != null
                            ? <span className="font-mono">{(cur / 1000).toFixed(1)}B{growth != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/50">{growth > 0 ? '+' : ''}{growth.toFixed(0)}%</span>}</span>
                            : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">FCF ($M)</td>
                    {fwdYears.map((yr, i) => {
                      const fcfM = data.forward_fcf[yr]?.fcf
                      const prevFcf = i > 0 ? data.forward_fcf[fwdYears[i-1]]?.fcf : null
                      const growth = fcfM && prevFcf && prevFcf > 0 ? (fcfM / prevFcf - 1) * 100 : null
                      const isProj = data.forward_fcf[yr]?.projected === true
                      return (
                        <td key={yr} className={cn('px-2 py-1.5 text-center', isProj && 'text-amber-400/70')}>
                          {fcfM != null
                            ? <span className="font-mono">{(fcfM / 1000).toFixed(1)}B{growth != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/50">{growth > 0 ? '+' : ''}{growth.toFixed(0)}%</span>}</span>
                            : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">FCF/sh</td>
                    {fwdYears.map((yr, i) => {
                      const fcfPs = data.forward_fcf[yr]?.fcf_per_share
                      const prevPs = i > 0 ? data.forward_fcf[fwdYears[i-1]]?.fcf_per_share : null
                      const growth = fcfPs && prevPs && prevPs > 0 ? (fcfPs / prevPs - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono text-cyan-400/80">
                          {fcfPs != null ? `$${fcfPs.toFixed(2)}${growth != null ? ` (${growth > 0 ? '+' : ''}${growth.toFixed(0)}%)` : ''}` : '—'}
                        </td>
                      )
                    })}
                  </tr>
                  {fwdYears.some(yr => data.forward_estimates?.[yr]?.eps_norm != null) && (
                    <tr className="hover:bg-white/2">
                      <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">EPS normalizado</td>
                      {fwdYears.map(yr => {
                        const eps = data.forward_estimates?.[yr]?.eps_norm
                        return (
                          <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/70">
                            {eps != null ? `$${eps.toFixed(2)}` : '—'}
                          </td>
                        )
                      })}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {fwdMode && fwdYears.length > 0 && (
          <Card className="border border-orange-500/15 bg-orange-500/3 overflow-clip">
            <div className="overflow-x-auto">
              <table className="w-full text-[0.7rem]">
                <thead>
                  <tr className="border-b border-orange-500/20">
                    <th className="text-left px-3 py-2 text-muted-foreground/50 font-semibold uppercase tracking-wider w-40">Supuesto</th>
                    {fwdYears.map(yr => (
                      <th key={yr} className="px-2 py-2 text-center text-muted-foreground/60 font-semibold">{yr}E</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Crec. Ingresos %</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.rev_growth_pct ?? 10}
                          onChange={v => setFwdField(yr, 'rev_growth_pct', v)} step={0.5} min={-30} max={50} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Margen EBIT %</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.ebit_margin_pct ?? 20}
                          onChange={v => setFwdField(yr, 'ebit_margin_pct', v)} step={0.5} min={0} max={80} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Tasa impositiva %</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.tax_rate_pct ?? 21}
                          onChange={v => setFwdField(yr, 'tax_rate_pct', v)} step={0.5} min={0} max={50} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">CapEx mant / Ventas %</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.capex_pct ?? 5}
                          onChange={v => setFwdField(yr, 'capex_pct', v)} step={0.5} min={0} max={40} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Capital Trabajo / Ventas %</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.wc_pct ?? 0}
                          onChange={v => setFwdField(yr, 'wc_pct', v)} step={0.5} min={-20} max={30} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Intereses ($M)</td>
                    {fwdYears.map(yr => (
                      <td key={yr} className="px-2 py-1 text-center">
                        <OrangeCell value={fwdInputs[yr]?.interest_m ?? 0}
                          onChange={v => setFwdField(yr, 'interest_m', v)} suffix="M" step={10} min={0} max={50000} />
                      </td>
                    ))}
                  </tr>
                  <tr className="bg-cyan-500/5 border-t border-cyan-500/20">
                    <td className="px-3 py-1.5 font-semibold text-cyan-400/80 whitespace-nowrap">FCF/sh (modelo)</td>
                    {fwdYears.map(yr => {
                      const localFcf = computeFwdFromModel(data, fwdInputs, daLastHist)
                      const fcfPs = localFcf[yr]?.fcf_per_share
                      const tikrPs = data.forward_fcf[yr]?.fcf_per_share
                      const diff = fcfPs != null && tikrPs != null ? ((fcfPs / tikrPs - 1) * 100) : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-bold tabular-nums text-cyan-400">
                          {fcfPs != null ? `$${fcfPs.toFixed(2)}` : '—'}
                          {diff != null && Math.abs(diff) > 0.5 && (
                            <span className={`ml-1 text-[0.55rem] ${diff > 0 ? 'text-emerald-400/60' : 'text-red-400/60'}`}>
                              {diff > 0 ? '+' : ''}{diff.toFixed(0)}%
                            </span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {/* ── Tabs: IS · FCF · Ratios · Valoración · Detalle ─────────────── */}
      <div className="flex gap-0 border-b border-border/30 overflow-x-auto">
        {([
          { id: 'is',         label: '1. IS',          show: bdownYears.length > 0 },
          { id: 'fcf',        label: '2. FCF',         show: bdownYears.length > 0 },
          { id: 'ratios',     label: '3. Ratios',      show: true },
          { id: 'valoracion', label: '4. Valoración',  show: true },
          { id: 'detalle',    label: '5. Detalle FCF', show: bdownYears.length > 0 },
        ] as const).filter(t => t.show).map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-2 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-muted-foreground/50 hover:text-muted-foreground hover:border-border/60'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── 1. Income Statement histórico ─────────────────────────────── */}
      {bdownYears.length > 0 && activeTab === 'is' && (
        <div>
          <p className="text-xs font-semibold mb-2">1. Income Statement</p>
          <Card className="glass overflow-clip">
            <div className="overflow-x-auto">
              <table className="w-full text-[0.7rem]">
                <thead>
                  <tr className="border-b border-border/30">
                    <th className="text-left px-3 py-2 text-muted-foreground/50 font-semibold uppercase tracking-wider w-44">(millones)</th>
                    {[...bdownYears].reverse().map(yr => (
                      <th key={yr} className="px-2 py-2 text-center text-muted-foreground/60 font-semibold">{yr}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/15">
                  {/* Revenue */}
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap font-medium">Revenue</td>
                    {[...bdownYears].reverse().map((yr, i, arr) => {
                      const b = data.fcf_breakdown?.[yr]
                      const prev = arr[i-1] ? data.fcf_breakdown?.[arr[i-1]] : null
                      const yoy = b?.revenue && prev?.revenue ? (b.revenue / prev.revenue - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono">
                          {b?.revenue != null ? <>{fmtM(b.revenue)}{yoy != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/40">{yoy > 0 ? '+' : ''}{yoy.toFixed(0)}%</span>}</> : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                  {/* EBITDA */}
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">EBITDA</td>
                    {[...bdownYears].reverse().map((yr, i, arr) => {
                      const b = data.fcf_breakdown?.[yr]
                      const prev = arr[i-1] ? data.fcf_breakdown?.[arr[i-1]] : null
                      const yoy = b?.ebitda && prev?.ebitda ? (b.ebitda / prev.ebitda - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono">
                          {b?.ebitda != null ? <>{fmtM(b.ebitda)}{b.ebitda_margin != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/40">{b.ebitda_margin.toFixed(0)}%</span>}{yoy != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/30">{yoy > 0 ? '+' : ''}{yoy.toFixed(0)}%</span>}</> : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                  {/* D&A */}
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 whitespace-nowrap pl-6">D&A</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/50">{b?.dna != null ? fmtM(b.dna) : <span className="text-muted-foreground/25">—</span>}</td>
                    })}
                  </tr>
                  {/* EBIT */}
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">EBIT</td>
                    {[...bdownYears].reverse().map((yr, i, arr) => {
                      const b = data.fcf_breakdown?.[yr]
                      const prev = arr[i-1] ? data.fcf_breakdown?.[arr[i-1]] : null
                      const yoy = b?.ebit && prev?.ebit ? (b.ebit / prev.ebit - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono">
                          {b?.ebit != null ? <>{fmtM(b.ebit)}{b.ebit_margin != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/40">{b.ebit_margin.toFixed(0)}%</span>}{yoy != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/30">{yoy > 0 ? '+' : ''}{yoy.toFixed(0)}%</span>}</> : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                  {/* Interest */}
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 whitespace-nowrap pl-6">Intereses</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-amber-400/70">{b?.interest != null ? fmtM(b.interest) : <span className="text-muted-foreground/25">—</span>}</td>
                    })}
                  </tr>
                  {/* Net Income */}
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70 whitespace-nowrap">Beneficio Neto</td>
                    {[...bdownYears].reverse().map((yr, i, arr) => {
                      const b = data.fcf_breakdown?.[yr]
                      const prev = arr[i-1] ? data.fcf_breakdown?.[arr[i-1]] : null
                      const yoy = b?.net_income && prev?.net_income ? (b.net_income / prev.net_income - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono">
                          {b?.net_income != null ? <>{fmtM(b.net_income)}{b.net_margin != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/40">{b.net_margin.toFixed(0)}%</span>}{yoy != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/30">{yoy > 0 ? '+' : ''}{yoy.toFixed(0)}%</span>}</> : <span className="text-muted-foreground/30">—</span>}
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* ── 2. FCF Statement histórico ────────────────────────────────── */}
      {bdownYears.length > 0 && activeTab === 'fcf' && (
        <div>
          <p className="text-xs font-semibold mb-2">2. Cash Flow — FCF = EBITDA − CapEx<sub>m</sub> − Interés − Impuestos + ΔCT</p>
          <Card className="glass overflow-clip">
            <div className="overflow-x-auto">
              <table className="w-full text-[0.7rem]">
                <thead>
                  <tr className="border-b border-border/30">
                    <th className="text-left px-3 py-2 text-muted-foreground/50 font-semibold uppercase tracking-wider w-44">(millones)</th>
                    {[...bdownYears].reverse().map(yr => (
                      <th key={yr} className="px-2 py-2 text-center text-muted-foreground/60 font-semibold">{yr}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/15">
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/70">EBITDA</td>
                    {[...bdownYears].reverse().map(yr => { const b = data.fcf_breakdown?.[yr]; return <td key={yr} className="px-2 py-1.5 text-center font-mono">{b?.ebitda != null ? fmtM(b.ebitda) : '—'}</td> })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">− CapEx mant.</td>
                    {[...bdownYears].reverse().map(yr => { const b = data.fcf_breakdown?.[yr]; return <td key={yr} className="px-2 py-1.5 text-center font-mono text-amber-400/70">{b?.capex_maint != null ? fmtM(b.capex_maint) : '—'}</td> })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">− Intereses</td>
                    {[...bdownYears].reverse().map(yr => { const b = data.fcf_breakdown?.[yr]; return <td key={yr} className="px-2 py-1.5 text-center font-mono text-amber-400/70">{b?.interest != null ? fmtM(b.interest) : '—'}</td> })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">− Impuestos</td>
                    {[...bdownYears].reverse().map(yr => { const b = data.fcf_breakdown?.[yr]; return <td key={yr} className="px-2 py-1.5 text-center font-mono text-amber-400/70">{b?.income_tax != null ? fmtM(b.income_tax) : '—'}</td> })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">+ ΔCap. Trabajo</td>
                    {[...bdownYears].reverse().map(yr => { const b = data.fcf_breakdown?.[yr]; return <td key={yr} className="px-2 py-1.5 text-center font-mono text-sky-400/70">{b?.delta_wc != null ? fmtM(b.delta_wc) : '—'}</td> })}
                  </tr>
                  <tr className="hover:bg-white/2 border-t border-border/30">
                    <td className="px-3 py-1.5 font-semibold text-cyan-400">FCF</td>
                    {[...bdownYears].reverse().map((yr, i, arr) => {
                      const b = data.fcf_breakdown?.[yr]
                      const prev = arr[i-1] ? data.fcf_breakdown?.[arr[i-1]] : null
                      const fcf = b?.owner_earnings ?? b?.template_fcf
                      const prevFcf = prev?.owner_earnings ?? prev?.template_fcf
                      const yoy = fcf && prevFcf ? (fcf / prevFcf - 1) * 100 : null
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center font-mono font-semibold text-cyan-400">
                          {fcf != null ? <>{fmtM(fcf)}{yoy != null && <span className="ml-1 text-[0.55rem] text-muted-foreground/40 font-normal">{yoy > 0 ? '+' : ''}{yoy.toFixed(0)}%</span>}</> : '—'}
                        </td>
                      )
                    })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">FCF Margin %</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      const fcf = b?.owner_earnings ?? b?.template_fcf
                      const margin = fcf && b?.revenue ? fcf / b.revenue * 100 : null
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/60">{margin != null ? `${margin.toFixed(1)}%` : '—'}</td>
                    })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">FCF/share</td>
                    {[...bdownYears].reverse().map(yr => {
                      const fcfPs = data.historical_fcf_per_share?.[yr]
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-cyan-400/70">{fcfPs != null ? `$${fcfPs.toFixed(2)}` : '—'}</td>
                    })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">CapEx/Ventas</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      const ratio = b?.capex_maint && b?.revenue ? Math.abs(b.capex_maint) / b.revenue * 100 : null
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/50">{ratio != null ? `${ratio.toFixed(1)}%` : '—'}</td>
                    })}
                  </tr>
                  <tr className="hover:bg-white/2 bg-white/1">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6">Conversión EBITDA→FCF</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      const fcf = b?.owner_earnings ?? b?.template_fcf
                      const conv = fcf && b?.ebitda ? fcf / b.ebitda * 100 : null
                      return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/50">{conv != null ? `${conv.toFixed(0)}%` : '—'}</td>
                    })}
                  </tr>
                  <tr className="hover:bg-white/2">
                    <td className="px-3 py-1.5 text-muted-foreground/50 pl-6 text-[0.6rem]">Fuente</td>
                    {[...bdownYears].reverse().map(yr => {
                      const b = data.fcf_breakdown?.[yr]
                      return (
                        <td key={yr} className="px-2 py-1.5 text-center">
                          <span className={cn('text-[0.55rem] px-1 py-0.5 rounded font-medium',
                            b?.source === 'tikr_est'  ? 'bg-emerald-500/10 text-emerald-400' :
                            b?.source === 'cfo_based' ? 'bg-sky-500/10 text-sky-400' :
                            b?.source === 'template'  ? 'bg-amber-500/10 text-amber-400' :
                                                        'bg-muted/20 text-muted-foreground'
                          )}>
                            {b?.source === 'tikr_est' ? 'TIKR' : b?.source === 'cfo_based' ? 'CFO' : b?.source === 'template' ? 'Tmpl' : b?.source ?? '—'}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* ── 3. Múltiplos históricos ───────────────────────────────────── */}
      {activeTab === 'ratios' && (() => {
        const multYears = Object.keys(data.historical_multiples ?? {}).map(Number).sort((a, b) => a - b)
        const hasMultiples = multYears.length > 0

        // Mediana helpers
        const med = (vals: number[]) => {
          if (!vals.length) return null
          const s = [...vals].sort((a, b) => a - b)
          return s.length % 2 ? s[Math.floor(s.length / 2)] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
        }
        const medEvFcf   = med(multYears.map(y => data.historical_multiples[y]?.ev_fcf).filter((v): v is number => v != null))
        const medPe      = med(multYears.map(y => data.historical_multiples[y]?.pe).filter((v): v is number => v != null))
        const medEvEb    = med(multYears.map(y => data.historical_multiples[y]?.ev_ebitda).filter((v): v is number => v != null))
        const medEvEbit  = med(multYears.map(y => data.historical_multiples[y]?.ev_ebit).filter((v): v is number => v != null))
        const medFcfYld  = med(multYears.map(y => data.historical_multiples[y]?.fcf_yield).filter((v): v is number => v != null))

        return (
          <div className="space-y-4">
            <p className="text-xs font-semibold">3. Ratios de valoración históricos</p>

            {!hasMultiples && (
              <div className="glass rounded-xl p-5 border border-border/20 text-center text-xs text-muted-foreground/50">
                Sin datos de precios históricos — disponibles tras el próximo pipeline (TIKR price_close).
                <div className="mt-1 text-[0.6rem]">Mediana NTM actual: EV/FCF {data.median_ev_fcf?.toFixed(1)}x · P/E {data.ntm_pe?.toFixed(1)}x · EV/EBITDA {data.ntm_ev_ebitda?.toFixed(1)}x · FCF Yield {data.ntm_fcf_yield_pct?.toFixed(1)}%</div>
              </div>
            )}

            {hasMultiples && (
              <Card className="glass overflow-clip">
                <div className="overflow-x-auto">
                  <table className="w-full text-[0.7rem]">
                    <thead>
                      <tr className="border-b border-border/30">
                        <th className="text-left px-3 py-2 text-muted-foreground/50 font-semibold uppercase tracking-wider w-36">Ratio</th>
                        {multYears.map(yr => (
                          <th key={yr} className="px-2 py-2 text-center text-muted-foreground/60 font-semibold">{yr}</th>
                        ))}
                        <th className="px-2 py-2 text-center text-cyan-400/70 font-semibold text-[0.65rem] whitespace-nowrap">Mediana</th>
                        <th className="px-2 py-2 text-center text-amber-400/60 font-semibold text-[0.65rem] whitespace-nowrap">NTM actual</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/15">
                      {/* Precio cierre */}
                      <tr className="hover:bg-white/2 bg-white/1">
                        <td className="px-3 py-1.5 text-muted-foreground/50 text-[0.65rem]">Precio cierre</td>
                        {multYears.map(yr => {
                          const m = data.historical_multiples[yr]
                          return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/50">{m?.price != null ? `$${m.price.toFixed(2)}` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center text-muted-foreground/30">—</td>
                        <td className="px-2 py-1.5 text-center font-mono text-amber-400/70">{data.current_price != null ? `$${data.current_price.toFixed(2)}` : '—'}</td>
                      </tr>
                      {/* EV/FCF */}
                      <tr className="hover:bg-white/2">
                        <td className="px-3 py-1.5 text-muted-foreground/70 font-medium">EV/FCF</td>
                        {multYears.map(yr => {
                          const v = data.historical_multiples[yr]?.ev_fcf
                          const isHigh = v != null && medEvFcf != null && v > medEvFcf * 1.3
                          const isLow  = v != null && medEvFcf != null && v < medEvFcf * 0.7
                          return <td key={yr} className={cn('px-2 py-1.5 text-center font-mono', isHigh ? 'text-red-400/70' : isLow ? 'text-emerald-400/70' : 'text-cyan-400/80')}>{v != null ? `${v.toFixed(1)}x` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center font-semibold text-cyan-400">{medEvFcf != null ? `${medEvFcf.toFixed(1)}x` : '—'}</td>
                        <td className="px-2 py-1.5 text-center font-semibold text-amber-400/70">{data.median_ev_fcf != null ? `${data.median_ev_fcf.toFixed(1)}x` : '—'}</td>
                      </tr>
                      {/* P/E */}
                      <tr className="hover:bg-white/2">
                        <td className="px-3 py-1.5 text-muted-foreground/70">P/E</td>
                        {multYears.map(yr => {
                          const v = data.historical_multiples[yr]?.pe
                          return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/70">{v != null ? `${v.toFixed(1)}x` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center font-semibold text-muted-foreground/60">{medPe != null ? `${medPe.toFixed(1)}x` : '—'}</td>
                        <td className="px-2 py-1.5 text-center font-semibold text-amber-400/70">{data.ntm_pe != null ? `${data.ntm_pe.toFixed(1)}x` : '—'}</td>
                      </tr>
                      {/* EV/EBITDA */}
                      <tr className="hover:bg-white/2">
                        <td className="px-3 py-1.5 text-muted-foreground/70">EV/EBITDA</td>
                        {multYears.map(yr => {
                          const v = data.historical_multiples[yr]?.ev_ebitda
                          return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/70">{v != null ? `${v.toFixed(1)}x` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center font-semibold text-muted-foreground/60">{medEvEb != null ? `${medEvEb.toFixed(1)}x` : '—'}</td>
                        <td className="px-2 py-1.5 text-center font-semibold text-amber-400/70">{data.ntm_ev_ebitda != null ? `${data.ntm_ev_ebitda.toFixed(1)}x` : '—'}</td>
                      </tr>
                      {/* EV/EBIT */}
                      <tr className="hover:bg-white/2">
                        <td className="px-3 py-1.5 text-muted-foreground/70">EV/EBIT</td>
                        {multYears.map(yr => {
                          const v = data.historical_multiples[yr]?.ev_ebit
                          return <td key={yr} className="px-2 py-1.5 text-center font-mono text-muted-foreground/70">{v != null ? `${v.toFixed(1)}x` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center font-semibold text-muted-foreground/60">{medEvEbit != null ? `${medEvEbit.toFixed(1)}x` : '—'}</td>
                        <td className="px-2 py-1.5 text-center text-muted-foreground/30">—</td>
                      </tr>
                      {/* FCF Yield */}
                      <tr className="hover:bg-white/2">
                        <td className="px-3 py-1.5 text-muted-foreground/70">FCF Yield</td>
                        {multYears.map(yr => {
                          const v = data.historical_multiples[yr]?.fcf_yield
                          const isHigh = v != null && medFcfYld != null && v > medFcfYld * 1.3
                          return <td key={yr} className={cn('px-2 py-1.5 text-center font-mono', isHigh ? 'text-emerald-400/70' : 'text-muted-foreground/60')}>{v != null ? `${v.toFixed(1)}%` : '—'}</td>
                        })}
                        <td className="px-2 py-1.5 text-center font-semibold text-muted-foreground/60">{medFcfYld != null ? `${medFcfYld.toFixed(1)}%` : '—'}</td>
                        <td className="px-2 py-1.5 text-center font-semibold text-amber-400/70">{data.ntm_fcf_yield_pct != null ? `${data.ntm_fcf_yield_pct.toFixed(1)}%` : '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )
      })()}

      {/* ── 4. Precio objetivo por múltiplo ──────────────────────────── */}
      {activeTab === 'valoracion' && Object.keys(computed.priceTargets).length > 0 && (
        <div>
          <p className="text-xs font-semibold mb-2">4. Precio objetivo por múltiplo</p>
          <Card className="glass overflow-clip">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-border/30">
                  <TableHead className="w-28">Año</TableHead>
                  <TableHead className="text-right text-cyan-400/70">EV/FCF <span className="text-muted-foreground/40 font-normal text-[0.6rem]">({evFcfT}x)</span></TableHead>
                  <TableHead className="text-right text-muted-foreground/70">PER <span className="text-muted-foreground/40 font-normal text-[0.6rem]">({perT}x)</span></TableHead>
                  <TableHead className="text-right text-muted-foreground/70">EV/EBITDA <span className="text-muted-foreground/40 font-normal text-[0.6rem]">({evEbT}x)</span></TableHead>
                  <TableHead className="text-right text-muted-foreground/70">EV/EBIT <span className="text-muted-foreground/40 font-normal text-[0.6rem]">({evEbitT}x)</span></TableHead>
                  <TableHead className="text-right font-semibold">Promedio</TableHead>
                  <TableHead className="text-right text-muted-foreground/60">CAGR</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {fwdYears.map(yr => {
                  const pt = computed.priceTargets[yr]
                  if (!pt) return null
                  const avgP = pt.average
                  const isExit = Number(yr) === data.exit_year
                  const cagr = avgP && data.current_price && data.years_to_exit
                    ? (Math.pow(avgP / data.current_price, 1 / (Number(yr) - new Date().getFullYear())) - 1) * 100
                    : null
                  return (
                    <TableRow key={yr} className={cn(isExit && 'bg-cyan-500/5')}>
                      <TableCell className="font-medium">
                        {yr}E {isExit && <span className="ml-1 text-[0.6rem] text-cyan-400/70">← salida</span>}
                      </TableCell>
                      <TableCell className="text-right font-mono text-cyan-400">{fmt(pt.ev_fcf, '$')}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground/70">{fmt(pt.per, '$')}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground/70">{fmt(pt.ev_ebitda, '$')}</TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground/70">{fmt(pt.ev_ebit, '$')}</TableCell>
                      <TableCell className={cn('text-right font-semibold', isExit ? 'text-cyan-400' : '')}>{fmt(avgP, '$')}</TableCell>
                      <TableCell className={cn('text-right font-semibold', cagr == null ? 'text-muted-foreground' : cagr >= returnT ? 'text-emerald-400' : cagr >= 0 ? 'text-amber-400' : 'text-red-400')}>
                        {cagr != null ? `${cagr > 0 ? '+' : ''}${cagr.toFixed(1)}%` : '—'}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </Card>
          <p className="text-[0.6rem] text-muted-foreground/40 mt-1">
            Precio de compra para {returnT}% anual: <span className="text-cyan-400/70 font-semibold">{fmt(computed.buyPrice, '$')}</span>
            {computed.upsidePct != null && <span className={cn('ml-2', upsideColor(computed.upsidePct))}>{computed.upsidePct > 0 ? '+' : ''}{computed.upsidePct.toFixed(1)}% vs actual</span>}
          </p>
        </div>
      )}

      {/* FCF Breakdown — template style */}
      {activeTab === 'detalle' && <div>
        <p className="text-xs font-semibold mb-1.5">5. Desglose FCF detallado — fórmula plantilla</p>
          <p className="text-[0.65rem] text-muted-foreground mb-2">
            FCF = EBITDA − CapEx<sub>mant</sub> − Interés − Impuestos + ΔCT
            <span className="ml-2 opacity-50">· TIKR = dato real de TIKR Pro · CFO = CFO − CapEx<sub>mant</sub> · —  = no disponible en TIKR</span>
          </p>
          <Card className="glass">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-border/40">
                  <TableHead>Año</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                  <TableHead className="text-right">EBITDA</TableHead>
                  <TableHead className="text-right text-muted-foreground/70">D&A</TableHead>
                  <TableHead className="text-right">EBIT</TableHead>
                  <TableHead className="text-right text-amber-400/80">− Interés</TableHead>
                  <TableHead className="text-right text-amber-400/80">− Imptos</TableHead>
                  <TableHead className="text-right text-muted-foreground/70">NI</TableHead>
                  <TableHead className="text-right text-sky-400/80">ΔCT</TableHead>
                  <TableHead className="text-right text-muted-foreground/70">− CapEx<sub>m</sub></TableHead>
                  <TableHead className="text-right font-bold text-cyan-400/80">FCF</TableHead>
                  <TableHead className="text-right">Fuente</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...bdownYears].reverse().map(yr => {
                  const b = data.fcf_breakdown?.[yr]
                  if (!b) return null
                  return (
                    <TableRow key={yr}>
                      <TableCell className="font-medium">{yr}</TableCell>
                      <TableCell className="text-right">{fmtM(b.revenue)}</TableCell>
                      <TableCell className="text-right">
                        <span>{fmtM(b.ebitda)}</span>
                        {b.ebitda_margin != null && <span className="ml-1 text-[0.6rem] text-muted-foreground/50">{b.ebitda_margin.toFixed(0)}%</span>}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground/60">{fmtM(b.dna)}</TableCell>
                      <TableCell className="text-right">
                        <span>{fmtM(b.ebit)}</span>
                        {b.ebit_margin != null && <span className="ml-1 text-[0.6rem] text-muted-foreground/50">{b.ebit_margin.toFixed(0)}%</span>}
                      </TableCell>
                      <TableCell className={cn('text-right', b.interest == null ? 'text-muted-foreground/30' : 'text-amber-400')}>
                        {fmtM(b.interest)}
                      </TableCell>
                      <TableCell className={cn('text-right', b.income_tax == null ? 'text-muted-foreground/30' : 'text-amber-400')}>
                        {fmtM(b.income_tax)}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground/60">
                        <span>{fmtM(b.net_income)}</span>
                        {b.net_margin != null && <span className="ml-1 text-[0.6rem] text-muted-foreground/40">{b.net_margin.toFixed(0)}%</span>}
                      </TableCell>
                      <TableCell className={cn('text-right', b.delta_wc == null ? 'text-muted-foreground/30' : 'text-sky-400')}>
                        {b.delta_wc != null ? fmtM(b.delta_wc) : '—'}
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground/60">{fmtM(b.capex_maint)}</TableCell>
                      <TableCell className="text-right font-bold text-cyan-400">{fmtM(b.owner_earnings)}</TableCell>
                      <TableCell className="text-right">
                        <span className={cn('text-[0.6rem] px-1.5 py-0.5 rounded font-medium',
                          b.source === 'tikr_est'  ? 'bg-emerald-500/10 text-emerald-400' :
                          b.source === 'cfo_based' ? 'bg-sky-500/10 text-sky-400' :
                          b.source === 'template'  ? 'bg-amber-500/10 text-amber-400' :
                                                     'bg-muted/20 text-muted-foreground'
                        )}>
                          {b.source === 'tikr_est' ? 'TIKR' : b.source === 'cfo_based' ? 'CFO' : b.source === 'template' ? 'Tmpl' : b.source ?? '—'}
                        </span>
                      </TableCell>
                    </TableRow>
                  )
                })}
                {bdownYears.length === 0 && (
                  <TableRow><TableCell colSpan={12} className="text-center text-muted-foreground py-6">Sin datos históricos</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </Card>
      </div>}
    </div>
  )
}

// ── Batch view ────────────────────────────────────────────────────────────────

type SortKey = 'ticker' | 'upside_pct' | 'current_price' | 'buy_price' | 'median_ev_fcf' | 'ntm_fcf_yield_pct'

const PAGE_SIZE = 20

function UpsideBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-muted-foreground/40">—</span>
  const capped = Math.max(-100, Math.min(200, pct))
  const barPct = Math.abs(capped) / 2  // 200% max → 100% bar
  const isPos  = pct >= 0
  return (
    <div className="flex items-center gap-2 justify-end">
      <span className={cn('font-bold tabular-nums text-sm', upsideColor(pct))}>
        {pct > 0 ? '+' : ''}{pct.toFixed(1)}%
      </span>
      <div className="w-14 h-1.5 rounded-full bg-white/5 overflow-clip shrink-0">
        <div
          className={cn('h-full rounded-full transition-all', isPos ? 'bg-emerald-500/60' : 'bg-red-500/60')}
          style={{ width: `${Math.min(100, barPct)}%` }}
        />
      </div>
    </div>
  )
}

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
  const [page, setPage] = useState(1)

  const onSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(k); setSortDir('desc') }
    setPage(1)
  }

  // Reset to page 1 when filters/search change
  useEffect(() => { setPage(1) }, [filter, signalFilter])

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return null
    return sortDir === 'desc' ? <ChevronDown size={11} className="inline ml-0.5" /> : <ChevronUp size={11} className="inline ml-0.5" />
  }

  const filtered = results
    .filter(r => !r.error)
    .filter(r => {
      const q = filter.trim().toUpperCase()
      if (!q) return true
      return (
        r.ticker?.toUpperCase().includes(q) ||
        (r.company_name ?? '').toUpperCase().includes(q)
      )
    })
    .filter(r => signalFilter === 'ALL' || r.signal === signalFilter)
    .sort((a, b) => {
      if (sortKey === 'ticker') {
        return sortDir === 'asc' ? a.ticker.localeCompare(b.ticker) : b.ticker.localeCompare(a.ticker)
      }
      const av = (a[sortKey] as number | null) ?? (sortDir === 'asc' ? Infinity : -Infinity)
      const bv = (b[sortKey] as number | null) ?? (sortDir === 'asc' ? Infinity : -Infinity)
      return sortDir === 'asc' ? av - bv : bv - av
    })

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated  = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const start      = filtered.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const end        = Math.min(page * PAGE_SIZE, filtered.length)

  const counts = results.reduce<Record<string, number>>((acc, r) => {
    if (!r.error) { acc[r.signal] = (acc[r.signal] ?? 0) + 1 }
    return acc
  }, {})

  const thCls = (k: SortKey, left = false) => cn(
    'cursor-pointer select-none whitespace-nowrap hover:text-foreground transition-colors',
    left ? 'text-left' : 'text-right',
    sortKey === k ? 'text-primary' : 'text-muted-foreground/50'
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

        <div className="flex-1 min-w-[160px] max-w-[260px]">
          <label className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 font-semibold block mb-1.5">
            Buscar ticker o empresa
          </label>
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <Input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="MSFT, Microsoft, Visa…"
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

      {/* Results count + page info */}
      {filtered.length > 0 && (
        <div className="flex items-center justify-between px-1">
          <span className="text-xs text-muted-foreground/50">
            Mostrando <span className="text-muted-foreground font-semibold">{start}–{end}</span> de <span className="text-muted-foreground font-semibold">{filtered.length}</span> empresas
          </span>
          {totalPages > 1 && (
            <span className="text-xs text-muted-foreground/40">
              Página {page} / {totalPages}
            </span>
          )}
        </div>
      )}

      {/* Table */}
      <Card className="glass">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead onClick={() => onSort('ticker')} className={thCls('ticker', true)}>
                Ticker <SortIcon k="ticker" />
              </TableHead>
              <TableHead className="text-muted-foreground/40">Empresa</TableHead>
              <TableHead onClick={() => onSort('current_price')} className={thCls('current_price')}>
                Precio actual <SortIcon k="current_price" />
              </TableHead>
              <TableHead onClick={() => onSort('buy_price')} className={thCls('buy_price')}>
                Precio compra <SortIcon k="buy_price" />
              </TableHead>
              <TableHead onClick={() => onSort('upside_pct')} className={thCls('upside_pct')}>
                Margen seg. <SortIcon k="upside_pct" />
              </TableHead>
              <TableHead className="text-right">Señal</TableHead>
              <TableHead onClick={() => onSort('median_ev_fcf')} className={thCls('median_ev_fcf')}>
                EV/FCF med. <SortIcon k="median_ev_fcf" />
              </TableHead>
              <TableHead onClick={() => onSort('ntm_fcf_yield_pct')} className={thCls('ntm_fcf_yield_pct')}>
                FCF Yield NTM <SortIcon k="ntm_fcf_yield_pct" />
              </TableHead>
              <TableHead className="text-right text-muted-foreground/40">Salida</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginated.map(row => (
              <TableRow key={row.ticker} onClick={() => { onSelect(row); window.scrollTo({ top: 0, behavior: 'smooth' }) }} className="cursor-pointer">
                <TableCell>
                  <div className="flex items-center gap-2">
                    <TickerLogo ticker={row.ticker} size="sm" />
                    <span className="font-bold tracking-wide">{row.ticker}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground/60 max-w-[160px] truncate text-xs">
                  {row.company_name || '—'}
                </TableCell>
                <TableCell className="text-right tabular-nums">{fmt(row.current_price, '$')}</TableCell>
                <TableCell className="text-right font-semibold tabular-nums">{fmt(row.buy_price, '$')}</TableCell>
                <TableCell className="text-right">
                  <UpsideBar pct={row.upside_pct} />
                </TableCell>
                <TableCell className="text-right">
                  <SignalBadge signal={row.signal} />
                </TableCell>
                <TableCell className="text-right text-muted-foreground/70 tabular-nums">
                  {fmt(row.median_ev_fcf, '', 'x', 1)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground/70 tabular-nums">
                  {fmt(row.ntm_fcf_yield_pct, '', '%', 1)}
                </TableCell>
                <TableCell className="text-right text-muted-foreground/50 text-xs tabular-nums">
                  {row.exit_year ?? '—'}E
                </TableCell>
              </TableRow>
            ))}
            {filtered.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground py-10">
                  No hay resultados
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <PaginationBar page={page} totalPages={totalPages} onPage={setPage} />
      </Card>
    </div>
  )
}

// ── Batch return recomputation (client-side, no API call needed) ──────────────

function applyBatchReturn(batch: BatchResult, ret: number): BatchResult {
  return {
    ...batch,
    target_return_pct: ret,
    results: batch.results.map(row => {
      if (!row.exit_price || !row.years_to_exit || !row.current_price) return row
      const buyPrice = Math.round(row.exit_price / Math.pow(1 + ret / 100, row.years_to_exit) * 100) / 100
      const upsidePct = Math.round((buyPrice / row.current_price - 1) * 1000) / 10
      const signal = upsidePct >= 15 ? 'BUY' : upsidePct >= 0 ? 'WATCH' : upsidePct >= -20 ? 'HOLD' : 'OVERVALUED'
      return { ...row, buy_price: buyPrice, upside_pct: upsidePct, signal }
    }),
  }
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OwnerEarnings() {
  const [targetReturn, setTargetReturn] = useState(15)
  const [rawBatch, setRawBatch] = useState<BatchResult | null>(null)
  const [loadingBatch, setLoadingBatch] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [selected, setSelected] = useState<OeResult | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [pendingReturn, setPendingReturn] = useState(15) // slider value before apply
  // Derive displayed batch by applying current targetReturn locally — no API call on slider change
  const batchData = useMemo(
    () => rawBatch ? applyBatchReturn(rawBatch, targetReturn) : null,
    [rawBatch, targetReturn],
  )

  const fetchBatch = useCallback(async () => {
    setLoadingBatch(true)
    setBatchError(null)
    try {
      const res = await fetchOwnerEarningsBatch()
      setRawBatch(res.data as BatchResult)
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

  // Load batch once on mount — served from GitHub Pages (fast)
  useEffect(() => { fetchBatch() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleApplyReturn = () => {
    setTargetReturn(pendingReturn)
    // Batch recomputes via useMemo — no re-fetch needed
    if (selected) {
      fetchDetail(selected.ticker, pendingReturn)
    }
  }

  const handleSelectTicker = (row: OeResult) => {
    fetchDetail(row.ticker, targetReturn)
    setPendingReturn(targetReturn)
  }

  const handleBack = useCallback(() => {
    setSelected(null)
    setDetailError(null)
  }, [])

  // Push a history entry when entering detail so browser back returns to list
  useEffect(() => {
    if (selected) {
      window.history.pushState({ oeDetail: selected.ticker }, '')
    }
  }, [selected?.ticker]) // eslint-disable-line react-hooks/exhaustive-deps

  // Intercept browser back button while in detail view
  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      if (e.state?.oeDetail) return // navigating between details — ignore
      setSelected(null)
      setDetailError(null)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

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
          onClick={() => selected ? fetchDetail(selected.ticker, targetReturn) : fetchBatch()}
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
