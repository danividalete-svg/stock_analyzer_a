import { useLocation, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Clock, Sun, Moon, Menu, Search, Brain, Grid3x3 } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { useNothingTheme } from '../hooks/useNothingTheme'
import { Button } from '@/components/ui/button'
import { fetchCerebroAlerts } from '../api/client'
import { useApi } from '../hooks/useApi'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard':       'Dashboard',
  '/cerebro':         'Cerebro IA — Señales Proactivas',
  '/value':           'VALUE — US · EU · Global',
  '/macro-radar':     'Macro — Radar & Países',
  '/insiders':        'Insiders — Compras Recurrentes',
  '/confluencia':     'Confluencia — Señales Multi-Timeframe',
  '/bounce':          'Bounce Trader — Rebotes',
  '/my-portfolio':    'Mi Cartera',
  '/owner-earnings':  'Owner Earnings — Valoración',
  '/search':          'Análisis de Ticker',
  '/entry-setups':    'Entry Setups — Mean Reversion & Momentum',
  '/options':         'Options Flow — Flujo Institucional',
  '/sectors':         'Rotación Sectorial',
  '/watchlist':       'Watchlist',
  '/alerts':          'Alertas de Precio',
  '/earnings':        'Calendario — Earnings & Catalizadores',
  '/dividend-traps':  'Dividend Traps — Rendimientos Peligrosos',
  '/position-sizing': 'Position Sizing — Kelly Criterion',
  '/backtest':        'Backtest — Resultados Históricos',
  '/compare':         'Comparador de Tickers',
  '/datos':           'Datos — Historial de Snapshots',
  '/calibration':     'Calibración del Sistema',
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
  const dateStr = time.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
  const timeStr = time.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })

  return (
    <header className="sticky top-0 z-50 flex h-[50px] items-center justify-between gap-3 px-6 bg-background/80 backdrop-blur-2xl border-b border-border/60 flex-shrink-0 transition-colors">
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden flex-shrink-0 h-8 w-8"
          onClick={onMenuClick}
          aria-label="Toggle navigation"
        >
          <Menu size={18} strokeWidth={1.75} />
        </Button>
        <span className="text-xs font-medium text-muted-foreground tracking-wide truncate">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-3.5 flex-shrink-0">
        {/* ⌘K trigger */}
        <button
          type="button"
          onClick={onOpenCmd}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 hover:border-primary/50 transition-all text-muted-foreground/70 hover:text-foreground text-xs shadow-sm"
          aria-label="Abrir paleta de comandos"
        >
          <Search size={12} strokeWidth={1.75} className="text-primary/70" />
          <span className="text-[0.7rem] font-medium">Buscar... ⌘K</span>
        </button>
        <button
          type="button"
          onClick={onOpenCmd}
          className="sm:hidden flex items-center justify-center w-8 h-8 rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 hover:border-primary/50 transition-all"
          aria-label="Abrir paleta de comandos"
        >
          <Search size={14} strokeWidth={1.75} className="text-primary/70" />
        </button>
        <span className="hidden sm:flex items-center gap-1.5 text-[0.67rem] text-muted-foreground">
          <span className="api-dot" />{' '}Pipeline activo
        </span>
        <span className="hidden md:flex items-center gap-1.5 text-[0.67rem] text-muted-foreground tabular-nums">
          <Clock size={11} strokeWidth={1.5} />
          {dateStr} · {timeStr}
        </span>
        {/* Cerebro bell */}
        <Link
          to="/cerebro"
          className="relative flex items-center justify-center h-8 w-8 rounded-lg border border-border/60 bg-transparent hover:bg-accent/10 transition-colors"
          title="Cerebro — IA Proactiva"
        >
          <Brain size={14} strokeWidth={1.75} className="text-muted-foreground" />
          {highAlerts > 0 && (
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5 items-center justify-center">
              <span className="absolute inset-0 rounded-full bg-red-500 animate-ping opacity-60" />
              <span className="relative flex h-3.5 w-3.5 items-center justify-center rounded-full bg-red-500 text-[0.45rem] font-bold text-white leading-none">
                {highAlerts > 9 ? '9+' : highAlerts}
              </span>
            </span>
          )}
        </Link>

        <Button
          variant="outline"
          size="icon"
          className={`h-8 w-8 transition-all border-border/60 ${nothingEnabled ? 'bg-primary/15 border-primary/50 text-primary' : ''}`}
          onClick={toggleNothing}
          title={nothingEnabled ? 'Desactivar tema Nothing' : 'Activar tema Nothing (dot matrix)'}
          aria-label="Toggle Nothing theme"
        >
          <Grid3x3 size={14} strokeWidth={1.75} />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8 transition-all hover:rotate-[14deg] hover:scale-110 border-border/60"
          onClick={toggle}
          aria-label={theme === 'dark' ? 'Activar modo claro' : 'Activar modo oscuro'}
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
