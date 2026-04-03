import { useEffect, useState } from 'react'
import { fetchPipelineStatus } from '../api/client'
import type { PipelineStatus } from '../api/client'

// ── Business-day staleness logic ─────────────────────────────────────────────
// Pipeline runs Mon-Fri at ~07:00 UTC. We consider data stale if:
//   - It's a weekday and last_run is >1 calendar day old (missed today's run)
//   - It's a weekend and last_run is >3 calendar days old (missed Friday)
// Threshold: 1.5 business days to tolerate timezone offsets + CI delays.

function businessDaysSince(isoDate: string): { calendarDays: number; stale: boolean; label: string } {
  const runDate = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - runDate.getTime()
  const calendarDays = diffMs / (1000 * 60 * 60 * 24)

  const dowNow = now.getUTCDay() // 0=Sun,6=Sat
  const isWeekend = dowNow === 0 || dowNow === 6

  // Stale if last run is more than 1 business day old
  // On weekends: 3 days is fine (Friday run), 4+ is stale
  const threshold = isWeekend ? 3.5 : 1.5
  const stale = calendarDays > threshold

  const daysRounded = Math.floor(calendarDays)
  const label = daysRounded === 0
    ? 'hoy'
    : daysRounded === 1
    ? 'ayer'
    : `hace ${daysRounded} días`

  return { calendarDays, stale, label }
}

function formatRunDate(isoDate: string): string {
  const d = new Date(isoDate)
  return d.toLocaleDateString('es-ES', {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  }) + ' UTC'
}

// ── Hook ─────────────────────────────────────────────────────────────────────

let _cached: PipelineStatus | null | undefined = undefined  // module-level cache

export function usePipelineStatus() {
  const [status, setStatus] = useState<PipelineStatus | null | undefined>(_cached)

  useEffect(() => {
    if (_cached !== undefined) return  // already fetched this session
    fetchPipelineStatus().then(s => {
      _cached = s
      setStatus(s)
    })
  }, [])

  if (status === undefined || status === null) return null

  const { calendarDays, stale, label } = businessDaysSince(status.last_run)
  return { status, calendarDays, stale, label }
}

// ── Component ─────────────────────────────────────────────────────────────────

const ACTIONS_URL = 'https://github.com/tantancansado/stock_analyzer_a/actions/workflows/daily-analysis.yml'

interface StaleDataBannerProps {
  /** Override: only show if data age > this many days (default: uses pipeline_status) */
  dataDate?: string | null
  className?: string
}

export default function StaleDataBanner({ dataDate, className = '' }: StaleDataBannerProps) {
  const pipelineInfo = usePipelineStatus()

  // Determine what date to use for staleness check
  const checkDate = dataDate || pipelineInfo?.status?.last_run || null

  if (!checkDate) return null

  const { stale, label, calendarDays } = businessDaysSince(checkDate)
  if (!stale) return null

  const daysOld = Math.floor(calendarDays)
  const isVeryStale = daysOld >= 3

  return (
    <div className={`rounded-xl border px-4 py-3 mb-5 animate-fade-in-up flex items-start gap-3 ${
      isVeryStale
        ? 'bg-red-500/8 border-red-500/30'
        : 'bg-amber-500/8 border-amber-500/30'
    } ${className}`}>
      {/* Icon */}
      <span className="text-lg shrink-0 mt-0.5">{isVeryStale ? '🔴' : '🟡'}</span>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-bold mb-0.5 ${isVeryStale ? 'text-red-400' : 'text-amber-400'}`}>
          Datos posiblemente desactualizados
          <span className="font-normal ml-1.5 text-[0.8rem]">— última actualización {label}</span>
        </div>
        {pipelineInfo?.status && (
          <div className="text-[0.7rem] text-muted-foreground/60">
            Pipeline ejecutado: {formatRunDate(pipelineInfo.status.last_run)}
            {isVeryStale && (
              <span className="ml-2 text-red-400/80 font-semibold">
                El pipeline no se ha ejecutado en {daysOld} días — los datos pueden ser incorrectos
              </span>
            )}
          </div>
        )}
      </div>

      {/* Action */}
      <a
        href={ACTIONS_URL}
        target="_blank"
        rel="noopener noreferrer"
        className={`shrink-0 text-[0.7rem] font-bold px-3 py-1.5 rounded-lg border transition-colors ${
          isVeryStale
            ? 'bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25'
            : 'bg-amber-500/15 border-amber-500/30 text-amber-400 hover:bg-amber-500/25'
        }`}
      >
        Lanzar pipeline →
      </a>
    </div>
  )
}
