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

type SortKey = 'micro_cap_score' | 'current_price' | 'market_cap' | 'piotroski_score' | 'fcf_yield_pct' | 'rev_growth_yoy'
type SortDir = 'asc' | 'desc'

function QualityBadge({ q }: { q: string }) {
  const map: Record<string, string> = {
    FUERTE:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    BUENA:    'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
    MODERADA: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    DÉBIL:    'bg-red-500/15 text-red-400 border-red-500/30',
  }
  return (
    <span className={`text-[0.65rem] font-bold px-1.5 py-0.5 rounded border ${map[q] ?? 'bg-muted/20 text-muted-foreground border-border/20'}`}>
      {q}
    </span>
  )
}

function fmt(n: number | undefined, decimals = 1, prefix = '') {
  if (n == null || isNaN(n)) return <span className="text-muted-foreground/30">—</span>
  const sign = n > 0 ? '+' : ''
  return <span>{prefix}{sign}{n.toFixed(decimals)}</span>
}

export default function MicroCap() {
  const { data, loading, error } = useApi(() => fetchMicroCapOpportunities(), [])
  const [sortKey, setSortKey] = useState<SortKey>('micro_cap_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [filterQuality, setFilterQuality] = useState('ALL')
  const [filterSector, setFilterSector]   = useState('ALL')

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const rows: MicroCapOpportunity[] = (data as any)?.data ?? data ?? []

  const sectors = Array.from(new Set(rows.map(r => r.sector).filter(Boolean))).sort() as string[]

  const filtered = rows
    .filter(r => filterQuality === 'ALL' || r.micro_cap_quality === filterQuality)
    .filter(r => filterSector  === 'ALL' || r.sector === filterSector)
    .sort((a, b) => {
      const av = (a as any)[sortKey] ?? 0
      const bv = (b as any)[sortKey] ?? 0
      return sortDir === 'desc' ? bv - av : av - bv
    })

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortKey(k); setSortDir('desc') }
  }

  function SortTh({ k, children }: { k: SortKey; children: React.ReactNode }) {
    const active = k === sortKey
    return (
      <TableHead
        className="cursor-pointer select-none whitespace-nowrap"
        onClick={() => toggleSort(k)}
      >
        {children}{active ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
      </TableHead>
    )
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Gem size={18} className="text-amber-400" />
            Micro-Cap de Calidad
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Penny stocks $1-$10 con fundamentos sólidos · Alto riesgo / Alto potencial · Máx 5-10% cartera
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CsvDownload dataset="micro-cap" label="CSV" />
        </div>
      </div>

      {/* Aviso de riesgo */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/8 px-4 py-2.5 text-xs text-amber-300/80">
        ⚠️ Sección experimental — micro-caps con alta volatilidad. Usa stops ajustados y tamaños de posición reducidos.
        Ejecuta <code className="font-mono bg-black/20 px-1 rounded">python3 micro_cap_scanner.py</code> para actualizar datos.
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={filterQuality}
          onChange={e => setFilterQuality(e.target.value)}
          className="text-xs rounded-md border border-border/40 bg-background/60 px-2 py-1.5 text-foreground"
        >
          <option value="ALL">Todas las calidades</option>
          {['FUERTE','BUENA','MODERADA'].map(q => <option key={q} value={q}>{q}</option>)}
        </select>
        {sectors.length > 0 && (
          <select
            value={filterSector}
            onChange={e => setFilterSector(e.target.value)}
            className="text-xs rounded-md border border-border/40 bg-background/60 px-2 py-1.5 text-foreground"
          >
            <option value="ALL">Todos los sectores</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
        <span className="text-xs text-muted-foreground ml-auto">{filtered.length} tickers</span>
      </div>

      {/* Tabla */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="💎"
          title="Sin micro-caps de calidad"
          subtitle="Ejecuta python3 micro_cap_scanner.py para analizar el universo"
        />
      ) : (
        <div className="glass rounded-xl overflow-clip">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Ticker</TableHead>
                <TableHead>Empresa</TableHead>
                <SortTh k="micro_cap_score">Score</SortTh>
                <TableHead>Calidad</TableHead>
                <SortTh k="current_price">Precio</SortTh>
                <SortTh k="market_cap">MCap</SortTh>
                <SortTh k="piotroski_score">Piotroski</SortTh>
                <SortTh k="fcf_yield_pct">FCF%</SortTh>
                <SortTh k="rev_growth_yoy">Rev+%</SortTh>
                <TableHead>Objetivo</TableHead>
                <TableHead>Sector</TableHead>
                <TableHead className="w-8" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(r => {
                const mcapM = ((r.market_cap ?? 0) / 1e6).toFixed(0)
                const hasEarningsWarning = r.earnings_warning || (r.days_to_earnings != null && r.days_to_earnings >= 0 && r.days_to_earnings <= 7)
                return (
                  <TableRow key={r.ticker} className="hover:bg-white/5">
                    <TableCell className="text-center">
                      {r.short_squeeze_potential === 'HIGH' && (
                        <span title="Potencial short squeeze" className="text-xs">🚀</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono font-bold text-foreground">
                      {r.ticker}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[160px] truncate">
                      {r.company_name ?? '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 min-w-[80px]">
                        <ScoreBar score={r.micro_cap_score} max={100} />
                        <span className="text-xs font-bold tabular-nums">{r.micro_cap_score?.toFixed(0)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <QualityBadge q={r.micro_cap_quality ?? ''} />
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
