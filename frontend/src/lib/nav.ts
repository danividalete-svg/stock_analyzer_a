import {
  TrendingUp, Users, Activity,
  PieChart, FlaskConical, Search, LayoutDashboard, Database,
  Ruler, Star, Radar, CalendarDays, AlertTriangle,
  DollarSign, Wallet, Bell, Brain,
  Crosshair, Calculator, Shuffle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type NavLinkItem = { path: string; icon: LucideIcon; label: string; color: string; keywords?: string[] }

// Primary nav — always visible in sidebar
export const NAV_PRIMARY: NavLinkItem[] = [
  { path: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard',      color: '#6366f1', keywords: ['inicio', 'home', 'resumen'] },
  { path: '/cerebro',        icon: Brain,           label: 'Cerebro',        color: '#8b5cf6', keywords: ['cerebro', 'ia', 'agente', 'proactivo', 'convergencia', 'alertas', 'entrada'] },
  { path: '/value',          icon: DollarSign,      label: 'Value',          color: '#10b981', keywords: ['value', 'fundamental', 'us', 'eu', 'europa', 'global', 'acciones'] },
  { path: '/macro-radar',    icon: Radar,           label: 'Macro',          color: '#e11d48', keywords: ['macro', 'radar', 'economía', 'países', 'pib', 'global', 'country'] },
  { path: '/insiders',       icon: Users,           label: 'Insiders',       color: '#8b5cf6', keywords: ['insiders', 'directivos', 'compras'] },
  { path: '/bounce',         icon: Crosshair,       label: 'Rebotes técnicos', color: '#f97316', keywords: ['bounce', 'rebote', 'corto plazo', 'oversold', 'rsi extremo'] },
  { path: '/my-portfolio',   icon: Wallet,          label: 'Mi cartera',     color: '#10b981', keywords: ['mis posiciones', 'personal', 'posiciones', 'mi cartera'] },
  { path: '/owner-earnings', icon: Calculator,      label: 'Owner Earnings', color: '#06b6d4', keywords: ['owner earnings', 'valoracion', 'compra', 'buffett', 'fcf', 'precio objetivo', 'dcf'] },
  { path: '/search',         icon: Search,          label: 'Buscar',         color: '#94a3b8', keywords: ['buscar', 'ticker', 'search', 'analisis'] },
]

// Secondary nav — shown in collapsible "Más" section
export const NAV_SECONDARY: NavLinkItem[] = [
  { path: '/entry-setups',    icon: TrendingUp,    label: 'Entry setups',    color: '#f97316', keywords: ['momentum', 'vcp', 'mean reversion', 'rebote', 'oversold', 'tendencia'] },
  { path: '/options',         icon: Activity,      label: 'Options flow',    color: '#ec4899', keywords: ['options', 'opciones', 'flujo', 'institucional'] },
  { path: '/sectors',         icon: PieChart,      label: 'Sectores',        color: '#6366f1', keywords: ['sector', 'rotacion', 'sectorial'] },
  { path: '/watchlist',       icon: Star,          label: 'Watchlist',       color: '#f59e0b', keywords: ['watchlist', 'seguimiento', 'favoritos'] },
  { path: '/alerts',          icon: Bell,          label: 'Alertas',         color: '#f59e0b', keywords: ['alertas', 'email', 'notificaciones', 'precio'] },
  { path: '/earnings',        icon: CalendarDays,  label: 'Calendario',      color: '#f59e0b', keywords: ['earnings', 'resultados', 'calendario', 'catalyst', 'catalizador', 'fda', 'pdufa'] },
  { path: '/dividend-traps',  icon: AlertTriangle, label: 'Dividend traps',  color: '#ef4444', keywords: ['dividendo', 'trampa', 'yield trap'] },
  { path: '/position-sizing', icon: Ruler,         label: 'Position sizing', color: '#f59e0b', keywords: ['position', 'tamaño', 'kelly', 'sizing'] },
  { path: '/backtest',        icon: FlaskConical,  label: 'Backtest',        color: '#6366f1', keywords: ['backtest', 'historico', 'simulacion'] },
  { path: '/compare',         icon: Shuffle,       label: 'Comparar tickers', color: '#0ea5e9', keywords: ['comparar', 'comparador', 'compare'] },
  { path: '/datos',           icon: Database,      label: 'Exportar datos',   color: '#64748b', keywords: ['datos', 'historial', 'csv', 'descarga', 'exportar'] },
]

// All items flat (for command palette)
export const NAV_LINKS: NavLinkItem[] = [...NAV_PRIMARY, ...NAV_SECONDARY]

// Legacy export — kept so CommandPalette doesn't break
export type NavSection = { section: string }
export type NavItem = NavSection | NavLinkItem
export const NAV: NavItem[] = NAV_LINKS
