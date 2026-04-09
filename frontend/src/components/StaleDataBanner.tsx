import { useEffect, useState } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { fetchPipelineStatus, fetchPipelineHealth } from '../api/client'
import type { PipelineStatus, PipelineHealth } from '../api/client'

// ── Helpers ───────────────────────────────────────────────────────────────────

function daysSince(isoDate: string): number {
  return (Date.now() - new Date(isoDate).getTime()) / (1000 * 60 * 60 * 24)
}

function isPipelineStale(lastRun: string): boolean {
  const days = daysSince(lastRun)
  const dow = new Date().getUTCDay()
  const isWeekend = dow === 0 || dow === 6
  return days > (isWeekend ? 3.5 : 1.5)
}

function daysLabel(isoDate: string): string {
  const d = Math.floor(daysSince(isoDate))
  if (d === 0) return 'hoy'
  if (d === 1) return 'ayer'
  return `hace ${d} días`
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString('es-ES', {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  }) + ' UTC'
}

function formatDateShort(isoDate: string): string {
  return new Date(isoDate + 'T12:00:00Z').toLocaleDateString('es-ES', {
    weekday: 'short', day: 'numeric', month: 'short',
  })
}

// ── Module-level caches ───────────────────────────────────────────────────────

let _statusCache: PipelineStatus | null | undefined = undefined
let _healthCache: PipelineHealth | null | undefined = undefined

export function usePipelineStatus() {
  const [status, setStatus] = useState<PipelineStatus | null | undefined>(_statusCache)
  useEffect(() => {
    if (_statusCache !== undefined) return
    fetchPipelineStatus().then(s => { _statusCache = s; setStatus(s) })
  }, [])
  if (!status) return null
  return { status, stale: isPipelineStale(status.last_run), label: daysLabel(status.last_run) }
}

export function usePipelineHealth() {
  const [health, setHealth] = useState<PipelineHealth | null | undefined>(_healthCache)
  useEffect(() => {
    if (_healthCache !== undefined) return
    fetchPipelineHealth().then(h => { _healthCache = h; setHealth(h) })
  }, [])
  return health ?? null
}

// ── Component ─────────────────────────────────────────────────────────────────

const ACTIONS_URL = 'https://github.com/tantancansado/stock_analyzer_a/actions/workflows/daily-analysis.yml'

interface StaleDataBannerProps {
  /** Module name from pipeline_health.json (e.g. "cerebro", "value_us") */
  module?: string
  /** Legacy: explicit date override — use module instead */
  dataDate?: string | null
  className?: string
}

export default function StaleDataBanner({ module, dataDate, className = '' }: StaleDataBannerProps) {
  const pipelineInfo = usePipelineStatus()
  const health = usePipelineHealth()

  // ── Case 1: module-aware mode ────────────────────────────────────────────
  if (module && health) {
    const mod = health.modules[module]
    const today = new Date().toISOString().slice(0, 10)
    const pipelineRanToday = health.pipeline_date === today
    const pipelineRanRecently = !isPipelineStale(health.generated_at)

    // Module is fresh → compact green badge (always visible so user can trust the data)
    if (mod?.status === 'ok') {
      const isToday = mod.date === today
      const dateLabel = isToday ? 'hoy' : `hace ${mod.days_ago}d`
      const dateFormatted = mod.date ? formatDateShort(mod.date) : ''
      return (
        <div className={`inline-flex items-center gap-2 text-[0.7rem] font-medium mb-4 px-3 py-1.5 rounded-lg border bg-emerald-500/8 border-emerald-500/20 text-emerald-400/80 ${className}`}>
          <span className="relative flex shrink-0 items-center">
            <CheckCircle2 size={13} className="text-emerald-400" />
          </span>
          <span className="font-semibold text-emerald-400">Datos en vivo</span>
          <span className="text-emerald-400/30">·</span>
          <span className="text-emerald-300/80">Actualizado {dateLabel}</span>
          {dateFormatted && (
            <>
              <span className="text-emerald-400/30">·</span>
              <span className="text-muted-foreground/50">{dateFormatted}</span>
            </>
          )}
        </div>
      )
    }

    // Pipeline never ran recently → red global warning (not module-specific)
    if (!pipelineRanRecently) {
      const days = Math.floor(daysSince(health.generated_at))
      return (
        <div className={`rounded-xl border px-4 py-3 mb-5 animate-fade-in-up flex items-start gap-3 bg-red-500/8 border-red-500/30 ${className}`}>
          <span className="shrink-0 mt-0.5 relative flex">
            <AlertCircle size={16} className="text-red-400 relative z-10" />
            <AlertCircle size={16} className="text-red-400 absolute inset-0 animate-ping opacity-50" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-red-400 mb-0.5">
              Pipeline no ejecutado en {days} días
              <span className="font-normal ml-1.5 text-[0.8rem] text-red-300/80">— datos posiblemente incorrectos</span>
            </div>
            <div className="text-[0.7rem] text-muted-foreground/60">Última ejecución: {formatDate(health.generated_at)}</div>
          </div>
          <a href={ACTIONS_URL} target="_blank" rel="noopener noreferrer"
            className="shrink-0 text-[0.7rem] font-bold px-3 py-1.5 rounded-lg border bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25 transition-colors">
            Lanzar pipeline →
          </a>
        </div>
      )
    }

    // Pipeline ran but this module didn't update → amber warning
    const moduleDate = mod?.date ?? null
    const daysOld = moduleDate ? Math.floor(daysSince(moduleDate)) : null
    return (
      <div className={`rounded-xl border px-4 py-3 mb-5 animate-fade-in-up flex items-start gap-3 bg-amber-500/8 border-amber-500/30 ${className}`}>
        <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-amber-400 mb-0.5">
            {mod?.status === 'missing' ? 'Módulo sin datos' : 'Módulo no actualizado hoy'}
            {daysOld != null && daysOld > 0 && (
              <span className="font-normal ml-1.5 text-[0.8rem]">— última actualización hace {daysOld} días</span>
            )}
          </div>
          <div className="text-[0.7rem] text-muted-foreground/60">
            {pipelineRanToday
              ? 'El pipeline corrió hoy pero este módulo no generó datos nuevos — puede haber fallado o no tener datos disponibles.'
              : `Pipeline ejecutado: ${formatDate(health.generated_at)}`}
          </div>
        </div>
        <a href={ACTIONS_URL} target="_blank" rel="noopener noreferrer"
          className="shrink-0 text-[0.7rem] font-bold px-3 py-1.5 rounded-lg border bg-amber-500/15 border-amber-500/30 text-amber-400 hover:bg-amber-500/25 transition-colors">
          Ver pipeline →
        </a>
      </div>
    )
  }

  // ── Case 2: legacy date-override or global pipeline check ────────────────
  const checkDate = dataDate || pipelineInfo?.status?.last_run || null
  if (!checkDate) return null

  const days = daysSince(checkDate)
  const stale = isPipelineStale(checkDate)
  if (!stale) return null

  const daysOld = Math.floor(days)
  const isVeryStale = daysOld >= 3

  return (
    <div className={`rounded-xl border px-4 py-3 mb-5 animate-fade-in-up flex items-start gap-3 ${
      isVeryStale ? 'bg-red-500/8 border-red-500/30' : 'bg-amber-500/8 border-amber-500/30'
    } ${className}`}>
      {isVeryStale ? (
        <span className="shrink-0 mt-0.5 relative flex">
          <AlertCircle size={16} className="text-red-400 relative z-10" />
          <AlertCircle size={16} className="text-red-400 absolute inset-0 animate-ping opacity-50" />
        </span>
      ) : (
        <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-bold mb-0.5 ${isVeryStale ? 'text-red-400' : 'text-amber-400'}`}>
          Datos posiblemente desactualizados
          <span className="font-normal ml-1.5 text-[0.8rem]">— última actualización {daysLabel(checkDate)}</span>
        </div>
        {pipelineInfo?.status && (
          <div className="text-[0.7rem] text-muted-foreground/60">
            Pipeline ejecutado: {formatDate(pipelineInfo.status.last_run)}
            {isVeryStale && (
              <span className="ml-2 text-red-400/80 font-semibold">
                · No ejecutado en {daysOld} días
              </span>
            )}
          </div>
        )}
      </div>
      <a href={ACTIONS_URL} target="_blank" rel="noopener noreferrer"
        className={`shrink-0 text-[0.7rem] font-bold px-3 py-1.5 rounded-lg border transition-colors ${
          isVeryStale
            ? 'bg-red-500/15 border-red-500/30 text-red-400 hover:bg-red-500/25'
            : 'bg-amber-500/15 border-amber-500/30 text-amber-400 hover:bg-amber-500/25'
        }`}>
        Lanzar pipeline →
      </a>
    </div>
  )
}
