import { useState } from 'react'
import api, { fetchPortfolioTracker, fetchCorrelationMatrix, fetchPortfolioInsight, type PortfolioSummary, type CorrelationData } from '../api/client'
import { useApi } from '../hooks/useApi'
import AiNarrativeCard from '../components/AiNarrativeCard'
import TickerLogo from '../components/TickerLogo'
import Loading, { ErrorState } from '../components/Loading'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

interface SignalRow {
  ticker: string
  strategy?: string
  signal_date?: string
  signal_price?: number
  value_score?: number
  fcf_yield_pct?: number
  risk_reward_ratio?: number
  analyst_upside_pct?: number
  sector?: string
  market_regime?: string
  return_7d?: number
  return_14d?: number
  return_30d?: number
  max_drawdown_30d?: number
  win_7d?: boolean
  win_14d?: boolean
  status?: string
}

interface SignalsResponse {
  data: SignalRow[]
  count: number
}

type Performer = {
  ticker: unknown
  company_name?: unknown
  strategy?: unknown
  signal_date: unknown
  signal_price?: unknown
  return_14d: unknown
}

type RecentSignal = {
  ticker: unknown
  company_name?: unknown
  strategy?: unknown
  signal_date: unknown
  signal_price?: unknown
  sector?: unknown
  value_score?: unknown
  days_active?: unknown
  first_result_date?: unknown
}

const stratVariant = (s?: unknown): 'blue' | 'green' | 'gray' =>
  s === 'VALUE' || s === 'EU_VALUE' ? 'blue' : s === 'MOMENTUM' ? 'green' : 'gray'

const stratLabel = (s?: unknown): string =>
  s === 'EU_VALUE' ? 'EU' : s === 'VALUE' ? 'US' : s === 'MOMENTUM' ? 'MOM' : String(s ?? '')

type SortKey = keyof SignalRow
type SortDir = 'asc' | 'desc'

function retColor(v?: number) {
  if (v == null) return 'text-muted-foreground'
  if (v > 0) return 'text-emerald-400'
  if (v < 0) return 'text-red-400'
  return 'text-muted-foreground'
}

export default function Portfolio() {
  const { data, loading, error } = useApi(() => fetchPortfolioTracker(), [])
  const { data: corrData } = useApi<CorrelationData>(() => fetchCorrelationMatrix(), [])
  const { data: insightRaw } = useApi(() => fetchPortfolioInsight(), [])
  const { data: signalsData } = useApi<SignalsResponse>(
    () => api.get<SignalsResponse>('/api/portfolio-tracker/signals'),
    []
  )
  const [sigSortKey, setSigSortKey] = useState<SortKey>('signal_date')
  const [sigSortDir, setSigSortDir] = useState<SortDir>('desc')
  const [sigFilter, setSigFilter] = useState<'ALL' | 'ACTIVE' | 'COMPLETED'>('ALL')
  const [sigPage, setSigPage] = useState(1)
  const SIG_PAGE_SIZE = 30

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const pf = (data as PortfolioSummary) || {}

  if (pf.total_signals == null) {
    return (
      <>
        <div className="mb-7 animate-fade-in-up">
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Portfolio Tracker</h2>
          <p className="text-sm text-muted-foreground">Seguimiento de rendimiento de recomendaciones</p>
        </div>
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">📋</div>
            <p className="font-medium text-muted-foreground">Sin datos de portfolio disponibles</p>
          </CardContent>
        </Card>
      </>
    )
  }

  const periods = ['7d', '14d', '30d'] as const
  const overall = pf.overall || {} as Record<string, { count: number; win_rate: number; avg_return: number }>

  const bestPeriod = periods.reduce((best, p) => {
    const d = (overall as Record<string, { count: number; win_rate: number; avg_return: number }>)[p]
    const bD = (overall as Record<string, { count: number; win_rate: number; avg_return: number }>)[best]
    if (!d) return best
    if (!bD) return p
    return d.win_rate > bD.win_rate ? p : best
  }, '7d' as string)

  const recentSignals = (pf as Record<string, unknown>).recent_signals as RecentSignal[] | undefined
  const hasReturns = (pf.overall as Record<string, { count: number }>)?.['7d']?.count > 0
  const activeCount = pf.active_signals ?? 0

  // Days until first result across all active signals
  const daysToFirst = recentSignals && recentSignals.length > 0
    ? Math.max(0, 7 - Number(recentSignals[0]?.days_active ?? 7))
    : null

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Portfolio Tracker</h2>
        <p className="text-sm text-muted-foreground">
          Rendimiento de las recomendaciones VALUE y Momentum — {pf.total_signals} señales, {pf.unique_tickers} tickers
          {pf.date_range && <span className="ml-1 opacity-60">({pf.date_range})</span>}
        </p>
      </div>

      {insightRaw?.narrative && (
        <AiNarrativeCard narrative={insightRaw.narrative} label="Análisis de Rendimiento" className="mb-5" />
      )}

      {/* Win Rate Cards — shown once returns exist */}
      {hasReturns && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          {periods.map((p, idx) => {
            const d = (overall as Record<string, { count: number; win_rate: number; avg_return: number }>)[p]
            if (!d || d.count === 0) return null
            return (
              <Card key={p} className={`glass p-5 stagger-${idx + 1}`}>
                <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2 flex items-center gap-1">
                  Win Rate {p}
                  {p === bestPeriod && <Badge variant="green" className="text-[0.5rem] px-1 py-0 leading-4">BEST</Badge>}
                </div>
                <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${d.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {d.win_rate?.toFixed(1)}%
                </div>
                <div className="text-[0.66rem] text-muted-foreground">
                  Avg: <span className={d.avg_return >= 0 ? 'text-emerald-400' : 'text-red-400'}>{d.avg_return >= 0 ? '+' : ''}{d.avg_return?.toFixed(2)}%</span>
                  {' '}| {d.count} señales
                </div>
              </Card>
            )
          })}
          {pf.score_correlation != null && (
            <Card className="glass p-5 stagger-4">
              <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Correlacion Score-Return</div>
              <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${pf.score_correlation > 0.1 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {pf.score_correlation.toFixed(3)}
              </div>
              <div className="text-[0.66rem] text-muted-foreground">
                {pf.score_correlation > 0.1 ? 'Scores predicen retornos' : 'Correlacion debil'}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Waiting state — no returns yet */}
      {!hasReturns && activeCount > 0 && (
        <Card className="glass p-5 mb-5 border border-primary/20 animate-fade-in-up">
          <div className="flex items-start gap-3">
            <div className="text-2xl opacity-60 mt-0.5">⏳</div>
            <div>
              <p className="text-sm font-semibold text-foreground mb-1">
                {activeCount} señales activas — primeras métricas disponibles
                {daysToFirst !== null && daysToFirst > 0
                  ? ` en ${daysToFirst} días`
                  : ' pronto'}
              </p>
              <p className="text-xs text-muted-foreground">
                El tracker graba el precio de cada señal y calcula el retorno real a los 7, 14 y 30 días.
                Vuelve en unos días para ver el rendimiento.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Stats bar */}
      {pf.avg_max_drawdown != null && (
        <div className="grid grid-cols-2 gap-3 mb-5">
          <Card className="glass p-5">
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Avg Max Drawdown</div>
            <div className="text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 text-red-400">{pf.avg_max_drawdown.toFixed(2)}%</div>
            <div className="text-[0.66rem] text-muted-foreground">riesgo promedio</div>
          </Card>
          <Card className="glass p-5">
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Señales</div>
            <div className="text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2">{pf.total_signals}</div>
            <div className="text-[0.66rem] text-muted-foreground">{pf.unique_tickers} tickers únicos</div>
          </Card>
        </div>
      )}

      {/* Top / Worst performers */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        {pf.top_performers && pf.top_performers.length > 0 && (
          <Card className="glass">
            <div className="px-5 py-3 border-b border-border/50 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-emerald-400">Top Performers</h3>
              <Badge variant="green" className="text-[0.6rem]">{pf.top_performers.length}</Badge>
            </div>
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead>Ticker</TableHead>
                  <TableHead>Empresa</TableHead>
                  <TableHead>Return 14d</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pf.top_performers as Performer[]).map((p, i) => (
                  <TableRow key={`top_${typeof p.ticker === 'string' ? p.ticker : ''}_${i}`}>
                    <TableCell className="font-mono font-bold text-primary text-[0.8rem]">
                      <div className="flex items-center gap-1.5">
                        <TickerLogo ticker={typeof p.ticker === 'string' ? p.ticker : ''} size="xs" />
                        <span>{typeof p.ticker === 'string' ? p.ticker : ''}</span>
                      </div>
                      <Badge variant={stratVariant(p.strategy)} className="text-[0.55rem] px-1 py-0 mt-0.5">
                        {stratLabel(p.strategy)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-[0.75rem]">
                      {typeof p.company_name === 'string' ? p.company_name : typeof p.ticker === 'string' ? p.ticker : ''}
                    </TableCell>
                    <TableCell><span className="text-emerald-400 font-semibold">+{Number(p.return_14d || 0).toFixed(2)}%</span></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

        {pf.worst_performers && pf.worst_performers.length > 0 && (
          <Card className="glass">
            <div className="px-5 py-3 border-b border-border/50 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-red-400">Worst Performers</h3>
              <Badge variant="red" className="text-[0.6rem]">{pf.worst_performers.length}</Badge>
            </div>
            <Table>
              <TableHeader>
                <TableRow className="border-border/50 hover:bg-transparent">
                  <TableHead>Ticker</TableHead>
                  <TableHead>Empresa</TableHead>
                  <TableHead>Return 14d</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pf.worst_performers as Performer[]).map((p, i) => (
                  <TableRow key={`worst_${typeof p.ticker === 'string' ? p.ticker : ''}_${i}`}>
                    <TableCell className="font-mono font-bold text-primary text-[0.8rem]">
                      <div className="flex items-center gap-1.5">
                        <TickerLogo ticker={typeof p.ticker === 'string' ? p.ticker : ''} size="xs" />
                        <span>{typeof p.ticker === 'string' ? p.ticker : ''}</span>
                      </div>
                      <Badge variant={stratVariant(p.strategy)} className="text-[0.55rem] px-1 py-0 mt-0.5">
                        {stratLabel(p.strategy)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-[0.75rem]">
                      {typeof p.company_name === 'string' ? p.company_name : typeof p.ticker === 'string' ? p.ticker : ''}
                    </TableCell>
                    <TableCell><span className="text-red-400 font-semibold">{Number(p.return_14d || 0).toFixed(2)}%</span></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>

      {/* Active Signals Table — always visible */}
      {recentSignals && recentSignals.length > 0 && (
        <Card className="glass animate-fade-in-up">
          <div className="px-5 py-3 border-b border-border/50 flex items-center gap-2">
            <h3 className="text-sm font-semibold">Señales Activas</h3>
            <Badge variant="gray" className="text-[0.6rem]">{activeCount}</Badge>
            <span className="text-xs text-muted-foreground ml-auto">últimas 20</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead>Ticker</TableHead>
                <TableHead>Empresa</TableHead>
                <TableHead>Estrategia</TableHead>
                <TableHead>Sector</TableHead>
                <TableHead>Señal</TableHead>
                <TableHead className="text-right">Precio</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead>1ª Métrica</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentSignals.map((s, i) => (
                <TableRow key={`sig_${String(s.ticker)}_${i}`}>
                  <TableCell className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">
                    <div className="flex items-center gap-1.5">
                      <TickerLogo ticker={String(s.ticker || '')} size="xs" />
                      <span>{String(s.ticker || '')}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-[0.75rem] text-muted-foreground max-w-[120px] truncate">
                    {String(s.company_name ?? s.ticker ?? '')}
                  </TableCell>
                  <TableCell>
                    <Badge variant={stratVariant(s.strategy)} className="text-[0.6rem]">
                      {stratLabel(s.strategy)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[0.75rem] text-muted-foreground">{String(s.sector ?? '')}</TableCell>
                  <TableCell className="text-[0.75rem] text-muted-foreground">{String(s.signal_date ?? '')}</TableCell>
                  <TableCell className="text-right tabular-nums text-[0.8rem]">
                    ${Number(s.signal_price ?? 0).toFixed(2)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-[0.8rem] text-primary">
                    {s.value_score != null ? Number(s.value_score).toFixed(0) : '—'}
                  </TableCell>
                  <TableCell className="text-[0.75rem]">
                    <span className={Number(s.days_active ?? 0) >= 7 ? 'text-emerald-400' : 'text-amber-400'}>
                      {Number(s.days_active ?? 0) >= 7 ? '✓ lista' : `${String(s.first_result_date ?? '')}`}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Full Signal History */}
      {signalsData && signalsData.data.length > 0 && (() => {
        const onSigSort = (key: SortKey) => {
          if (sigSortKey === key) setSigSortDir(d => d === 'asc' ? 'desc' : 'asc')
          else { setSigSortKey(key); setSigSortDir('desc') }
        }
        const thS = (key: SortKey) =>
          `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground text-xs ${sigSortKey === key ? 'text-primary' : ''}`

        const sigFiltered = signalsData.data.filter(s => {
          if (sigFilter === 'ACTIVE') return s.status === 'ACTIVE'
          if (sigFilter === 'COMPLETED') return s.status !== 'ACTIVE'
          return true
        })
        const sigVisible = sigPage * SIG_PAGE_SIZE

        const sigSorted = [...sigFiltered].sort((a, b) => {
          const av = a[sigSortKey] ?? ''
          const bv = b[sigSortKey] ?? ''
          if (typeof av === 'string' && typeof bv === 'string') {
            return sigSortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
          }
          const an = Number(av); const bn = Number(bv)
          if (an < bn) return sigSortDir === 'asc' ? -1 : 1
          if (an > bn) return sigSortDir === 'asc' ? 1 : -1
          return 0
        })

        return (
          <div className="mt-6">
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-sm font-semibold">Historial de Señales</h3>
              <Badge variant="gray" className="text-[0.6rem]">{signalsData.count}</Badge>
              <div className="flex gap-1 ml-2">
                {(['ALL', 'ACTIVE', 'COMPLETED'] as const).map(f => (
                  <button
                    key={f}
                    onClick={() => { setSigFilter(f); setSigPage(1) }}
                    className={`text-[0.65rem] px-2 py-0.5 rounded border transition-colors ${sigFilter === f ? 'border-primary/60 bg-primary/15 text-primary' : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'}`}
                  >
                    {f === 'ALL' ? 'Todas' : f === 'ACTIVE' ? 'Activas' : 'Completadas'}
                  </button>
                ))}
              </div>
              <span className="text-xs text-muted-foreground ml-auto">{sigFiltered.length} señales</span>
            </div>
            <Card className="glass animate-fade-in-up">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50 hover:bg-transparent">
                    <TableHead className={thS('ticker')} onClick={() => onSigSort('ticker')}>Ticker</TableHead>
                    <TableHead className={thS('strategy')} onClick={() => onSigSort('strategy')}>Estrategia</TableHead>
                    <TableHead className={thS('signal_date')} onClick={() => onSigSort('signal_date')}>Fecha</TableHead>
                    <TableHead className={thS('signal_price')} onClick={() => onSigSort('signal_price')}>Precio Entrada</TableHead>
                    <TableHead className={thS('value_score')} onClick={() => onSigSort('value_score')}>Score</TableHead>
                    <TableHead className={thS('return_7d')} onClick={() => onSigSort('return_7d')}>Ret. 7d</TableHead>
                    <TableHead className={thS('return_14d')} onClick={() => onSigSort('return_14d')}>Ret. 14d</TableHead>
                    <TableHead className={thS('return_30d')} onClick={() => onSigSort('return_30d')}>Ret. 30d</TableHead>
                    <TableHead className={thS('max_drawdown_30d')} onClick={() => onSigSort('max_drawdown_30d')}>Max DD</TableHead>
                    <TableHead className={thS('sector')} onClick={() => onSigSort('sector')}>Sector</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sigSorted.slice(0, sigVisible).map((s, i) => (
                    <TableRow key={`${s.ticker}_${i}`}>
                      <TableCell className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">
                        <div className="flex items-center gap-1.5">
                          <TickerLogo ticker={s.ticker} size="xs" />
                          <span>{s.ticker}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={stratVariant(s.strategy)} className="text-[0.6rem]">
                          {stratLabel(s.strategy)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-[0.75rem] text-muted-foreground tabular-nums">{s.signal_date ?? '—'}</TableCell>
                      <TableCell className="text-[0.8rem] tabular-nums">
                        {s.signal_price != null ? `$${s.signal_price.toFixed(2)}` : '—'}
                      </TableCell>
                      <TableCell className="tabular-nums text-[0.8rem] text-primary">
                        {s.value_score != null ? s.value_score.toFixed(0) : '—'}
                      </TableCell>
                      <TableCell className={`tabular-nums text-[0.8rem] font-semibold ${retColor(s.return_7d)}`}>
                        {s.return_7d != null ? `${s.return_7d >= 0 ? '+' : ''}${s.return_7d.toFixed(2)}%` : '—'}
                      </TableCell>
                      <TableCell className={`tabular-nums text-[0.8rem] font-semibold ${retColor(s.return_14d)}`}>
                        {s.return_14d != null ? `${s.return_14d >= 0 ? '+' : ''}${s.return_14d.toFixed(2)}%` : '—'}
                      </TableCell>
                      <TableCell className={`tabular-nums text-[0.8rem] font-semibold ${retColor(s.return_30d)}`}>
                        {s.return_30d != null ? `${s.return_30d >= 0 ? '+' : ''}${s.return_30d.toFixed(2)}%` : '—'}
                      </TableCell>
                      <TableCell className="tabular-nums text-[0.8rem] text-red-400">
                        {s.max_drawdown_30d != null ? `${s.max_drawdown_30d.toFixed(2)}%` : '—'}
                      </TableCell>
                      <TableCell className="text-[0.75rem] text-muted-foreground max-w-[110px] truncate">{s.sector ?? '—'}</TableCell>
                      <TableCell>
                        <Badge variant={s.status === 'ACTIVE' ? 'green' : 'gray'} className="text-[0.6rem]">
                          {s.status ?? 'ACTIVE'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
            {sigVisible < sigFiltered.length && (
              <div className="mt-3 flex justify-center">
                <button
                  onClick={() => setSigPage(p => p + 1)}
                  className="text-xs px-4 py-1.5 rounded-lg border border-border/40 text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
                >
                  Ver más ({sigFiltered.length - sigVisible} restantes)
                </button>
              </div>
            )}
          </div>
        )
      })()}

      {/* Correlation Matrix */}
      {corrData && corrData.tickers.length >= 3 && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-muted-foreground mb-1 uppercase tracking-wider">
            Correlación entre picks VALUE (últimos {corrData.days}d)
          </h2>
          <p className="text-xs text-muted-foreground/60 mb-3">
            Riesgo de concentración oculto — correlación &gt;0.7 significa que los picks se mueven juntos
          </p>
          <Card className="glass border border-border/40" style={{ overflowX: 'clip' }}>
            <CardContent className="p-3">
              <table className="text-[0.62rem] border-collapse w-full">
                <thead>
                  <tr>
                    <th className="text-muted-foreground/60 font-normal p-1 text-left w-12"></th>
                    {corrData.tickers.map(t => (
                      <th key={t} className="text-muted-foreground font-mono font-semibold p-1 text-center whitespace-nowrap">{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {corrData.tickers.map((rowT, ri) => (
                    <tr key={rowT}>
                      <td className="text-muted-foreground font-mono font-semibold p-1 whitespace-nowrap">{rowT}</td>
                      {corrData.tickers.map((colT) => {
                        const val = corrData.matrix[ri]?.[colT]
                        const isDiag = rowT === colT
                        const absVal = Math.abs(val ?? 0)
                        const bg = isDiag ? 'bg-muted/20' :
                          absVal >= 0.8 ? 'bg-red-500/25' :
                          absVal >= 0.6 ? 'bg-orange-500/15' :
                          absVal >= 0.4 ? 'bg-yellow-500/10' : ''
                        const textColor = isDiag ? 'text-muted-foreground/40' :
                          absVal >= 0.8 ? 'text-red-400 font-bold' :
                          absVal >= 0.6 ? 'text-orange-400' : 'text-foreground/60'
                        return (
                          <td key={colT} className={`p-1 text-center rounded ${bg} ${textColor}`}>
                            {val != null ? val.toFixed(2) : '—'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex gap-4 mt-3 text-[0.6rem] text-muted-foreground/60">
                <span><span className="text-red-400 font-bold">■</span> &gt;0.8 — Muy correlados (riesgo alto)</span>
                <span><span className="text-orange-400">■</span> 0.6–0.8 — Correlados (vigilar)</span>
                <span><span className="text-yellow-400">■</span> 0.4–0.6 — Correlación moderada</span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
