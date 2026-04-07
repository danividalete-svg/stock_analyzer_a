import StaleDataBanner from '../components/StaleDataBanner'
import { useState } from 'react'
import { fetchMicroCapOpportunities, type MicroCapOpportunity } from '../api/client'
import EmptyState from '../components/EmptyState'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import CsvDownload from '../components/CsvDownload'
import WatchlistButton from '../components/WatchlistButton'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Gem } from 'lucide-react'

function fmt(n: number | undefined, decimals = 1) {
  if (n == null || isNaN(n)) return <span className="text-muted-foreground/30">—</span>
  const sign = n > 0 ? '+' : ''
  return <span>{sign}{n.toFixed(decimals)}</span>
}

function AiBadge({ verdict, confidence }: { verdict: string | null | undefined; confidence: number | null | undefined }) {
  if (!verdict) return null
  if (verdict === 'BUY') return (
    <span className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded border bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
      IA {confidence}
    </span>
  )
  return null
}

export default function MicroCap() {
  const { data, loading, error } = useApi(() => fetchMicroCapOpportunities(), [])
  const [showAll, setShowAll] = useState(false)

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const rows: MicroCapOpportunity[] = (data as any)?.data ?? data ?? []

  const aiAvailable = rows.some(r => r.ai_verdict != null)

  // High-conviction: AI BUY ≥65, or if no AI data yet, score ≥65 + quality contains "Excellent"/"Good"
  const highConviction = rows.filter(r => {
    if (aiAvailable) return r.ai_verdict === 'BUY' && (r.ai_confidence ?? 0) >= 65
    return (r.micro_cap_score ?? 0) >= 65
  }).sort((a, b) => (b.micro_cap_score ?? 0) - (a.micro_cap_score ?? 0))

  const displayed = showAll
    ? [...rows].sort((a, b) => (b.micro_cap_score ?? 0) - (a.micro_cap_score ?? 0))
    : highConviction

  return (
    <div className="space-y-4 p-4">
      <StaleDataBanner module="micro_cap" />

      {/* Header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Gem size={18} className="text-amber-400" />
            Micro-Cap de Calidad
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {aiAvailable
              ? `${highConviction.length} confirmadas por IA · Alta convicción únicamente`
              : `${highConviction.length} con score ≥65 · Sin filtro IA aún`}
          </p>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {!showAll ? (
            <button onClick={() => setShowAll(true)} className="filter-btn">
              Ver todas ({rows.length})
            </button>
          ) : (
            <button onClick={() => setShowAll(false)} className="filter-btn active">
              Solo IA ({highConviction.length})
            </button>
          )}
          <CsvDownload dataset="micro-cap" label="CSV" />
        </div>
      </div>

      {/* Risk warning */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/8 px-4 py-2.5 text-xs text-amber-300/80">
        ⚠️ Micro-caps con alta volatilidad. Stops ajustados, posiciones reducidas (máx 5% cartera).
      </div>

      {/* Table */}
      {displayed.length === 0 ? (
        <EmptyState
          icon="💎"
          title="Sin micro-caps de alta convicción hoy"
          subtitle={aiAvailable ? 'La IA no confirmó ninguna entrada — mercado no favorable para micro-caps' : 'Ejecuta python3 micro_cap_scanner.py para analizar el universo'}
        />
      ) : (
        <div className="glass rounded-xl overflow-clip">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead>Empresa</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>IA</TableHead>
                <TableHead>Precio</TableHead>
                <TableHead>MCap</TableHead>
                <TableHead>Piotroski</TableHead>
                <TableHead>FCF%</TableHead>
                <TableHead>Rev+%</TableHead>
                <TableHead>Objetivo</TableHead>
                <TableHead>Sector</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {displayed.map(r => {
                const mcapM = ((r.market_cap ?? 0) / 1e6).toFixed(0)
                const hasEarningsWarning = r.earnings_warning || (r.days_to_earnings != null && r.days_to_earnings >= 0 && r.days_to_earnings <= 7)
                return (
                  <TableRow key={r.ticker} className="hover:bg-white/5" title={r.ai_reasoning ?? undefined}>
                    <TableCell className="font-mono font-bold text-foreground">
                      {r.ticker}
                      {r.short_squeeze_potential === 'HIGH' && (
                        <span title="Potencial short squeeze" className="ml-1 text-xs">🚀</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[140px] truncate">
                      {r.company_name ?? '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 min-w-[80px]">
                        <ScoreBar score={r.micro_cap_score} max={100} />
                        <span className="text-xs font-bold tabular-nums">{r.micro_cap_score?.toFixed(0)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <AiBadge verdict={r.ai_verdict} confidence={r.ai_confidence} />
                    </TableCell>
                    <TableCell className="tabular-nums text-sm font-medium">
                      ${r.current_price?.toFixed(2) ?? '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-xs text-muted-foreground">
                      ${mcapM}M
                    </TableCell>
                    <TableCell className="tabular-nums text-sm text-center">
                      {r.piotroski_score != null ? (
                        <span className={r.piotroski_score >= 7 ? 'text-emerald-400 font-bold' : r.piotroski_score >= 5 ? 'text-cyan-400' : 'text-muted-foreground'}>
                          {r.piotroski_score}/9
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-sm">
                      {r.fcf_yield_pct != null ? (
                        <span className={r.fcf_yield_pct >= 5 ? 'text-emerald-400' : r.fcf_yield_pct < 0 ? 'text-red-400' : 'text-muted-foreground'}>
                          {r.fcf_yield_pct.toFixed(1)}%
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-sm">
                      {r.rev_growth_yoy != null ? (
                        <span className={r.rev_growth_yoy >= 15 ? 'text-emerald-400' : r.rev_growth_yoy < 0 ? 'text-red-400' : 'text-muted-foreground'}>
                          {fmt(r.rev_growth_yoy, 1)}%
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-sm text-muted-foreground">
                      {r.target_price_analyst ? (
                        <span className={r.analyst_upside_pct != null && r.analyst_upside_pct > 20 ? 'text-emerald-400' : ''}>
                          ${r.target_price_analyst.toFixed(2)}
                          {r.analyst_upside_pct != null && (
                            <span className="text-xs ml-1 opacity-60">({r.analyst_upside_pct.toFixed(0)}%)</span>
                          )}
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[100px] truncate">
                      {r.sector ?? '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {hasEarningsWarning && (
                          <Badge variant="outline" className="text-[0.6rem] px-1 py-0 border-amber-500/40 text-amber-400">
                            EARN
                          </Badge>
                        )}
                        <WatchlistButton ticker={r.ticker} />
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
