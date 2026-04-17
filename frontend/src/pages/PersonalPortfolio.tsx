import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, TrendingUp, TrendingDown, Wallet, AlertTriangle, X, Loader2, BookOpen, Send, Trash2, ChevronDown, ChevronUp, Zap, Brain, Pencil, Check } from 'lucide-react'
import { nlPositionStatus } from '@/lib/nl'
import { supabase } from '@/lib/supabase'
import { apiClient } from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import TickerLogo from '../components/TickerLogo'
import PriceChart from '../components/PriceChart'
import { useCerebroSignals, type CerebroMaps } from '../hooks/useCerebroSignals'
import { usePortfolioConfluence, type ConfluenceSignals } from '../hooks/usePortfolioConfluence'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Position {
  id: string
  ticker: string
  shares: number
  avg_price: number
  currency: 'USD' | 'EUR'
}

interface JournalEntry {
  id: string
  ticker: string
  note: string
  created_at: string
}

interface PositionResult {
  ticker: string
  company_name: string
  sector: string
  shares: number
  avg_price: number
  current_price: number
  currency: string
  market_value: number
  pl_pct: number
  pl_abs: number
  portfolio_pct: number
  forward_pe?: number
  analyst_target?: number
  analyst_upside?: number
  fcf_yield?: number
  dividend_yield?: number
  fifty_two_week_high?: number
  fifty_two_week_low?: number
  action: 'MANTENER' | 'AÑADIR' | 'REDUCIR' | 'VENDER'
  conviction: 'ALTA' | 'MEDIA' | 'BAJA'
  target_price?: number
  stop_loss?: number
  recommended_weight_pct: number
  analysis: string
  key_risk: string
  options_strategy?: string
  options_rationale?: string
  // Position sizing
  volatility_pct?: number
  kelly_pct?: number
  optimal_size_pct?: number
  stop_loss_atr?: number
  stop_loss_pct_atr?: number
  risk_amount?: number
  vol_multiplier?: number
}

interface RiskMetrics {
  total_risk_amount: number
  total_risk_pct: number
  kelly_base_pct: number
  oversized_positions: string[]
  win_rate_used: number
}

interface PortfolioAnalysis {
  summary?: string
  concentration_warning?: string | null
  overall_recommendation?: string
}

interface AnalysisResult {
  total_value: number
  risk_metrics?: RiskMetrics
  portfolio_analysis: PortfolioAnalysis
  positions: PositionResult[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const ACTION_STYLES: Record<string, string> = {
  MANTENER: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  AÑADIR:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  REDUCIR:  'bg-amber-500/15 text-amber-400 border-amber-500/25',
  VENDER:   'bg-red-500/15 text-red-400 border-red-500/25',
}

const ACTION_BAR: Record<string, string> = {
  AÑADIR:   'bg-emerald-500/60',
  MANTENER: 'bg-blue-500/60',
  REDUCIR:  'bg-amber-500/60',
  VENDER:   'bg-red-500/60',
}

const CONVICTION_DOT: Record<string, string> = {
  ALTA:  'bg-emerald-400',
  MEDIA: 'bg-amber-400',
  BAJA:  'bg-red-400',
}

// ── Journal Section ───────────────────────────────────────────────────────────

function JournalSection({ ticker, userId }: { ticker: string; userId: string }) {
  const [open,    setOpen]    = useState(false)
  const [notes,   setNotes]   = useState<JournalEntry[]>([])
  const [loaded,  setLoaded]  = useState(false)
  const [text,    setText]    = useState('')
  const [saving,  setSaving]  = useState(false)
  const [count,   setCount]   = useState<number | null>(null)

  // Load count eagerly so badge shows up even when collapsed
  useEffect(() => {
    supabase
      .from('trade_journal')
      .select('id', { count: 'exact', head: true })
      .eq('user_id', userId)
      .eq('ticker', ticker)
      .then(({ count: c }) => setCount(c ?? 0))
  }, [ticker, userId])

  const load = useCallback(async () => {
    const { data } = await supabase
      .from('trade_journal')
      .select('*')
      .eq('user_id', userId)
      .eq('ticker', ticker)
      .order('created_at', { ascending: false })
    setNotes((data ?? []) as JournalEntry[])
    setCount((data ?? []).length)
    setLoaded(true)
  }, [ticker, userId])

  const toggle = () => {
    if (!open && !loaded) load()
    setOpen(o => !o)
  }

  const addNote = async () => {
    const t = text.trim()
    if (!t) return
    setSaving(true)
    const { data } = await supabase
      .from('trade_journal')
      .insert({ user_id: userId, ticker, note: t })
      .select()
      .single()
    if (data) {
      setNotes(prev => [data as JournalEntry, ...prev])
      setCount(c => (c ?? 0) + 1)
    }
    setText('')
    setSaving(false)
  }

  const deleteNote = async (id: string) => {
    await supabase.from('trade_journal').delete().eq('id', id)
    setNotes(prev => prev.filter(n => n.id !== id))
    setCount(c => Math.max(0, (c ?? 1) - 1))
  }

  return (
    <div className="border-t border-border/20">
      <button
        onClick={toggle}
        className="w-full flex items-center gap-2 px-5 py-2.5 text-[0.72rem] text-muted-foreground hover:text-foreground transition-colors"
      >
        <BookOpen size={12} />
        <span className="font-semibold">Notas del journal</span>
        {count !== null && count > 0 && (
          <span className="px-1.5 py-0.5 rounded-full bg-primary/15 text-primary text-[0.6rem] font-bold">{count}</span>
        )}
        <span className="ml-auto">{open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
      </button>

      {open && (
        <div className="px-5 pb-4 space-y-3">
          {/* Add note */}
          <div className="flex gap-2 items-start">
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Añade una nota: razón de compra, tesis, eventos..."
              rows={2}
              className="flex-1 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50 resize-none"
            />
            <button
              onClick={addNote}
              disabled={saving || !text.trim()}
              className="p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-primary hover:bg-primary/20 transition-colors disabled:opacity-40"
              title="Guardar nota"
            >
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
            </button>
          </div>

          {/* Notes list */}
          {!loaded && <div className="flex justify-center py-2"><Loader2 size={14} className="animate-spin text-muted-foreground" /></div>}
          {loaded && notes.length === 0 && (
            <p className="text-[0.72rem] text-muted-foreground/50 text-center py-1">Sin notas todavía</p>
          )}
          {notes.map(n => (
            <div key={n.id} className="group flex gap-2 items-start px-4 py-3 rounded-xl bg-muted/20 border border-border/20">
              <div className="flex-1 min-w-0">
                <p className="text-[0.78rem] text-foreground/80 leading-relaxed whitespace-pre-wrap">{n.note}</p>
                <p className="text-[0.6rem] text-muted-foreground/50 mt-1">
                  {new Date(n.created_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
              <button
                onClick={() => deleteNote(n.id)}
                className="p-1 rounded text-muted-foreground/30 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Add Position Form ─────────────────────────────────────────────────────────

function AddForm({ onAdd, saving }: { onAdd: (p: Omit<Position, 'id'>) => Promise<void>; saving: boolean }) {
  const [ticker, setTicker]     = useState('')
  const [shares, setShares]     = useState('')
  const [price, setPrice]       = useState('')
  const [currency, setCurrency] = useState<'USD' | 'EUR'>('USD')
  const [error, setError]       = useState('')

  const submit = async () => {
    const t = ticker.trim().toUpperCase()
    const s = parseFloat(shares)
    const p = parseFloat(price)
    if (!t) return setError('Introduce el ticker')
    if (!s || s <= 0) return setError('Acciones inválidas')
    if (!p || p <= 0) return setError('Precio inválido')
    setError('')
    await onAdd({ ticker: t, shares: s, avg_price: p, currency })
    setTicker(''); setShares(''); setPrice('')
  }

  return (
    <div className="glass rounded-2xl p-5">
      <h2 className="text-sm font-bold text-foreground mb-4 flex items-center gap-2">
        <Plus size={14} className="text-primary" />
        Añadir posición
      </h2>
      <div className="flex flex-col sm:flex-row flex-wrap gap-2 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Ticker</label>
          <input
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="AAPL"
            className="w-24 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm font-mono font-bold text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Acciones</label>
          <input
            value={shares}
            onChange={e => setShares(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="100"
            type="number"
            min="0"
            className="w-24 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Precio medio</label>
          <input
            value={price}
            onChange={e => setPrice(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="150.00"
            type="number"
            min="0"
            step="0.01"
            className="w-28 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/50"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground">Moneda</label>
          <select
            value={currency}
            onChange={e => setCurrency(e.target.value as 'USD' | 'EUR')}
            className="px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-sm text-foreground focus:outline-none focus:border-primary/50"
          >
            <option value="USD">USD $</option>
            <option value="EUR">EUR €</option>
          </select>
        </div>
        <button
          onClick={submit}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 active:scale-[0.98] transition-all disabled:opacity-50"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} strokeWidth={2.5} />}
          Añadir
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </div>
  )
}

// ── Options Panel ─────────────────────────────────────────────────────────────

const STRAT_META: Record<string, { label: string; color: string; bg: string; border: string }> = {
  COVERED_CALL:      { label: 'Covered Call',       color: 'text-amber-400',   bg: 'bg-amber-500/8',   border: 'border-amber-500/20' },
  PROTECTIVE_PUT:    { label: 'Protective Put',      color: 'text-blue-400',    bg: 'bg-blue-500/8',    border: 'border-blue-500/20' },
  COLLAR:            { label: 'Collar',              color: 'text-purple-400',  bg: 'bg-purple-500/8',  border: 'border-purple-500/20' },
  BUY_MORE:          { label: 'Añadir posición',     color: 'text-emerald-400', bg: 'bg-emerald-500/8', border: 'border-emerald-500/20' },
  CASH_SECURED_PUT:  { label: 'Cash-Secured Put',   color: 'text-cyan-400',    bg: 'bg-cyan-500/8',    border: 'border-cyan-500/20' },
  TRAILING_STOP:     { label: 'Trailing Stop',       color: 'text-amber-400',   bg: 'bg-amber-500/8',   border: 'border-amber-500/20' },
  HOLD:              { label: 'Mantener',            color: 'text-primary',     bg: 'bg-primary/8',     border: 'border-primary/20' },
  SELL:              { label: 'Cerrar posición',     color: 'text-red-400',     bg: 'bg-red-500/8',     border: 'border-red-500/20' },
}

interface OptionsChainData {
  ticker: string
  current_price: number
  expiries: Array<{
    expiry: string
    days_out: number
    bucket: string
    covered_calls: Array<{ strike: number; bid: number; ask: number; mid: number; volume: number; open_interest: number; iv: number; pct_otm: number; annual_yield_pct: number }>
    protective_puts: Array<{ strike: number; bid: number; ask: number; mid: number; volume: number; open_interest: number; iv: number; pct_otm: number; cost_pct: number }>
  }>
  ai_recommendation: {
    recommended_strategy: string
    thesis_alignment?: string
    primary_contract: {
      action?: string; type: string; strike: number; expiry: string
      premium_approx?: number; premium?: number; total_cost_100_shares?: number
      horizon?: string; rationale?: string; order_instructions?: string
    } | null
    secondary_contract: { type: string; strike: number; expiry: string; premium: number; rationale: string } | null
    expected_outcome?: string
    profit_if_target?: string
    loss_if_drops?: string
    scenario_bull?: string
    scenario_bear?: string
    max_risk?: string
    when_to_close?: string
    step_by_step?: string
  } | null
}

function OptionsPanel({ result, sym }: { result: PositionResult; sym: string }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<OptionsChainData | null>(null)
  const [err, setErr] = useState('')

  const meta = STRAT_META[result.options_strategy ?? ''] ?? STRAT_META['HOLD']

  const fetchChain = async () => {
    if (data) { setOpen(o => !o); return }
    setOpen(true)
    setLoading(true)
    setErr('')
    try {
      const params = new URLSearchParams({
        price:      String(result.current_price ?? 0),
        pl:         String(result.pl_pct ?? 0),
        upside:     String(result.analyst_upside ?? 0),
        action:     result.action,
        conviction: result.conviction,
        thesis:     result.analysis ?? '',
        key_risk:   result.key_risk ?? '',
      })
      const { data: json } = await apiClient.get(`/api/options-chain/${result.ticker}?${params}`)
      setData(json)
    } catch (e) {
      setErr('Error de red')
    }
    setLoading(false)
  }

  return (
    <div className="border-t border-border/20">
      {/* Header strip — always visible */}
      <div className={`mx-0 px-5 py-2.5 ${meta.bg} border-b ${meta.border}`}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Zap size={12} className={meta.color} />
            <span className="text-[0.55rem] font-bold uppercase tracking-widest text-muted-foreground/50">Estrategia IA</span>
            <span className={`text-[0.72rem] font-bold ${meta.color}`}>{meta.label}</span>
            {result.options_rationale && (
              <span className="text-[0.7rem] text-foreground/60 truncate hidden sm:block">{result.options_rationale}</span>
            )}
          </div>
          <button
            onClick={fetchChain}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[0.65rem] font-semibold border transition-all ${meta.border} ${meta.color} hover:${meta.bg}`}
          >
            {loading ? <Loader2 size={10} className="animate-spin" /> : <ChevronDown size={10} className={open ? 'rotate-180' : ''} />}
            {data ? (open ? 'Ocultar' : 'Ver contratos') : 'Ver contratos reales'}
          </button>
        </div>
        {result.options_rationale && (
          <p className="text-[0.7rem] text-foreground/60 mt-1 sm:hidden">{result.options_rationale}</p>
        )}
      </div>

      {/* Options chain detail */}
      {open && (
        <div className="px-5 py-4 space-y-4">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 size={13} className="animate-spin" /> Cargando cadena de opciones desde Yahoo Finance…
            </div>
          )}
          {err && (
            <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
              {err.includes('no tiene opciones') ? (
                <span>{err} — Las estrategias basadas en opciones no están disponibles para este activo. Consulta el análisis de la IA arriba.</span>
              ) : err}
            </div>
          )}

          {data && (
            <>
              {/* AI recommendation */}
              {data.ai_recommendation && (() => {
                const rec = data.ai_recommendation!
                const pc = rec.primary_contract
                const premium = pc?.premium_approx ?? pc?.premium ?? 0
                return (
                <div className={`p-3 rounded-xl ${meta.bg} border ${meta.border} space-y-2.5`}>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[0.55rem] font-bold uppercase tracking-widest text-muted-foreground/50">Recomendación IA</span>
                    <span className={`text-[0.72rem] font-bold ${meta.color}`}>{rec.recommended_strategy?.replace(/_/g, ' ')}</span>
                    {rec.thesis_alignment && (
                      <span className="text-[0.68rem] text-foreground/60 flex-1">— {rec.thesis_alignment}</span>
                    )}
                  </div>

                  {pc && (
                    <div className="p-3 rounded-lg bg-background/40 border border-primary/20 space-y-2">
                      {/* Contract header */}
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded ${pc.action === 'COMPRAR' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                          {pc.action ?? (rec.recommended_strategy?.includes('COVERED') ? 'VENDER' : 'COMPRAR')}
                        </span>
                        <span className="font-bold text-foreground text-lg">{pc.type?.toUpperCase()} ${pc.strike}</span>
                        <span className="text-muted-foreground text-sm">exp {pc.expiry}</span>
                        <span className="text-[0.65rem] text-muted-foreground/50 uppercase">{pc.horizon}</span>
                      </div>
                      {/* Key numbers */}
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[0.72rem]">
                        <div>
                          <div className="text-muted-foreground/50 text-[0.58rem] uppercase mb-0.5">Prima por contrato</div>
                          <div className={`font-bold text-sm ${meta.color}`}>{sym}{premium?.toFixed(2)}</div>
                        </div>
                        {pc.total_cost_100_shares != null && (
                          <div>
                            <div className="text-muted-foreground/50 text-[0.58rem] uppercase mb-0.5">Coste total (100 acc)</div>
                            <div className="font-bold text-sm text-foreground">{sym}{pc.total_cost_100_shares?.toFixed(0)}</div>
                          </div>
                        )}
                        {(rec.profit_if_target ?? rec.expected_outcome) && (
                          <div>
                            <div className="text-muted-foreground/50 text-[0.58rem] uppercase mb-0.5">Si acierta</div>
                            <div className="text-emerald-400/80 text-[0.7rem]">{rec.profit_if_target ?? rec.expected_outcome}</div>
                          </div>
                        )}
                      </div>
                      {/* Order instructions — the "para tontos" section */}
                      {pc.order_instructions && (
                        <div className="p-2 rounded-lg bg-primary/5 border border-primary/15 text-[0.72rem] text-foreground/80">
                          <div className="text-primary font-semibold text-[0.6rem] uppercase tracking-wide mb-1">Orden exacta en tu broker</div>
                          {pc.order_instructions}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Step by step */}
                  {rec.step_by_step && (
                    <div className="p-2 rounded-lg bg-blue-500/5 border border-blue-500/15 text-[0.72rem] text-foreground/70 leading-relaxed">
                      <div className="text-blue-400 font-semibold text-[0.6rem] uppercase tracking-wide mb-1">Paso a paso</div>
                      {rec.step_by_step}
                    </div>
                  )}

                  {pc?.rationale && (
                    <p className="text-[0.72rem] text-foreground/70 leading-relaxed border-l-2 border-primary/30 pl-2.5">
                      {pc.rationale}
                    </p>
                  )}

                  {/* Bull/Bear scenarios */}
                  <div className="grid grid-cols-2 gap-2 text-[0.68rem]">
                    {(rec.profit_if_target || rec.scenario_bull) && (
                      <div className="p-2 rounded-lg bg-emerald-500/8 border border-emerald-500/15">
                        <div className="text-emerald-400 font-semibold mb-0.5">Si sube al target</div>
                        <div className="text-foreground/60">{rec.profit_if_target || rec.scenario_bull}</div>
                      </div>
                    )}
                    {(rec.loss_if_drops || rec.scenario_bear) && (
                      <div className="p-2 rounded-lg bg-red-500/8 border border-red-500/15">
                        <div className="text-red-400 font-semibold mb-0.5">Si cae -15%</div>
                        <div className="text-foreground/60">{rec.loss_if_drops || rec.scenario_bear}</div>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[0.68rem] pt-1 border-t border-border/20">
                    {rec.max_risk && <div><span className="text-red-400 font-semibold">Riesgo máx: </span><span className="text-foreground/60">{rec.max_risk}</span></div>}
                    {rec.when_to_close && <div><span className="text-amber-400 font-semibold">Cuándo cerrar: </span><span className="text-foreground/60">{rec.when_to_close}</span></div>}
                  </div>
                </div>
                )
              })()}

              {/* Raw contracts per expiry */}
              {data.expiries.map(exp => (
                <div key={exp.expiry}>
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-2">
                    {exp.bucket === 'long' ? '🔵 LEAPS' : exp.bucket === 'medium' ? '🟡 Medio plazo' : '⚡ Corto plazo'} — {exp.expiry} · {exp.days_out} días
                  </div>

                  {exp.covered_calls.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[0.62rem] font-semibold text-amber-400 mb-1.5">Covered Calls disponibles</div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-[0.7rem] border-collapse">
                          <thead>
                            <tr className="border-b border-border/30">
                              {['Strike', 'Bid', 'Ask', 'Prima', '% OTM', 'Yield anual', 'Vol', 'IV%'].map(h => (
                                <th key={h} className="text-left py-1 px-2 text-muted-foreground/50 font-semibold whitespace-nowrap">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {exp.covered_calls.map((c, i) => (
                              <tr key={i} className="border-b border-border/10 hover:bg-muted/10">
                                <td className="py-1.5 px-2 font-bold text-foreground">{sym}{c.strike}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{sym}{c.bid}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{sym}{c.ask}</td>
                                <td className="py-1.5 px-2 font-bold text-amber-400">{sym}{c.mid}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">+{c.pct_otm}%</td>
                                <td className="py-1.5 px-2 font-bold text-emerald-400">{c.annual_yield_pct}%</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{c.volume.toLocaleString()}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{c.iv}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {exp.protective_puts.length > 0 && (
                    <div>
                      <div className="text-[0.62rem] font-semibold text-blue-400 mb-1.5">Protective Puts disponibles</div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-[0.7rem] border-collapse">
                          <thead>
                            <tr className="border-b border-border/30">
                              {['Strike', 'Bid', 'Ask', 'Prima', '% OTM', 'Coste %', 'Vol', 'IV%'].map(h => (
                                <th key={h} className="text-left py-1 px-2 text-muted-foreground/50 font-semibold whitespace-nowrap">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {exp.protective_puts.map((p, i) => (
                              <tr key={i} className="border-b border-border/10 hover:bg-muted/10">
                                <td className="py-1.5 px-2 font-bold text-foreground">{sym}{p.strike}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{sym}{p.bid}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{sym}{p.ask}</td>
                                <td className="py-1.5 px-2 font-bold text-blue-400">{sym}{p.mid}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">-{p.pct_otm}%</td>
                                <td className="py-1.5 px-2 text-red-400">{p.cost_pct}%</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{p.volume.toLocaleString()}</td>
                                <td className="py-1.5 px-2 text-muted-foreground">{p.iv}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Position Card ─────────────────────────────────────────────────────────────

function MetricChip({ label, value, valueClass = 'text-foreground' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[0.58rem] font-semibold uppercase tracking-wider text-muted-foreground/50 leading-none">{label}</span>
      <span className={`text-sm font-bold tabular-nums leading-tight ${valueClass}`}>{value}</span>
    </div>
  )
}

function PositionCard({ result, pos, userId, onRemove, onEdit, cerebro, confluence }: {
  result?: PositionResult
  pos: Position
  userId: string
  onRemove: () => void
  onEdit: (id: string, shares: number, avgPrice: number) => void
  cerebro: CerebroMaps
  confluence: ConfluenceSignals | null
}) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing]   = useState(false)
  const [editShares, setEditShares]   = useState(String(pos.shares))
  const [editPrice, setEditPrice]     = useState(String(pos.avg_price))
  const ticker = pos.ticker
  const cur    = result?.current_price ?? pos.avg_price
  const pl     = result?.pl_pct ?? 0
  const sym    = pos.currency === 'EUR' ? '€' : '$'
  const action = result?.action ?? 'MANTENER'

  const exit   = cerebro.exitMap[ticker]
  const trap   = cerebro.trapMap[ticker]
  const sm     = cerebro.smMap[ticker]
  const div    = cerebro.divMap[ticker]
  const hasCerebro = !!(exit || trap || sm || div)

  const overweight  = result && result.portfolio_pct > (result.optimal_size_pct ?? 100) * 1.5
  const underweight = result && result.portfolio_pct < (result.optimal_size_pct ?? 0) * 0.5 && (result.optimal_size_pct ?? 0) > 0

  return (
    <div className={`glass rounded-2xl overflow-clip transition-all border ${
      exit?.severity === 'HIGH' ? 'border-red-500/40' :
      trap ? 'border-amber-500/30' :
      action === 'AÑADIR' ? 'border-emerald-500/25' :
      action === 'VENDER' ? 'border-red-500/20' :
      'border-white/6'
    }`}>
      {/* Top accent line */}
      <div className={`h-0.5 w-full ${ACTION_BAR[action]}`} />

      {/* ── HEADER ── */}
      <div className="flex items-start gap-3 px-4 pt-4 pb-3">
        <TickerLogo ticker={ticker} size="sm" className="mt-0.5 shrink-0" />

        <div className="flex-1 min-w-0">
          {/* Row 1: ticker + company + sector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-extrabold text-lg text-foreground leading-none">{ticker}</span>
            {result?.sector && (
              <span className="text-[0.58rem] px-1.5 py-0.5 rounded bg-muted/40 border border-border/20 text-muted-foreground/50 uppercase tracking-wide">
                {result.sector}
              </span>
            )}
          </div>
          {result?.company_name && result.company_name !== ticker && (
            <p className="text-xs text-muted-foreground/60 truncate mt-0.5 leading-tight">{result.company_name}</p>
          )}
          {/* Row 2: cost basis */}
          <p className="text-[0.65rem] text-muted-foreground/40 mt-1">
            {pos.shares} acc · base {sym}{pos.avg_price.toFixed(2)}
          </p>
        </div>

        {/* Right: price + action + remove + edit */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <div className="flex items-center gap-1.5">
            {result && !editing && (
              <span className={`text-[0.62rem] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wide ${ACTION_STYLES[action]}`}>
                {action}
              </span>
            )}
            <button
              onClick={() => { setEditing(e => !e); setEditShares(String(pos.shares)); setEditPrice(String(pos.avg_price)) }}
              className={`p-1 rounded-md transition-colors ${editing ? 'text-primary bg-primary/10' : 'text-muted-foreground/40 hover:text-primary hover:bg-primary/10'}`}
              title="Editar posición"
            >
              <Pencil size={12} />
            </button>
            <button onClick={onRemove} className="p-1 rounded-md text-muted-foreground/40 hover:text-red-400 hover:bg-red-500/10 transition-colors">
              <X size={12} />
            </button>
          </div>
          {editing ? (
            <div className="flex flex-col items-end gap-1 mt-1">
              <div className="flex items-center gap-1">
                <span className="text-[0.6rem] text-muted-foreground/50">acc</span>
                <input
                  type="number"
                  value={editShares}
                  onChange={e => setEditShares(e.target.value)}
                  className="w-16 text-right text-xs bg-background/60 border border-border/40 rounded px-1 py-0.5 focus:outline-none focus:border-primary/50"
                  min="0"
                  step="any"
                />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[0.6rem] text-muted-foreground/50">base</span>
                <input
                  type="number"
                  value={editPrice}
                  onChange={e => setEditPrice(e.target.value)}
                  className="w-20 text-right text-xs bg-background/60 border border-border/40 rounded px-1 py-0.5 focus:outline-none focus:border-primary/50"
                  min="0"
                  step="any"
                />
              </div>
              <button
                onClick={() => {
                  const s = parseFloat(editShares)
                  const p = parseFloat(editPrice)
                  if (s > 0 && p > 0) { onEdit(pos.id, s, p); setEditing(false) }
                }}
                className="flex items-center gap-1 text-[0.6rem] font-bold px-2 py-0.5 rounded bg-primary/15 border border-primary/30 text-primary hover:bg-primary/25 transition-colors"
              >
                <Check size={10} /> Guardar
              </button>
            </div>
          ) : (
            <div className="text-right">
              <div className="font-extrabold text-base tabular-nums text-foreground">{sym}{cur.toFixed(2)}</div>
              {result && (
                <div className="text-[0.6rem] text-muted-foreground/40 tabular-nums">
                  {sym}{result.market_value.toFixed(0)} · {result.portfolio_pct.toFixed(1)}%
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── P&L BAND ── */}
      <div className={`flex items-center gap-2 px-4 py-2.5 mx-3 mb-3 rounded-xl ${pl >= 0 ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
        {pl >= 0 ? <TrendingUp size={15} className="text-emerald-400 shrink-0" /> : <TrendingDown size={15} className="text-red-400 shrink-0" />}
        <span className={`text-2xl font-black tabular-nums leading-none ${pl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {pl >= 0 ? '+' : ''}{pl.toFixed(2)}%
        </span>
        {result && (
          <span className={`text-sm font-semibold tabular-nums opacity-60 ${pl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {result.pl_abs >= 0 ? '+' : ''}{sym}{Math.abs(result.pl_abs).toFixed(0)}
          </span>
        )}
        {result && (
          <span className="ml-auto flex items-center gap-1.5 text-[0.6rem]">
            <span className={`w-1.5 h-1.5 rounded-full ${CONVICTION_DOT[result.conviction]}`} />
            <span className="text-muted-foreground/50 uppercase tracking-wide">{result.conviction}</span>
          </span>
        )}
      </div>

      {/* ── NL STATUS SENTENCE ── */}
      <div className="px-4 pb-2">
        <p className="text-[0.73rem] leading-relaxed text-muted-foreground/70">
          {nlPositionStatus({
            pl_pct:          pl,
            action,
            cerebro_exit:    !!exit,
            cerebro_trap:    !!trap,
            cerebro_smart_money: !!sm,
            optimal_size_pct:    result?.optimal_size_pct,
            portfolio_pct:       result?.portfolio_pct,
          })}
        </p>
      </div>

      {/* ── CEREBRO SIGNALS (compact pills) ── */}
      {hasCerebro && (
        <div className="flex flex-wrap gap-1.5 px-4 mb-3">
          {exit && (
            <span className={`inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full border ${exit.severity === 'HIGH' ? 'bg-red-500/15 text-red-400 border-red-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'}`}>
              <Brain size={9} />EXIT {exit.severity} · {exit.reasons[0]}
            </span>
          )}
          {trap && !exit && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <Brain size={9} />TRAP · {trap.flags[0]}
            </span>
          )}
          {sm && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400 border border-violet-500/30">
              <Brain size={9} />SMART $ · {sm.n_hedge_funds}HF {sm.n_insiders}INS
            </span>
          )}
          {div && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
              <Brain size={9} />DIV {div.rating} · {div.div_yield.toFixed(1)}%
            </span>
          )}
        </div>
      )}

      {/* ── CONFLUENCE SIGNALS ── */}
      {confluence && (confluence.bounce || confluence.value || confluence.flow) && (
        <div className="flex flex-wrap gap-1.5 px-4 mb-3">
          {confluence.bounce && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
              🎯 Bounce
            </span>
          )}
          {confluence.value && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
              💎 VALUE
            </span>
          )}
          {confluence.flow === 'BULLISH' && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              ⚡ Flow alcista
            </span>
          )}
          {confluence.flow === 'PUT_COVERING' && (
            <span className="inline-flex items-center gap-1 text-[0.62rem] font-bold px-2 py-0.5 rounded-full bg-yellow-500/15 text-yellow-300 border border-yellow-500/30">
              🔄 Suelo probable
            </span>
          )}
        </div>
      )}

      {/* ── CHART ── */}
      <div className="mx-3 rounded-xl overflow-hidden border border-border/20 mb-3">
        <PriceChart ticker={ticker} height={58} mini />
      </div>

      {/* ── KEY METRICS GRID (2×3, no scroll) ── */}
      {result && (
        <div className="grid grid-cols-3 gap-px bg-border/20 border border-border/20 rounded-xl overflow-hidden mx-3 mb-3">
          {[
            result.forward_pe != null && { label: 'PE fwd', value: `${result.forward_pe.toFixed(1)}x` },
            result.fcf_yield != null && { label: 'FCF yield', value: `${result.fcf_yield.toFixed(1)}%`, valueClass: result.fcf_yield >= 5 ? 'text-emerald-400' : result.fcf_yield < 0 ? 'text-red-400' : 'text-foreground' },
            result.dividend_yield != null && result.dividend_yield > 0 && { label: 'Div yield', value: `${result.dividend_yield.toFixed(2)}%`, valueClass: 'text-emerald-400' },
            result.analyst_target != null && { label: 'Target', value: `${sym}${result.analyst_target.toFixed(0)}`, valueClass: 'text-foreground', suffix: result.analyst_upside != null ? ` ${result.analyst_upside >= 0 ? '+' : ''}${result.analyst_upside.toFixed(0)}%` : undefined, suffixClass: result.analyst_upside != null && result.analyst_upside >= 0 ? 'text-emerald-400' : 'text-red-400' },
            result.stop_loss != null && { label: 'Stop loss', value: `${sym}${result.stop_loss.toFixed(2)}`, valueClass: 'text-red-400' },
            { label: 'Peso', value: `${result.portfolio_pct.toFixed(1)}%`, valueClass: overweight ? 'text-red-400' : underweight ? 'text-blue-400' : 'text-foreground' },
          ].filter(Boolean).slice(0, 6).map((m, i) => {
            if (!m) return null
            const metric = m as { label: string; value: string; valueClass?: string; suffix?: string; suffixClass?: string }
            return (
              <div key={i} className="bg-muted/8 px-3 py-2.5">
                <div className="text-[0.55rem] font-semibold uppercase tracking-wider text-muted-foreground/40 mb-0.5">{metric.label}</div>
                <div className={`text-sm font-bold tabular-nums ${metric.valueClass ?? 'text-foreground'}`}>
                  {metric.value}
                  {metric.suffix && <span className={`text-xs ml-1 ${metric.suffixClass}`}>{metric.suffix}</span>}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── SIZING ROW (compact, no scroll) ── */}
      {result?.volatility_pct != null && (
        <div className="flex items-center gap-3 px-4 py-2.5 mx-3 mb-3 rounded-xl bg-primary/4 border border-primary/10">
          <span className="text-[0.55rem] font-bold uppercase tracking-widest text-primary/50 shrink-0">Sizing</span>
          <div className="flex gap-4 flex-wrap">
            <MetricChip label="Vol" value={`${result.volatility_pct.toFixed(1)}%`} valueClass={(result.volatility_pct) > 15 ? 'text-red-400' : 'text-amber-400'} />
            <MetricChip label="Kelly" value={`${result.kelly_pct?.toFixed(1)}%`} />
            <MetricChip label="Óptimo" value={`${result.optimal_size_pct?.toFixed(1)}%`} valueClass={overweight ? 'text-red-400' : underweight ? 'text-blue-400' : 'text-primary'} />
            {result.stop_loss_atr != null && (
              <MetricChip label="Stop ATR" value={`${sym}${result.stop_loss_atr.toFixed(2)}`} valueClass="text-red-400" />
            )}
          </div>
          {(overweight || underweight) && (
            <span className={`ml-auto text-[0.6rem] font-bold uppercase tracking-wide ${overweight ? 'text-red-400' : 'text-blue-400'}`}>
              {overweight ? '↑ SOBRE' : '↓ INFRA'}
            </span>
          )}
        </div>
      )}

      {/* ── AI ANALYSIS (expand toggle) ── */}
      {result?.analysis && (
        <div className="mx-3 mb-3">
          <button
            onClick={() => setExpanded(v => !v)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-muted/10 border border-border/20 text-xs text-muted-foreground hover:border-border/40 transition-colors"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <Brain size={11} className="text-primary/60" />
              Análisis IA
            </span>
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {expanded && (
            <div className="mt-1.5 px-3 py-3 rounded-xl bg-muted/8 border border-border/15 space-y-2">
              <p className="text-xs text-foreground/75 leading-relaxed">{result.analysis}</p>
              {result.key_risk && (
                <div className="flex items-start gap-2 px-2.5 py-2 rounded-lg border border-amber-500/20 bg-amber-500/5">
                  <AlertTriangle size={11} className="text-amber-400 mt-0.5 shrink-0" />
                  <p className="text-[0.7rem] text-amber-300/75 leading-relaxed">{result.key_risk}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── OPTIONS PANEL ── */}
      {result && <div className="mx-3 mb-3"><OptionsPanel result={result} sym={sym} /></div>}

      {/* ── JOURNAL ── */}
      <JournalSection ticker={ticker} userId={userId} />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function PersonalPortfolio() {
  const { user } = useAuth()
  const cerebro    = useCerebroSignals()
  const confluence = usePortfolioConfluence()
  const [positions, setPositions] = useState<Position[]>([])
  const [loadingDb, setLoadingDb] = useState(true)
  const [saving, setSaving]       = useState(false)
  const [result, setResult]       = useState<AnalysisResult | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError]         = useState('')
  const [analyzed, setAnalyzed]   = useState(false)

  // Load positions from Supabase on mount
  useEffect(() => {
    if (!user) return
    setLoadingDb(true)
    supabase
      .from('personal_portfolio_positions')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: true })
      .then(({ data, error: err }) => {
        if (!err && data) {
          setPositions(data.map(r => ({
            id: r.id,
            ticker: r.ticker,
            shares: r.shares,
            avg_price: r.avg_price,
            currency: r.currency,
          })))
        }
        setLoadingDb(false)
      })
  }, [user])

  // Auto-analyze once positions are loaded
  useEffect(() => {
    if (!loadingDb && positions.length > 0 && !analyzed) {
      analyze()
    }
  }, [loadingDb]) // eslint-disable-line react-hooks/exhaustive-deps

  const analyze = useCallback(async () => {
    if (!positions.length) return
    setAnalyzing(true); setError('')
    try {
      const resp = await apiClient.post('/api/analyze-personal-portfolio', { positions })
      setResult(resp.data)
      setAnalyzed(true)
    } catch {
      setError('Error al analizar. Asegúrate de que el backend está corriendo.')
    } finally {
      setAnalyzing(false)
    }
  }, [positions])

  const addPosition = async (p: Omit<Position, 'id'>) => {
    if (!user) return
    const existing = positions.find(x => x.ticker === p.ticker)
    if (existing) {
      const newShares = existing.shares + p.shares
      const newAvg    = (existing.shares * existing.avg_price + p.shares * p.avg_price) / newShares
      setSaving(true)
      const { error: err } = await supabase
        .from('personal_portfolio_positions')
        .update({ shares: newShares, avg_price: newAvg })
        .eq('id', existing.id)
      setSaving(false)
      if (!err) {
        setPositions(prev => prev.map(x => x.id === existing.id ? { ...x, shares: newShares, avg_price: newAvg } : x))
        setResult(null); setAnalyzed(false)
      }
      return
    }
    setSaving(true)
    const { data, error: err } = await supabase
      .from('personal_portfolio_positions')
      .insert({ user_id: user.id, ticker: p.ticker, shares: p.shares, avg_price: p.avg_price, currency: p.currency })
      .select()
      .single()
    setSaving(false)
    if (!err && data) {
      setPositions(prev => [...prev, { id: data.id, ticker: data.ticker, shares: data.shares, avg_price: data.avg_price, currency: data.currency }])
      setResult(null); setAnalyzed(false)
    }
  }

  const removePosition = async (id: string) => {
    await supabase.from('personal_portfolio_positions').delete().eq('id', id)
    setPositions(prev => prev.filter(p => p.id !== id))
    setResult(null); setAnalyzed(false)
  }

  const updatePosition = async (id: string, shares: number, avgPrice: number) => {
    await supabase
      .from('personal_portfolio_positions')
      .update({ shares, avg_price: avgPrice })
      .eq('id', id)
    setPositions(prev => prev.map(p => p.id === id ? { ...p, shares, avg_price: avgPrice } : p))
    setResult(null); setAnalyzed(false)
  }

  const totalCost  = positions.reduce((s, p) => s + p.shares * p.avg_price, 0)
  const totalValue = result?.total_value ?? totalCost
  const totalPL    = totalValue - totalCost
  const totalPLPct = totalCost > 0 ? (totalPL / totalCost * 100) : 0

  // Dividend projection from analysis results
  const annualDividends = result?.positions.reduce((sum, p) => {
    if (p.dividend_yield && p.dividend_yield > 0 && p.market_value) {
      return sum + (p.market_value * p.dividend_yield / 100)
    }
    return sum
  }, 0) ?? 0

  const dividendPositions = result?.positions.filter(p => p.dividend_yield && p.dividend_yield > 0) ?? []

  if (loadingDb) {
    return (
      <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
        <Loader2 size={18} className="animate-spin" />
        <span className="text-sm">Cargando cartera...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="animate-fade-in-up">
        <h1 className="gradient-title text-2xl font-extrabold flex items-center gap-2">
          <Wallet size={22} className="text-primary" />
          Mi Cartera Personal
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Tus posiciones se guardan en la nube. El análisis IA se actualiza en cada visita.
        </p>
      </div>

      {/* Summary (after analysis) */}
      {result && (
        <div className="glass rounded-2xl p-5 space-y-4">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex gap-6 flex-wrap">
              <div className="animate-fade-in-up text-center sm:text-left" style={{ animationDelay: '0ms' }}>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Valor total</div>
                <div className="text-4xl font-black tabular-nums text-foreground">
                  ${result.total_value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="animate-fade-in-up text-center sm:text-left" style={{ animationDelay: '60ms' }}>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">P&L total</div>
                <div className={`text-2xl font-bold tabular-nums flex items-center gap-1 ${totalPL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {totalPL >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                  {totalPL >= 0 ? '+' : ''}${totalPL.toFixed(0)}
                  <span className="text-sm font-semibold ml-1">({totalPLPct >= 0 ? '+' : ''}{totalPLPct.toFixed(2)}%)</span>
                </div>
              </div>
              <div className="animate-fade-in-up text-center sm:text-left" style={{ animationDelay: '120ms' }}>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Posiciones</div>
                <div className="text-2xl font-bold text-foreground">{positions.length}</div>
              </div>
              {annualDividends > 0 && (
                <div className="animate-fade-in-up text-center sm:text-left" style={{ animationDelay: '180ms' }}>
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Dividendos / año</div>
                  <div className="text-2xl font-bold tabular-nums text-emerald-400">
                    ~${annualDividends.toFixed(0)}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={analyze}
              disabled={analyzing}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary/10 border border-primary/25 text-primary text-sm font-semibold hover:bg-primary/20 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} className={analyzing ? 'animate-spin' : ''} />
              {analyzing ? 'Analizando...' : 'Re-analizar'}
            </button>
          </div>

          {result.portfolio_analysis?.summary && (
            <div className="pt-3 border-t border-border/30 space-y-2">
              <p className="text-sm text-foreground/80 leading-relaxed">{result.portfolio_analysis.summary}</p>
              {result.portfolio_analysis.overall_recommendation && (
                <p className="text-sm text-muted-foreground leading-relaxed">{result.portfolio_analysis.overall_recommendation}</p>
              )}
              {result.portfolio_analysis.concentration_warning && (
                <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20">
                  <AlertTriangle size={12} className="text-amber-400 mt-0.5 shrink-0" />
                  <p className="text-[0.75rem] text-amber-300/80">{result.portfolio_analysis.concentration_warning}</p>
                </div>
              )}
            </div>
          )}

          {/* Risk & Position Sizing overview */}
          {result.risk_metrics && (
            <div className="pt-3 border-t border-border/30">
              <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-2">
                Risk Management · Position Sizing (Kelly)
              </div>
              <div className="flex gap-4 flex-wrap text-[0.72rem] mb-2">
                <span className="text-muted-foreground">
                  Riesgo total cartera{' '}
                  <strong className={result.risk_metrics.total_risk_pct > 10 ? 'text-red-400' : result.risk_metrics.total_risk_pct > 5 ? 'text-amber-400' : 'text-emerald-400'}>
                    {result.risk_metrics.total_risk_pct.toFixed(1)}%
                  </strong>
                  <span className="text-muted-foreground/50 ml-1">(${result.risk_metrics.total_risk_amount.toFixed(0)} en riesgo)</span>
                </span>
                <span className="text-muted-foreground">
                  Kelly base <strong className="text-foreground">{result.risk_metrics.kelly_base_pct.toFixed(1)}%</strong>
                </span>
                <span className="text-muted-foreground">
                  Win rate <strong className="text-foreground">{result.risk_metrics.win_rate_used.toFixed(0)}%</strong>
                </span>
              </div>
              {result.risk_metrics.oversized_positions.length > 0 && (
                <div className="flex items-start gap-2 p-2 rounded-lg bg-red-500/8 border border-red-500/15 text-[0.72rem]">
                  <AlertTriangle size={11} className="text-red-400 mt-0.5 shrink-0" />
                  <span className="text-red-300/80">
                    Posiciones sobreexpuestas (peso actual &gt; 1.5× Kelly óptimo):{' '}
                    <strong>{result.risk_metrics.oversized_positions.join(', ')}</strong>
                    {' '}— considera reducir o abrir hedge
                  </span>
                </div>
              )}
              {/* Per-position sizing bars */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
                {result.positions.map(p => {
                  const actual = p.portfolio_pct
                  const optimal = p.optimal_size_pct ?? 0
                  const maxBar = Math.max(actual, optimal, 1)
                  const isOver = actual > optimal * 1.5
                  const isUnder = actual < optimal * 0.5 && optimal > 0
                  return (
                    <div key={p.ticker} className="p-2 rounded-lg bg-muted/10 border border-border/20">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono font-bold text-[0.68rem] text-foreground">{p.ticker}</span>
                        <span className={`text-[0.6rem] font-bold ${isOver ? 'text-red-400' : isUnder ? 'text-blue-400' : 'text-emerald-400'}`}>
                          {isOver ? 'SOBRE' : isUnder ? 'INFRA' : 'OK'}
                        </span>
                      </div>
                      <div className="relative h-2 rounded-full bg-muted/30 overflow-hidden">
                        <div className="absolute inset-y-0 left-0 rounded-full bg-primary/40" style={{ width: `${(optimal / maxBar) * 100}%` }} />
                        <div className={`absolute inset-y-0 left-0 rounded-full ${isOver ? 'bg-red-400/60' : 'bg-emerald-400/60'}`} style={{ width: `${(actual / maxBar) * 100}%`, height: '50%', top: '25%' }} />
                      </div>
                      <div className="flex justify-between mt-0.5 text-[0.58rem] text-muted-foreground/60">
                        <span>Actual {actual.toFixed(1)}%</span>
                        <span>Kelly {optimal.toFixed(1)}%</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Dividend breakdown */}
          {dividendPositions.length > 0 && (
            <div className="pt-3 border-t border-border/30">
              <div className="text-[0.62rem] font-bold uppercase tracking-widest text-muted-foreground/50 mb-2">
                Proyección dividendos anuales
              </div>
              <div className="flex flex-wrap gap-2">
                {dividendPositions.map(p => (
                  <div key={p.ticker} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/8 border border-emerald-500/15 text-[0.72rem]">
                    <span className="font-mono font-bold text-emerald-400">{p.ticker}</span>
                    <span className="text-muted-foreground">{p.dividend_yield?.toFixed(2)}%</span>
                    <span className="text-emerald-400 font-semibold">
                      ~${((p.market_value * (p.dividend_yield ?? 0)) / 100).toFixed(0)}/año
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Add form */}
      <AddForm onAdd={addPosition} saving={saving} />

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {/* Empty state */}
      {positions.length === 0 && (
        <div className="glass rounded-2xl p-12 text-center animate-fade-in-up">
          <Wallet size={40} className="mx-auto text-muted-foreground/30 mb-4" />
          <p className="text-foreground font-semibold mb-1">Sin posiciones todavía</p>
          <p className="text-sm text-muted-foreground">Añade tus posiciones arriba y el análisis IA se generará automáticamente.</p>
        </div>
      )}

      {/* Positions */}
      {positions.length > 0 && (
        <div className="space-y-4">
          {!analyzed && !analyzing && (
            <button
              onClick={analyze}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              <RefreshCw size={14} />
              Analizar cartera con IA
            </button>
          )}

          {analyzing && positions.map(p => (
            <div key={p.id} className="glass rounded-2xl p-5 animate-pulse">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-muted/40" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-24 bg-muted/40 rounded" />
                  <div className="h-3 w-40 bg-muted/30 rounded" />
                </div>
              </div>
            </div>
          ))}

          {!analyzing && (() => {
            const posWithAlerts = positions.filter(p =>
              cerebro.exitMap[p.ticker] || cerebro.trapMap[p.ticker] || cerebro.divMap[p.ticker]
            )
            const criticalCount = positions.filter(p =>
              cerebro.exitMap[p.ticker]?.severity === 'HIGH' || cerebro.trapMap[p.ticker]?.severity === 'HIGH'
            ).length
            return (
              <>
                {posWithAlerts.length > 0 && (
                  <div className={`flex items-start gap-3 p-4 rounded-xl border ${criticalCount > 0 ? 'border-red-500/30 bg-red-500/8' : 'border-amber-500/25 bg-amber-500/6'}`}>
                    <Brain size={16} className={criticalCount > 0 ? 'text-red-400 mt-0.5 shrink-0' : 'text-amber-400 mt-0.5 shrink-0'} />
                    <div>
                      <p className={`text-sm font-bold ${criticalCount > 0 ? 'text-red-400' : 'text-amber-400'}`}>
                        Cerebro IA detectó alertas en {posWithAlerts.length} de {positions.length} posiciones
                        {criticalCount > 0 && ` — ${criticalCount} crítica${criticalCount > 1 ? 's' : ''}`}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {posWithAlerts.map(p => p.ticker).join(', ')} · Ver detalles en cada posición
                      </p>
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {positions.map((pos, index) => (
                    <div key={pos.id} className="animate-fade-in-up" style={{ animationDelay: `${index * 80}ms` }}>
                      <PositionCard
                        pos={pos}
                        userId={user!.id}
                        result={result?.positions.find(r => r.ticker === pos.ticker)}
                        onRemove={() => removePosition(pos.id)}
                        onEdit={updatePosition}
                        cerebro={cerebro}
                        confluence={confluence[pos.ticker] ?? null}
                      />
                    </div>
                  ))}
                </div>
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}
