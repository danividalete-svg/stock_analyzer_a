import { useApi } from '../hooks/useApi'
import { fetchCalibration, type CalibrationBucket, type CalibrationRegime, type CalibrationSector } from '../api/client'
import Loading, { ErrorState } from '../components/Loading'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

function WinBar({ value, max = 80 }: { value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100)
  const color = value >= 50 ? '#22c55e' : value >= 35 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs w-10 text-right" style={{ color }}>{value.toFixed(1)}%</span>
    </div>
  )
}

function ReturnBadge({ value }: { value: number }) {
  const color = value > 0 ? '#22c55e' : value > -3 ? '#f59e0b' : '#ef4444'
  return <span style={{ color }} className="text-xs font-mono">{value > 0 ? '+' : ''}{value.toFixed(2)}%</span>
}

function ScoreBucketsTable({ buckets }: { buckets: CalibrationBucket[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="pb-2 text-xs text-white/50 font-medium">Score</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Señales</th>
            <th className="pb-2 text-xs text-white/50 font-medium pl-4">Win Rate 14d</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Retorno Medio</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Mediana</th>
          </tr>
        </thead>
        <tbody>
          {buckets.map(b => (
            <tr key={b.range} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-2.5 font-mono font-medium text-white">{b.range}</td>
              <td className="py-2.5 text-right text-white/60">{b.count}</td>
              <td className="py-2.5 pl-4 min-w-[160px]">
                <WinBar value={b.win_rate_14d} />
              </td>
              <td className="py-2.5 text-right">
                <ReturnBadge value={b.avg_return_14d} />
              </td>
              <td className="py-2.5 text-right">
                <ReturnBadge value={b.median_return_14d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RegimeTable({ rows }: { rows: CalibrationRegime[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="pb-2 text-xs text-white/50 font-medium">Régimen</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Señales</th>
            <th className="pb-2 text-xs text-white/50 font-medium pl-4">Win Rate 14d</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Retorno Medio</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.regime} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-2.5 font-medium text-white">{r.regime}</td>
              <td className="py-2.5 text-right text-white/60">{r.count}</td>
              <td className="py-2.5 pl-4 min-w-[160px]">
                <WinBar value={r.win_rate_14d} />
              </td>
              <td className="py-2.5 text-right">
                <ReturnBadge value={r.avg_return_14d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SectorTable({ rows }: { rows: CalibrationSector[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="pb-2 text-xs text-white/50 font-medium">Sector</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Señales</th>
            <th className="pb-2 text-xs text-white/50 font-medium pl-4">Win Rate 14d</th>
            <th className="pb-2 text-xs text-white/50 font-medium text-right">Retorno Medio</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.sector} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-2.5 text-white/90">{r.sector}</td>
              <td className="py-2.5 text-right text-white/60">{r.count}</td>
              <td className="py-2.5 pl-4 min-w-[160px]">
                <WinBar value={r.win_rate_14d} />
              </td>
              <td className="py-2.5 text-right">
                <ReturnBadge value={r.avg_return_14d} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ScoreInsight({ buckets }: { buckets: CalibrationBucket[] }) {
  if (buckets.length < 2) return null
  const sorted = [...buckets].sort((a, b) => b.win_rate_14d - a.win_rate_14d)
  const best = sorted[0]
  const worst = sorted[sorted.length - 1]
  const hasMonotone = buckets.every((b, i) =>
    i === 0 || b.win_rate_14d >= buckets[i - 1].win_rate_14d
  )
  return (
    <div className="mt-4 p-3 rounded-lg text-xs text-white/70" style={{ background: 'rgba(255,255,255,0.04)' }}>
      {hasMonotone
        ? '✅ El score es monotónico: a mayor score, mayor win rate.'
        : `📊 Mejor bucket: <b>${best.range}</b> (${best.win_rate_14d}% win rate) · Peor: ${worst.range} (${worst.win_rate_14d}%)`
      }
      {' '}El sistema es más fiable con score {'>'}={buckets.find(b => b.win_rate_14d >= 35)?.range?.split('-')[0] || 65}pts.
    </div>
  )
}

export default function Calibration() {
  const { data, loading, error } = useApi(fetchCalibration)

  if (loading) return <Loading />
  if (error || !data) return <ErrorState message="No hay datos de calibración aún. Se generan al final del pipeline diario." />

  const bestScore = [...(data.score_buckets || [])].sort((a, b) => b.win_rate_14d - a.win_rate_14d)[0]
  const bestSector = [...(data.sector_calibration || [])].sort((a, b) => b.win_rate_14d - a.win_rate_14d)[0]
  const bestRegime = [...(data.regime_analysis || [])].sort((a, b) => b.win_rate_14d - a.win_rate_14d)[0]

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Calibración del Sistema</h1>
        <p className="text-sm text-white/50 mt-1">
          ¿Cuándo predice bien el sistema? Análisis sobre {data.total_completed.toLocaleString()} señales completadas.
        </p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {bestScore && (
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <div className="text-xs text-white/50 mb-1">Mejor rango de score</div>
              <div className="text-lg font-semibold text-white">{bestScore.range} pts</div>
              <Badge variant="outline" className="mt-1 text-xs" style={{ color: '#22c55e', borderColor: '#22c55e44' }}>
                {bestScore.win_rate_14d}% win rate
              </Badge>
            </CardContent>
          </Card>
        )}
        {bestSector && (
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <div className="text-xs text-white/50 mb-1">Sector más fiable</div>
              <div className="text-lg font-semibold text-white truncate">{bestSector.sector}</div>
              <Badge variant="outline" className="mt-1 text-xs" style={{ color: '#22c55e', borderColor: '#22c55e44' }}>
                {bestSector.win_rate_14d}% win rate
              </Badge>
            </CardContent>
          </Card>
        )}
        {bestRegime && (
          <Card className="glass border-white/10">
            <CardContent className="p-4">
              <div className="text-xs text-white/50 mb-1">Régimen más favorable</div>
              <div className="text-lg font-semibold text-white">{bestRegime.regime}</div>
              <Badge variant="outline" className="mt-1 text-xs" style={{ color: '#22c55e', borderColor: '#22c55e44' }}>
                {bestRegime.win_rate_14d}% win rate
              </Badge>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Score Calibration */}
      {data.score_buckets?.length > 0 && (
        <Card className="glass border-white/10">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Calibración por Score VALUE</h2>
            <ScoreBucketsTable buckets={data.score_buckets} />
            <ScoreInsight buckets={data.score_buckets} />
          </CardContent>
        </Card>
      )}

      {/* Regime + Sector side by side */}
      <div className="grid md:grid-cols-2 gap-4">
        {data.regime_analysis?.length > 0 && (
          <Card className="glass border-white/10">
            <CardContent className="p-5">
              <h2 className="text-sm font-semibold text-white mb-4">Por Régimen de Mercado</h2>
              <RegimeTable rows={data.regime_analysis} />
            </CardContent>
          </Card>
        )}
        {data.fcf_yield_buckets?.length > 0 && (
          <Card className="glass border-white/10">
            <CardContent className="p-5">
              <h2 className="text-sm font-semibold text-white mb-4">Por FCF Yield</h2>
              <ScoreBucketsTable buckets={data.fcf_yield_buckets} />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Sector Calibration */}
      {data.sector_calibration?.length > 0 && (
        <Card className="glass border-white/10">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-white mb-4">Calibración por Sector</h2>
            <SectorTable rows={data.sector_calibration} />
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-white/30 text-right">
        Actualizado: {new Date(data.generated_at).toLocaleString('es-ES')}
      </p>
    </div>
  )
}
