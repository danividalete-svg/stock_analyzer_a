import { useLocation, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Clock, Sun, Moon, Menu, Search, Brain, Grid3x3 } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { useNothingTheme } from '../hooks/useNothingTheme'
import { Button } from '@/components/ui/button'
import { fetchCerebroAlerts, fetchPipelineStatus, type PipelineStatus as PipelineStatusType } from '../api/client'
import { useApi } from '../hooks/useApi'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard':       'Dashboard',
  '/cerebro':         'Cerebro',
  '/value':           'Value',
  '/macro-radar':     'Macro',
  '/insiders':        'Insiders',
  '/bounce':          'Bounce',
  '/my-portfolio':    'Mi cartera',
  '/owner-earnings':  'Valoración',
  '/search':          'Buscar ticker',
  '/entry-setups':    'Entry setups',
  '/options':         'Options flow',
  '/sectors':         'Sectores',
  '/watchlist':       'Watchlist',
  '/alerts':          'Alertas',
  '/earnings':        'Calendario',
  '/dividend-traps':  'Dividend traps',
  '/position-sizing': 'Position sizing',
  '/backtest':        'Backtest',
  '/compare':         'Comparar',
  '/datos':           'Datos',
  '/calibration':     'Calibración',
}

function PipelineStatus() {
  const [status, setStatus] = useState<PipelineStatusType | null>(null)
  useEffect(() => { fetchPipelineStatus().then(setStatus) }, [])
  if (!status?.run_date) return null

  const today     = new Date().toISOString().slice(0, 10)
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)

  let color = '#ef4444'
  let label = status.run_date
  if (status.run_date === today)      { color = '#22c55e'; label = 'Hoy' }
  else if (status.run_date === yesterday) { color = '#f59e0b'; label = 'Ayer' }

  return (
    <span
      className="hidden sm:flex items-center gap-1.5 text-[0.67rem] tabular-nums"
      style={{ color }}
      title={`Pipeline ejecutado: ${status.run_date}`}
    >
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
      {label}
    </span>
  )
}

interface Props {
  readonly onMenuClick: () => void
  readonly onOpenCmd: () => void
}

export default function TopBar({ onMenuClick, onOpenCmd }: Readonly<Props>) {
  const location = useLocation()
  const [time, setTime]   = useState(new Date())
  const { theme, toggle } = useTheme()
  const { enabled: nothingEnabled, toggle: toggleNothing } = useNothingTheme()
  const { data: alertsData } = useApi(() => fetchCerebroAlerts(), [])
  const highAlerts = alertsData?.high_count ?? 0

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 30_000)
    return () => clearInterval(t)
  }, [])

  const title   = ROUTE_TITLES[location.pathname] || 'Stock Analyzer'
  const timeStr = time.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
  const dateStr = time.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' })

  return (
    <header className="sticky top-0 z-50 flex h-[50px] items-center justify-between gap-3 px-6 bg-background/80 backdrop-blur-2xl border-b border-border/60 flex-shrink-0 transition-colors">
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden flex-shrink-0 h-8 w-8"
          onClick={onMenuClick}
          aria-label="Menú"
        >
          <Menu size={18} strokeWidth={1.75} />
        </Button>
        <span className="text-xs font-medium text-muted-foreground/70 tracking-wide truncate">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {/* Search — desktop shows label, mobile shows icon only */}
        <button
          type="button"
          onClick={onOpenCmd}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-primary/25 bg-primary/5 hover:bg-primary/10 hover:border-primary/40 transition-all text-muted-foreground/60 hover:text-foreground text-xs"
          aria-label="Buscar"
        >
          <Search size={12} strokeWidth={1.75} className="text-primary/60" />
          <span className="text-[0.7rem]">Buscar... ⌘K</span>
        </button>
        <button
          type="button"
          onClick={onOpenCmd}
          className="sm:hidden flex items-center justify-center w-8 h-8 rounded-lg border border-primary/25 bg-primary/5 hover:bg-primary/10 transition-all"
          aria-label="Buscar"
        >
          <Search size={14} strokeWidth={1.75} className="text-primary/60" />
        </button>

        {/* Real pipeline freshness indicator */}
        <PipelineStatus />

        {/* Date/time */}
        <span className="hidden md:flex items-center gap-1.5 text-[0.67rem] text-muted-foreground/50 tabular-nums">
          <Clock size={11} strokeWidth={1.5} />
          {dateStr} · {timeStr}
        </span>

        {/* Cerebro alert bell — ping only when there are real alerts */}
        <Link
          to="/cerebro"
          className="relative flex items-center justify-center h-8 w-8 rounded-lg border border-border/50 hover:bg-accent/10 transition-colors"
          title="Cerebro"
        >
          <Brain size={14} strokeWidth={1.75} className="text-muted-foreground" />
          {highAlerts > 0 && (
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5 items-center justify-center">
              <span className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-50" />
              <span className="relative flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[0.45rem] font-bold text-white leading-none">
                {highAlerts > 9 ? '9+' : highAlerts}
              </span>
            </span>
          )}
        </Link>

        {/* Nothing theme toggle */}
        <Button
          variant="outline"
          size="icon"
          className={`h-8 w-8 border-border/50 transition-colors ${nothingEnabled ? 'bg-primary/15 border-primary/50 text-primary' : ''}`}
          onClick={toggleNothing}
          title={nothingEnabled ? 'Desactivar tema matrix' : 'Activar tema matrix'}
          aria-label="Toggle Nothing theme"
        >
          <Grid3x3 size={14} strokeWidth={1.75} />
        </Button>

        {/* Light/dark toggle */}
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 border-border/50 transition-colors"
          onClick={toggle}
          aria-label={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
          title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
        >
          {theme === 'dark'
            ? <Sun  size={14} strokeWidth={1.75} />
            : <Moon size={14} strokeWidth={1.75} />
          }
        </Button>
      </div>
    </header>
  )
}
