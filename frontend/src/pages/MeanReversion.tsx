import React, { useState, useEffect, useRef } from 'react'
import { fetchMeanReversion } from '../api/client'
import StaleDataBanner from '../components/StaleDataBanner'
import AiNarrativeCard from '../components/AiNarrativeCard'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import { Badge } from '@/components/ui/badge'
import CsvDownload from '../components/CsvDownload'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Wallet } from 'lucide-react'
import EmptyState from '../components/EmptyState'

interface MRItem {
  ticker: string
  company_name?: string
  strategy: string
  quality: string
  reversion_score: number
  current_price?: number
  entry_zone?: string
  target?: number
  stop_loss?: number
  rsi?: number
  drawdown_pct?: number
  risk_reward?: number
  support_level?: number
  resistance_level?: number
  distance_to_support_pct?: number
  volume_ratio?: number
  detected_date?: string
  ai_confirmation?: 'YES' | 'CAUTION' | 'NO' | null
  ai_confidence?: number | null
  ai_reason?: string | null
  historical_win_rate?: number | null
  [key: string]: unknown
}

const QUALITY_LEVELS = [
  { label: 'EXCELENTE', match: 'EXCELENTE' },
  { label: 'MUY BUENA', match: 'MUY BUENA' },
  { label: 'BUENA',     match: 'BUENA' },
]

function qualMatch(q: string, match: string) {
  return (q || '').toUpperCase().includes(match)
}

export default function MeanReversion() {
  const { data, loading, error } = useApi(() => fetchMeanReversion(), [])
  const { positions: myPositions } = usePersonalPortfolio()
  const [sortKey, setSortKey] = useState<string>('reversion_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [filterQuality, setFilterQuality] = useState<string>('EXCELENTE')
  const [compact, setCompact] = useState(false)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const pagedRef = useRef<MRItem[]>([])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (e.key === 'Escape') { setFocusedIdx(-1); setExpanded(null); return }
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
          if (i >= 0 && pagedRef.current[i]) {
            const d = pagedRef.current[i]
            setExpanded(prev => prev === d.ticker ? null : d.ticker)
          }
          return i
        })
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const raw = data as Record<string, unknown>
  let items: MRItem[] = []
  if (Array.isArray(raw?.opportunities)) items = raw.opportunities as MRItem[]
  else if (Array.isArray(raw?.data)) items = raw.data as MRItem[]

  // Filtro de seguridad: ocultar setups donde el precio ya rompió el soporte (>3% bajo)
  // El scanner ya filtra en backend, pero como segunda línea de defensa en el frontend
  const validItems = items.filter(i =>
    i.distance_to_support_pct == null || i.distance_to_support_pct >= -3
  )

  const filtered = filterQuality === ''
    ? validItems
    : validItems.filter(i => qualMatch(i.quality, filterQuality))

  const sorted = [...filtered].sort((a, b) => {
    const av = (a[sortKey] as number) ?? 0
    const bv = (b[sortKey] as number) ?? 0
    return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })
  pagedRef.current = sorted

  const onSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: string) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const qualVariant = (q: string): 'green' | 'blue' | 'yellow' => {
    const upper = (q || '').toUpperCase()
    if (upper.includes('EXCELENTE')) return 'green'
    if (upper.includes('MUY BUENA') || upper.includes('BUENA')) return 'blue'
    return 'yellow'
  }

  const fmtDate = (d?: string) => {
    if (!d) return '—'
    const m = d.match(/(\d{4})-(\d{2})-(\d{2})/)
    return m ? `${m[2]}/${m[3]}` : d
  }

  const qualCounts = QUALITY_LEVELS.map(ql => ({
    ...ql,
    count: validItems.filter(i => qualMatch(i.quality, ql.match)).length,
  }))
  const bestScore = filtered.length ? Math.max(...filtered.map(i => i.reversion_score || 0)) : 0
  const bestTicker = filtered.find(i => (i.reversion_score || 0) >= bestScore - 0.001)?.ticker

  return (
    <>
      <StaleDataBanner module="mean_reversion" />
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Mean Reversion</h2>
          <p className="text-sm text-muted-foreground">Oversold bounces y pullbacks — oportunidades de reversión a la media</p>
        </div>
        <div className="flex items-center gap-2 mt-1 shrink-0">
          <button
            onClick={() => setCompact(c => !c)}
            className={`text-[0.65rem] font-bold px-2.5 py-1 rounded border transition-colors hidden sm:block ${
              compact
                ? 'bg-primary/20 border-primary/50 text-primary'
                : 'bg-muted/20 border-border/30 text-muted-foreground hover:text-foreground hover:border-border/60'
            }`}
          >
            Compacto
          </button>
          <CsvDownload dataset="mean-reversion" label="CSV" />
        </div>
      </div>

      {(raw?.ai_narrative as string | null | undefined) && (
        <AiNarrativeCard narrative={raw.ai_narrative as string} label="Análisis del Batch Actual" className="mb-5" />
      )}

      {/* ── Top Rebotes Panel ──────────────────────────────────────────────── */}
      {(() => {
        const top = validItems
          .filter(i => qualMatch(i.quality, 'EXCELENTE') || qualMatch(i.quality, 'MUY BUENA'))
          .sort((a, b) => (b.reversion_score ?? 0) - (a.reversion_score ?? 0))
          .slice(0, 5)
        if (top.length === 0) return null
        return (
          <div className="mb-6 animate-fade-in-up">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[0.6rem] font-black uppercase tracking-[0.15em] text-muted-foreground/50">Top Rebotes Hoy</span>
              <div className="flex-1 h-px bg-border/20" />
              <span className="text-[0.6rem] text-muted-foreground/40">{top.length} setups</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2">
              {top.map((d, idx) => {
                const strategyShort = (d.strategy || '').includes('Flag') ? 'Flag' : 'Oversold'
                const rr = d.risk_reward != null && Number(d.risk_reward) > 0 ? Number(d.risk_reward) : null
                const rrColor = rr == null ? '' : rr >= 3 ? 'text-emerald-400' : rr >= 2 ? 'text-cyan-400' : rr >= 1 ? 'text-amber-400' : 'text-red-400'
                return (
                  <div
                    key={d.ticker}
                    className="glass rounded-xl p-3 border border-border/20 hover:border-primary/30 transition-colors cursor-pointer active:scale-[0.98]"
                    style={{ animationDelay: `${idx * 50}ms` }}
                    onClick={() => {
                      setFilterQuality('')
                      setTimeout(() => {
                        const el = document.querySelector(`[data-row-idx]`) as HTMLElement
                        el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                      }, 100)
                    }}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-black text-sm text-foreground">{d.ticker}</span>
                        <span className={`text-[0.55rem] font-bold px-1.5 py-0.5 rounded border ${
                          strategyShort === 'Oversold'
                            ? 'bg-amber-500/10 border-amber-500/25 text-amber-400'
                            : 'bg-blue-500/10 border-blue-500/25 text-blue-400'
                        }`}>{strategyShort}</span>
                      </div>
                      {d.rsi != null && (
                        <span className={`text-[0.65rem] font-bold tabular-nums ${d.rsi < 25 ? 'text-red-400' : d.rsi < 35 ? 'text-amber-400' : 'text-muted-foreground'}`}>
                          RSI {d.rsi.toFixed(0)}
                        </span>
                      )}
                    </div>
                    {/* Price ladder */}
                    <div className="grid grid-cols-3 gap-1 mb-2 text-center">
                      <div className="rounded bg-muted/15 px-1.5 py-1">
                        <div className="text-[0.6rem] text-muted-foreground/50 leading-none mb-0.5">Entrada</div>
                        <div className="text-[0.72rem] font-bold text-muted-foreground leading-none truncate">{d.entry_zone?.split(' ')[0] ?? '—'}</div>
                      </div>
                      <div className="rounded bg-emerald-500/8 px-1.5 py-1">
                        <div className="text-[0.6rem] text-muted-foreground/50 leading-none mb-0.5">Target</div>
                        <div className="text-[0.72rem] font-bold text-emerald-400 leading-none">{d.target != null ? `$${d.target.toFixed(1)}` : '—'}</div>
                      </div>
                      <div className="rounded bg-red-500/6 px-1.5 py-1">
                        <div className="text-[0.6rem] text-muted-foreground/50 leading-none mb-0.5">Stop</div>
                        <div className="text-[0.72rem] font-bold text-red-400 leading-none">{d.stop_loss != null ? `$${d.stop_loss.toFixed(1)}` : '—'}</div>
                      </div>
                    </div>
                    {/* R:R + AI + Win Rate row */}
                    <div className="flex items-center justify-between mt-1">
                      <div className="flex items-center gap-1.5">
                        {d.ai_confirmation && (
                          <span className={`text-[0.55rem] font-black px-1 py-0.5 rounded leading-none ${
                            d.ai_confirmation === 'YES' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                            : d.ai_confirmation === 'CAUTION' ? 'bg-amber-500/15 text-amber-400 border border-amber-500/20'
                            : 'bg-red-500/15 text-red-400 border border-red-500/20'
                          }`} title={d.ai_reason ?? ''}>
                            {d.ai_confirmation === 'YES' ? '✓ IA' : d.ai_confirmation === 'CAUTION' ? '⚠ IA' : '✗ IA'}
                            {d.ai_confidence != null ? ` ${d.ai_confidence}%` : ''}
                          </span>
                        )}
                        {d.historical_win_rate != null && (
                          <span className="text-[0.55rem] text-muted-foreground/50 tabular-nums">{d.historical_win_rate.toFixed(0)}% hist</span>
                        )}
                      </div>
                      {rr != null && (
                        <span className={`text-xs font-black tabular-nums ${rrColor}`}>{rr.toFixed(1)}x</span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* Quality filter */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <span className="text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground mr-1">Calidad</span>
        {[{ label: 'TODAS', value: '' }, ...QUALITY_LEVELS.map(q => ({ label: q.label, value: q.match }))].map(opt => {
          const count = opt.value === '' ? validItems.length : (qualCounts.find(q => q.match === opt.value)?.count ?? 0)
          const active = filterQuality === opt.value
          return (
            <button
              key={opt.value}
              onClick={() => setFilterQuality(opt.value)}
              className={`text-[0.7rem] font-bold px-3 py-1 rounded border transition-colors ${
                active
                  ? 'bg-primary/20 border-primary/50 text-primary'
                  : 'bg-muted/20 border-border/30 text-muted-foreground hover:text-foreground hover:border-border/60'
              }`}
            >
              {opt.label} <span className="opacity-60 font-normal ml-0.5">{count}</span>
            </button>
          )
        })}
        <span className="ml-auto text-[0.65rem] text-muted-foreground">{sorted.length} señales</span>
      </div>

      {/* My positions in oversold zone */}
      {(() => {
        const ownedTickers = new Set(myPositions.map(p => p.ticker))
        const myMR = filtered.filter(r => ownedTickers.has(r.ticker))
        if (myMR.length === 0) return null
        return (
          <Card className="glass border border-primary/20 mb-5 animate-fade-in-up">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Wallet size={14} className="text-primary" />
                <span className="text-[0.62rem] font-bold uppercase tracking-widest text-primary/70">Mis Posiciones en Zona Oversold</span>
                <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">{myMR.length}</span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead>Ticker</TableHead>
                    <TableHead>Calidad</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Soporte</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Stop</TableHead>
                    <TableHead>R:R</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {myMR.map(d => (
                    <TableRow key={d.ticker}>
                      <TableCell>
                        <div className="flex items-center gap-1.5">
                          <TickerLogo ticker={d.ticker} size="xs" />
                          <span className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{d.ticker}</span>
                        </div>
                      </TableCell>
                      <TableCell><Badge variant={qualVariant(d.quality)}>{d.quality}</Badge></TableCell>
                      <TableCell><ScoreBar score={d.reversion_score} /></TableCell>
                      <TableCell className="tabular-nums text-amber-400">{d.support_level != null ? `$${d.support_level.toFixed(2)}` : '—'}</TableCell>
                      <TableCell className="tabular-nums">{d.target ? `$${d.target.toFixed(2)}` : '—'}</TableCell>
                      <TableCell className="tabular-nums">{d.stop_loss ? `$${d.stop_loss.toFixed(2)}` : '—'}</TableCell>
                      <TableCell className="tabular-nums">
                        {d.risk_reward != null && Number(d.risk_reward) > 0
                          ? <span className={(d.risk_reward as number) >= 2 ? 'text-emerald-400' : (d.risk_reward as number) >= 1 ? 'text-amber-400' : 'text-red-400'}>{Number(d.risk_reward).toFixed(1)}</span>
                          : <span className="text-muted-foreground/30">—</span>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )
      })()}

      {/* Mobile cards */}
      <div className="sm:hidden space-y-2 mb-2">
        {sorted.map((d, i) => (
          <div
            key={d.ticker}
            data-row-idx={i}
            onClick={() => { setFocusedIdx(i); setExpanded(expanded === d.ticker ? null : d.ticker) }}
            className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform ${expanded === d.ticker ? 'border-primary/30' : ''}`}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-sm">{d.ticker}</span>
                  <Badge variant={qualVariant(d.quality)}>{d.quality}</Badge>
                </div>
                <span className="text-[0.65rem] text-muted-foreground">{d.company_name}</span>
              </div>
              <div className="text-right">
                <ScoreBar score={d.reversion_score} />
                {d.risk_reward != null && (
                  <div className={`text-xs font-semibold mt-0.5 ${Number(d.risk_reward) >= 2 ? 'text-emerald-400' : Number(d.risk_reward) >= 1 ? 'text-amber-400' : 'text-red-400'}`}>
                    R:R {Number(d.risk_reward).toFixed(1)}
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-3 mt-2 text-[0.62rem] text-muted-foreground/60">
              {d.support_level != null && <span>Soporte ${d.support_level.toFixed(2)}</span>}
              {d.target != null && <span>Target ${d.target.toFixed(2)}</span>}
              {d.rsi != null && <span>RSI {d.rsi.toFixed(0)}</span>}
            </div>
            {expanded === d.ticker && d.entry_zone && (
              <div className="mt-3 pt-3 border-t border-border/20 grid grid-cols-2 gap-2 text-[0.7rem]">
                <div className="bg-muted/10 rounded-lg p-2">
                  <div className="text-muted-foreground">Entrada</div>
                  <div className="font-semibold">{d.entry_zone}</div>
                </div>
                {d.stop_loss != null && (
                  <div className="bg-red-500/8 rounded-lg p-2">
                    <div className="text-muted-foreground">Stop</div>
                    <div className="font-semibold text-red-400">${d.stop_loss.toFixed(2)}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {sorted.length === 0 && (
          <EmptyState
            icon="🔄"
            title="Sin señales de mean reversion"
            subtitle="Aparecen cuando acciones de calidad caen >8% desde máximos con RSI<32"
          />
        )}
      </div>

      {/* Desktop table */}
      <div className="hidden sm:block">
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
                <TableHead>Calidad</TableHead>
                <TableHead className={thCls('reversion_score')} onClick={() => onSort('reversion_score')}>Score</TableHead>
                {!compact && <TableHead>Entry / Soporte</TableHead>}
                {compact && <TableHead className={thCls('support_level')} onClick={() => onSort('support_level')}>Soporte</TableHead>}
                <TableHead className={thCls('target')} onClick={() => onSort('target')}>Target</TableHead>
                {!compact && <TableHead>Stop</TableHead>}
                <TableHead className={thCls('risk_reward')} onClick={() => onSort('risk_reward')}>R:R</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((d, i) => (
                <React.Fragment key={d.ticker + i}>
                  <TableRow
                    data-row-idx={i}
                    className={`cursor-pointer transition-colors ${i === focusedIdx ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                    onClick={() => { setFocusedIdx(i); setExpanded(expanded === d.ticker ? null : d.ticker) }}
                  >
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <TickerLogo ticker={d.ticker} size="xs" />
                        <div>
                          <div className="font-mono font-bold text-primary text-[0.8rem] tracking-wide flex items-center gap-1.5">
                            {d.ticker}
                            <OwnedBadge ticker={d.ticker} />
                            {d.ticker === bestTicker && <Badge variant="green" className="text-[0.5rem] px-1 py-0 leading-4">BEST</Badge>}
                          </div>
                          {d.company_name && d.company_name !== d.ticker && (
                            <div className="text-[0.65rem] text-muted-foreground truncate max-w-[110px]">{d.company_name}</div>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant={qualVariant(d.quality)}>{d.quality}</Badge></TableCell>
                    <TableCell><ScoreBar score={d.reversion_score} /></TableCell>
                    {!compact ? (
                      <TableCell>
                        <div className="text-muted-foreground text-[0.76rem]">{d.entry_zone || '—'}</div>
                        {d.support_level != null && (
                          <div className="text-[0.65rem] text-amber-400">
                            S: ${d.support_level.toFixed(2)}
                            {d.distance_to_support_pct != null && (
                              <span className="ml-1 text-muted-foreground">({d.distance_to_support_pct.toFixed(1)}%)</span>
                            )}
                          </div>
                        )}
                      </TableCell>
                    ) : (
                      <TableCell className="tabular-nums text-amber-400">
                        {d.support_level != null ? `$${d.support_level.toFixed(2)}` : '—'}
                      </TableCell>
                    )}
                    <TableCell className="tabular-nums">{d.target ? `$${d.target.toFixed(2)}` : '—'}</TableCell>
                    {!compact && (
                      <TableCell className="tabular-nums">{d.stop_loss ? `$${d.stop_loss.toFixed(2)}` : '—'}</TableCell>
                    )}
                    <TableCell className="tabular-nums">
                      {d.risk_reward != null && Number(d.risk_reward) > 0
                        ? <span className={(d.risk_reward as number) >= 2 ? 'text-emerald-400' : (d.risk_reward as number) >= 1 ? 'text-amber-400' : 'text-red-400'}>{Number(d.risk_reward).toFixed(1)}</span>
                        : <span className="text-muted-foreground/30">—</span>}
                    </TableCell>
                  </TableRow>
                  {expanded === d.ticker && (
                    <tr className="thesis-row">
                      <td colSpan={compact ? 5 : 7}>
                        <div className="px-5 py-4 space-y-3">
                          {/* Price ladder */}
                          <div className="flex items-center gap-2">
                            {[
                              { label: 'Soporte', value: d.support_level, color: 'emerald' as const },
                              { label: 'Precio', value: d.current_price != null ? Number(d.current_price) : null, color: 'primary' as const },
                              { label: 'Resistencia', value: d.resistance_level, color: 'red' as const },
                            ].map(({ label, value, color }) => value != null && (
                              <div key={label} className={`flex-1 rounded-lg border px-3 py-2 ${
                                color === 'emerald' ? 'bg-emerald-500/8 border-emerald-500/20' :
                                color === 'red' ? 'bg-red-500/8 border-red-500/15' :
                                'bg-primary/6 border-primary/15'
                              }`}>
                                <div className={`text-sm font-bold tabular-nums ${
                                  color === 'emerald' ? 'text-emerald-400' :
                                  color === 'red' ? 'text-red-400' : 'text-primary'
                                }`}>${value.toFixed(2)}</div>
                                <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/45 mt-0.5">{label}</div>
                              </div>
                            ))}
                          </div>
                          {/* Detail metrics */}
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-1.5 text-[0.75rem]">
                            {[
                              { label: 'Estrategia', value: d.strategy || null, q: '' },
                              { label: 'RSI', value: d.rsi != null ? d.rsi.toFixed(0) : null,
                                q: d.rsi != null ? (d.rsi < 30 ? 'good' : '') : '' },
                              { label: 'Drawdown', value: d.drawdown_pct != null ? `${d.drawdown_pct.toFixed(1)}%` : null, q: '' },
                              { label: 'Vol. Ratio', value: d.volume_ratio != null ? `${Number(d.volume_ratio).toFixed(2)}x` : null,
                                q: d.volume_ratio != null ? (Number(d.volume_ratio) >= 1.5 ? 'good' : '') : '' },
                              { label: 'Detectado', value: d.detected_date ? fmtDate(d.detected_date) : null, q: '' },
                            ].filter(x => x.value != null).map(({ label, value, q }) => (
                              <div key={label} className={`rounded-lg border px-2.5 py-2 ${
                                q === 'good' ? 'bg-emerald-500/8 border-emerald-500/20' : 'bg-muted/12 border-border/20'
                              }`}>
                                <div className={`text-[0.82rem] font-bold tabular-nums leading-tight ${
                                  q === 'good' ? 'text-emerald-400' : 'text-foreground/70'
                                }`}>{value}</div>
                                <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/45 mt-0.5 leading-tight">{label}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
          {sorted.length === 0 && (
            <EmptyState
              icon="🔄"
              title="Sin señales de mean reversion"
              subtitle="Aparecen cuando acciones de calidad caen >8% desde máximos con RSI<32"
            />
          )}
          {sorted.length > 0 && (
            <div className="px-4 py-2 border-t border-border/20 flex items-center gap-3 text-[0.6rem] text-muted-foreground/50">
              <span>j/k or ↑↓ navegar</span>
              <span>Enter expandir</span>
              <span>Esc cerrar</span>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
