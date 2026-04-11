import {
  Globe, TrendingUp, TrendingDown, Users, Activity,
  ArrowLeftRight, PieChart, BarChart2, FlaskConical, Search, LayoutDashboard, Database,
  Ruler, Layers, Star, Radar, CalendarDays, AlertTriangle, Sparkles, Building2, Zap,
  DollarSign, Euro, Wallet, GitCompare, Bell, SlidersHorizontal, CalendarCheck, CandlestickChart, Brain,
  Gem, Flame, Crosshair,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type NavLinkItem = { path: string; icon: LucideIcon; label: string; color: string; tag?: string; keywords?: string[] }

// Primary nav — always visible in sidebar
export const NAV_PRIMARY: NavLinkItem[] = [
  { path: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard',      color: '#6366f1', keywords: ['inicio', 'home', 'resumen'] },
  { path: '/cerebro',        icon: Brain,           label: 'Cerebro IA',     color: '#8b5cf6', keywords: ['cerebro', 'ia', 'agente', 'proactivo', 'convergencia', 'alertas', 'entrada'] },
  { path: '/value',          icon: DollarSign,      label: 'Value',          color: '#10b981', tag: '🇺🇸', keywords: ['value', 'fundamental', 'us', 'acciones'] },
  { path: '/value-eu',       icon: Euro,            label: 'Value',          color: '#3b82f6', tag: '🇪🇺', keywords: ['value', 'europa', 'europeo'] },
  { path: '/value-global',   icon: Globe,           label: 'Value',          color: '#a855f7', tag: '🌍', keywords: ['value', 'global', 'mundial'] },
  { path: '/macro-radar',    icon: Radar,           label: 'Macro Radar',    color: '#e11d48', keywords: ['macro', 'radar', 'economía'] },
  { path: '/macro-countries', icon: Globe,          label: 'Macro Países',   color: '#06b6d4', keywords: ['macro', 'países', 'pib', 'global', 'economía', 'country'] },
  { path: '/insiders',       icon: Users,           label: 'Insiders',       color: '#8b5cf6', keywords: ['insiders', 'directivos', 'compras'] },
  { path: '/confluencia',    icon: GitCompare,      label: 'Confluencia',    color: '#22c55e', tag: '🎯', keywords: ['confluencia', 'convergencia', 'señales', 'alineado', 'conviction'] },
  { path: '/bounce',         icon: Crosshair,       label: 'Bounce Trader',  color: '#f97316', tag: '⚡', keywords: ['bounce', 'rebote', 'corto plazo', 'oversold', 'rsi extremo'] },
  { path: '/my-portfolio',   icon: Wallet,          label: 'Mi Cartera',     color: '#10b981', keywords: ['mis posiciones', 'personal', 'posiciones', 'mi cartera'] },
  { path: '/search',         icon: Search,          label: 'Buscar Ticker',  color: '#94a3b8', keywords: ['buscar', 'ticker', 'search', 'analisis'] },
]

// Secondary nav — shown in collapsible "Más" section
export const NAV_SECONDARY: NavLinkItem[] = [
  { path: '/shorts',          icon: TrendingDown,     label: 'Cortos',             color: '#ef4444', keywords: ['cortos', 'short', 'bajista', 'squeeze'] },
  { path: '/momentum',        icon: TrendingUp,       label: 'Momentum',           color: '#f97316', keywords: ['momentum', 'tendencia', 'minervini', 'vcp'] },
  { path: '/screener',        icon: SlidersHorizontal, label: 'Screener',          color: '#8b5cf6', keywords: ['screener', 'filtro', 'filtrar'] },
  { path: '/micro-cap',       icon: Gem,              label: 'Micro-Cap',          color: '#f59e0b', keywords: ['micro cap', 'small cap', 'micro', 'gemas'] },
  { path: '/technical',       icon: CandlestickChart, label: 'Señales Técnicas',   color: '#f97316', keywords: ['tecnico', 'señales', 'rsi', 'macd', 'golden cross'] },
  { path: '/options',         icon: Activity,         label: 'Options Flow',       color: '#ec4899', keywords: ['options', 'opciones', 'flujo', 'institucional'] },
  { path: '/mean-reversion',  icon: ArrowLeftRight,   label: 'Mean Reversion',     color: '#14b8a6', keywords: ['mean reversion', 'rebote', 'soporte', 'oversold'] },
  { path: '/sectors',         icon: PieChart,         label: 'Rotación Sectorial', color: '#6366f1', keywords: ['sector', 'rotacion', 'sectorial'] },
  { path: '/hedge-funds',     icon: Building2,        label: 'Hedge Funds 13F',    color: '#f59e0b', keywords: ['hedge fund', '13f', 'buffett', 'sec', 'whales'] },
  { path: '/portfolio',       icon: BarChart2,        label: 'Signal Tracker',     color: '#22c55e', keywords: ['signal tracker', 'rendimiento', 'tracker'] },
  { path: '/calibration',     icon: FlaskConical,     label: 'Calibración',        color: '#a78bfa', keywords: ['calibracion', 'calibration', 'score', 'precision', 'accuracy'] },
  { path: '/watchlist',       icon: Star,             label: 'Watchlist',          color: '#f59e0b', keywords: ['watchlist', 'seguimiento', 'favoritos'] },
  { path: '/alerts',          icon: Bell,             label: 'Alertas',            color: '#f59e0b', keywords: ['alertas', 'email', 'notificaciones', 'precio'] },
  { path: '/earnings',        icon: CalendarDays,     label: 'Earnings',           color: '#f59e0b', keywords: ['earnings', 'resultados', 'calendario'] },
  { path: '/catalysts',       icon: Flame,            label: 'Catalizadores',      color: '#f97316', keywords: ['catalyst', 'catalizador', 'fda', 'pdufa', 'earnings', 'opex', 'macro events'] },
  { path: '/macro-calendar',  icon: CalendarCheck,    label: 'Calendario Macro',   color: '#f59e0b', keywords: ['calendario', 'macro', 'fed', 'cpi', 'nfp'] },
  { path: '/dividend-traps',  icon: AlertTriangle,    label: 'Dividend Traps',     color: '#ef4444', keywords: ['dividendo', 'trampa', 'yield trap'] },
  { path: '/smart-portfolio', icon: Sparkles,         label: 'Smart Portfolio',    color: '#a855f7', keywords: ['portfolio', 'cartera', 'smart', 'builder'] },
  { path: '/industry-groups', icon: Layers,           label: 'Industry Groups',    color: '#0ea5e9', keywords: ['industry', 'grupos', 'industria', 'rs'] },
  { path: '/position-sizing', icon: Ruler,            label: 'Position Sizing',    color: '#f59e0b', keywords: ['position', 'tamaño', 'kelly', 'sizing'] },
  { path: '/backtest',        icon: FlaskConical,     label: 'Backtest',           color: '#6366f1', keywords: ['backtest', 'historico', 'simulacion'] },
  { path: '/factor-status',   icon: Zap,              label: 'Factor Status',      color: '#6366f1', keywords: ['factor', 'value momentum quality'] },
  { path: '/compare',         icon: GitCompare,       label: 'Comparador',         color: '#0ea5e9', keywords: ['comparar', 'comparador', 'compare'] },
  { path: '/datos',           icon: Database,         label: 'Datos & Historial',  color: '#64748b', keywords: ['datos', 'historial', 'csv', 'descarga'] },
]

// All items flat (for command palette)
export const NAV_LINKS: NavLinkItem[] = [...NAV_PRIMARY, ...NAV_SECONDARY]

// Legacy export — kept so CommandPalette doesn't break
export type NavSection = { section: string }
export type NavItem = NavSection | NavLinkItem
export const NAV: NavItem[] = NAV_LINKS
