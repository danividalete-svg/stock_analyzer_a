import StaleDataBanner from '../components/StaleDataBanner'
import { useState, useEffect, useRef } from 'react'
import { fetchRecurringInsiders, fetchInsidersInsight, downloadCsv, type InsiderData } from '../api/client'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import AiNarrativeCard from '../components/AiNarrativeCard'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'
import ScoreRing from '../components/ScoreRing'
import Loading, { ErrorState } from '../components/Loading'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Wallet } from 'lucide-react'
import PaginationBar from '../components/PaginationBar'

type InsiderRow = InsiderData & { market?: string }
type SortKey = keyof InsiderRow

function getCompany(r: InsiderRow) {
  return r.company_name || r.company || r.ticker
}

// Normalize score to 0-100 for display (US scores can be 50-3570)
function normScore(score: number, maxScore: number): number {
  if (maxScore <= 100) return score
  return Math.min(100, Math.round((score / maxScore) * 100))
}

function fmtQty(v?: number) {
  if (v == null || v === 0) return '—'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`
  return v.toFixed(0)
}

export default function Insiders() {
  const { data, loading, error } = useApi(() => fetchRecurringInsiders(), [])
  const { data: insightRaw } = useApi(() => fetchInsidersInsight(), [])
  const { positions: myPositions } = usePersonalPortfolio()
  const [sortKey, setSortKey] = useState<SortKey>('confidence_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [filterMarket, setFilterMarket] = useState<'ALL' | 'US' | 'EU'>('ALL')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1280)
  const PAGE_SIZE = 30
  const pagedRef = useRef<InsiderRow[]>([])

  useEffect(() => { setPage(1) }, [filterMarket, sortKey])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (e.key === 'Escape') { setFocusedIdx(-1); return }
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

  const allRows = (data?.data ?? []) as InsiderRow[]
  const maxScore = allRows.length ? Math.max(...allRows.map(r => r.confidence_score || 0)) : 100

  const filtered = filterMarket === 'ALL' ? allRows
    : filterMarket === 'US' ? allRows.filter(r => !r.market || r.market === 'US')
    : allRows.filter(r => r.market && r.market !== 'US')

  const sorted = [...filtered].sort((a, b) => {
    const av = (a[sortKey] ?? 0) as number
    const bv = (b[sortKey] ?? 0) as number
    if (typeof av === 'string' || typeof bv === 'string') return sortDir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  const paged = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  pagedRef.current = paged

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: SortKey) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const confVariant = (score: number, max: number): 'green' | 'yellow' | 'red' => {
    const n = normScore(score, max)
    return n >= 70 ? 'green' : n >= 40 ? 'yellow' : 'red'
  }

  const marketVariant = (m?: string): 'blue' | 'green' | 'gray' => {
    if (!m || m === 'US') return 'gray'
    if (m === 'FTSE100') return 'blue'
    return 'green'
  }

  const usRows = allRows.filter(r => !r.market || r.market === 'US')
  const euRows = allRows.filter(r => r.market && r.market !== 'US')
  const highConf = filtered.filter(r => normScore(r.confidence_score, maxScore) >= 70).length
  const avgConf = filtered.length ? filtered.reduce((s, r) => s + normScore(r.confidence_score, maxScore), 0) / filtered.length : 0
  const multiInsider = filtered.filter(r => r.unique_insiders >= 2).length

  return (
    <>
      <StaleDataBanner module="insiders" />
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Recurring Insiders</h2>
        <p className="text-sm text-muted-foreground">Insiders comprando repetidamente sus propias acciones — señal de convicción directiva</p>
      </div>

      {insightRaw?.narrative && (
        <AiNarrativeCard narrative={insightRaw.narrative} label="Análisis de Patrones Insider" className="mb-5" />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Tickers', value: filtered.length, sub: `${euRows.length} EU · ${usRows.length} US`, idx: 1 },
          { label: 'Alta Confianza', value: highConf, sub: 'score normalizado 70+', color: 'text-emerald-400', idx: 2 },
          { label: 'Multi-Insider', value: multiInsider, sub: '≥2 directivos comprando', color: 'text-blue-400', idx: 3 },
          { label: 'Confianza Media', value: avgConf.toFixed(0), sub: 'normalizado 0-100', color: avgConf >= 60 ? 'text-emerald-400' : 'text-amber-400', idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {/* My Portfolio insiders */}
      {(() => {
        const ownedTickers = new Set(myPositions.map(p => p.ticker))
        const myInsiders = filtered.filter(r => ownedTickers.has(r.ticker))
        if (myInsiders.length === 0) return null
        return (
          <Card className="glass border border-primary/20 mb-5">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Wallet size={14} className="text-primary" />
                <span className="text-[0.62rem] font-bold uppercase tracking-widest text-primary/70">Insiders en Mi Cartera</span>
                <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">{myInsiders.length}</span>
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead>Ticker / Empresa</TableHead>
                    <TableHead className="hidden sm:table-cell">Mercado</TableHead>
                    <TableHead>Compras</TableHead>
                    <TableHead>Direct.</TableHead>
                    <TableHead className="hidden md:table-cell">Acciones</TableHead>
                    <TableHead className="hidden sm:table-cell">Última Compra</TableHead>
                    <TableHead>Confianza</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {myInsiders.map(d => {
                    const company = getCompany(d)
                    const normConf = normScore(d.confidence_score, maxScore)
                    const isEu = d.market && d.market !== 'US'
                    return (
                      <TableRow key={d.ticker}>
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            <TickerLogo ticker={d.ticker} size="xs" />
                            <div>
                              <div className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{d.ticker}</div>
                              {company !== d.ticker && (
                                <div className="text-[0.65rem] text-muted-foreground truncate max-w-[180px]">{company}</div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell"><Badge variant={marketVariant(d.market)}>{d.market ?? 'US'}</Badge></TableCell>
                        <TableCell className="font-bold tabular-nums">{d.purchase_count}</TableCell>
                        <TableCell>
                          <span className={d.unique_insiders >= 3 ? 'text-emerald-400 font-bold' : d.unique_insiders >= 2 ? 'text-amber-400 font-semibold' : ''}>
                            {d.unique_insiders}
                          </span>
                        </TableCell>
                        <TableCell className="hidden md:table-cell tabular-nums text-muted-foreground">{fmtQty(d.total_qty)}</TableCell>
                        <TableCell className="hidden sm:table-cell text-muted-foreground text-[0.75rem]">{d.last_purchase}</TableCell>
                        <TableCell>
                          {isEu && d.confidence_label
                            ? <Badge variant={confVariant(d.confidence_score, maxScore)}>{d.confidence_label}</Badge>
                            : <Badge variant={confVariant(d.confidence_score, maxScore)}>{normConf}</Badge>
                          }
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )
      })()}

      {/* Filter + Download bar */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {(['ALL', 'US', 'EU'] as const).map(m => (
          <button
            key={m}
            onClick={() => setFilterMarket(m)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${filterMarket === m ? 'bg-primary text-primary-foreground border-primary' : 'border-border/50 text-muted-foreground hover:text-foreground'}`}
          >
            {m === 'ALL' ? `Todos (${allRows.length})` : m === 'US' ? `US (${usRows.length})` : `EU (${euRows.length})`}
          </button>
        ))}
        <button
          onClick={() => setCompact(v => !v)}
          className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ${compact ? 'border-primary/60 bg-primary/15 text-primary' : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'}`}
          title="Alternar entre vista compacta y completa"
        >
          {compact ? '⊟ Compacta' : '⊞ Completa'}
        </button>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => downloadCsv('insiders')}
            className="text-xs px-3 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
          >
            ↓ CSV US
          </button>
          <button
            onClick={() => downloadCsv('insiders-eu')}
            className="text-xs px-3 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
          >
            ↓ CSV EU
          </button>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden space-y-2 mb-2">
        {paged.map((d, i) => {
          const company = getCompany(d)
          const normConf = normScore(d.confidence_score, maxScore)
          return (
            <div
              key={d.ticker}
              onClick={() => { setFocusedIdx(i); setExpanded(expanded === d.ticker ? null : d.ticker) }}
              className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform ${focusedIdx === i ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ScoreRing score={normConf} size="sm" />
                  <div>
                    <div className="flex items-center gap-1.5">
                      <TickerLogo ticker={d.ticker} size="xs" />
                      <span className="font-mono font-bold text-sm">{d.ticker}</span>
                      <OwnedBadge ticker={d.ticker} />
                    </div>
                    <span className="text-[0.65rem] text-muted-foreground block truncate max-w-[140px]">{company !== d.ticker ? company : ''}</span>
                  </div>
                </div>
                <div className="text-right">
                  {d.confidence_label && d.market && d.market !== 'US'
                    ? <Badge variant={confVariant(d.confidence_score, maxScore)}>{d.confidence_label}</Badge>
                    : <Badge variant={confVariant(d.confidence_score, maxScore)}>{normConf}</Badge>
                  }
                  {d.market && d.market !== 'US' && (
                    <div className="mt-1">
                      <Badge variant={marketVariant(d.market)}>{d.market}</Badge>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex gap-3 mt-2.5 text-[0.62rem] text-muted-foreground/60">
                <span>{d.purchase_count} compras</span>
                <span>{d.unique_insiders} direct.</span>
                {d.last_purchase && <span>últ. {d.last_purchase}</span>}
              </div>
            </div>
          )
        })}
        {allRows.length === 0 && (
          <div className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">👤</div>
            <p className="font-medium text-muted-foreground">Sin datos de insiders disponibles</p>
          </div>
        )}
      </div>

      {/* Desktop table */}
      <div className="hidden sm:block">
        <Card className="glass animate-fade-in-up">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker / Empresa</TableHead>
                  <TableHead className="hidden sm:table-cell">Mercado</TableHead>
                  <TableHead className={thCls('purchase_count')} onClick={() => onSort('purchase_count')}>Compras</TableHead>
                  <TableHead className={thCls('unique_insiders')} onClick={() => onSort('unique_insiders')}>Direct.</TableHead>
                  {!compact && <TableHead className={`hidden md:table-cell ${thCls('total_qty')}`} onClick={() => onSort('total_qty')}>Acciones</TableHead>}
                  {!compact && <TableHead className={`hidden md:table-cell ${thCls('first_purchase')}`} onClick={() => onSort('first_purchase')}>Desde</TableHead>}
                  <TableHead className={`hidden sm:table-cell ${thCls('last_purchase')}`} onClick={() => onSort('last_purchase')}>Última Compra</TableHead>
                  <TableHead className={thCls('confidence_score')} onClick={() => onSort('confidence_score')}>Confianza</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paged.map((d, i) => {
                  const company = getCompany(d)
                  const normConf = normScore(d.confidence_score, maxScore)
                  const isEu = d.market && d.market !== 'US'
                  return (
                    <>
                      <TableRow
                        key={d.ticker}
                        data-row-idx={i}
                        className={`cursor-pointer transition-colors ${focusedIdx === i ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                        onClick={() => { setFocusedIdx(i); setExpanded(expanded === d.ticker ? null : d.ticker) }}
                      >
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            <TickerLogo ticker={d.ticker} size="xs" />
                            <div>
                              <div className="font-mono font-bold text-primary text-[0.8rem] tracking-wide flex items-center gap-1.5">{d.ticker}<OwnedBadge ticker={d.ticker} /></div>
                              {company !== d.ticker && (
                                <div className="text-[0.65rem] text-muted-foreground truncate max-w-[180px]">{company}</div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell"><Badge variant={marketVariant(d.market)}>{d.market ?? 'US'}</Badge></TableCell>
                        <TableCell className="font-bold tabular-nums">{d.purchase_count}</TableCell>
                        <TableCell>
                          <span className={d.unique_insiders >= 3 ? 'text-emerald-400 font-bold' : d.unique_insiders >= 2 ? 'text-amber-400 font-semibold' : ''}>
                            {d.unique_insiders}
                          </span>
                        </TableCell>
                        {!compact && <TableCell className="hidden md:table-cell tabular-nums text-muted-foreground">{fmtQty(d.total_qty)}</TableCell>}
                        {!compact && <TableCell className="hidden md:table-cell text-muted-foreground text-[0.75rem]">{d.first_purchase || '—'}</TableCell>}
                        <TableCell className="hidden sm:table-cell text-muted-foreground text-[0.75rem]">{d.last_purchase}</TableCell>
                        <TableCell>
                          {isEu && d.confidence_label
                            ? <Badge variant={confVariant(d.confidence_score, maxScore)}>{d.confidence_label}</Badge>
                            : (
                              <div className="flex items-center gap-2">
                                <Badge variant={confVariant(d.confidence_score, maxScore)}>{normConf}</Badge>
                                {d.confidence_score > 100 && (
                                  <span className="text-[0.6rem] text-muted-foreground">raw: {d.confidence_score}</span>
                                )}
                              </div>
                            )}
                        </TableCell>
                      </TableRow>
                      {expanded === d.ticker && (
                        <tr className="thesis-row">
                          <td colSpan={8}>
                            <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-[0.75rem]">
                              {[
                                { label: 'Empresa', value: company, q: '' },
                                { label: 'Mercado', value: d.market ?? 'US', q: '' },
                                { label: 'Total compras', value: d.purchase_count, q: Number(d.purchase_count) >= 5 ? 'good' : Number(d.purchase_count) >= 3 ? 'warn' : '' },
                                { label: 'Directivos únicos', value: d.unique_insiders, q: d.unique_insiders >= 3 ? 'good' : d.unique_insiders >= 2 ? 'warn' : '' },
                                { label: 'Acciones compradas', value: fmtQty(d.total_qty), q: '' },
                                { label: 'Periodo activo', value: `${d.days_span} días`, q: d.days_span >= 30 ? 'good' : '' },
                                { label: 'Primera compra', value: d.first_purchase || '—', q: '' },
                                { label: 'Última compra', value: d.last_purchase, q: '' },
                              ].map(({ label, value, q }) => (
                                <div key={label} className={`rounded-lg border px-2.5 py-2 ${
                                  q === 'good' ? 'bg-emerald-500/8 border-emerald-500/20' :
                                  q === 'warn' ? 'bg-amber-500/8 border-amber-500/15' :
                                  'bg-muted/12 border-border/20'
                                }`}>
                                  <div className={`text-[0.82rem] font-bold tabular-nums leading-tight ${
                                    q === 'good' ? 'text-emerald-400' : q === 'warn' ? 'text-amber-400' : 'text-foreground/70'
                                  }`}>{String(value)}</div>
                                  <div className="text-[0.5rem] uppercase tracking-widest text-muted-foreground/45 mt-0.5 leading-tight">{label}</div>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </TableBody>
            </Table>
          </div>
          {allRows.length === 0 && (
            <CardContent className="py-16 text-center">
              <div className="text-4xl mb-4 opacity-20">👤</div>
              <p className="font-medium text-muted-foreground">Sin datos de insiders disponibles</p>
            </CardContent>
          )}
          {sorted.length > 0 && (
            <div className="text-[0.6rem] text-muted-foreground/25 text-right px-3 py-1.5 border-t border-border/10">
              j / k navegar · Enter abrir · Esc cerrar
            </div>
          )}
        </Card>
      </div>
      <PaginationBar page={page} totalPages={Math.ceil(sorted.length / PAGE_SIZE)} onPage={setPage} />
    </>
  )
}
