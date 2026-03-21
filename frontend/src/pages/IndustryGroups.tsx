import { useState } from 'react'
import api, { fetchIndustryGroupsInsight } from '../api/client'
import { useApi } from '../hooks/useApi'
import AiNarrativeCard from '../components/AiNarrativeCard'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import InfoTooltip from '../components/InfoTooltip'

interface IndustryRow {
  industry: string
  sector?: string
  num_tickers?: number
  avg_rs_percentile?: number
  avg_rs_score?: number
  avg_fundamental_score?: number
  pct_at_new_high?: number
  pct_eps_accel?: number
  rank?: number
  rank_total?: number
  percentile?: number
  label?: string
}

interface ApiResponse {
  data: IndustryRow[]
  count: number
}

type SortKey = keyof IndustryRow
type SortDir = 'asc' | 'desc'

function labelVariant(label: string | undefined): 'green' | 'blue' | 'yellow' | 'red' | 'gray' {
  if (!label) return 'gray'
  const l = label.toLowerCase()
  if (l.includes('top 10')) return 'green'
  if (l.includes('top 25')) return 'blue'
  if (l.includes('bottom')) return 'red'
  if (l.includes('sin datos')) return 'gray'
  return 'yellow'
}

function rsBar(pct: number | undefined) {
  if (pct == null) return <span className="text-muted-foreground">—</span>
  const color = pct >= 75 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : pct >= 25 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-16 rounded-full bg-white/10 overflow-hidden">
        <div className={`absolute inset-y-0 left-0 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-[0.78rem]">{pct.toFixed(0)}</span>
    </div>
  )
}

export default function IndustryGroups() {
  const { data, loading, error } = useApi<ApiResponse>(
    () => api.get<ApiResponse>('/api/industry-groups'),
    []
  )
  const { data: insightRaw } = useApi(() => fetchIndustryGroupsInsight(), [])
  const [sortKey, setSortKey] = useState<SortKey>('rank')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [filterSector, setFilterSector] = useState('ALL')
  const [showSingleTicker, setShowSingleTicker] = useState(false)

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const rows = data?.data ?? []

  const sectors = ['ALL', ...Array.from(new Set(rows.map(r => r.sector).filter(Boolean) as string[])).sort()]

  const singleTickerCount = rows.filter(r => (r.num_tickers ?? 0) <= 1).length

  const filtered = rows
    .filter(r => filterSector === 'ALL' || r.sector === filterSector)
    .filter(r => showSingleTicker || (r.num_tickers ?? 0) > 1)

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    const an = Number(av)
    const bn = Number(bv)
    if (an < bn) return sortDir === 'asc' ? -1 : 1
    if (an > bn) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir(key === 'rank' ? 'asc' : 'desc') }
  }

  const thCls = (key: SortKey) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const rankedRows = rows.filter(r => (r.num_tickers ?? 0) > 1)
  const top10 = rankedRows.filter(r => r.label?.includes('Top 10')).length
  const top25 = rankedRows.filter(r => r.label?.includes('Top 25')).length
  const avgRs = rankedRows.length ? rankedRows.reduce((s, r) => s + (r.avg_rs_percentile ?? 0), 0) / rankedRows.length : 0
  const pctNewHigh = rankedRows.length ? rankedRows.reduce((s, r) => s + (r.pct_at_new_high ?? 0), 0) / rankedRows.length : 0

  return (
    <>
      <div className="mb-7 animate-fade-in-up">
        <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Industry Groups</h2>
        <p className="text-sm text-muted-foreground">
          Grupos industriales rankeados por Relative Strength, fundamentales y % en nuevos máximos
        </p>
      </div>

      {insightRaw?.narrative && (
        <AiNarrativeCard narrative={insightRaw.narrative} label="Rotación Sectorial" className="mb-5" />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <Card className="glass p-5 stagger-1">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Total Grupos</div>
          <div className="text-3xl font-extrabold tabular-nums leading-none mb-2">{rankedRows.length}</div>
          <div className="text-[0.66rem] text-muted-foreground">grupos rankeados (≥2 tickers)</div>
        </Card>
        <Card className="glass p-5 stagger-2">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Top 10%</div>
          <div className="text-3xl font-extrabold text-emerald-400 tabular-nums leading-none mb-2">{top10}</div>
          <div className="text-[0.66rem] text-muted-foreground">{top25} en top 25%</div>
        </Card>
        <Card className="glass p-5 stagger-3">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">RS Medio</div>
          <div className={`text-3xl font-extrabold tabular-nums leading-none mb-2 ${avgRs >= 60 ? 'text-emerald-400' : avgRs >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
            {avgRs.toFixed(0)}
          </div>
          <div className="text-[0.66rem] text-muted-foreground">percentil RS promedio</div>
        </Card>
        <Card className="glass p-5 stagger-4">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">% Nuevos Máx.</div>
          <div className={`text-3xl font-extrabold tabular-nums leading-none mb-2 ${pctNewHigh >= 30 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {pctNewHigh.toFixed(0)}%
          </div>
          <div className="text-[0.66rem] text-muted-foreground">media del grupo</div>
        </Card>
      </div>

      {/* Filters row */}
      <Card className="glass px-4 py-3 mb-3 animate-fade-in-up">
        <div className="flex items-center gap-1.5 flex-wrap">
          {sectors.length > 2 && (
            <>
              <span className="text-[0.58rem] font-bold uppercase tracking-wider text-muted-foreground/60 mr-0.5">Sector</span>
              {sectors.map(s => (
                <button
                  key={s}
                  onClick={() => setFilterSector(s)}
                  className={`text-[0.65rem] px-2 py-0.5 rounded border transition-colors ${
                    filterSector === s
                      ? 'border-primary/60 bg-primary/15 text-primary'
                      : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'
                  }`}
                >
                  {s === 'ALL' ? 'Todos' : s}
                </button>
              ))}
              <span className="text-border/60 mx-1">|</span>
            </>
          )}
          <button
            onClick={() => setShowSingleTicker(v => !v)}
            className={`text-[0.65rem] px-2 py-0.5 rounded border transition-colors ${
              showSingleTicker
                ? 'border-primary/60 bg-primary/15 text-primary'
                : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'
            }`}
          >
            {showSingleTicker ? `Ocultar grupos únicos (${singleTickerCount})` : `Mostrar grupos únicos (${singleTickerCount})`}
          </button>
          <span className="text-[0.65rem] text-muted-foreground/50 ml-auto">
            {filtered.length} grupos
          </span>
        </div>
      </Card>

      {/* RS color legend */}
      <div className="flex items-center gap-3 mb-3 px-1 flex-wrap">
        <span className="text-[0.6rem] font-bold uppercase tracking-wider text-muted-foreground/60">RS%</span>
        {[
          { color: 'bg-emerald-500', label: '≥75 Fuerte' },
          { color: 'bg-blue-500',    label: '50-74 Neutral+' },
          { color: 'bg-amber-500',   label: '25-49 Neutral-' },
          { color: 'bg-red-500',     label: '<25 Débil' },
        ].map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1">
            <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
            <span className="text-[0.6rem] text-muted-foreground">{label}</span>
          </span>
        ))}
      </div>

      {rows.length === 0 ? (
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">📊</div>
            <p className="font-medium text-muted-foreground">Sin datos de industry groups disponibles</p>
            <p className="text-xs text-muted-foreground/60 mt-2">Ejecuta vcp_scanner_usa.py para generar</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('rank')} onClick={() => onSort('rank')}>
                  #
                  <InfoTooltip
                    text="Ranking dentro de grupos con ≥2 tickers. Grupos con 1 solo ticker no pueden rankearse estadísticamente."
                    align="left"
                  />
                </TableHead>
                <TableHead className={thCls('industry')} onClick={() => onSort('industry')}>Industria</TableHead>
                <TableHead className={thCls('sector')} onClick={() => onSort('sector')}>Sector</TableHead>
                <TableHead className={thCls('num_tickers')} onClick={() => onSort('num_tickers')}>Tickers</TableHead>
                <TableHead className={thCls('avg_rs_percentile')} onClick={() => onSort('avg_rs_percentile')}>
                  RS%
                  <InfoTooltip text="Relative Strength percentil (0-100): fuerza relativa vs. el universo. ≥75 = fuerte, ≥50 = neutral, <25 = débil. Promedio de los tickers del grupo." />
                </TableHead>
                <TableHead className={thCls('avg_fundamental_score')} onClick={() => onSort('avg_fundamental_score')}>
                  Fund.
                  <InfoTooltip text="Score fundamental promedio del grupo (0-100): combina calidad de balance, márgenes, EPS y salud financiera." />
                </TableHead>
                <TableHead className={thCls('pct_at_new_high')} onClick={() => onSort('pct_at_new_high')}>
                  % Máx.
                  <InfoTooltip text="% de tickers del grupo cotizando en máximos de 52 semanas. Un grupo con muchos tickers en máximos indica liderazgo sectorial." />
                </TableHead>
                <TableHead className={thCls('pct_eps_accel')} onClick={() => onSort('pct_eps_accel')}>
                  % EPS↑
                  <InfoTooltip
                    text="% de tickers con EPS acelerando trimestre a trimestre (QoQ). Actualmente no disponible en el pipeline — muestra 0% para todos los grupos. No refleja ausencia de aceleración real."
                    align="right"
                  />
                </TableHead>
                <TableHead>
                  Label
                  <InfoTooltip
                    text={
                      <span>
                        Ranking por percentil dentro del grupo:<br />
                        <span className="text-emerald-400">Top 10%</span> — grupo líder<br />
                        <span className="text-blue-400">Top 25%</span> — grupo fuerte<br />
                        <span className="text-amber-400">Medio</span> — rendimiento neutral<br />
                        <span className="text-red-400">Bottom 25%</span> — grupo débil<br />
                        <span className="text-muted-foreground">Sin datos</span> — solo 1 ticker
                      </span>
                    }
                    align="right"
                  />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map(r => (
                <TableRow key={r.industry}>
                  <TableCell className="tabular-nums text-muted-foreground text-[0.76rem]">
                    {r.rank != null ? `${r.rank}/${r.rank_total ?? '—'}` : '—'}
                  </TableCell>
                  <TableCell className="font-semibold text-[0.82rem]">
                    <div className="flex items-center gap-1.5">
                      {r.industry}
                      {r.rank === 1 && <Badge variant="green" className="text-[0.5rem] px-1 py-0 leading-4">BEST</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-[0.76rem]">{r.sector}</TableCell>
                  <TableCell className="tabular-nums text-[0.78rem] text-muted-foreground">{r.num_tickers ?? '—'}</TableCell>
                  <TableCell>{rsBar(r.avg_rs_percentile)}</TableCell>
                  <TableCell className="tabular-nums text-[0.78rem]">
                    {r.avg_fundamental_score != null ? r.avg_fundamental_score.toFixed(0) : '—'}
                  </TableCell>
                  <TableCell>
                    <span className={`tabular-nums text-[0.78rem] ${(r.pct_at_new_high ?? 0) >= 50 ? 'text-emerald-400' : (r.pct_at_new_high ?? 0) >= 25 ? 'text-amber-400' : 'text-muted-foreground'}`}>
                      {r.pct_at_new_high != null ? `${r.pct_at_new_high.toFixed(0)}%` : '—'}
                    </span>
                  </TableCell>
                  <TableCell className="tabular-nums text-[0.78rem] text-muted-foreground/40 italic">
                    N/D
                  </TableCell>
                  <TableCell>
                    {r.label ? (
                      <Badge variant={labelVariant(r.label)} className="text-[0.6rem]">{r.label}</Badge>
                    ) : '—'}
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
