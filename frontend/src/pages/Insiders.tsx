import { useState } from 'react'
import { fetchRecurringInsiders, fetchInsidersInsight, downloadCsv, type InsiderData } from '../api/client'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import AiNarrativeCard from '../components/AiNarrativeCard'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'
import Loading, { ErrorState } from '../components/Loading'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Wallet } from 'lucide-react'

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

      <Card className="glass animate-fade-in-up">
        <Table>
          <TableHeader>
            <TableRow className="border-border/50 hover:bg-transparent">
              <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker / Empresa</TableHead>
              <TableHead className="hidden sm:table-cell">Mercado</TableHead>
              <TableHead className={thCls('purchase_count')} onClick={() => onSort('purchase_count')}>Compras</TableHead>
              <TableHead className={thCls('unique_insiders')} onClick={() => onSort('unique_insiders')}>Direct.</TableHead>
              <TableHead className={`hidden md:table-cell ${thCls('total_qty')}`} onClick={() => onSort('total_qty')}>Acciones</TableHead>
              <TableHead className={`hidden md:table-cell ${thCls('first_purchase')}`} onClick={() => onSort('first_purchase')}>Desde</TableHead>
              <TableHead className={`hidden sm:table-cell ${thCls('last_purchase')}`} onClick={() => onSort('last_purchase')}>Última Compra</TableHead>
              <TableHead className={thCls('confidence_score')} onClick={() => onSort('confidence_score')}>Confianza</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.slice(0, 60).map(d => {
              const company = getCompany(d)
              const normConf = normScore(d.confidence_score, maxScore)
              const isEu = d.market && d.market !== 'US'
              return (
                <>
                  <TableRow
                    key={d.ticker}
                    className="cursor-pointer"
                    onClick={() => setExpanded(expanded === d.ticker ? null : d.ticker)}
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
                    <TableCell className="hidden md:table-cell tabular-nums text-muted-foreground">{fmtQty(d.total_qty)}</TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground text-[0.75rem]">{d.first_purchase || '—'}</TableCell>
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
                        <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-[0.75rem]">
                          {[
                            { label: 'Empresa', value: company },
                            { label: 'Mercado', value: d.market ?? 'US' },
                            { label: 'Total compras', value: d.purchase_count },
                            { label: 'Directivos únicos', value: d.unique_insiders },
                            { label: 'Acciones compradas', value: fmtQty(d.total_qty) },
                            { label: 'Periodo activo', value: `${d.days_span} días` },
                            { label: 'Primera compra', value: d.first_purchase || '—' },
                            { label: 'Última compra', value: d.last_purchase },
                          ].map(({ label, value }) => (
                            <div key={label}>
                              <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground mb-1">{label}</div>
                              <div className="font-semibold">{String(value)}</div>
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
        {allRows.length === 0 && (
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">👤</div>
            <p className="font-medium text-muted-foreground">Sin datos de insiders disponibles</p>
          </CardContent>
        )}
      </Card>
    </>
  )
}
