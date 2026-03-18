import { useState } from 'react'
import { fetchMeanReversion } from '../api/client'
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
  [key: string]: unknown
}

export default function MeanReversion() {
  const { data, loading, error } = useApi(() => fetchMeanReversion(), [])
  const { positions: myPositions } = usePersonalPortfolio()
  const [sortKey, setSortKey] = useState<string>('reversion_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [expanded, setExpanded] = useState<string | null>(null)

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const raw = data as Record<string, unknown>
  let items: MRItem[] = []
  if (Array.isArray(raw?.opportunities)) items = raw.opportunities as MRItem[]
  else if (Array.isArray(raw?.data)) items = raw.data as MRItem[]

  const sorted = [...items].sort((a, b) => {
    const av = (a[sortKey] as number) ?? 0
    const bv = (b[sortKey] as number) ?? 0
    return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  const onSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: string) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const qualVariant = (q: string): 'green' | 'blue' | 'yellow' => {
    const upper = (q || '').toUpperCase()
    if (upper.includes('EXCELENTE') || upper.includes('EXCELLENT')) return 'green'
    if (upper.includes('BUENO') || upper.includes('GOOD')) return 'blue'
    return 'yellow'
  }

  const fmtDate = (d?: string) => {
    if (!d) return '—'
    // Try to show a shorter format: YYYY-MM-DD → MM/DD
    const m = d.match(/(\d{4})-(\d{2})-(\d{2})/)
    return m ? `${m[2]}/${m[3]}` : d
  }

  const excellent = items.filter(i => (i.quality || '').toUpperCase().includes('EXCELENTE') || (i.quality || '').toUpperCase().includes('EXCELLENT')).length
  const good = items.filter(i => (i.quality || '').toUpperCase().includes('BUENO') || (i.quality || '').toUpperCase().includes('GOOD')).length
  const avgScore = items.length ? items.reduce((s, r) => s + (r.reversion_score || 0), 0) / items.length : 0
  const oversold = items.filter(i => i.rsi != null && i.rsi < 30).length
  const strategies = new Set(items.map(i => i.strategy))

  return (
    <>
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Mean Reversion</h2>
          <p className="text-sm text-muted-foreground">Oversold bounces y pullbacks — oportunidades de reversion a la media</p>
        </div>
        <CsvDownload dataset="mean-reversion" label="CSV" className="mt-1 shrink-0" />
      </div>

      {(raw?.ai_narrative as string | null | undefined) && (
        <AiNarrativeCard narrative={raw.ai_narrative as string} label="Análisis del Batch Actual" className="mb-5" />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Oportunidades', value: items.length, sub: `${strategies.size} estrategias`, idx: 1 },
          { label: 'Calidad Excelente', value: excellent, sub: `${good} buenas`, color: 'text-emerald-400', idx: 2 },
          { label: 'Score Medio', value: avgScore.toFixed(0), sub: 'reversion score', color: avgScore >= 60 ? 'text-emerald-400' : 'text-amber-400', idx: 3 },
          { label: 'RSI Oversold', value: oversold, sub: 'RSI < 30', color: 'text-blue-400', idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {/* My positions in oversold zone */}
      {(() => {
        const ownedTickers = new Set(myPositions.map(p => p.ticker))
        const myMR = items.filter(r => ownedTickers.has(r.ticker))
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
                    <TableHead>Resistencia</TableHead>
                    <TableHead>Vol x</TableHead>
                    <TableHead>RSI</TableHead>
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
                      <TableCell className="tabular-nums">{d.resistance_level != null ? `$${d.resistance_level.toFixed(2)}` : '—'}</TableCell>
                      <TableCell className="tabular-nums">
                        {d.volume_ratio != null
                          ? <span className={(d.volume_ratio as number) >= 1.5 ? 'text-emerald-400' : ''}>{Number(d.volume_ratio).toFixed(2)}x</span>
                          : '—'}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {d.rsi != null
                          ? <span className={d.rsi < 30 ? 'text-emerald-400' : ''}>{d.rsi.toFixed(0)}</span>
                          : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <p className="text-[0.65rem] text-muted-foreground mt-2">Tus posiciones en zona de rebote — considera ampliar si los fundamentales lo respaldan</p>
            </CardContent>
          </Card>
        )
      })()}

      <Card className="glass animate-fade-in-up">
        <Table>
          <TableHeader>
            <TableRow className="border-border/50 hover:bg-transparent">
              <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
              <TableHead>Estrategia</TableHead>
              <TableHead>Calidad</TableHead>
              <TableHead className={thCls('reversion_score')} onClick={() => onSort('reversion_score')}>Score</TableHead>
              <TableHead>Entry / Soporte</TableHead>
              <TableHead className={thCls('target')} onClick={() => onSort('target')}>Target</TableHead>
              <TableHead>Stop</TableHead>
              <TableHead className={thCls('rsi')} onClick={() => onSort('rsi')}>RSI</TableHead>
              <TableHead className={thCls('drawdown_pct')} onClick={() => onSort('drawdown_pct')}>Drawdown</TableHead>
              <TableHead className={thCls('volume_ratio')} onClick={() => onSort('volume_ratio')}>Vol×</TableHead>
              <TableHead>R:R</TableHead>
              <TableHead className={thCls('detected_date')} onClick={() => onSort('detected_date')}>Fecha</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.slice(0, 30).map((d, i) => (
              <>
                <TableRow
                  key={d.ticker + i}
                  className="cursor-pointer"
                  onClick={() => setExpanded(expanded === d.ticker ? null : d.ticker)}
                >
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <TickerLogo ticker={d.ticker} size="xs" />
                      <div>
                        <div className="font-mono font-bold text-primary text-[0.8rem] tracking-wide flex items-center gap-1.5">{d.ticker}<OwnedBadge ticker={d.ticker} /></div>
                        {d.company_name && d.company_name !== d.ticker && (
                          <div className="text-[0.65rem] text-muted-foreground truncate max-w-[100px]">{d.company_name}</div>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell><Badge variant="blue">{d.strategy}</Badge></TableCell>
                  <TableCell><Badge variant={qualVariant(d.quality)}>{d.quality}</Badge></TableCell>
                  <TableCell><ScoreBar score={d.reversion_score} /></TableCell>
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
                  <TableCell className="tabular-nums">{d.target ? `$${d.target.toFixed(2)}` : '—'}</TableCell>
                  <TableCell className="tabular-nums">{d.stop_loss ? `$${d.stop_loss.toFixed(2)}` : '—'}</TableCell>
                  <TableCell className="tabular-nums">
                    {d.rsi != null
                      ? <span className={d.rsi < 30 ? 'text-emerald-400' : d.rsi > 70 ? 'text-red-400' : ''}>{d.rsi.toFixed(0)}</span>
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {d.drawdown_pct != null
                      ? <span className="text-red-400">{d.drawdown_pct.toFixed(1)}%</span>
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {d.volume_ratio != null
                      ? <span className={(d.volume_ratio as number) >= 1.5 ? 'text-emerald-400' : (d.volume_ratio as number) >= 1 ? '' : 'text-muted-foreground'}>
                          {Number(d.volume_ratio).toFixed(2)}x
                        </span>
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {d.risk_reward != null
                      ? <span className={(d.risk_reward as number) >= 2 ? 'text-emerald-400' : (d.risk_reward as number) >= 1 ? 'text-amber-400' : 'text-red-400'}>{Number(d.risk_reward).toFixed(1)}</span>
                      : '—'}
                  </TableCell>
                  <TableCell className="tabular-nums text-muted-foreground text-[0.75rem]">{fmtDate(d.detected_date)}</TableCell>
                </TableRow>
                {expanded === d.ticker && (
                  <tr className="thesis-row">
                    <td colSpan={12}>
                      <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-[0.75rem]">
                        {[
                          { label: 'Soporte', value: d.support_level != null ? `$${d.support_level.toFixed(2)}` : '—' },
                          { label: 'Resistencia', value: d.resistance_level != null ? `$${d.resistance_level.toFixed(2)}` : '—' },
                          { label: 'Dist. a Soporte', value: d.distance_to_support_pct != null ? `${d.distance_to_support_pct.toFixed(1)}%` : '—' },
                          { label: 'Volumen Ratio', value: d.volume_ratio != null ? `${Number(d.volume_ratio).toFixed(2)}x` : '—' },
                          { label: 'Precio Actual', value: d.current_price != null ? `$${Number(d.current_price).toFixed(2)}` : '—' },
                          { label: 'SMA 50', value: (d as Record<string,unknown>).sma_50 != null ? `$${Number((d as Record<string,unknown>).sma_50).toFixed(2)}` : '—' },
                          { label: 'SMA 200', value: (d as Record<string,unknown>).sma_200 != null ? `$${Number((d as Record<string,unknown>).sma_200).toFixed(2)}` : '—' },
                          { label: 'Detectado', value: d.detected_date || '—' },
                        ].map(({ label, value }) => (
                          <div key={label}>
                            <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground mb-1">{label}</div>
                            <div className="font-semibold">{value}</div>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </TableBody>
        </Table>
        {items.length === 0 && (
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">🔄</div>
            <p className="font-medium text-muted-foreground">Sin oportunidades de mean reversion</p>
          </CardContent>
        )}
      </Card>
    </>
  )
}
