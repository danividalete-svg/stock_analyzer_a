import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, TrendingUp, TrendingDown, Wallet, AlertTriangle, X, Loader2, BookOpen, Send, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import axios from 'axios'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/context/AuthContext'
import TickerLogo from '../components/TickerLogo'
import PriceChart from '../components/PriceChart'

const API_BASE = import.meta.env.VITE_API_URL || ''

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
}

interface PortfolioAnalysis {
  summary?: string
  concentration_warning?: string | null
  overall_recommendation?: string
}

interface AnalysisResult {
  total_value: number
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
            <div key={n.id} className="group flex gap-2 items-start p-3 rounded-lg bg-muted/15 border border-border/20">
              <div className="flex-1 min-w-0">
                <p className="text-[0.78rem] text-foreground/80 leading-relaxed whitespace-pre-wrap">{n.note}</p>
                <p className="text-[0.62rem] text-muted-foreground/50 mt-1">
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
      <div className="flex flex-wrap gap-2 items-end">
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
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} strokeWidth={2.5} />}
          Añadir
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </div>
  )
}

// ── Strategy Panel ────────────────────────────────────────────────────────────

type Strategy = { label: string; color: string; bg: string; border: string; desc: string }

function getStrategy(result: PositionResult): Strategy {
  const upside  = result.analyst_upside ?? 0
  const pl      = result.pl_pct
  const fcf     = result.fcf_yield ?? 0
  const action  = result.action
  const conviction = result.conviction

  if (action === 'VENDER')
    return { label: 'Rotación', color: 'text-red-400', bg: 'bg-red-500/8', border: 'border-red-500/20',
      desc: 'Cierra la posición y rota hacia una oportunidad con mejor R:R. Prioriza preservar capital.' }

  if (action === 'AÑADIR' && conviction === 'ALTA' && upside > 25)
    return { label: 'Doblar posición', color: 'text-emerald-400', bg: 'bg-emerald-500/8', border: 'border-emerald-500/20',
      desc: `Máxima convicción con +${upside.toFixed(0)}% de upside. Añade hasta el peso recomendado aprovechando la corrección.` }

  if (pl > 20 && upside < 15)
    return { label: 'Covered Call OTM', color: 'text-amber-400', bg: 'bg-amber-500/8', border: 'border-amber-500/20',
      desc: `+${pl.toFixed(0)}% de ganancia y poco upside restante. Vende calls OTM a 30-45 días para generar ingreso adicional mientras mantienes la posición.` }

  if (pl > 30 && conviction !== 'ALTA')
    return { label: 'Toma parcial de ganancias', color: 'text-amber-400', bg: 'bg-amber-500/8', border: 'border-amber-500/20',
      desc: `Posición con +${pl.toFixed(0)}%. Reduce 1/3 para asegurar beneficios; mantén el resto con trailing stop del 8%.` }

  if (pl < -10 && upside > 30 && conviction === 'ALTA')
    return { label: 'Promedio a la baja', color: 'text-blue-400', bg: 'bg-blue-500/8', border: 'border-blue-500/20',
      desc: `Drawdown temporal con tesis intacta y +${upside.toFixed(0)}% de upside. Añadir reduce el coste medio y mejora el R:R.` }

  if (pl < -15 && conviction !== 'ALTA')
    return { label: 'Stop Loss defensivo', color: 'text-red-400', bg: 'bg-red-500/8', border: 'border-red-500/20',
      desc: `Pérdida del ${pl.toFixed(0)}% con convicción ${conviction.toLowerCase()}. Evalúa salida con stop al -8% adicional para limitar daños.` }

  if (fcf >= 5 && pl > 0 && upside > 15)
    return { label: 'Mantener + reinversión dividendos', color: 'text-emerald-400', bg: 'bg-emerald-500/8', border: 'border-emerald-500/20',
      desc: `FCF yield del ${fcf.toFixed(1)}% + ${upside.toFixed(0)}% de upside. Reinvierte dividendos/buybacks. Posición de largo plazo óptima.` }

  return { label: 'Mantener — tesis vigente', color: 'text-primary', bg: 'bg-primary/8', border: 'border-primary/20',
    desc: `Posición equilibrada (${pl >= 0 ? '+' : ''}${pl.toFixed(0)}% P&L, ${upside.toFixed(0)}% upside). Mantén con stop del 8% y revisa en el próximo earnings.` }
}

function StrategyPanel({ result, sym: _sym }: { result: PositionResult; sym: string }) {
  const s = getStrategy(result)
  return (
    <div className={`mx-5 mb-3.5 p-3 rounded-xl ${s.bg} border ${s.border}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[0.55rem] font-bold uppercase tracking-widest text-muted-foreground/50">Estrategia sugerida</span>
        <span className={`text-[0.7rem] font-bold ${s.color}`}>{s.label}</span>
      </div>
      <p className="text-[0.75rem] text-foreground/70 leading-relaxed">{s.desc}</p>
    </div>
  )
}

// ── Position Card ─────────────────────────────────────────────────────────────

function PositionCard({ result, pos, userId, onRemove }: {
  result?: PositionResult
  pos: Position
  userId: string
  onRemove: () => void
}) {
  const ticker = pos.ticker
  const cur    = result?.current_price ?? pos.avg_price
  const pl     = result?.pl_pct ?? 0
  const sym    = pos.currency === 'EUR' ? '€' : '$'
  const action = result?.action ?? 'MANTENER'

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border/30">
        <TickerLogo ticker={ticker} size="sm" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-extrabold text-foreground text-base">{ticker}</span>
            {result?.company_name && result.company_name !== ticker && (
              <span className="text-xs text-muted-foreground truncate">{result.company_name}</span>
            )}
            {result?.sector && (
              <span className="text-[0.6rem] px-1.5 py-0.5 rounded bg-muted/40 border border-border/30 text-muted-foreground/60 uppercase tracking-wide">
                {result.sector}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
            <span className="text-xs text-muted-foreground">
              {pos.shares} acc · coste {sym}{pos.avg_price.toFixed(2)}
            </span>
            <span className={`text-xs font-bold flex items-center gap-0.5 ${pl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {pl >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
              {pl >= 0 ? '+' : ''}{pl.toFixed(2)}%
              {result && ` (${result.pl_abs >= 0 ? '+' : ''}${sym}${result.pl_abs.toFixed(0)})`}
            </span>
          </div>
        </div>

        <div className="flex items-start gap-3 shrink-0">
          <div className="text-right">
            <div className="font-extrabold text-lg tabular-nums text-foreground">{sym}{cur.toFixed(2)}</div>
            {result && (
              <div className="text-[0.62rem] text-muted-foreground tabular-nums">
                {sym}{result.market_value.toFixed(0)} · {result.portfolio_pct.toFixed(1)}%
              </div>
            )}
          </div>
          {result && (
            <span className={`text-[0.65rem] font-bold px-2.5 py-1 rounded-full border uppercase tracking-wide ${ACTION_STYLES[action]}`}>
              {action}
            </span>
          )}
          <button
            onClick={onRemove}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-colors"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Mini sparkline */}
      <div className="border-b border-border/20">
        <PriceChart ticker={ticker} height={52} mini />
      </div>

      {/* Metrics strip */}
      {result && (
        <div className="flex gap-4 px-5 py-2.5 bg-muted/10 border-b border-border/20 overflow-x-auto scrollbar-hide text-[0.72rem] text-muted-foreground">
          {result.forward_pe != null && (
            <span>PE fwd <strong className="text-foreground">{result.forward_pe.toFixed(1)}x</strong></span>
          )}
          {result.fcf_yield != null && (
            <span>FCF yield <strong className={result.fcf_yield >= 5 ? 'text-emerald-400' : result.fcf_yield < 0 ? 'text-red-400' : 'text-foreground'}>
              {result.fcf_yield.toFixed(1)}%
            </strong></span>
          )}
          {result.dividend_yield != null && result.dividend_yield > 0 && (
            <span>Div yield <strong className="text-emerald-400">{result.dividend_yield.toFixed(2)}%</strong></span>
          )}
          {result.analyst_target != null && (
            <span>Target analistas <strong className="text-foreground">{sym}{result.analyst_target.toFixed(2)}</strong>
              {result.analyst_upside != null && (
                <span className={result.analyst_upside >= 0 ? ' text-emerald-400' : ' text-red-400'}>
                  {' '}({result.analyst_upside >= 0 ? '+' : ''}{result.analyst_upside.toFixed(1)}%)
                </span>
              )}
            </span>
          )}
          {result.target_price != null && result.target_price !== result.analyst_target && (
            <span>IA objetivo <strong className="text-primary">{sym}{result.target_price.toFixed(2)}</strong></span>
          )}
          {result.stop_loss != null && (
            <span>Stop <strong className="text-red-400">{sym}{result.stop_loss.toFixed(2)}</strong></span>
          )}
          {result.fifty_two_week_high != null && (
            <span>52w <strong className="text-foreground">{sym}{result.fifty_two_week_low?.toFixed(0)}–{result.fifty_two_week_high.toFixed(0)}</strong></span>
          )}
          <span className="ml-auto shrink-0">
            Peso actual <strong className="text-foreground">{result.portfolio_pct.toFixed(1)}%</strong>
            {' '}→ recomendado{' '}
            <strong className={
              result.recommended_weight_pct > result.portfolio_pct + 3 ? 'text-emerald-400' :
              result.recommended_weight_pct < result.portfolio_pct - 3 ? 'text-amber-400' :
              'text-foreground'
            }>
              {result.recommended_weight_pct.toFixed(1)}%
            </strong>
          </span>
          <span className="shrink-0 flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${CONVICTION_DOT[result.conviction]}`} />
            conv. {result.conviction.toLowerCase()}
          </span>
        </div>
      )}

      {/* AI analysis */}
      {result?.analysis && (
        <div className="px-5 py-3.5 space-y-2">
          <p className="text-sm text-foreground/80 leading-relaxed">{result.analysis}</p>
          {result.key_risk && (
            <div className="flex items-start gap-2 mt-2 p-2.5 rounded-lg bg-red-500/6 border border-red-500/15">
              <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />
              <p className="text-[0.75rem] text-red-300/80 leading-relaxed">{result.key_risk}</p>
            </div>
          )}
        </div>
      )}

      {/* Estrategias para maximizar rentabilidad */}
      {result && <StrategyPanel result={result} sym={sym} />}

      {/* Journal */}
      <JournalSection ticker={ticker} userId={userId} />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function PersonalPortfolio() {
  const { user } = useAuth()
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
      const resp = await axios.post(`${API_BASE}/api/analyze-personal-portfolio`, { positions })
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
      <div>
        <h1 className="text-2xl font-extrabold text-foreground flex items-center gap-2">
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
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Valor total</div>
                <div className="text-2xl font-extrabold tabular-nums text-foreground">
                  ${result.total_value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">P&L total</div>
                <div className={`text-2xl font-extrabold tabular-nums flex items-center gap-1 ${totalPL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {totalPL >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                  {totalPL >= 0 ? '+' : ''}${totalPL.toFixed(0)}
                  <span className="text-sm font-semibold ml-1">({totalPLPct >= 0 ? '+' : ''}{totalPLPct.toFixed(2)}%)</span>
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Posiciones</div>
                <div className="text-2xl font-extrabold text-foreground">{positions.length}</div>
              </div>
              {annualDividends > 0 && (
                <div>
                  <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-0.5">Dividendos / año</div>
                  <div className="text-2xl font-extrabold tabular-nums text-emerald-400">
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
        <div className="glass rounded-2xl p-12 text-center">
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

          {!analyzing && positions.map(pos => (
            <PositionCard
              key={pos.id}
              pos={pos}
              userId={user!.id}
              result={result?.positions.find(r => r.ticker === pos.ticker)}
              onRemove={() => removePosition(pos.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
