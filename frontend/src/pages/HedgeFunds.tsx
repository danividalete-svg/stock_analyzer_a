import { useState, useEffect, useRef, useMemo } from 'react'
import { fetchHedgeFunds, type HedgeFundConsensusItem } from '../api/client'
import { useApi } from '../hooks/useApi'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Building2, TrendingUp, DollarSign, Users2, Info, Wallet, Brain } from 'lucide-react'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'

const FUND_COLORS: Record<string, string> = {
  'Berkshire Hathaway (Buffett)': '#f59e0b',
  'Pershing Square (Ackman)':     '#3b82f6',
  'Third Point (Loeb)':           '#8b5cf6',
  'Appaloosa (Tepper)':           '#10b981',
  'Baupost Group (Klarman)':      '#ec4899',
  'Lone Pine Capital':            '#14b8a6',
  'Viking Global':                '#f97316',
  'Coatue Management':            '#6366f1',
}

function fundBadge(fundName: string) {
  const color = FUND_COLORS[fundName] || '#94a3b8'
  const short = fundName.split('(')[0].trim()
  return (
    <span
      key={fundName}
      className="inline-block text-[0.6rem] font-semibold px-1.5 py-0.5 rounded border"
      style={{ color, borderColor: `${color}40`, backgroundColor: `${color}15` }}
    >
      {short}
    </span>
  )
}

function ConsensusBadge({ count }: { count: number }) {
  if (count >= 4) return <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">{count} fondos</span>
  if (count >= 2) return <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">{count} fondos</span>
  return <span className="text-[0.65rem] font-bold px-2 py-0.5 rounded-full bg-muted/30 text-muted-foreground border border-border/30">{count} fondo</span>
}

/** Generate client-side AI insight from the 13F data */
function generateInsight(rows: HedgeFundConsensusItem[], _funds: string[]): string {
  if (rows.length === 0) return ''

  const multi = rows.filter(r => r.funds_count >= 2)
  const topByValue = [...rows].sort((a, b) => b.total_value_m - a.total_value_m).slice(0, 5)
  const topByConcentration = [...rows].sort((a, b) => b.avg_portfolio_pct - a.avg_portfolio_pct).slice(0, 3)
  const totalAum = rows.reduce((sum, r) => sum + r.total_value_m, 0)

  const parts: string[] = []

  if (multi.length > 0) {
    const tickers = multi.map(r => `**${r.ticker}** (${r.funds_count} fondos)`).join(', ')
    parts.push(`Convergencia de due diligence: ${tickers} — múltiples gestores value llegaron a la misma conclusión independientemente.`)
  } else {
    parts.push('No hay convergencia 2+ fondos actualmente — cada gestor tiene posiciones únicas, lo cual sugiere oportunidades diferenciadas.')
  }

  const topTickers = topByValue.map(r => `${r.ticker} ($${(r.total_value_m / 1000).toFixed(1)}B)`).join(', ')
  parts.push(`Mayores posiciones por valor: ${topTickers}. AUM total rastreado: $${(totalAum / 1000).toFixed(0)}B.`)

  const highConv = topByConcentration.filter(r => r.avg_portfolio_pct >= 3)
  if (highConv.length > 0) {
    const convTickers = highConv.map(r => `${r.ticker} (${r.avg_portfolio_pct.toFixed(1)}% del portfolio)`).join(', ')
    parts.push(`Alta convicción: ${convTickers} — posiciones concentradas indican fuerte tesis de inversión.`)
  }

  const buffettCount = rows.filter(r => r.funds_list.includes('Berkshire')).length
  if (buffettCount > rows.length * 0.5) {
    parts.push(`Berkshire Hathaway domina con ${buffettCount} de ${rows.length} posiciones mostradas — el oráculo de Omaha sigue concentrado en financieras y consumo.`)
  }

  return parts.join(' ')
}

export default function HedgeFunds() {
  const { data, loading, error } = useApi(() => fetchHedgeFunds(), [])
  const { isOwned, positions: myPositions } = usePersonalPortfolio()
  const [minFunds, setMinFunds] = useState(1)
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1280)
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const pagedRef = useRef<HedgeFundConsensusItem[]>([])

  const allRows  = data?.top_consensus ?? []
  const funds    = data?.funds_scraped ?? []
  const insight  = useMemo(() => generateInsight(allRows, funds), [allRows, funds])
  const filtered = useMemo(() => allRows.filter(r => r.funds_count >= minFunds), [allRows, minFunds])

  pagedRef.current = filtered

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
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const genAt        = data?.generated_at ? new Date(data.generated_at).toLocaleDateString('es-ES') : '—'
  const multi        = allRows.filter(r => r.funds_count >= 2).length
  const top3         = allRows.filter(r => r.funds_count >= 3).length
  const overlapCount = myPositions.length > 0 ? allRows.filter(r => isOwned(r.ticker || '')).length : 0
  const maxPct       = Math.max(...allRows.map(r => r.avg_portfolio_pct), 1)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Building2 size={22} className="text-amber-400" />
          Hedge Fund Consensus
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Holdings 13F — {funds.length} fondos value/quality · {allRows.length} posiciones · actualizado {genAt}
        </p>
      </div>

      {/* AI Insight */}
      {insight && (
        <div className="rounded-xl border border-amber-500/25 bg-gradient-to-r from-amber-500/8 to-transparent overflow-clip">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-amber-500/15 bg-amber-500/8">
            <Brain size={13} className="text-amber-400" />
            <span className="text-[0.62rem] font-bold text-amber-400 uppercase tracking-widest">Lectura de los 13F</span>
          </div>
          <p className="px-4 py-3 text-sm text-foreground/80 leading-relaxed">
            {insight.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
              part.startsWith('**') && part.endsWith('**')
                ? <strong key={i} className="text-amber-300 font-semibold">{part.slice(2, -2)}</strong>
                : <span key={i}>{part}</span>
            )}
          </p>
        </div>
      )}

      {/* Info banner */}
      <div className="flex items-start gap-2 px-4 py-3 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs text-amber-400/80">
        <Info size={13} className="mt-0.5 flex-shrink-0 text-amber-400" />
        <span>
          Los <strong className="text-amber-300">13F filings</strong> son declaraciones trimestrales obligatorias ante la SEC.
          Buffett, Ackman, Klarman y otros gestores con +$100M bajo gestión deben revelar sus posiciones.
          <strong className="text-amber-300"> 2+ fondos holding = convergencia de due diligence independiente.</strong>
        </span>
      </div>

      {/* Portfolio overlap */}
      {overlapCount > 0 && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg border border-primary/20 bg-primary/5 text-xs text-primary/80">
          <Wallet size={13} className="flex-shrink-0 text-primary" />
          <span>
            <strong className="text-primary">{overlapCount} de tus {myPositions.length} posiciones</strong> coinciden con holdings de hedge funds — validación de tesis independiente.
          </span>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: Building2,   label: 'Fondos rastreados', value: funds.length.toString(),                 color: 'text-amber-400' },
          { icon: TrendingUp,  label: 'Total holdings',     value: (data?.holdings_count ?? 0).toString(), color: 'text-blue-400' },
          { icon: Users2,      label: 'Consenso 2+ fondos', value: multi.toString(),                        color: 'text-emerald-400' },
          { icon: DollarSign,  label: 'Consenso 3+ fondos', value: top3.toString(),                         color: 'text-purple-400' },
        ].map(s => (
          <Card key={s.label} className="glass">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-1">
                <s.icon size={14} className={s.color} />
                <span className="text-[0.65rem] text-muted-foreground uppercase tracking-wide">{s.label}</span>
              </div>
              <div className={`text-2xl font-bold tabular-nums ${s.color}`}>{s.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Funds legend */}
      <Card className="glass">
        <CardContent className="p-4">
          <div className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wider">Fondos incluidos</div>
          <div className="flex flex-wrap gap-2">
            {funds.map(f => fundBadge(f))}
          </div>
        </CardContent>
      </Card>

      {/* Filter */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs text-muted-foreground">Mínimo fondos holding:</span>
        {[1, 2, 3].map(n => (
          <button
            key={n}
            onClick={() => setMinFunds(n)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
              minFunds === n
                ? 'bg-primary/20 border-primary/50 text-primary font-semibold'
                : 'border-border/40 text-muted-foreground hover:border-border/80'
            }`}
          >
            {n}+
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-2">{filtered.length} posiciones</span>
        <button
          onClick={() => setCompact(v => !v)}
          className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ml-auto ${
            compact
              ? 'border-primary/60 bg-primary/15 text-primary'
              : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'
          }`}
        >
          {compact ? '⊟ Compacta' : '⊞ Completa'}
        </button>
      </div>

      {filtered.length === 0 ? (
        <Card className="glass">
          <CardContent className="py-12 text-center">
            <div className="text-4xl mb-4 opacity-20">🏛️</div>
            <p className="font-medium text-muted-foreground">No hay datos disponibles. Los 13F se actualizan trimestralmente.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Mobile cards */}
          <div className="sm:hidden space-y-2 mb-2">
            {filtered.map((row, i) => {
              const fundsList = row.funds_list.split(' | ')
              const owned = isOwned(row.ticker || '')
              const isMulti = row.funds_count >= 2
              return (
                <div
                  key={`${row.ticker}-${i}`}
                  data-row-idx={i}
                  onClick={() => setFocusedIdx(i)}
                  className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform ${
                    isMulti ? 'border border-amber-500/20' : ''
                  } ${i === focusedIdx ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <TickerLogo ticker={row.ticker || ''} size="xs" />
                      <div>
                        <div className="font-mono font-bold text-[0.85rem] text-primary leading-tight flex items-center gap-1.5">
                          {row.ticker || '—'}
                          <OwnedBadge ticker={row.ticker || ''} />
                          {owned && <span className="text-[0.5rem] font-bold px-1 py-0 rounded bg-primary/15 text-primary border border-primary/25">CARTERA</span>}
                        </div>
                        <div className="text-[0.62rem] text-muted-foreground truncate max-w-[160px]">{row.company_name}</div>
                      </div>
                    </div>
                    <ConsensusBadge count={row.funds_count} />
                  </div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-[0.8rem] tabular-nums">
                      ${row.total_value_m >= 1000
                        ? `${(row.total_value_m / 1000).toFixed(1)}B`
                        : `${row.total_value_m.toLocaleString('en-US', { maximumFractionDigits: 0 })}M`}
                    </span>
                    <span className="text-[0.65rem] text-muted-foreground tabular-nums">
                      {row.avg_portfolio_pct.toFixed(1)}% cartera
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {fundsList.slice(0, 3).map(f => fundBadge(f))}
                    {fundsList.length > 3 && (
                      <span className="text-[0.6rem] text-muted-foreground/50">+{fundsList.length - 3}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden sm:block">
            <Card className="glass animate-fade-in-up">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead className="w-8">#</TableHead>
                    <TableHead>Ticker</TableHead>
                    <TableHead>Consenso</TableHead>
                    <TableHead className="text-right">Valor</TableHead>
                    {!compact && <TableHead>Concentración</TableHead>}
                    <TableHead>Fondos</TableHead>
                    {!compact && <TableHead className="text-right hidden md:table-cell">Filing</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((row, i) => {
                    const fundsList = row.funds_list.split(' | ')
                    const barWidth = Math.min(100, (row.avg_portfolio_pct / maxPct) * 100)
                    const owned = isOwned(row.ticker || '')
                    const isMulti = row.funds_count >= 2

                    return (
                      <TableRow
                        key={`${row.ticker}-${i}`}
                        data-row-idx={i}
                        onClick={() => setFocusedIdx(i)}
                        className={`cursor-pointer transition-colors ${isMulti ? 'bg-amber-500/[0.03]' : ''} ${i === focusedIdx ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                      >
                        <TableCell className="text-[0.65rem] text-muted-foreground/40 font-bold tabular-nums">
                          {i + 1}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <TickerLogo ticker={row.ticker || ''} size="xs" />
                            <div>
                              <div className="font-mono font-bold text-[0.8rem] text-primary leading-tight flex items-center gap-1.5">
                                {row.ticker || '—'}
                                <OwnedBadge ticker={row.ticker || ''} />
                                {owned && <span className="text-[0.5rem] font-bold px-1 py-0 rounded bg-primary/15 text-primary border border-primary/25">CARTERA</span>}
                              </div>
                              <div className="text-[0.62rem] text-muted-foreground truncate max-w-[140px]">{row.company_name}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <ConsensusBadge count={row.funds_count} />
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="font-bold text-[0.8rem] tabular-nums">
                            ${row.total_value_m >= 1000
                              ? `${(row.total_value_m / 1000).toFixed(1)}B`
                              : `${row.total_value_m.toLocaleString('en-US', { maximumFractionDigits: 0 })}M`}
                          </span>
                        </TableCell>
                        {!compact && (
                          <TableCell>
                            <div className="flex items-center gap-2 min-w-[100px]">
                              <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-clip">
                                <div
                                  className={`h-full rounded-full ${row.avg_portfolio_pct >= 5 ? 'bg-emerald-500' : row.avg_portfolio_pct >= 2 ? 'bg-emerald-500/70' : 'bg-emerald-500/40'}`}
                                  style={{ width: `${barWidth}%` }}
                                />
                              </div>
                              <span className="text-[0.65rem] text-muted-foreground tabular-nums w-12 text-right">
                                {row.avg_portfolio_pct.toFixed(1)}%
                              </span>
                            </div>
                          </TableCell>
                        )}
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {compact
                              ? fundsList.slice(0, 2).map(f => fundBadge(f))
                              : fundsList.map(f => fundBadge(f))
                            }
                            {compact && fundsList.length > 2 && (
                              <span className="text-[0.6rem] text-muted-foreground/50">+{fundsList.length - 2}</span>
                            )}
                          </div>
                        </TableCell>
                        {!compact && (
                          <TableCell className="text-right hidden md:table-cell">
                            <span className="text-[0.6rem] text-muted-foreground/40 tabular-nums">{row.latest_date}</span>
                          </TableCell>
                        )}
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              <div className="text-[0.6rem] text-muted-foreground/25 text-right px-3 py-1.5 border-t border-border/10">
                j / k navegar · Esc cerrar
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
