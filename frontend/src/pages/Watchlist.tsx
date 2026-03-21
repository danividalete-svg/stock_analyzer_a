import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Star, Trash2, StickyNote, ChevronRight, Brain } from 'lucide-react'
import { useWatchlist, type WatchlistEntry } from '../hooks/useWatchlist'
import { fetchValueOpportunities, fetchEUValueOpportunities, fetchCerebroAlerts, type CerebroAlert } from '../api/client'
import { useApi } from '../hooks/useApi'
import { useCerebroSignals } from '../hooks/useCerebroSignals'
import CerebroBadges from '../components/CerebroBadges'
import GradeBadge from '../components/GradeBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

function fmt(n: number | undefined | null, dec = 1) {
  if (n == null) return '—'
  return n.toFixed(dec)
}

function NoteEditor({ entry, onSave }: { entry: WatchlistEntry; onSave: (note: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(entry.note ?? '')

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="text-[0.65rem] text-muted-foreground/50 hover:text-foreground transition-colors flex items-center gap-1"
        title={entry.note || 'Añadir nota'}
      >
        <StickyNote size={11} />
        {entry.note ? <span className="truncate max-w-[100px]">{entry.note}</span> : <span>nota</span>}
      </button>
    )
  }

  return (
    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
      <input
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') { onSave(val); setEditing(false) }
          if (e.key === 'Escape') { setVal(entry.note ?? ''); setEditing(false) }
        }}
        className="text-[0.7rem] px-1.5 py-0.5 rounded border border-border/50 bg-transparent text-foreground w-28 focus:outline-none focus:border-primary/50"
        placeholder="Nota..."
      />
      <button
        onClick={() => { onSave(val); setEditing(false) }}
        className="text-[0.65rem] text-primary hover:text-primary/80 transition-colors"
      >
        OK
      </button>
    </div>
  )
}

type LiveEntry = { value_score: number; conviction_grade?: string }

function alertSeverityStyle(severity: string) {
  if (severity === 'HIGH') return 'text-red-400 bg-red-500/10 border-red-500/30'
  if (severity === 'MEDIUM') return 'text-amber-400 bg-amber-500/10 border-amber-500/30'
  return 'text-blue-400 bg-blue-500/10 border-blue-500/30'
}

function WatchlistAlerts({ alerts, watchlistTickers, loading }: Readonly<{
  alerts: CerebroAlert[] | undefined
  watchlistTickers: Set<string>
  loading: boolean
}>) {
  const filtered = (alerts ?? [])
    .filter(a => watchlistTickers.has(a.ticker.toUpperCase()))
    .sort((a, b) => {
      const sev = { HIGH: 0, MEDIUM: 1, LOW: 2 }
      return (sev[a.severity] ?? 2) - (sev[b.severity] ?? 2)
    })

  if (!loading && filtered.length === 0) return null

  return (
    <div className="mb-5 animate-fade-in-up">
      <div className="flex items-center gap-2 mb-2 px-1">
        <Brain size={13} className="text-purple-400" />
        <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Alertas Cerebro IA</span>
        {!loading && filtered.length > 0 && (
          <span className="text-[0.6rem] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary font-bold">{filtered.length}</span>
        )}
      </div>
      <Card className="glass p-4">
        {loading ? (
          <div className="space-y-2">{['a','b','c'].map(k => <Skeleton key={k} className="h-8 w-full" />)}</div>
        ) : (
          <div className="space-y-1.5">
            {filtered.map(a => (
              <div key={`${a.ticker}-${a.type}`} className={`flex items-start gap-2 px-3 py-2 rounded-md border ${alertSeverityStyle(a.severity)}`}>
                <span className="text-[0.55rem] font-bold uppercase mt-0.5 shrink-0">{a.severity}</span>
                <div className="flex-1 min-w-0">
                  <span className="font-mono font-bold text-[0.78rem] mr-1.5">{a.ticker}</span>
                  <span className="text-[0.72rem] font-semibold">{a.title}</span>
                  <p className="text-[0.66rem] text-muted-foreground mt-0.5 leading-relaxed">{a.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

export default function Watchlist() {
  const { entries, remove, updateNote } = useWatchlist()
  const [sortKey, setSortKey] = useState<keyof WatchlistEntry>('added_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [liveMap, setLiveMap] = useState<Record<string, LiveEntry>>({})
  const { data: cerebroAlertsRaw, loading: loadingAlerts } = useApi(() => fetchCerebroAlerts(), [])
  const cerebro = useCerebroSignals()
  const watchlistTickers = new Set(entries.map(e => e.ticker.toUpperCase()))

  useEffect(() => {
    Promise.all([fetchValueOpportunities(), fetchEUValueOpportunities()])
      .then(([us, eu]) => {
        const map: Record<string, LiveEntry> = {}
        for (const item of [...(us.data.data ?? []), ...(eu.data.data ?? [])]) {
          map[item.ticker] = { value_score: item.value_score, conviction_grade: item.conviction_grade }
        }
        setLiveMap(map)
      })
      .catch(() => {})
  }, [])

  const onSort = (key: keyof WatchlistEntry) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: keyof WatchlistEntry) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const sorted = [...entries].sort((a, b) => {
    const av = a[sortKey] ?? ''
    const bv = b[sortKey] ?? ''
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    const an = Number(av); const bn = Number(bv)
    if (an < bn) return sortDir === 'asc' ? -1 : 1
    if (an > bn) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  return (
    <>
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 flex items-center gap-2">
            <Star size={20} className="text-amber-400" strokeWidth={1.75} />
            <span className="gradient-title">Watchlist</span>
          </h2>
          <p className="text-sm text-muted-foreground">
            Tickers guardados · {entries.length} {entries.length === 1 ? 'ticker' : 'tickers'} · Guardado localmente
          </p>
        </div>
      </div>

      <WatchlistAlerts
        alerts={cerebroAlertsRaw?.alerts}
        watchlistTickers={watchlistTickers}
        loading={loadingAlerts}
      />

      {entries.length === 0 ? (
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <Star size={40} strokeWidth={1.25} className="text-muted-foreground/20 mx-auto mb-4" />
            <p className="font-medium text-muted-foreground mb-2">Tu watchlist está vacía</p>
            <p className="text-xs text-muted-foreground/60 mb-5">
              Añade tickers desde VALUE US, VALUE EU o Buscar Ticker pulsando la estrella ★
            </p>
            <div className="flex gap-2 justify-center flex-wrap">
              {[
                { to: '/value',    label: 'VALUE US' },
                { to: '/value-eu', label: 'VALUE EU' },
                { to: '/search',   label: 'Buscar Ticker' },
              ].map(l => (
                <Link
                  key={l.to}
                  to={l.to}
                  className="flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
                >
                  {l.label} <ChevronRight size={11} />
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
                <TableHead className={`hidden sm:table-cell ${thCls('company_name')}`} onClick={() => onSort('company_name')}>Empresa</TableHead>
                <TableHead className={`hidden md:table-cell ${thCls('sector')}`} onClick={() => onSort('sector')}>Sector</TableHead>
                <TableHead className={`hidden sm:table-cell ${thCls('current_price')}`} onClick={() => onSort('current_price')}>Precio</TableHead>
                <TableHead className={`hidden md:table-cell ${thCls('value_score')}`} onClick={() => onSort('value_score')}>Score</TableHead>
                <TableHead>Hoy</TableHead>
                <TableHead>Grade</TableHead>
                <TableHead className={`hidden sm:table-cell ${thCls('analyst_upside_pct')}`} onClick={() => onSort('analyst_upside_pct')}>Upside</TableHead>
                <TableHead className={`hidden sm:table-cell ${thCls('fcf_yield_pct')}`} onClick={() => onSort('fcf_yield_pct')}>FCF%</TableHead>
                <TableHead className={`hidden md:table-cell ${thCls('added_at')}`} onClick={() => onSort('added_at')}>Añadido</TableHead>
                <TableHead className="hidden sm:table-cell">Nota</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map(e => (
                <TableRow key={e.ticker}>
                  <TableCell className="font-mono font-bold text-amber-400 text-[0.8rem] tracking-wide">
                    <Link to={`/search?q=${e.ticker}`} className="hover:underline">{e.ticker}</Link>
                    <CerebroBadges
                      trapInfo={cerebro.trapMap[e.ticker]}
                      smInfo={cerebro.smMap[e.ticker]}
                      exitInfo={cerebro.exitMap[e.ticker]}
                      divInfo={cerebro.divMap[e.ticker]}
                      piotrInfo={cerebro.piotrMap[e.ticker]}
                    />
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-[0.76rem] text-muted-foreground max-w-[140px] truncate">
                    {e.company_name || '—'}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-[0.75rem] text-muted-foreground">{e.sector || '—'}</TableCell>
                  <TableCell className="hidden sm:table-cell tabular-nums text-[0.8rem]">
                    {e.current_price != null ? `$${e.current_price.toFixed(2)}` : '—'}
                  </TableCell>
                  <TableCell className="hidden md:table-cell tabular-nums text-[0.8rem] text-muted-foreground font-semibold">
                    {e.value_score != null ? fmt(e.value_score, 0) : '—'}
                  </TableCell>
                  <TableCell>
                    {liveMap[e.ticker] ? (
                      <div className="flex items-center gap-1">
                        <Badge variant="green" className="text-[0.6rem] px-1.5 py-0.5">EN VALUE</Badge>
                        <span className="text-[0.75rem] font-semibold text-emerald-400 tabular-nums">
                          {liveMap[e.ticker].value_score.toFixed(0)}
                        </span>
                      </div>
                    ) : (
                      <span className="text-[0.7rem] text-muted-foreground/40">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <GradeBadge grade={liveMap[e.ticker]?.conviction_grade ?? e.conviction_grade} />
                  </TableCell>
                  <TableCell className={`hidden sm:table-cell tabular-nums text-[0.8rem] font-semibold ${e.analyst_upside_pct != null && e.analyst_upside_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {e.analyst_upside_pct != null ? `${e.analyst_upside_pct >= 0 ? '+' : ''}${e.analyst_upside_pct.toFixed(1)}%` : '—'}
                  </TableCell>
                  <TableCell className={`hidden sm:table-cell tabular-nums text-[0.8rem] ${e.fcf_yield_pct != null && e.fcf_yield_pct >= 5 ? 'text-emerald-400' : ''}`}>
                    {e.fcf_yield_pct != null ? `${e.fcf_yield_pct.toFixed(1)}%` : '—'}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-[0.72rem] text-muted-foreground tabular-nums">
                    {new Date(e.added_at).toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <NoteEditor entry={e} onSave={note => updateNote(e.ticker, note)} />
                  </TableCell>
                  <TableCell>
                    <button
                      onClick={() => remove(e.ticker)}
                      className="text-muted-foreground/40 hover:text-red-400 transition-colors"
                      title="Eliminar de watchlist"
                    >
                      <Trash2 size={13} />
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  )
}
