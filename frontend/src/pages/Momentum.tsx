import StaleDataBanner from '../components/StaleDataBanner'
import { useState, useRef, useEffect } from 'react'
import { fetchMomentumOpportunities, type MomentumOpportunity, downloadCsv } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import ScoreBar from '../components/ScoreBar'
import ScoreRing from '../components/ScoreRing'
import { Badge } from '@/components/ui/badge'
import InfoTooltip from '../components/InfoTooltip'
import { Card } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import TickerLogo from '../components/TickerLogo'
import EmptyState from '../components/EmptyState'

type SortKey = keyof MomentumOpportunity
type SortDir = 'asc' | 'desc'

export default function Momentum() {
  const { data, loading, error } = useApi(() => fetchMomentumOpportunities(), [])
  const [sortKey, setSortKey] = useState<SortKey>('momentum_score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [focusedIdx, setFocusedIdx] = useState(-1)
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.innerWidth < 1280)
  const pagedRef = useRef<MomentumOpportunity[]>([])

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

  const rows = data?.data ?? []
  const source = data?.source ?? ''

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey] ?? 0; const bv = b[sortKey] ?? 0
    return sortDir === 'asc' ? (av < bv ? -1 : 1) : (av > bv ? -1 : 1)
  })

  const paged = sorted.slice(0, 20)
  pagedRef.current = paged

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: SortKey) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const avgScore = rows.length ? rows.reduce((s, r) => s + (r.momentum_score || 0), 0) / rows.length : 0
  const vcpHigh = rows.filter(r => (r.vcp_score || 0) >= 70).length
  const nearHigh = rows.filter(r => r.proximity_to_52w_high != null && r.proximity_to_52w_high > -10).length
  const trendStrong = rows.filter(r => (r.trend_template_score || 0) >= 7).length

  return (
    <>
      <StaleDataBanner module="momentum" />
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 flex items-center gap-2">
            <span className="gradient-title">Momentum</span>
            {source && <span className="text-[0.58rem] font-bold uppercase tracking-widest text-muted-foreground/60 border border-border/50 rounded px-1.5 py-0.5">{source}</span>}
          </h2>
          <p className="text-sm text-muted-foreground">Setups VCP y momentum Minervini — filtrados por tendencia y volumen</p>
        </div>
        <div className="flex items-center gap-2 mt-1 shrink-0">
          <button
            onClick={() => setCompact(v => !v)}
            className={`text-[0.68rem] px-2.5 py-0.5 rounded border transition-colors ${compact ? 'border-primary/60 bg-primary/15 text-primary' : 'border-border/40 text-muted-foreground hover:border-border/70 hover:text-foreground'}`}
            title="Alternar entre vista compacta y completa"
          >
            {compact ? '⊟ Compacta' : '⊞ Completa'}
          </button>
          <button
            onClick={() => downloadCsv('momentum')}
            className="text-xs px-3 py-1 rounded border border-border/50 text-muted-foreground hover:text-foreground hover:border-primary transition-colors"
          >↓ CSV</button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Setups', value: rows.length, sub: 'configuraciones activas', idx: 1 },
          { label: 'Score Medio', value: avgScore.toFixed(1), sub: 'momentum score', color: avgScore >= 60 ? 'text-emerald-400' : 'text-amber-400', idx: 2 },
          { label: 'VCP Alto', value: vcpHigh, sub: 'VCP score 70+', color: 'text-blue-400', idx: 3 },
          { label: 'Cerca de Máximos', value: nearHigh, sub: `dentro del 10% | ${trendStrong} tendencia 7+/8`, color: 'text-emerald-400', idx: 4 },
        ].map(({ label, value, sub, color, idx }) => (
          <Card key={label} className={`glass p-5 stagger-${idx}`}>
            <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">{label}</div>
            <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${color ?? ''}`}>{value}</div>
            <div className="text-[0.66rem] text-muted-foreground">{sub}</div>
          </Card>
        ))}
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden space-y-2 mb-2">
        {paged.map((d, i) => (
          <div
            key={d.ticker}
            onClick={() => setFocusedIdx(i)}
            className={`glass rounded-2xl p-4 cursor-pointer active:scale-[0.98] transition-transform ${focusedIdx === i ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ScoreRing score={d.momentum_score ?? 0} size="sm" />
                <div>
                  <div className="flex items-center gap-2">
                    <TickerLogo ticker={d.ticker} size="sm" />
                    <span className="font-mono font-bold text-sm">{d.ticker}</span>
                  </div>
                  <span className="text-[0.65rem] text-muted-foreground block truncate max-w-[140px]">{d.company_name}</span>
                </div>
              </div>
              <div className="text-right flex flex-col items-end gap-1">
                {d.vcp_score != null && (
                  <Badge variant={d.vcp_score >= 70 ? 'green' : d.vcp_score >= 50 ? 'yellow' : 'red'} >
                    VCP {d.vcp_score.toFixed(0)}
                  </Badge>
                )}
                {d.trend_template_score != null && (
                  <Badge variant={d.trend_template_score >= 7 ? 'green' : d.trend_template_score >= 5 ? 'yellow' : 'red'}>
                    {d.trend_template_score}/8
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex gap-3 mt-2.5 text-[0.62rem] text-muted-foreground/60">
              {d.current_price != null && (
                <span>${d.current_price.toFixed(2)}</span>
              )}
              {d.proximity_to_52w_high != null && (
                <span className={d.proximity_to_52w_high > -5 ? 'text-emerald-400' : d.proximity_to_52w_high > -15 ? 'text-amber-400' : 'text-red-400'}>
                  Dist.Max {d.proximity_to_52w_high.toFixed(1)}%
                </span>
              )}
              {d.analyst_upside_pct != null && (
                <span className={d.analyst_upside_pct > 0 ? 'text-emerald-400' : 'text-red-400'}>
                  Obj {d.analyst_upside_pct > 0 ? '+' : ''}{d.analyst_upside_pct.toFixed(0)}%
                </span>
              )}
            </div>
          </div>
        ))}
        {rows.length === 0 && (
          <EmptyState
            icon="📉"
            title="Sin setups momentum"
            subtitle="Normal durante correcciones — el sistema espera tendencias Stage 2 confirmadas"
          />
        )}
      </div>

      {/* Desktop table */}
      <div className="hidden sm:block">
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
                {!compact && <TableHead className={thCls('company_name')} onClick={() => onSort('company_name')}>Empresa</TableHead>}
                <TableHead className={thCls('current_price')} onClick={() => onSort('current_price')}>Precio</TableHead>
                <TableHead className={thCls('momentum_score')} onClick={() => onSort('momentum_score')}>Score</TableHead>
                <TableHead className={thCls('vcp_score')} onClick={() => onSort('vcp_score')}>
                  VCP
                  <InfoTooltip
                    text="Volatility Contraction Pattern (Minervini): patrón de consolidación con contracciones de rango y volumen decreciente. Score 0-100. ≥70 = patrón de alta calidad."
                    align="left"
                  />
                </TableHead>
                <TableHead className={thCls('proximity_to_52w_high')} onClick={() => onSort('proximity_to_52w_high')}>
                  Dist.Max
                  <InfoTooltip text="Distancia en % respecto al máximo de 52 semanas. Negativo = está por debajo del máximo. >-5% = muy cerca del máximo (zona de ruptura potencial)." />
                </TableHead>
                <TableHead className={thCls('trend_template_score')} onClick={() => onSort('trend_template_score')}>
                  Tendencia
                  <InfoTooltip
                    text={
                      <span>
                        Score Minervini Trend Template (0-8 criterios):<br />
                        precio &gt; MA50 · precio &gt; MA150 · precio &gt; MA200<br />
                        MA50 &gt; MA150 · MA150 &gt; MA200 · MA200 subiendo<br />
                        RS vs. mercado · precio cerca de máximos<br />
                        <span className="text-emerald-400">≥7/8</span> fuerte · <span className="text-amber-400">5-6/8</span> moderado
                      </span>
                    }
                    align="right"
                  />
                </TableHead>
                {!compact && <TableHead className={thCls('analyst_upside_pct')} onClick={() => onSort('analyst_upside_pct')}>Objetivo</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {paged.map((d, i) => (
                <TableRow
                  key={d.ticker}
                  data-row-idx={i}
                  onClick={() => setFocusedIdx(i)}
                  className={`cursor-pointer transition-colors ${focusedIdx === i ? 'ring-1 ring-inset ring-primary/40 bg-primary/5' : ''}`}
                >
                  <TableCell className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">
                    <div className="flex items-center gap-2">
                      <TickerLogo ticker={d.ticker} size="sm" />
                      {d.ticker}
                    </div>
                  </TableCell>
                  {!compact && (
                    <TableCell className="max-w-[150px] truncate text-muted-foreground text-[0.76rem]">{d.company_name}</TableCell>
                  )}
                  <TableCell className="tabular-nums">${d.current_price?.toFixed(2)}</TableCell>
                  <TableCell><ScoreBar score={d.momentum_score} /></TableCell>
                  <TableCell><ScoreBar score={d.vcp_score} /></TableCell>
                  <TableCell>
                    {d.proximity_to_52w_high != null
                      ? <span className={d.proximity_to_52w_high > -5 ? 'text-emerald-400' : d.proximity_to_52w_high > -15 ? 'text-amber-400' : 'text-red-400'}>
                          {d.proximity_to_52w_high.toFixed(1)}%
                        </span>
                      : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell>
                    {d.trend_template_score != null
                      ? <Badge variant={d.trend_template_score >= 7 ? 'green' : d.trend_template_score >= 5 ? 'yellow' : 'red'}>
                          {d.trend_template_score}/8
                        </Badge>
                      : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  {!compact && (
                    <TableCell className="tabular-nums">
                      {d.target_price_analyst ? `$${d.target_price_analyst.toFixed(0)}` : '—'}
                      {d.analyst_upside_pct != null && (
                        <span className={`ml-1 text-xs font-semibold ${d.analyst_upside_pct > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {d.analyst_upside_pct > 0 ? '+' : ''}{d.analyst_upside_pct.toFixed(0)}%
                        </span>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {rows.length === 0 && (
            <EmptyState
              icon="📉"
              title="Sin setups momentum"
              subtitle="Normal durante correcciones — el sistema espera tendencias Stage 2 confirmadas"
            />
          )}
          {sorted.length > 0 && (
            <div className="text-[0.6rem] text-muted-foreground/25 text-right px-3 py-1.5 border-t border-border/10">
              j / k navegar · Esc cerrar
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
