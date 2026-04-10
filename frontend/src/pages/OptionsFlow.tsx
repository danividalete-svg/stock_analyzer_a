import { useState, useMemo } from 'react'
import { fetchUnusualFlow, downloadCsv } from '../api/client'
import { useApi } from '../hooks/useApi'
import TickerLogo from '../components/TickerLogo'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

interface TopContract {
  side: 'CALL' | 'PUT'
  strike: number
  expiry: string
  dte: number
  volume: number
  open_interest?: number
  vol_oi_ratio?: number
  last_price: number
  last_trade_date?: string | null
  premium_usd: number
  iv?: number
  itm: boolean
  speculative: boolean
}

interface FlowResult {
  ticker: string
  signal: 'BULLISH' | 'BEARISH' | 'MIXED'
  call_pct: number
  total_call_premium: number
  total_put_premium: number
  total_premium: number
  net_premium: number
  total_call_volume: number
  total_put_volume: number
  avg_iv?: number
  unusual_score: number
  top_contracts: TopContract[]
  has_large_premium: boolean
  max_single_premium: number
  detected_at: string
}

interface FlowData {
  scan_date: string
  total_tickers_with_flow: number
  unusual_count: number
  bullish_count: number
  bearish_count: number
  results: FlowResult[]
}

const fmtPremium = (v?: number) => {
  if (v == null) return '—'
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

const fmtIV = (v?: number) => v != null ? `${(v * 100).toFixed(0)}%` : '—'

function SignalBadge({ signal }: { signal: string }) {
  const cls =
    signal === 'BULLISH' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
    signal === 'BEARISH' ? 'bg-red-500/15 text-red-400 border-red-500/30' :
    'bg-yellow-500/15 text-yellow-400 border-yellow-500/30'
  const icon = signal === 'BULLISH' ? '🟢' : signal === 'BEARISH' ? '🔴' : '⚪'
  return (
    <span className={`inline-flex items-center gap-1 text-[0.68rem] font-bold px-1.5 py-0.5 rounded border ${cls}`}>
      {icon} {signal}
    </span>
  )
}

function CallPutBar({ callPct }: { callPct: number }) {
  const putPct = 100 - callPct
  return (
    <div className="flex items-center gap-1.5 min-w-[90px]">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden bg-muted/30 flex">
        <div className="bg-emerald-500/70 h-full" style={{ width: `${callPct}%` }} />
        <div className="bg-red-500/70 h-full" style={{ width: `${putPct}%` }} />
      </div>
      <span className="text-[0.6rem] text-muted-foreground tabular-nums w-16 text-right">
        <span className="text-emerald-400/80">{callPct.toFixed(0)}C</span>
        {' / '}
        <span className="text-red-400/80">{putPct.toFixed(0)}P</span>
      </span>
    </div>
  )
}

function ContractRow({ c }: { c: TopContract }) {
  const isCall = c.side === 'CALL'
  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[0.62rem] py-0.5 ${isCall ? 'text-emerald-400/80' : 'text-red-400/80'}`}>
      <span className="font-bold w-8">{c.side}</span>
      <span className="font-mono">${c.strike}</span>
      <span className="text-muted-foreground">{c.expiry} ({c.dte}d)</span>
      <span className="text-muted-foreground">vol {c.volume.toLocaleString()}</span>
      {c.vol_oi_ratio != null && (
        <span className="text-muted-foreground">v/OI {c.vol_oi_ratio.toFixed(1)}x</span>
      )}
      <span className="font-bold">{fmtPremium(c.premium_usd)}</span>
      {c.iv != null && <span className="text-muted-foreground">IV {fmtIV(c.iv)}</span>}
      {c.speculative && <span className="text-yellow-400/80 font-semibold">⚡SWEEP</span>}
      {c.itm && <span className="text-muted-foreground/60">[ITM]</span>}
      {c.last_trade_date && (
        <span className="text-muted-foreground/50 ml-1">
          {c.last_trade_date.includes('T') ? c.last_trade_date.slice(0, 16).replace('T', ' ') : c.last_trade_date}
        </span>
      )}
    </div>
  )
}

export default function OptionsFlow() {
  const { data, loading, error } = useApi(() => fetchUnusualFlow(), [])
  const [sortKey, setSortKey] = useState<keyof FlowResult>('total_premium')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [signalFilter, setSignalFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'MIXED'>('ALL')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [onlyLarge, setOnlyLarge] = useState(false)

  const raw = data as FlowData | null
  const results: FlowResult[] = raw?.results ?? []

  const filtered = useMemo(() => {
    let r = results
    if (signalFilter !== 'ALL') r = r.filter(x => x.signal === signalFilter)
    if (onlyLarge) r = r.filter(x => x.has_large_premium)
    return [...r].sort((a, b) => {
      const av = (a[sortKey] as number) ?? 0
      const bv = (b[sortKey] as number) ?? 0
      return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
    })
  }, [results, signalFilter, onlyLarge, sortKey, sortDir])

  const onSort = (key: keyof FlowResult) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: keyof FlowResult) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const totalPremium = results.reduce((s, r) => s + r.total_premium, 0)
  const scanDate = raw?.scan_date ? new Date(raw.scan_date) : null

  return (
    <>
      <div className="mb-6 animate-fade-in-up flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-extrabold tracking-tight mb-1 gradient-title">Unusual Options Flow</h2>
          <p className="text-sm text-muted-foreground">
            Actividad inusual de opciones — sweeps, bloques grandes, sesgo direccional
            {scanDate && (
              <span className="ml-2 opacity-50 text-xs">
                · {scanDate.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })} ET
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => downloadCsv('unusual-flow')}
          className="text-xs px-3 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary transition-colors shrink-0"
        >↓ CSV</button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Tickers con flujo', value: raw?.total_tickers_with_flow ?? 0, sub: 'con actividad opciones', idx: 1 },
          { label: 'Bullish', value: raw?.bullish_count ?? 0, sub: 'calls dominan', color: 'text-emerald-400', idx: 2 },
          { label: 'Bearish', value: raw?.bearish_count ?? 0, sub: 'puts dominan', color: 'text-red-400', idx: 3 },
          { label: 'Premium Total', value: fmtPremium(totalPremium), sub: `${raw?.unusual_count ?? 0} con bloque >$100K`, idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        {(['ALL', 'BULLISH', 'BEARISH', 'MIXED'] as const).map(f => (
          <button
            key={f}
            onClick={() => setSignalFilter(f)}
            className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ${
              signalFilter === f
                ? f === 'BULLISH' ? 'border-emerald-500/60 bg-emerald-500/15 text-emerald-400'
                  : f === 'BEARISH' ? 'border-red-500/60 bg-red-500/15 text-red-400'
                  : 'border-primary/60 bg-primary/15 text-primary'
                : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'
            }`}
          >
            {f === 'ALL' ? `Todos (${results.length})` : `${f === 'BULLISH' ? '🟢' : f === 'BEARISH' ? '🔴' : '⚪'} ${f}`}
          </button>
        ))}
        <button
          onClick={() => setOnlyLarge(v => !v)}
          className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ${
            onlyLarge ? 'border-yellow-500/60 bg-yellow-500/10 text-yellow-400' : 'border-border/40 text-muted-foreground hover:border-border/70'
          }`}
        >
          ⚡ Solo bloques &gt;$100K
        </button>
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden space-y-2 mb-2">
        {filtered.slice(0, 20).map(r => (
          <div
            key={r.ticker}
            onClick={() => setExpanded(expanded === r.ticker ? null : r.ticker)}
            className="glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <TickerLogo ticker={r.ticker} size="xs" />
                <span className="font-mono font-bold text-sm text-primary">{r.ticker}</span>
              </div>
              <SignalBadge signal={r.signal} />
            </div>
            <div className="flex items-center justify-between mb-2">
              <CallPutBar callPct={r.call_pct} />
              <span className="text-xs font-mono font-bold">{fmtPremium(r.total_premium)}</span>
            </div>
            {expanded === r.ticker && r.top_contracts.map((c, i) => (
              <ContractRow key={i} c={c} />
            ))}
          </div>
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden sm:block">
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
                <TableHead>Señal</TableHead>
                <TableHead>Calls / Puts</TableHead>
                <TableHead className={thCls('total_premium')} onClick={() => onSort('total_premium')}>Premium Total</TableHead>
                <TableHead className={thCls('max_single_premium')} onClick={() => onSort('max_single_premium')}>Mayor Contrato</TableHead>
                <TableHead className={thCls('unusual_score')} onClick={() => onSort('unusual_score')}>Score</TableHead>
                <TableHead>Top Contratos</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(r => (
                <>
                  <TableRow
                    key={r.ticker}
                    className="cursor-pointer hover:bg-muted/5 transition-colors"
                    onClick={() => setExpanded(expanded === r.ticker ? null : r.ticker)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <TickerLogo ticker={r.ticker} size="xs" />
                        <span className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{r.ticker}</span>
                        {r.has_large_premium && <span className="text-yellow-400 text-[0.6rem]">⚡</span>}
                      </div>
                    </TableCell>
                    <TableCell><SignalBadge signal={r.signal} /></TableCell>
                    <TableCell><CallPutBar callPct={r.call_pct} /></TableCell>
                    <TableCell className="tabular-nums font-semibold">{fmtPremium(r.total_premium)}</TableCell>
                    <TableCell className="tabular-nums text-muted-foreground">{fmtPremium(r.max_single_premium)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-16 rounded-full bg-muted/20 overflow-clip">
                          <div className="h-full bg-primary/60 rounded-full" style={{ width: `${r.unusual_score}%` }} />
                        </div>
                        <span className="text-[0.65rem] tabular-nums text-muted-foreground">{r.unusual_score}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-[0.65rem]">
                      {r.top_contracts.slice(0, 1).map((c, i) => (
                        <span key={i} className={c.side === 'CALL' ? 'text-emerald-400/70' : 'text-red-400/70'}>
                          {c.side} ${c.strike} {c.expiry} {fmtPremium(c.premium_usd)}
                          {c.speculative && ' ⚡'}
                        </span>
                      ))}
                      {r.top_contracts.length > 1 && (
                        <span className="text-muted-foreground/40 ml-1">+{r.top_contracts.length - 1}</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {expanded === r.ticker && (
                    <TableRow key={`${r.ticker}-expanded`} className="bg-muted/5">
                      <TableCell colSpan={7} className="py-3 px-4">
                        <div className="space-y-1">
                          {r.top_contracts.map((c, i) => <ContractRow key={i} c={c} />)}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
          {filtered.length === 0 && (
            <CardContent className="py-16 text-center">
              <div className="text-4xl mb-4 opacity-20">📊</div>
              <p className="font-medium text-muted-foreground">
                {results.length === 0
                  ? 'Esperando datos del scanner (corre cada 30 min en mercado abierto)'
                  : 'Ningún ticker pasa el filtro seleccionado'}
              </p>
            </CardContent>
          )}
        </Card>
      </div>
    </>
  )
}
