import { useState } from 'react'
import { fetchHedgeFunds, type HedgeFundConsensusItem } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Building2, TrendingUp, DollarSign, Users2, Info } from 'lucide-react'
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

function HoldingRow({ row, rank }: { row: HedgeFundConsensusItem; rank: number }) {
  const funds = row.funds_list.split(' | ')
  const barWidth = Math.min(100, (row.avg_portfolio_pct / 15) * 100)

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 border-b border-border/20 last:border-0 hover:bg-muted/5 transition-colors">
      {/* Rank + Ticker */}
      <div className="flex items-center gap-2 min-w-[160px]">
        <span className="text-[0.6rem] text-muted-foreground/40 font-bold w-4 tabular-nums">#{rank}</span>
        <TickerLogo ticker={row.ticker || ''} size="xs" />
        <div>
          <div className="font-mono font-bold text-sm text-primary leading-tight flex items-center gap-1.5">{row.ticker || '—'}<OwnedBadge ticker={row.ticker || ''} /></div>
          <div className="text-[0.65rem] text-muted-foreground truncate max-w-[160px]">{row.company_name}</div>
        </div>
      </div>

      {/* Consensus badge */}
      <ConsensusBadge count={row.funds_count} />

      {/* Value held */}
      <div className="flex items-center gap-1 text-xs text-muted-foreground min-w-[90px]">
        <DollarSign size={11} className="text-muted-foreground/50" />
        <span className="font-bold text-foreground tabular-nums">${row.total_value_m.toLocaleString('en-US', { maximumFractionDigits: 0 })}M</span>
      </div>

      {/* Avg portfolio % bar */}
      <div className="flex items-center gap-2 min-w-[130px]">
        <div className="flex-1 h-1 rounded-full bg-muted/30 overflow-hidden w-20">
          <div
            className="h-full rounded-full bg-emerald-500/70"
            style={{ width: `${barWidth}%` }}
          />
        </div>
        <span className="text-[0.65rem] text-muted-foreground tabular-nums">{row.avg_portfolio_pct.toFixed(1)}% avg</span>
      </div>

      {/* Fund badges */}
      <div className="flex flex-wrap gap-1 flex-1 min-w-[200px]">
        {funds.map(f => fundBadge(f))}
      </div>

      {/* Latest date */}
      <div className="text-[0.6rem] text-muted-foreground/40 ml-auto">{row.latest_date}</div>
    </div>
  )
}

export default function HedgeFunds() {
  const { data, loading, error } = useApi(() => fetchHedgeFunds(), [])
  const [minFunds, setMinFunds] = useState(1)

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const allRows  = data?.top_consensus ?? []
  const funds    = data?.funds_scraped ?? []
  const genAt    = data?.generated_at ? new Date(data.generated_at).toLocaleDateString('es-ES') : '—'

  const filtered = allRows.filter(r => r.funds_count >= minFunds)
  const multi    = allRows.filter(r => r.funds_count >= 2).length
  const top3     = allRows.filter(r => r.funds_count >= 3).length

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

      {/* Info banner */}
      <div className="flex items-start gap-2 px-4 py-3 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs text-amber-400/80">
        <Info size={13} className="mt-0.5 flex-shrink-0 text-amber-400" />
        <span>
          Los <strong className="text-amber-300">13F filings</strong> son declaraciones trimestrales obligatorias ante la SEC.
          Buffett, Ackman, Klarman y otros gestores con +$100M bajo gestión deben revelar sus posiciones.
          <strong className="text-amber-300"> 2+ fondos holding = convergencia de due diligence independiente.</strong>
        </span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: Building2,   label: 'Fondos rastreados', value: funds.length.toString(),            color: 'text-amber-400' },
          { icon: TrendingUp,  label: 'Total holdings',     value: (data?.holdings_count ?? 0).toString(), color: 'text-blue-400' },
          { icon: Users2,      label: 'Consenso 2+ fondos', value: multi.toString(),                   color: 'text-emerald-400' },
          { icon: DollarSign,  label: 'Consenso 3+ fondos', value: top3.toString(),                    color: 'text-purple-400' },
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
      <div className="flex items-center gap-3">
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
      </div>

      {/* Table */}
      <Card className="glass overflow-hidden">
        <CardContent className="p-0">
          {/* Header — column widths must match HoldingRow flex layout */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 border-b border-border/30 bg-muted/5">
            <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 min-w-[160px]">Ticker / Empresa</span>
            <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 w-[70px]">Consenso</span>
            <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 min-w-[90px]">Valor total</span>
            <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 min-w-[130px]">% portfolio avg</span>
            <span className="text-[0.6rem] uppercase tracking-widest text-muted-foreground/50 flex-1 min-w-[200px]">Fondos</span>
          </div>
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No hay datos disponibles. Los 13F se actualizan trimestralmente.
            </div>
          ) : (
            filtered.map((row, i) => (
              <HoldingRow key={`${row.ticker}-${i}`} row={row} rank={i + 1} />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
