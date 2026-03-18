import { useState, useMemo } from 'react'
import { fetchEarningsCalendar } from '../api/client'
import type { EarningsEntry } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Calendar, AlertTriangle, Zap, TrendingUp, Wallet } from 'lucide-react'
import TickerLogo from '../components/TickerLogo'
import OwnedBadge from '../components/OwnedBadge'
import { usePersonalPortfolio } from '../context/PersonalPortfolioContext'

type FilterMode = 'all' | 'warning' | 'catalyst'

function daysLabel(days: number | null): string {
  if (days === null) return '—'
  if (days === 0) return 'Hoy'
  if (days === 1) return 'Mañana'
  return `${days}d`
}

function urgencyColor(days: number | null, warning: boolean): string {
  if (warning || (days !== null && days <= 7)) return 'text-red-400'
  if (days !== null && days <= 14) return 'text-orange-400'
  if (days !== null && days <= 30) return 'text-yellow-400'
  return 'text-muted-foreground'
}

function urgencyBg(days: number | null, warning: boolean): string {
  if (warning || (days !== null && days <= 7)) return 'bg-red-500/10 border-red-500/20'
  if (days !== null && days <= 14) return 'bg-orange-500/10 border-orange-500/20'
  if (days !== null && days <= 30) return 'bg-yellow-500/10 border-yellow-500/20'
  return 'bg-card/50 border-border/40'
}

// Group entries by date
function groupByDate(entries: EarningsEntry[]): Record<string, EarningsEntry[]> {
  const groups: Record<string, EarningsEntry[]> = {}
  for (const e of entries) {
    if (!groups[e.earnings_date]) groups[e.earnings_date] = []
    groups[e.earnings_date].push(e)
  }
  return groups
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })
  } catch {
    return dateStr
  }
}

export default function EarningsCalendar() {
  const { data, loading, error } = useApi(() => fetchEarningsCalendar(), [])
  const [filter, setFilter] = useState<FilterMode>('all')
  const [search, setSearch] = useState('')
  const { positions: myPositions } = usePersonalPortfolio()

  const filtered = useMemo(() => {
    if (!data?.earnings) return []
    let rows = data.earnings
    if (filter === 'warning') rows = rows.filter(r => r.earnings_warning)
    if (filter === 'catalyst') rows = rows.filter(r => r.earnings_catalyst)
    if (search.trim()) {
      const q = search.trim().toUpperCase()
      rows = rows.filter(r => r.ticker.includes(q) || r.company.toUpperCase().includes(q) || r.sector.toUpperCase().includes(q))
    }
    return rows
  }, [data, filter, search])

  const grouped = useMemo(() => groupByDate(filtered), [filtered])
  const sortedDates = Object.keys(grouped).sort()

  const myTickers = useMemo(() => new Set(myPositions.map(p => p.ticker.toUpperCase())), [myPositions])
  const myEarnings = useMemo(() => {
    if (!data?.earnings || myTickers.size === 0) return []
    return data.earnings
      .filter(e => myTickers.has(e.ticker.toUpperCase()))
      .sort((a, b) => (a.days_to_earnings ?? 999) - (b.days_to_earnings ?? 999))
  }, [data, myTickers])

  const warningCount = data?.earnings.filter(e => e.earnings_warning).length ?? 0
  const catalystCount = data?.earnings.filter(e => e.earnings_catalyst).length ?? 0
  const within7d = data?.earnings.filter(e => e.days_to_earnings !== null && e.days_to_earnings <= 7).length ?? 0

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />
  if (!data) return <ErrorState message="Sin datos de earnings" />

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground mb-1">Earnings Calendar</h1>
          <p className="text-sm text-muted-foreground">
            Próximos reportes de resultados — evita entrar antes de earnings sin catalizador
          </p>
        </div>
        <span className="text-xs text-muted-foreground self-start sm:self-center">
          {data.total} tickers · {data.as_of}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="glass border border-border/50">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-red-400">{within7d}</div>
              <div className="text-xs text-muted-foreground">Earnings en 7 días</div>
            </div>
          </CardContent>
        </Card>
        <Card className="glass border border-border/50">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertTriangle size={18} className="text-orange-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-orange-400">{warningCount}</div>
              <div className="text-xs text-muted-foreground">Con alerta activa</div>
            </div>
          </CardContent>
        </Card>
        <Card className="glass border border-border/50">
          <CardContent className="p-4 flex items-center gap-3">
            <Zap size={18} className="text-emerald-400 flex-shrink-0" />
            <div>
              <div className="text-xl font-bold text-emerald-400">{catalystCount}</div>
              <div className="text-xs text-muted-foreground">Posible catalizador</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* My Portfolio Earnings */}
      {myEarnings.length > 0 && (
        <Card className="glass border border-primary/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Wallet size={14} className="text-primary" />
              <span className="text-[0.62rem] font-bold uppercase tracking-widest text-primary/70">Earnings de Mi Cartera</span>
              <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">{myEarnings.length}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {myEarnings.map(entry => (
                <div
                  key={entry.ticker}
                  className={`flex items-center gap-2.5 p-2.5 rounded-lg border ${urgencyBg(entry.days_to_earnings, entry.earnings_warning)}`}
                >
                  <TickerLogo ticker={entry.ticker} size="xs" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-sm text-primary">{entry.ticker}</span>
                      <span className="text-[0.65rem] text-muted-foreground truncate">{entry.company}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[0.65rem] text-muted-foreground">{formatDate(entry.earnings_date)}</span>
                      {entry.earnings_warning && (
                        <span className="text-[0.58rem] font-semibold text-red-400 flex items-center gap-0.5">
                          <AlertTriangle size={8} /> Alerta
                        </span>
                      )}
                      {entry.earnings_catalyst && (
                        <span className="text-[0.58rem] font-semibold text-emerald-400 flex items-center gap-0.5">
                          <Zap size={8} /> Catalizador
                        </span>
                      )}
                    </div>
                  </div>
                  <div className={`text-lg font-bold tabular-nums shrink-0 ${urgencyColor(entry.days_to_earnings, entry.earnings_warning)}`}>
                    {daysLabel(entry.days_to_earnings)}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          type="text"
          placeholder="Buscar ticker, empresa, sector..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 px-3 py-2 text-sm rounded-lg bg-card/60 border border-border/50 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/40"
        />
        <div className="flex gap-1">
          {([
            { key: 'all',      label: 'Todos' },
            { key: 'warning',  label: 'Alerta' },
            { key: 'catalyst', label: 'Catalizador' },
          ] as { key: FilterMode; label: string }[]).map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
                filter === f.key
                  ? 'bg-primary/15 border-primary/30 text-primary'
                  : 'bg-card/40 border-border/40 text-muted-foreground hover:text-foreground'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grouped by date */}
      {sortedDates.length === 0 ? (
        <Card className="glass border border-border/40">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            Sin earnings próximos con los filtros actuales
          </CardContent>
        </Card>
      ) : (
        sortedDates.map(date => (
          <div key={date}>
            {/* Date header */}
            <div className="flex items-center gap-2 mb-2">
              <Calendar size={13} className="text-muted-foreground" />
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                {formatDate(date)}
              </span>
              <span className="text-xs text-muted-foreground/50">
                — {grouped[date].length} empresa{grouped[date].length !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="space-y-1.5 mb-5">
              {grouped[date].map(entry => (
                <Card
                  key={entry.ticker}
                  className={`glass border ${urgencyBg(entry.days_to_earnings, entry.earnings_warning)}`}
                >
                  <CardContent className="p-3">
                    <div className="flex items-center gap-3 flex-wrap">
                      {/* Ticker + company */}
                      <div className="flex items-center gap-1.5 min-w-[80px]">
                        <TickerLogo ticker={entry.ticker} size="xs" />
                        <span className="font-mono font-bold text-sm text-primary">{entry.ticker}</span>
                        <OwnedBadge ticker={entry.ticker} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-xs text-foreground/80 truncate">{entry.company}</span>
                        <span className="text-xs text-muted-foreground/60 ml-2">{entry.sector}</span>
                      </div>

                      {/* Days countdown */}
                      <div className={`text-sm font-bold min-w-[40px] text-right ${urgencyColor(entry.days_to_earnings, entry.earnings_warning)}`}>
                        {daysLabel(entry.days_to_earnings)}
                      </div>

                      {/* Badges */}
                      <div className="flex items-center gap-1.5">
                        {entry.earnings_warning && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.62rem] font-semibold bg-red-500/15 text-red-400 border border-red-500/20">
                            <AlertTriangle size={9} /> Alerta
                          </span>
                        )}
                        {entry.earnings_catalyst && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[0.62rem] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                            <Zap size={9} /> Catalizador
                          </span>
                        )}
                        {entry.fundamental_score != null && (
                          <span className="text-[0.62rem] text-muted-foreground/60 ml-1">
                            Fund: <span className="text-foreground/70 font-medium">{entry.fundamental_score.toFixed(0)}</span>
                          </span>
                        )}
                        {entry.analyst_upside_pct != null && (
                          <span className={`text-[0.62rem] font-medium ${entry.analyst_upside_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            <TrendingUp size={9} className="inline mr-0.5" />
                            {entry.analyst_upside_pct >= 0 ? '+' : ''}{entry.analyst_upside_pct.toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        ))
      )}

      {/* Legend */}
      <Card className="glass border border-border/30">
        <CardContent className="p-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <span>Earnings en ≤7 días — evitar entrada nueva</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-orange-400" />
            <span>8–14 días — precaución</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Zap size={10} className="text-emerald-400" />
            <span>Catalizador — earnings puede impulsar precio</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
