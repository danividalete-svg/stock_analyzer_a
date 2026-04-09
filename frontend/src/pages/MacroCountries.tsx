import { useState, useMemo } from 'react'
import { fetchMacroCountries } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import StaleDataBanner from '../components/StaleDataBanner'
import { ChevronDown, ChevronUp, Globe } from 'lucide-react'

// ─── Types ──────────────────────────────────────────────────────────────────

interface MarketData {
  current: number
  ma200: number
  ma50: number
  pct_from_200: number
  pct_from_52h: number
  position_in_range: number
  ytd_return: number
  m1_return: number
  ma200_slope: number
  w52_high: number
  w52_low: number
}

interface CountryData {
  code: string
  name: string
  flag: string
  region: string
  // macro
  gdp_growth: number
  inflation: number
  unemployment: number
  current_account: number
  rate_direction: string
  policy_rate: number
  debt_to_gdp: number | null
  currency_sovereign: boolean
  macro_notes: string
  // AI
  ai_narrative?: string
  ai_risks?: string[]
  ai_opportunities?: string[]
  ai_verdict?: string
  ai_confidence?: number
  ai_insight?: string
  // market
  etf: string
  index: string
  etf_data: MarketData | null
  index_data: MarketData | null
  currency_ytd: number | null
  // scores
  macro_score: number
  market_score: number
  macro_breakdown: string[]
  market_breakdown: string[]
  // signal
  signal: 'STRONG_BUY' | 'BUY' | 'NEUTRAL' | 'SHORT' | 'STRONG_SHORT'
  color: string
  combined_score: number
  contrarian: boolean
  wait_pullback: boolean
}

interface MacroData {
  generated_at: string
  generated_ts: string
  macro_source: string
  market_source: string
  countries: CountryData[]
  summary: {
    strong_buy: string[]
    buy: string[]
    neutral: string[]
    short: string[]
    strong_short: string[]
  }
}

// ─── Constants ───────────────────────────────────────────────────────────────

const SIGNAL_CONFIG = {
  STRONG_BUY:   { label: 'STRONG BUY',   bg: 'bg-emerald-500/20', text: 'text-emerald-300', border: 'border-emerald-500/40', icon: '⬆⬆' },
  BUY:          { label: 'BUY',           bg: 'bg-cyan-500/20',    text: 'text-cyan-300',    border: 'border-cyan-500/40',    icon: '⬆' },
  NEUTRAL:      { label: 'NEUTRAL',       bg: 'bg-slate-500/15',   text: 'text-slate-300',   border: 'border-slate-500/30',   icon: '—' },
  SHORT:        { label: 'SHORT',         bg: 'bg-orange-500/20',  text: 'text-orange-300',  border: 'border-orange-500/40',  icon: '⬇' },
  STRONG_SHORT: { label: 'STRONG SHORT',  bg: 'bg-red-500/20',     text: 'text-red-300',     border: 'border-red-500/40',     icon: '⬇⬇' },
}

const REGIONS = ['Todos', 'Americas', 'Europe', 'Asia-Pacific']
const SIGNALS = ['Todos', 'STRONG_BUY', 'BUY', 'NEUTRAL', 'SHORT', 'STRONG_SHORT']

// ─── Helpers ─────────────────────────────────────────────────────────────────

function pctColor(v: number, inverse = false) {
  const pos = inverse ? v < 0 : v > 0
  if (pos)  return 'text-emerald-400'
  if (v === 0) return 'text-slate-400'
  return 'text-red-400'
}

function rateLabel(dir: string) {
  if (dir === 'CUTTING')  return { text: '↓ Recortando', cls: 'text-cyan-400' }
  if (dir === 'HIKING')   return { text: '↑ Subiendo',   cls: 'text-orange-400' }
  return                         { text: '→ Estable',    cls: 'text-slate-400' }
}

function ScoreBar({ value, max = 100, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div className="h-1.5 w-full rounded-full bg-white/10 overflow-clip">
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
    </div>
  )
}

// ─── Country Card ─────────────────────────────────────────────────────────────

function CountryCard({ c }: { c: CountryData }) {
  const [expanded, setExpanded] = useState(false)
  const sig = SIGNAL_CONFIG[c.signal]
  const mkt = c.etf_data ?? c.index_data
  const rl = rateLabel(c.rate_direction)

  return (
    <div
      className="glass rounded-lg border border-white/10 overflow-clip cursor-pointer hover:border-white/20 transition-colors"
      onClick={() => setExpanded(e => !e)}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{c.flag}</span>
            <div>
              <div className="font-semibold text-sm text-white leading-tight">{c.name}</div>
              <div className="text-[0.65rem] text-slate-500">{c.region}</div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className={`inline-flex items-center gap-0.5 text-[0.6rem] font-black px-1.5 py-0.5 rounded border tracking-wide ${sig.bg} ${sig.text} ${sig.border}`}>
              {sig.icon} {sig.label}
            </span>
            <span className="text-[0.6rem] text-slate-500">{c.combined_score.toFixed(0)}/100</span>
          </div>
        </div>

        {/* Score bars */}
        <div className="space-y-1.5 mb-3">
          <div className="flex items-center justify-between text-[0.6rem] text-slate-400">
            <span>Macro salud</span>
            <span className="text-white font-mono">{c.macro_score.toFixed(0)}/100</span>
          </div>
          <ScoreBar value={c.macro_score} color="#22d3ee" />
          <div className="flex items-center justify-between text-[0.6rem] text-slate-400">
            <span>Oportunidad mercado</span>
            <span className="text-white font-mono">{c.market_score.toFixed(0)}/100</span>
          </div>
          <ScoreBar value={c.market_score} color="#a78bfa" />
        </div>

        {/* Key metrics row */}
        <div className="grid grid-cols-3 gap-1.5 text-center">
          <div className="bg-white/5 rounded px-1 py-1.5">
            <div className="text-[0.55rem] text-slate-500 mb-0.5">PIB</div>
            <div className={`text-xs font-bold ${pctColor(c.gdp_growth)}`}>{c.gdp_growth > 0 ? '+' : ''}{c.gdp_growth.toFixed(1)}%</div>
          </div>
          <div className="bg-white/5 rounded px-1 py-1.5">
            <div className="text-[0.55rem] text-slate-500 mb-0.5">IPC</div>
            <div className={`text-xs font-bold ${c.inflation >= 1.5 && c.inflation <= 3 ? 'text-emerald-400' : c.inflation > 5 ? 'text-red-400' : 'text-amber-400'}`}>
              {c.inflation.toFixed(1)}%
            </div>
          </div>
          <div className="bg-white/5 rounded px-1 py-1.5">
            <div className="text-[0.55rem] text-slate-500 mb-0.5">vs 200MA</div>
            <div className={`text-xs font-bold ${mkt ? pctColor(mkt.pct_from_200) : 'text-slate-400'}`}>
              {mkt ? `${mkt.pct_from_200 > 0 ? '+' : ''}${mkt.pct_from_200.toFixed(1)}%` : 'N/A'}
            </div>
          </div>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1 mt-2.5">
          {c.contrarian && (
            <span className="text-[0.55rem] px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">⚡ CONTRARIAN</span>
          )}
          {c.wait_pullback && (
            <span className="text-[0.55rem] px-1 py-0.5 rounded bg-slate-500/10 text-slate-400 border border-slate-500/20">⏳ ESPERAR PULLBACK</span>
          )}
          {mkt && mkt.ytd_return < -10 && (
            <span className="text-[0.55rem] px-1 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">📉 YTD {mkt.ytd_return.toFixed(0)}%</span>
          )}
          {c.debt_to_gdp != null && !c.currency_sovereign && c.debt_to_gdp >= 100 && (
            <span title="Deuda elevada sin soberanía monetaria — riesgo real de mercado" className="text-[0.55rem] px-1 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">⚠ Deuda {c.debt_to_gdp.toFixed(0)}% GDP</span>
          )}
          {c.debt_to_gdp != null && c.currency_sovereign && c.debt_to_gdp >= 180 && (
            <span title="Deuda muy alta — monetizable pero riesgo latente" className="text-[0.55rem] px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">⚠ Deuda {c.debt_to_gdp.toFixed(0)}% GDP</span>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-white/10 p-4 space-y-4 text-xs" onClick={e => e.stopPropagation()}>

          {/* Macro fundamentals */}
          <div>
            <div className="text-[0.6rem] font-semibold text-slate-400 uppercase tracking-wider mb-2">Macro Fundamentales</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-400">PIB real 2025e</span>
                <span className={`font-mono font-semibold ${pctColor(c.gdp_growth)}`}>{c.gdp_growth > 0 ? '+' : ''}{c.gdp_growth.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Inflación (IPC)</span>
                <span className="font-mono font-semibold text-white">{c.inflation.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Desempleo</span>
                <span className="font-mono font-semibold text-white">{c.unemployment.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">C/A % GDP</span>
                <span className={`font-mono font-semibold ${pctColor(c.current_account)}`}>{c.current_account > 0 ? '+' : ''}{c.current_account.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Tipos banco central</span>
                <span className="font-mono font-semibold text-white">{c.policy_rate.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Dirección tipos</span>
                <span className={`font-semibold ${rl.cls}`}>{rl.text}</span>
              </div>
              {c.debt_to_gdp != null && (
                <div className="flex justify-between col-span-2">
                  <span className="text-slate-400">
                    Deuda pública / GDP
                    <span className={`ml-1 text-[0.6rem] ${c.currency_sovereign ? 'text-slate-500' : 'text-amber-500'}`}>
                      {c.currency_sovereign ? '(moneda propia)' : '(sin soberanía monetaria ⚠)'}
                    </span>
                  </span>
                  <span className={`font-mono font-semibold ${
                    !c.currency_sovereign && c.debt_to_gdp >= 100 ? 'text-red-400' :
                    c.debt_to_gdp >= 120 ? 'text-amber-400' : 'text-slate-300'
                  }`}>{c.debt_to_gdp.toFixed(0)}%</span>
                </div>
              )}
            </div>
            <p className="mt-2 text-slate-400 leading-snug">{c.macro_notes}</p>
          </div>

          {/* AI Analysis */}
          {c.ai_narrative && (
            <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-3 space-y-2">
              <div className="text-[0.6rem] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-1">
                🤖 Análisis IA — {c.ai_verdict ?? c.signal}
                {c.ai_confidence != null && <span className="text-purple-500 font-normal">· confianza {c.ai_confidence}%</span>}
              </div>
              <p className="text-[0.7rem] text-slate-300 leading-relaxed">{c.ai_narrative}</p>
              {c.ai_insight && (
                <p className="text-[0.68rem] text-cyan-400 italic">💡 {c.ai_insight}</p>
              )}
              {(c.ai_risks?.length ?? 0) > 0 && (
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div>
                    <div className="text-[0.55rem] text-red-400 font-semibold mb-1">RIESGOS</div>
                    {c.ai_risks!.map((r, i) => <div key={i} className="text-[0.62rem] text-slate-400">• {r}</div>)}
                  </div>
                  <div>
                    <div className="text-[0.55rem] text-emerald-400 font-semibold mb-1">OPORTUNIDADES</div>
                    {c.ai_opportunities!.map((o, i) => <div key={i} className="text-[0.62rem] text-slate-400">• {o}</div>)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Market data */}
          {mkt && (
            <div>
              <div className="text-[0.6rem] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Mercado — {c.etf_data ? c.etf : c.index}
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">Precio actual</span>
                  <span className="font-mono font-semibold text-white">{mkt.current.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">MA 200</span>
                  <span className="font-mono font-semibold text-white">{mkt.ma200.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">vs 200MA</span>
                  <span className={`font-mono font-semibold ${pctColor(mkt.pct_from_200)}`}>{mkt.pct_from_200 > 0 ? '+' : ''}{mkt.pct_from_200.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Rango 52s</span>
                  <span className="font-mono text-white">{mkt.position_in_range.toFixed(0)}% del rango</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">YTD</span>
                  <span className={`font-mono font-semibold ${pctColor(mkt.ytd_return)}`}>{mkt.ytd_return > 0 ? '+' : ''}{mkt.ytd_return.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">1 mes</span>
                  <span className={`font-mono font-semibold ${pctColor(mkt.m1_return)}`}>{mkt.m1_return > 0 ? '+' : ''}{mkt.m1_return.toFixed(1)}%</span>
                </div>
                {c.currency_ytd !== null && (
                  <div className="flex justify-between col-span-2">
                    <span className="text-slate-400">Divisa vs USD (YTD)</span>
                    <span className={`font-mono font-semibold ${pctColor(c.currency_ytd)}`}>{c.currency_ytd > 0 ? '+' : ''}{c.currency_ytd.toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Scoring breakdown */}
          <div>
            <div className="text-[0.6rem] font-semibold text-slate-400 uppercase tracking-wider mb-2">Desglose Scoring</div>
            <div className="space-y-0.5">
              {c.macro_breakdown.map((b, i) => (
                <div key={i} className="text-[0.65rem] text-slate-400">{b}</div>
              ))}
              <div className="my-1 border-t border-white/5" />
              {c.market_breakdown.map((b, i) => (
                <div key={i} className="text-[0.65rem] text-slate-400">{b}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Expand toggle */}
      <div className="flex justify-center py-1 border-t border-white/5">
        {expanded
          ? <ChevronUp className="h-3 w-3 text-slate-600" />
          : <ChevronDown className="h-3 w-3 text-slate-600" />}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function MacroCountries() {
  const { data, loading, error } = useApi<MacroData>(fetchMacroCountries)
  const [region, setRegion] = useState('Todos')
  const [signalFilter, setSignalFilter] = useState('Todos')
  const [sortBy, setSortBy] = useState<'score' | 'gdp' | 'ytd'>('score')

  const countries = useMemo(() => {
    if (!data?.countries) return []
    let list = [...data.countries]

    if (region !== 'Todos')
      list = list.filter(c => c.region === region)
    if (signalFilter !== 'Todos')
      list = list.filter(c => c.signal === signalFilter)

    if (sortBy === 'score')
      list.sort((a, b) => b.combined_score - a.combined_score)
    else if (sortBy === 'gdp')
      list.sort((a, b) => b.gdp_growth - a.gdp_growth)
    else if (sortBy === 'ytd') {
      list.sort((a, b) => {
        const am = (a.etf_data ?? a.index_data)?.ytd_return ?? 0
        const bm = (b.etf_data ?? b.index_data)?.ytd_return ?? 0
        return bm - am
      })
    }
    return list
  }, [data, region, signalFilter, sortBy])

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message="No hay datos de países disponibles. Ejecuta macro_country_scanner.py primero." />

  const s = data.summary

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-7xl mx-auto">
      <StaleDataBanner dataDate={data.generated_at} />

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Globe className="h-6 w-6 text-cyan-400" />
            Análisis Macro Global
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {data.countries.length} países · macro {data.macro_source.split(' ').slice(-2).join(' ')} · mercado tiempo real
          </p>
        </div>
        <div className="text-right text-[0.65rem] text-slate-500">
          <div>Actualizado: {data.generated_at}</div>
          <div className="text-slate-600">Macro: {data.macro_source}</div>
        </div>
      </div>

      {/* Signal summary pills */}
      <div className="flex flex-wrap gap-2">
        {([
          { key: 'strong_buy',   label: '⬆⬆ STRONG BUY',  cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
          { key: 'buy',          label: '⬆ BUY',            cls: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30' },
          { key: 'neutral',      label: '— NEUTRAL',         cls: 'bg-slate-500/15 text-slate-300 border-slate-500/25' },
          { key: 'short',        label: '⬇ SHORT',           cls: 'bg-orange-500/15 text-orange-300 border-orange-500/30' },
          { key: 'strong_short', label: '⬇⬇ STRONG SHORT', cls: 'bg-red-500/15 text-red-300 border-red-500/30' },
        ] as const).map(({ key, label, cls }) => {
          const codes = s[key] as string[]
          if (!codes.length) return null
          return (
            <div key={key} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold ${cls}`}>
              <span>{label}</span>
              <span className="font-normal opacity-70">
                {codes.map(c => data.countries.find(x => x.code === c)?.flag ?? c).join(' ')}
              </span>
            </div>
          )
        })}
      </div>

      {/* Filters + sort */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* Region */}
        <div className="flex bg-white/5 rounded-lg p-0.5 gap-0.5">
          {REGIONS.map(r => (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className={`px-3 py-1 rounded-md text-xs transition-colors ${region === r ? 'bg-white/15 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
            >
              {r}
            </button>
          ))}
        </div>

        {/* Signal filter */}
        <select
          value={signalFilter}
          onChange={e => setSignalFilter(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/50"
        >
          {SIGNALS.map(s => <option key={s} value={s} className="bg-slate-900">{s === 'Todos' ? 'Todas las señales' : s}</option>)}
        </select>

        {/* Sort */}
        <div className="flex bg-white/5 rounded-lg p-0.5 gap-0.5 ml-auto">
          {([['score','Score'],['gdp','PIB'],['ytd','YTD']] as const).map(([k, l]) => (
            <button
              key={k}
              onClick={() => setSortBy(k)}
              className={`px-3 py-1 rounded-md text-xs transition-colors ${sortBy === k ? 'bg-white/15 text-white font-semibold' : 'text-slate-400 hover:text-white'}`}
            >
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Country grid */}
      {countries.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No hay países con los filtros aplicados.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {countries.map(c => <CountryCard key={c.code} c={c} />)}
        </div>
      )}

      {/* Legend */}
      <div className="glass rounded-lg border border-white/10 p-4">
        <div className="text-[0.6rem] font-semibold text-slate-400 uppercase tracking-wider mb-2">Metodología</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[0.65rem] text-slate-400 leading-relaxed">
          <div>
            <span className="text-cyan-400 font-semibold">Score Macro (45%):</span> PIB real, inflación (óptimo 1.5-3%), desempleo, dirección de tipos, balanza corriente.
          </div>
          <div>
            <span className="text-purple-400 font-semibold">Score Mercado (55%):</span> Posición vs 200MA (zona de corrección = mejor entrada), percentil del rango 52 semanas, rentabilidad YTD (caída = más barato), pendiente de tendencia.
          </div>
          <div>
            <span className="text-amber-400 font-semibold">⚡ CONTRARIAN:</span> Mercado barato pero macro débil — posible rebote, alto riesgo.
          </div>
          <div>
            <span className="text-slate-400 font-semibold">Datos macro:</span> {data.macro_source}. Mercado: tiempo real vía yfinance (ETFs cotizados en USD).
          </div>
        </div>
      </div>
    </div>
  )
}
