import { useState } from 'react'
import api from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import InfoTooltip from '../components/InfoTooltip'

interface PositionRow {
  ticker: string
  current_price?: number
  position_size_pct?: number
  position_value?: number
  shares?: number
  stop_loss_price?: number
  stop_loss_pct?: number
  risk_amount?: number
  risk_pct_portfolio?: number
  volatility?: number
  kelly_pct?: number
  multipliers?: string | Record<string, number>
}

interface ApiResponse {
  data: PositionRow[]
  count: number
}

function parseMultipliers(m: string | Record<string, number> | undefined): Record<string, number> | null {
  if (!m) return null
  if (typeof m === 'object') return m
  try {
    return JSON.parse(m.replace(/'/g, '"')) as Record<string, number>
  } catch {
    return null
  }
}

const BASE_PORTFOLIO = 100_000

export default function PositionSizing() {
  const { data, loading, error } = useApi<ApiResponse>(
    () => api.get<ApiResponse>('/api/position-sizing'),
    []
  )
  const [portfolioSize, setPortfolioSize] = useState(BASE_PORTFOLIO)
  const [sortKey, setSortKey] = useState<keyof PositionRow>('position_size_pct')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  if (loading) return <Loading />
  if (error) return <ErrorState message={error} />

  const rows = data?.data ?? []
  const scale = portfolioSize / BASE_PORTFOLIO

  const sorted = [...rows].sort((a, b) => {
    const av = Number(a[sortKey] ?? 0)
    const bv = Number(b[sortKey] ?? 0)
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const onSort = (key: keyof PositionRow) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const thCls = (key: keyof PositionRow) =>
    `cursor-pointer select-none whitespace-nowrap transition-colors hover:text-foreground ${sortKey === key ? 'text-primary' : ''}`

  const totalRisk = rows.reduce((s, r) => s + (r.risk_pct_portfolio ?? 0), 0)
  const totalValue = rows.reduce((s, r) => s + (r.position_value ?? 0), 0) * scale
  const avgSize = rows.length ? rows.reduce((s, r) => s + (r.position_size_pct ?? 0), 0) / rows.length : 0

  function riskColor(pct: number) {
    if (pct > 4) return 'text-red-400'
    if (pct > 2) return 'text-amber-400'
    return 'text-emerald-400'
  }

  return (
    <>
      <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight mb-2 gradient-title">Position Sizing</h2>
          <p className="text-sm text-muted-foreground">
            Kelly criterion · Ajuste por volatilidad, score y timing
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[0.65rem] font-bold uppercase tracking-wider text-muted-foreground/60">Portfolio ($)</span>
          <input
            type="number"
            value={portfolioSize}
            onChange={e => setPortfolioSize(Math.max(1000, Number(e.target.value)))}
            className="w-28 text-sm px-2.5 py-1.5 rounded border border-border/50 bg-transparent text-foreground focus:outline-none focus:border-primary/50 tabular-nums"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <Card className="glass p-5 stagger-1">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Posiciones</div>
          <div className="text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2">{rows.length}</div>
          <div className="text-[0.66rem] text-muted-foreground">tickers en cartera</div>
        </Card>
        <Card className="glass p-5 stagger-2">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Capital Asignado</div>
          <div className="text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2">
            ${(totalValue / 1000).toFixed(0)}k
          </div>
          <div className="text-[0.66rem] text-muted-foreground">de ${(portfolioSize / 1000).toFixed(0)}k</div>
        </Card>
        <Card className="glass p-5 stagger-3">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Riesgo Total</div>
          <div className={`text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2 ${riskColor(totalRisk)}`}>
            {totalRisk.toFixed(1)}%
          </div>
          <div className="text-[0.66rem] text-muted-foreground">del portfolio</div>
        </Card>
        <Card className="glass p-5 stagger-4">
          <div className="text-[0.6rem] font-bold uppercase tracking-widest text-muted-foreground mb-2">Posición Media</div>
          <div className="text-3xl font-extrabold tracking-tight tabular-nums leading-none mb-2">
            {avgSize.toFixed(1)}%
          </div>
          <div className="text-[0.66rem] text-muted-foreground">del portfolio</div>
        </Card>
      </div>

      {rows.length === 0 ? (
        <Card className="glass">
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4 opacity-20">📐</div>
            <p className="font-medium text-muted-foreground">Sin datos de position sizing disponibles</p>
            <p className="text-xs text-muted-foreground/60 mt-2">Ejecuta position_sizer.py para generar</p>
          </CardContent>
        </Card>
      ) : (
        <Card className="glass animate-fade-in-up">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50 hover:bg-transparent">
                <TableHead className={thCls('ticker')} onClick={() => onSort('ticker')}>Ticker</TableHead>
                <TableHead className={thCls('current_price')} onClick={() => onSort('current_price')}>Precio</TableHead>
                <TableHead className={thCls('position_size_pct')} onClick={() => onSort('position_size_pct')}>
                  Tamaño %
                  <InfoTooltip
                    text="% del portfolio asignado a esta posición. Calculado como Kelly ajustado × multiplicadores de calidad."
                    align="left"
                  />
                </TableHead>
                <TableHead className={thCls('position_value')} onClick={() => onSort('position_value')}>Valor ($)</TableHead>
                <TableHead className={thCls('shares')} onClick={() => onSort('shares')}>Acciones</TableHead>
                <TableHead className={thCls('stop_loss_price')} onClick={() => onSort('stop_loss_price')}>Stop Loss</TableHead>
                <TableHead className={thCls('stop_loss_pct')} onClick={() => onSort('stop_loss_pct')}>
                  Stop %
                  <InfoTooltip text="Distancia en % desde el precio actual hasta el nivel de stop loss. Suele ser ~8% (Minervini)." />
                </TableHead>
                <TableHead className={thCls('risk_pct_portfolio')} onClick={() => onSort('risk_pct_portfolio')}>
                  Riesgo %
                  <InfoTooltip
                    text="Pérdida máxima del portfolio si el precio cae al stop loss. = Tamaño% × Stop%. Rojo >4%, Ámbar >2%, Verde ≤2%."
                  />
                </TableHead>
                <TableHead className={thCls('kelly_pct')} onClick={() => onSort('kelly_pct')}>
                  Kelly %
                  <InfoTooltip
                    text="Kelly Criterion: fracción matemáticamente óptima del portfolio. Basado en win rate y ratio ganancia/pérdida histórico. Se aplica dividido por 2-4 (half-Kelly) por seguridad."
                  />
                </TableHead>
                <TableHead className={thCls('volatility')} onClick={() => onSort('volatility')}>
                  Volatilidad
                  <InfoTooltip
                    text="Volatilidad histórica anualizada a 30 días (desviación estándar de retornos diarios × √252). Mayor volatilidad → posición más pequeña."
                  />
                </TableHead>
                <TableHead>
                  Mult.
                  <InfoTooltip
                    text={
                      <span>
                        Multiplicadores que ajustan el tamaño Kelly:<br />
                        <span className="text-emerald-400">≥1.1×</span> — aumenta posición (alta calidad)<br />
                        <span className="text-muted-foreground">~1.0×</span> — sin ajuste<br />
                        <span className="text-red-400">≤0.8×</span> — reduce posición (baja calidad)<br />
                        Factores: score, timing, sector, volatilidad.
                      </span>
                    }
                    align="right"
                  />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map(r => {
                const mults = parseMultipliers(r.multipliers)
                const scaledValue = (r.position_value ?? 0) * scale
                const scaledShares = Math.round((r.shares ?? 0) * scale)
                return (
                  <TableRow key={r.ticker}>
                    <TableCell className="font-mono font-bold text-primary text-[0.8rem] tracking-wide">{r.ticker}</TableCell>
                    <TableCell className="tabular-nums text-[0.8rem]">
                      {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="relative h-1.5 w-12 rounded-full bg-white/10 overflow-hidden">
                          <div
                            className="absolute inset-y-0 left-0 bg-primary/60 rounded-full"
                            style={{ width: `${Math.min((r.position_size_pct ?? 0) * 5, 100)}%` }}
                          />
                        </div>
                        <span className="tabular-nums text-[0.8rem]">{(r.position_size_pct ?? 0).toFixed(1)}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="tabular-nums text-[0.8rem] text-foreground">
                      ${scaledValue.toLocaleString('en', { maximumFractionDigits: 0 })}
                    </TableCell>
                    <TableCell className="tabular-nums text-[0.8rem]">{scaledShares}</TableCell>
                    <TableCell className="tabular-nums text-[0.8rem] text-red-400">
                      {r.stop_loss_price != null ? `$${r.stop_loss_price.toFixed(2)}` : '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-[0.8rem] text-red-400">
                      {r.stop_loss_pct != null ? `${r.stop_loss_pct.toFixed(0)}%` : '—'}
                    </TableCell>
                    <TableCell>
                      <span className={`tabular-nums text-[0.8rem] font-semibold ${riskColor(r.risk_pct_portfolio ?? 0)}`}>
                        {(r.risk_pct_portfolio ?? 0).toFixed(2)}%
                      </span>
                    </TableCell>
                    <TableCell className="tabular-nums text-[0.8rem]">
                      {r.kelly_pct != null ? `${r.kelly_pct.toFixed(1)}%` : '—'}
                    </TableCell>
                    <TableCell className="tabular-nums text-[0.8rem] text-amber-400">
                      {r.volatility != null ? `${r.volatility.toFixed(0)}%` : '—'}
                    </TableCell>
                    <TableCell>
                      {mults ? (
                        <div className="flex gap-1 flex-wrap">
                          {Object.entries(mults).map(([k, v]) => (
                            <Badge
                              key={k}
                              variant={v >= 1.1 ? 'green' : v <= 0.8 ? 'red' : 'gray'}
                              className="text-[0.55rem] px-1 py-0"
                            >
                              {k}: {v.toFixed(1)}×
                            </Badge>
                          ))}
                        </div>
                      ) : '—'}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  )
}
