import {
  Globe, TrendingUp, TrendingDown, Users, Activity,
  ArrowLeftRight, PieChart, BarChart2, FlaskConical, Search, LayoutDashboard, Database,
  Ruler, Layers, Star, Radar, CalendarDays, AlertTriangle, Sparkles, Building2, Zap,
  DollarSign, Euro, Wallet, GitCompare, Bell, SlidersHorizontal, CalendarCheck, CandlestickChart, Brain,
  Gem,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type NavSection  = { section: string }
export type NavLinkItem = { path: string; icon: LucideIcon; label: string; color: string; tag?: string; keywords?: string[] }
export type NavItem = NavSection | NavLinkItem

export const NAV: NavItem[] = [
  { path: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard',           color: '#6366f1', keywords: ['inicio', 'home', 'resumen'] },
  { path: '/cerebro',        icon: Brain,           label: 'Cerebro IA',          color: '#8b5cf6', keywords: ['cerebro', 'ia', 'agente', 'proactivo', 'aprendizaje', 'convergencia', 'alertas', 'entrada', 'semaforo'] },
  { section: 'Estrategias' },
  { path: '/value',          icon: DollarSign,      label: 'Value',               color: '#10b981', tag: '🇺🇸', keywords: ['value', 'fundamental', 'us', 'acciones'] },
  { path: '/value-eu',       icon: Euro,            label: 'Value',               color: '#3b82f6', tag: '🇪🇺', keywords: ['value', 'europa', 'europeo'] },
  { path: '/value-global',   icon: Globe,           label: 'Value',               color: '#a855f7', tag: '🌍', keywords: ['value', 'global', 'mundial'] },
  { path: '/screener',       icon: SlidersHorizontal, label: 'Screener',          color: '#8b5cf6', keywords: ['screener', 'filtro', 'filtrar', 'buscar acciones', 'fcf', 'pe', 'roe'] },
  { path: '/micro-cap',      icon: Gem,               label: 'Micro-Cap',         color: '#f59e0b', keywords: ['micro cap', 'penny', 'small cap', 'micro', 'gemas', 'hidden gems', 'revalorizacion'] },
  { path: '/shorts',         icon: TrendingDown,      label: 'Cortos',            color: '#ef4444', keywords: ['cortos', 'short', 'bajista', 'ventas en corto', 'squeeze', 'death cross', 'weinstein'] },
  { path: '/momentum',       icon: TrendingUp,      label: 'Momentum',            color: '#f97316', keywords: ['momentum', 'tendencia', 'minervini', 'vcp'] },
  { path: '/macro-radar',    icon: Radar,           label: 'Macro Radar',         color: '#e11d48', keywords: ['macro', 'radar', 'economía'] },
  { path: '/macro-calendar', icon: CalendarCheck,   label: 'Calendario Macro',    color: '#f59e0b', keywords: ['calendario', 'macro', 'fed', 'cpi', 'nfp', 'tipos'] },
  { path: '/earnings',       icon: CalendarDays,    label: 'Earnings Calendar',   color: '#f59e0b', keywords: ['earnings', 'resultados', 'calendario', 'earnings date'] },
  { path: '/dividend-traps', icon: AlertTriangle,   label: 'Dividend Traps',      color: '#ef4444', keywords: ['dividendo', 'trampa', 'yield trap'] },
  { path: '/smart-portfolio', icon: Sparkles,       label: 'Smart Portfolio',     color: '#a855f7', keywords: ['portfolio', 'cartera', 'smart', 'builder'] },
  { path: '/hedge-funds',     icon: Building2,      label: 'Hedge Funds 13F',     color: '#f59e0b', keywords: ['hedge fund', '13f', 'buffett', 'ackman', 'klarman', 'sec', 'whales'] },
  { path: '/factor-status',   icon: Zap,            label: 'Factor Status',       color: '#6366f1', keywords: ['factor', 'value momentum quality insider smart money fama french aqr'] },
  { section: 'Señales' },
  { path: '/technical',      icon: CandlestickChart, label: 'Señales Técnicas',   color: '#f97316', keywords: ['tecnico', 'señales', 'rsi', 'macd', 'bollinger', 'velas', 'candlestick', 'golden cross', 'hammer'] },
  { path: '/insiders',       icon: Users,           label: 'Insiders',            color: '#8b5cf6', keywords: ['insiders', 'directivos', 'compras'] },
  { path: '/options',        icon: Activity,        label: 'Options Flow',        color: '#ec4899', keywords: ['options', 'opciones', 'flujo', 'institucional'] },
  { path: '/mean-reversion', icon: ArrowLeftRight,  label: 'Mean Reversion',      color: '#14b8a6', keywords: ['mean reversion', 'rebote', 'soporte', 'oversold'] },
  { path: '/sectors',        icon: PieChart,        label: 'Rotación Sectorial',  color: '#6366f1', keywords: ['sector', 'rotacion', 'sectorial'] },
  { section: 'Rendimiento' },
  { path: '/my-portfolio',   icon: Wallet,          label: 'Mis Posiciones',      color: '#10b981', keywords: ['mis posiciones', 'personal', 'posiciones', 'mis acciones', 'mi cartera'] },
  { path: '/portfolio',      icon: BarChart2,       label: 'Signal Tracker',      color: '#22c55e', keywords: ['signal tracker', 'señales', 'rendimiento', 'tracker', 'portfolio'] },
  { path: '/backtest',       icon: FlaskConical,    label: 'Backtest',            color: '#a78bfa', keywords: ['backtest', 'historico', 'simulacion'] },
  { section: 'Análisis' },
  { path: '/industry-groups', icon: Layers,         label: 'Industry Groups',     color: '#0ea5e9', keywords: ['industry', 'grupos', 'industria', 'rs'] },
  { path: '/position-sizing', icon: Ruler,          label: 'Position Sizing',     color: '#f59e0b', keywords: ['position', 'tamaño', 'kelly', 'sizing'] },
  { section: 'Herramientas' },
  { path: '/watchlist',      icon: Star,            label: 'Watchlist',           color: '#f59e0b', keywords: ['watchlist', 'seguimiento', 'favoritos'] },
  { path: '/compare',        icon: GitCompare,      label: 'Comparador',          color: '#0ea5e9', keywords: ['comparar', 'comparador', 'compare', 'side by side'] },
  { path: '/alerts',         icon: Bell,            label: 'Alertas',             color: '#f59e0b', keywords: ['alertas', 'email', 'notificaciones', 'precio'] },
  { path: '/search',         icon: Search,          label: 'Buscar Ticker',       color: '#94a3b8', keywords: ['buscar', 'ticker', 'search', 'analisis'] },
  { path: '/datos',          icon: Database,        label: 'Datos & Historial',   color: '#64748b', keywords: ['datos', 'historial', 'csv', 'descarga'] },
]

export const NAV_LINKS = NAV.filter((item): item is NavLinkItem => 'path' in item)
