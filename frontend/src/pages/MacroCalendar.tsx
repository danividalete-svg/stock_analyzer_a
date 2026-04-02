import { CalendarCheck } from 'lucide-react'
import { fetchEconomicCalendar, type EconEvent } from '../api/client'
import { useApi } from '../hooks/useApi'
import Loading, { ErrorState } from '../components/Loading'

// ── Config ────────────────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { emoji: string; label: string; bg: string; border: string; text: string }> = {
  FED:      { emoji: '🏛️', label: 'Fed',      bg: 'bg-red-500/8',     border: 'border-red-500/20',     text: 'text-red-400'     },
  CPI:      { emoji: '📊', label: 'CPI',      bg: 'bg-orange-500/8',  border: 'border-orange-500/20',  text: 'text-orange-400'  },
  PCE:      { emoji: '📈', label: 'PCE',      bg: 'bg-purple-500/8',  border: 'border-purple-500/20',  text: 'text-purple-400'  },
  JOBS:     { emoji: '💼', label: 'NFP/Jobs', bg: 'bg-blue-500/8',    border: 'border-blue-500/20',    text: 'text-blue-400'    },
  EARNINGS: { emoji: '📅', label: 'Earnings', bg: 'bg-emerald-500/8', border: 'border-emerald-500/20', text: 'text-emerald-400' },
}

const DEFAULT_TYPE = { emoji: '📌', label: 'Evento', bg: 'bg-muted/20', border: 'border-border/30', text: 'text-muted-foreground' }

// ── Helpers ───────────────────────────────────────────────────────────────────

function daysUntil(dateStr: string): number {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const d     = new Date(dateStr + 'T00:00:00')
  return Math.round((d.getTime() - today.getTime()) / 86400000)
}

function fmtDate(dateStr: string): string {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('es-ES', {
    weekday: 'short', day: 'numeric', month: 'long'
  })
}

function groupByMonth(events: EconEvent[]): { month: string; events: (EconEvent & { days: number })[] }[] {
  const map = new Map<string, (EconEvent & { days: number })[]>()
  for (const e of events) {
    const d = new Date(e.date + 'T00:00:00')
    const key = d.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push({ ...e, days: daysUntil(e.date) })
  }
  return Array.from(map.entries()).map(([month, events]) => ({ month, events }))
}

// ── Event Card ────────────────────────────────────────────────────────────────

function EventCard({ event }: { event: EconEvent & { days: number } }) {
  const cfg = TYPE_CONFIG[event.type] ?? DEFAULT_TYPE
  const isToday    = event.days === 0
  const isTomorrow = event.days === 1
  const isSoon     = event.days <= 7

  return (
    <div className={`flex gap-4 p-4 rounded-xl border transition-all ${cfg.bg} ${cfg.border} ${isSoon ? 'ring-1 ring-inset ring-current/10' : ''}`}>
      {/* Date column */}
      <div className="shrink-0 w-16 text-center">
        <div className="text-2xl">{cfg.emoji}</div>
        <div className={`text-[0.65rem] font-bold uppercase tracking-wide mt-0.5 ${cfg.text}`}>
          {cfg.label}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div>
            <p className="text-sm font-bold text-foreground">{event.event}</p>
            <p className="text-[0.7rem] text-muted-foreground mt-0.5">{fmtDate(event.date)}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {event.impact === 'HIGH' && (
              <span className="text-[0.58rem] font-bold px-1.5 py-0.5 rounded bg-red-500/15 border border-red-500/25 text-red-400 uppercase tracking-wide">
                Alto impacto
              </span>
            )}
            <span className={`text-[0.65rem] font-bold px-2 py-1 rounded-lg border ${
              isToday    ? 'bg-red-500/15 border-red-500/30 text-red-400' :
              isTomorrow ? 'bg-amber-500/15 border-amber-500/30 text-amber-400' :
              isSoon     ? 'bg-blue-500/15 border-blue-500/30 text-blue-400' :
              'bg-muted/30 border-border/30 text-muted-foreground'
            }`}>
              {isToday ? 'HOY' : isTomorrow ? 'Mañana' : `en ${event.days}d`}
            </span>
          </div>
        </div>
        {event.description && (
          <p className="text-[0.72rem] text-muted-foreground/70 mt-2 leading-relaxed">{event.description}</p>
        )}
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function MacroCalendar() {
  const { data, loading, error } = useApi(() => fetchEconomicCalendar(), [])

  if (loading) return <Loading />
  if (error)   return <ErrorState message={error} />

  const events      = data?.events ?? []
  const grouped     = groupByMonth(events)
  const next7       = events.filter(e => daysUntil(e.date) <= 7 && daysUntil(e.date) >= 0)
  const sortedGroups = grouped

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="animate-fade-in-up">
        <h1 className="text-2xl font-extrabold flex items-center gap-2 gradient-title">
          <CalendarCheck size={22} className="text-primary" />
          Calendario Macro
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Próximos eventos macroeconómicos — Fed, CPI, NFP, PCE — que mueven los mercados.
        </p>
      </div>

      {/* Quick-view strip: próximos 14 días */}
      {sortedGroups.length > 0 && (() => {
        const upcoming = sortedGroups
          .flatMap(g => g.events)
          .filter(e => e.days >= 0 && e.days <= 14)
          .slice(0, 4)
        if (upcoming.length === 0) return null
        return (
          <div className="flex gap-2 flex-wrap mb-5 animate-fade-in-up" style={{ animationDelay: '60ms' }}>
            {upcoming.map((e) => {
              const cfg = TYPE_CONFIG[e.type] ?? DEFAULT_TYPE
              let daysLabel: string
              if (e.days === 0) { daysLabel = 'Hoy' }
              else if (e.days === 1) { daysLabel = 'Mañana' }
              else { daysLabel = `${e.days}d` }
              return (
                <div key={`${e.date}-${e.event}`} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium ${cfg.bg} ${cfg.border} ${cfg.text}`}>
                  <span>{cfg.emoji}</span>
                  <span>{daysLabel}</span>
                  <span className="font-bold">{e.event || e.type}</span>
                </div>
              )
            })}
          </div>
        )
      })()}

      {/* Upcoming alert (≤7 days) */}
      {next7.length > 0 && (
        <div className="glass rounded-2xl p-4 border border-amber-500/20 bg-amber-500/5 animate-fade-in-up" style={{ animationDelay: '120ms' }}>
          <p className="text-xs font-bold text-amber-400 uppercase tracking-widest mb-2">⚡ Próximos 7 días</p>
          <div className="space-y-1">
            {next7.map(e => {
              const cfg  = TYPE_CONFIG[e.type] ?? DEFAULT_TYPE
              const days = daysUntil(e.date)
              return (
                <div key={`${e.date}-${e.event}`} className="flex items-center gap-2 text-sm">
                  <span>{cfg.emoji}</span>
                  <span className={`font-bold ${cfg.text}`}>{e.event}</span>
                  <span className="text-muted-foreground text-xs">{fmtDate(e.date)}</span>
                  <span className="ml-auto text-xs font-bold text-amber-400">{days === 0 ? 'HOY' : days === 1 ? 'Mañana' : `en ${days}d`}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Type legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
          <span key={key} className={`flex items-center gap-1.5 text-[0.65rem] font-semibold px-2.5 py-1 rounded-full border ${cfg.bg} ${cfg.border} ${cfg.text}`}>
            {cfg.emoji} {cfg.label}
          </span>
        ))}
      </div>

      {/* Timeline */}
      {sortedGroups.length === 0 ? (
        <div className="glass rounded-2xl p-12 text-center">
          <CalendarCheck size={40} className="mx-auto text-muted-foreground/30 mb-4" />
          <p className="text-foreground font-semibold">Sin eventos próximos</p>
          <p className="text-sm text-muted-foreground mt-1">El pipeline diario actualiza este calendario cada mañana.</p>
        </div>
      ) : (
        sortedGroups.map(({ month, events }, gi) => (
          <div key={month} className="animate-fade-in-up" style={{ animationDelay: `${(gi + 2) * 80}ms` }}>
            <div className="text-[0.65rem] font-bold uppercase tracking-widest text-muted-foreground/50 px-1 mb-3 capitalize">
              {month}
            </div>
            <div className="space-y-2">
              {events.map(e => (
                <EventCard key={`${e.date}-${e.event}`} event={e} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
