import StaleDataBanner from '../components/StaleDataBanner'
import { useState } from 'react'
import { fetchShortOpportunities, type ShortOpportunity } from '../api/client'
import EmptyState from '../components/EmptyState'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import WatchlistButton from '../components/WatchlistButton'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { TrendingDown } from 'lucide-react'

type SortKey = 'short_score' | 'current_price' | 'pct_from_52w_high' | 'analyst_upside_pct' | 'rev_growth_yoy' | 'short_interest_pct'
type SortDir = 'asc' | 'desc'

function QualityBadge({ q }: { q: string }) {
  const map: Record<string, string> = {
    ALTA:  'bg-red-500/15 text-red-400 border-red-500/30',
    MEDIA: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    BAJA:  'bg-muted/20 text-muted-foreground border-border/20',
  }
  return (
    <span className={`text-[0.65rem] font-bold px-1.5 py-0.5 rounded border ${map[q] ?? map.BAJA}`}>
      {q}
    </span>
  )
}

function SqueezeBadge({ risk }: { risk?: string }) {
  if (!risk || risk === 'LOW') return null
  const map: Record<string, string> = {
    HIGH:    'bg-red-500/20 text-red-400 border-red-500/30',
    MEDIUM:  'bg-amber-500/15 text-amber-400 border-amber-500/30',
    UNKNOWN: 'bg-muted/20 text-muted-foreground/60 border-border/20',
  }
  const labels: Record<string, string> = { HIGH: '🚀 SQUEEZE', MEDIUM: '⚠ SQUEEZE', UNKNOWN: '? SI' }
  return (
    <span className={`text-[0.58rem] font-bold px-1 py-0.5 rounded border ${map[risk] ?? map.UNKNOWN}`}>
      {labels[risk] ?? risk}
    </span>
  )
}

function WeinsteinBadge({ stage }: { stage?: number }) {
  if (!stage) return null
  const cfg: Record<number, { label: string; cls: string }> = {
    1: { label: 'S1', cls: 'bg-blue-500/10 text-blue-400/80 border-blue-500/20' },
    2: { label: 'S2', cls: 'bg-emerald-500/10 text-emerald-400/80 border-emerald-500/20' },
    3: { label: 'S3', cls: 'bg-amber-500/15 text-amber-400 border-amber-500/25' },
    4: { label: 'S4', cls: 'bg-red-500/15 text-red-400 border-red-500/25 font-black' },
  }
  const c = cfg[stage] ?? { label: `S${stage}`, cls: 'bg-muted/20 text-muted-foreground border-border/20' }
  return (
    <span className={`text-[0.6rem] font-bold px-1 py-0.5 rounded border ${c.cls}`}>{c.label}</span>
  )
}

function fmt(n: number | undefined | null, decimals = 1, suffix = '') {
  if (n == null || isNaN(n)) return <span className="text-muted-foreground/30">—</span>
  const sign = n > 0 ? '+' : ''
  return <span>{sign}{n.toFixed(decimals)}{suffix}</span>
}

export default function Shorts() {
  const { data, loading, error } = useApi(() => fetchShortOpportunities(), [])
  const [sortKey, setSortKey] = useState<SortKey>('short_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [showAll, setShowAll] = useState(false)
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const rows: ShortOpportunity[] = (data as any)?.data ?? []
  const aiFilterAvailable: boolean = (data as any)?.ai_filtered_available ?? false

  // Por defecto: solo ALTA calidad + squeeze risk no HIGH
  // Si hay filtro IA activo: solo confirmados por IA (BUY ≥65)
  const highConviction = rows.filter(r => {
    if (r.short_quality !== 'ALTA') return false
    if (r.squeeze_risk === 'HIGH') return false
    if (aiFilterAvailable && r.ai_verdict !== null) {
      return r.ai_verdict === 'BUY' && (r.ai_confidence ?? 0) >= 65
    }
    return true
  })

  const displayed = showAll
    ? [...rows].sort((a, b) => b.short_score - a.short_score)
    : [...highConviction].sort((a, b) => {
        const av = (a as any)[sortKey] ?? 0
        const bv = (b as any)[sortKey] ?? 0
        return sortDir === 'desc' ? bv - av : av - bv
      })

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortKey(k); setSortDir('desc') }
  }

  function SortTh({ k, children }: { k: SortKey; children: React.ReactNode }) {
    const active = k === sortKey
    return (
      <TableHead className="cursor-pointer select-none whitespace-nowrap" onClick={() => toggleSort(k)}>
        {children}{active ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
      </TableHead>
    )
  }

  return (
    <div className="space-y-4">
      <StaleDataBanner module="shorts" />

      {/* Header */}
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight gradient-title mb-1 flex items-center gap-2">
            <TrendingDown size={20} className="text-red-400" />
            Cortos
          </h1>
          <p className="text-sm text-muted-foreground">
            Alta convicción · deterioro fundamental + rotura técnica · squeeze risk bajo
            {aiFilterAvailable && <span className="ml-2 text-purple-400/70">· validados por IA</span>}
          </p>
        </div>
        {!showAll && rows.length > highConviction.length && (
          <button onClick={() => setShowAll(true)} className="filter-btn shrink-0 mt-1">
            Ver todos ({rows.length})
          </button>
        )}
        {showAll && (
          <button onClick={() => setShowAll(false)} className="filter-btn active shrink-0 mt-1">
            Solo alta convicción
          </button>
        )}
      </div>

      {/* Risk disclaimer — compacto */}
      <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-2 text-xs text-red-300/60 flex items-center gap-2">
        <span>⚠️</span>
        <span>Pérdida potencial ilimitada. Stop-loss 5-8%, máx 3-5% cartera por posición.</span>
      </div>

      {/* Tabla */}
      {displayed.length === 0 ? (
        <EmptyState
          icon="📉"
          title={rows.length === 0 ? "Sin datos" : "Sin cortos de alta convicción hoy"}
          subtitle={rows.length === 0 ? "Lanza el pipeline para escanear el universo" : `${rows.length} escaneados, ninguno supera el filtro de calidad`}
        />
      ) : (
        <div className="glass rounded-xl overflow-clip">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead>Empresa</TableHead>
                <SortTh k="short_score">Score</SortTh>
                <SortTh k="current_price">Precio</SortTh>
                <TableHead>Técnico</TableHead>
                <SortTh k="pct_from_52w_high">Dist.Máx</SortTh>
                <SortTh k="analyst_upside_pct">Objetivo</SortTh>
                <SortTh k="rev_growth_yoy">Rev%</SortTh>
                <SortTh k="short_interest_pct">SI%</SortTh>
                <TableHead>Riesgos</TableHead>
                {aiFilterAvailable && <TableHead>IA</TableHead>}
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayed.map(r => {
                const isExpanded = expandedTicker === r.ticker
                const riskList: string[] = (() => {
                  if (!r.key_risks) return []
                  try { return JSON.parse(r.key_risks).filter((x: string) => !x.startsWith('SHORT_INTEREST')) }
                  catch { return [] }
                })()
                return (
                  <>
                    <TableRow
                      key={r.ticker}
                      className={`cursor-pointer hover:bg-white/5 ${isExpanded ? 'bg-red-500/5' : ''}`}
                      onClick={() => setExpandedTicker(isExpanded ? null : r.ticker)}
                    >
                      <TableCell className="font-mono font-bold text-red-400">{r.ticker}</TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[140px] truncate">
                        {r.company_name ?? '—'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 min-w-[80px]">
                          <ScoreBar score={r.short_score} max={100} />
                          <span className="text-xs font-bold tabular-nums text-red-400">{r.short_score.toFixed(0)}</span>
                        </div>
                      </TableCell>
                      <TableCell><QualityBadge q={r.short_quality} /></TableCell>
                      <TableCell className="tabular-nums text-sm font-medium">${r.current_price.toFixed(2)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 flex-wrap">
                          <WeinsteinBadge stage={r.weinstein_stage} />
                          {r.death_cross && (
                            <span className="text-[0.58rem] font-bold px-1 py-0.5 rounded border bg-red-500/10 text-red-400 border-red-500/20">DC</span>
                          )}
                          {r.below_ma200 && (
                            <span className="text-[0.58rem] font-bold px-1 py-0.5 rounded border bg-red-500/8 text-red-400/70 border-red-500/15">↓MA200</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="tabular-nums text-sm">
                        <span className={`font-medium ${(r.pct_from_52w_high ?? 0) < -30 ? 'text-red-400' : (r.pct_from_52w_high ?? 0) < -15 ? 'text-amber-400' : 'text-muted-foreground'}`}>
                          {r.pct_from_52w_high != null ? `${r.pct_from_52w_high.toFixed(1)}%` : '—'}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-nums text-sm">
                        {r.analyst_target != null ? (
                          <span>
                            ${r.analyst_target.toFixed(2)}
                            {r.analyst_upside_pct != null && (
                              <span className={`text-xs ml-1 font-semibold ${r.analyst_upside_pct < 0 ? 'text-red-400' : 'text-muted-foreground/60'}`}>
                                ({r.analyst_upside_pct.toFixed(0)}%)
                              </span>
                            )}
                          </span>
                        ) : '—'}
                      </TableCell>
                      <TableCell className="tabular-nums text-sm">
                        <span className={(r.rev_growth_yoy ?? 0) < 0 ? 'text-red-400' : 'text-muted-foreground/60'}>
                          {fmt(r.rev_growth_yoy, 1, '%')}
                        </span>
                      </TableCell>
                      <TableCell className="tabular-nums text-xs">
                        <div className="flex items-center gap-1">
                          <span className={(r.short_interest_pct ?? 0) > 15 ? 'text-amber-400 font-bold' : 'text-muted-foreground/60'}>
                            {r.short_interest_pct != null ? `${r.short_interest_pct.toFixed(1)}%` : '—'}
                          </span>
                          <SqueezeBadge risk={r.squeeze_risk} />
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-0.5">
                          {r.earnings_warning && (
                            <Badge variant="outline" className="text-[0.58rem] px-1 py-0 border-amber-500/40 text-amber-400">
                              EARN
                            </Badge>
                          )}
                          {riskList.slice(0, 1).map(risk => (
                            <Badge key={risk} variant="outline" className="text-[0.58rem] px-1 py-0 border-red-500/30 text-red-400/70">
                              {risk.replace(/_/g, ' ')}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      {aiFilterAvailable && (
                        <TableCell>
                          {r.ai_verdict === 'BUY' ? (
                            <span title={r.ai_reasoning ?? ''} className="text-[0.62rem] font-bold px-1.5 py-0.5 rounded border bg-purple-500/15 border-purple-500/30 text-purple-400 cursor-help">
                              ✓ {r.ai_confidence}
                            </span>
                          ) : r.ai_verdict === 'AVOID' ? (
                            <span title={r.ai_reasoning ?? ''} className="text-[0.62rem] font-bold px-1.5 py-0.5 rounded border bg-red-500/10 border-red-500/20 text-red-400/60 cursor-help">
                              ✗
                            </span>
                          ) : r.ai_verdict === 'HOLD' ? (
                            <span title={r.ai_reasoning ?? ''} className="text-[0.62rem] font-bold px-1.5 py-0.5 rounded border bg-amber-500/10 border-amber-500/20 text-amber-400/60 cursor-help">
                              ~
                            </span>
                          ) : (
                            <span className="text-muted-foreground/30 text-xs">—</span>
                          )}
                        </TableCell>
                      )}
                      <TableCell>
                        <WatchlistButton ticker={r.ticker} />
                      </TableCell>
                    </TableRow>

                    {/* Expanded row: sub-scores + thesis */}
                    {isExpanded && (
                      <TableRow key={`${r.ticker}-expand`} className="bg-red-500/5 hover:bg-red-500/5">
                        <TableCell colSpan={12} className="py-3 px-4">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {/* Sub-scores */}
                            <div className="space-y-2">
                              <p className="text-[0.65rem] font-bold uppercase tracking-wider text-muted-foreground/50">Desglose de puntuación</p>
                              {[
                                { label: 'Técnico',      val: r.tech_score,  max: 40, color: 'bg-red-500' },
                                { label: 'Fundamental',  val: r.fund_score,  max: 35, color: 'bg-orange-500' },
                                { label: 'Bajada',       val: r.down_score,  max: 15, color: 'bg-amber-500' },
                                { label: 'Seguridad',    val: r.safety_score, max: 10, color: 'bg-blue-500' },
                              ].map(({ label, val, max, color }) => (
                                <div key={label} className="flex items-center gap-2">
                                  <span className="text-[0.65rem] text-muted-foreground/60 w-20 shrink-0">{label}</span>
                                  <div className="flex-1 h-1.5 bg-muted/20 rounded-full overflow-clip">
                                    <div
                                      className={`h-full rounded-full ${color}`}
                                      style={{ width: `${(val / max) * 100}%` }}
                                    />
                                  </div>
                                  <span className="text-[0.65rem] font-bold tabular-nums text-muted-foreground/70 w-10 text-right">
                                    {val}/{max}
                                  </span>
                                </div>
                              ))}
                            </div>

                            {/* Fundamentals + Thesis */}
                            <div className="space-y-2">
                              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[0.68rem]">
                                {[
                                  { label: 'ROE',     val: r.roe_pct,     suffix: '%' },
                                  { label: 'FCF yld', val: r.fcf_yield_pct, suffix: '%' },
                                  { label: 'D/E',     val: r.debt_to_equity, suffix: '×' },
                                  { label: 'Piotroski', val: r.piotroski_score, suffix: '/9' },
                                  { label: 'RSI',     val: r.rsi_daily,  suffix: '' },
                                  { label: 'Op.Mg',   val: r.operating_margin, suffix: '%' },
                                ].map(({ label, val, suffix }) => (
                                  <div key={label} className="flex justify-between border-b border-border/10 pb-0.5">
                                    <span className="text-muted-foreground/50">{label}</span>
                                    <span className="font-medium tabular-nums">
                                      {val != null ? `${val}${suffix}` : '—'}
                                    </span>
                                  </div>
                                ))}
                              </div>

                              {r.short_thesis && (
                                <div className="mt-2 rounded-lg bg-red-500/6 border border-red-500/15 px-3 py-2">
                                  <p className="text-[0.6rem] font-bold uppercase text-red-400/60 mb-1">Tesis bajista</p>
                                  <p className="text-xs text-foreground/80 leading-snug">{r.short_thesis}</p>
                                </div>
                              )}
                              {r.ai_reasoning && (
                                <div className={`mt-2 rounded-lg px-3 py-2 border ${r.ai_verdict === 'BUY' ? 'bg-purple-500/8 border-purple-500/20' : 'bg-amber-500/6 border-amber-500/15'}`}>
                                  <p className="text-[0.6rem] font-bold uppercase mb-1" style={{ color: r.ai_verdict === 'BUY' ? '#a78bfa' : '#fbbf24' }}>
                                    🤖 Validación IA — {r.ai_verdict} ({r.ai_confidence}% conf.)
                                  </p>
                                  <p className="text-xs text-foreground/80 leading-snug">{r.ai_reasoning}</p>
                                </div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
