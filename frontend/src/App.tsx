import React, { useState, useEffect, useCallback } from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { LayoutDashboard, X, LogOut } from 'lucide-react'
import { ThemeProvider } from './context/ThemeContext'
import { useAuth } from './context/AuthContext'
import { PersonalPortfolioProvider } from './context/PersonalPortfolioContext'
import { cn } from '@/lib/utils'
import { NAV } from '@/lib/nav'
import TopBar from './components/TopBar'
import ProtectedRoute from './components/ProtectedRoute'
import CommandPalette from './components/CommandPalette'
import ErrorBoundary from './components/ErrorBoundary'
import ScrollToTop from './components/ScrollToTop'
import Login from './pages/Login'
import ValueUS from './pages/ValueUS'
import ValueEU from './pages/ValueEU'
import Momentum from './pages/Momentum'
import Insiders from './pages/Insiders'
import OptionsFlow from './pages/OptionsFlow'
import MeanReversion from './pages/MeanReversion'
import SectorRotation from './pages/SectorRotation'
import Portfolio from './pages/Portfolio'
import Backtest from './pages/Backtest'
import TickerSearch from './pages/TickerSearch'
import Datos from './pages/Datos'
import Dashboard from './pages/Dashboard'
import PositionSizing from './pages/PositionSizing'
import IndustryGroups from './pages/IndustryGroups'
import Watchlist from './pages/Watchlist'
import GlobalValue from './pages/GlobalValue'
import MacroRadar from './pages/MacroRadar'
import EarningsCalendar from './pages/EarningsCalendar'
import DividendTraps from './pages/DividendTraps'
import SmartPortfolio from './pages/SmartPortfolio'
import HedgeFunds from './pages/HedgeFunds'
import FactorStatus from './pages/FactorStatus'
import PersonalPortfolio from './pages/PersonalPortfolio'
import Comparador from './pages/Comparador'
import Alerts from './pages/Alerts'
import Screener from './pages/Screener'
import MacroCalendar from './pages/MacroCalendar'
import TechnicalSignals from './pages/TechnicalSignals'

function SidebarContent({ onClose, onSignOut }: Readonly<{ onClose: () => void; onSignOut: () => void }>) {
  return (
    <>
      {/* Header */}
      <div className="px-4 py-5 border-b border-border/60 relative flex-shrink-0">
        <div className="flex items-center gap-2.5 mb-1">
          <div className="sidebar-logo-icon w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0">
            <LayoutDashboard size={14} color="white" strokeWidth={2} />
          </div>
          <h1 className="text-sm font-bold tracking-tight text-foreground">Stock Analyzer</h1>
        </div>
        <span className="text-[0.58rem] text-muted-foreground/60 uppercase tracking-widest font-semibold block">
          Pipeline diario automatizado
        </span>
        <button
          className="absolute top-3.5 right-3.5 flex md:hidden items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
          onClick={onClose}
          aria-label="Cerrar menú"
        >
          <X size={15} strokeWidth={1.75} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {NAV.map((item) =>
          'section' in item ? (
            <div key={`section-${item.section}`} className="px-3 pt-5 pb-1.5 text-[0.55rem] font-bold uppercase tracking-[0.14em] text-muted-foreground/50">
              {item.section}
            </div>
          ) : (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              style={{ '--nav-color': item.color } as React.CSSProperties}
              className={({ isActive }) => cn(
                'nav-link flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-0.5 relative',
                'text-muted-foreground',
                isActive
                  ? 'nav-link-active bg-[color-mix(in_srgb,var(--nav-color)_12%,transparent)]'
                  : 'hover:bg-[color-mix(in_srgb,var(--nav-color)_8%,transparent)] hover:text-foreground'
              )}
            >
              <span className="nav-icon">
                <item.icon size={15} strokeWidth={1.65} />
              </span>
              <span className="flex-1">{item.label}</span>
              {'tag' in item && item.tag && (
                <span className="text-sm leading-none opacity-75">{item.tag}</span>
              )}
            </NavLink>
          )
        )}
      </nav>

      {/* Logout */}
      <div className="px-2 py-3 border-t border-border/40 flex-shrink-0">
        <button
          onClick={onSignOut}
          className="flex w-full items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-muted-foreground hover:bg-red-500/10 hover:text-red-400 transition-all"
        >
          <LogOut size={15} strokeWidth={1.65} />
          Cerrar sesión
        </button>
      </div>
    </>
  )
}

export default function App() {
  const { user, signOut } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [cmdOpen, setCmdOpen]         = useState(false)
  const close = () => setSidebarOpen(false)
  const handleSignOut = () => { close(); signOut() }

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (user) setCmdOpen(o => !o)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [user])


  // Cursor spotlight — feeds --mouse-x/y to .glass::after radial gradient
  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      const el = (e.target as Element).closest<HTMLElement>('.glass')
      if (!el) return
      const rect = el.getBoundingClientRect()
      el.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`)
      el.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`)
    }
    document.addEventListener('mousemove', handleMove, { passive: true })
    return () => document.removeEventListener('mousemove', handleMove)
  }, [])

  const openCmd = useCallback(() => setCmdOpen(true), [])

  return (
    <ThemeProvider>
    <PersonalPortfolioProvider>
      {/* Aurora top line */}
      <div className="aurora-line" aria-hidden="true" />

      {/* Animated gradient orbs */}
      <div className="bg-orbs" aria-hidden="true">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
        <div className="orb orb-4" />
        <div className="orb orb-5" />
      </div>

      {user && (
        <>
          {/* Mobile overlay */}
          {sidebarOpen && (
            <button
              type="button"
              aria-label="Cerrar menú"
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden animate-fade-in w-full cursor-default"
              onClick={close}
            />
          )}

          {/* Sidebar */}
          <aside className={cn(
            'fixed inset-y-0 left-0 z-50 flex flex-col w-56',
            'border-r border-white/10 bg-card/20 backdrop-blur-2xl',
            'transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]',
            'max-md:-translate-x-full',
            sidebarOpen && 'max-md:translate-x-0',
          )}>
            <SidebarContent onClose={close} onSignOut={handleSignOut} />
          </aside>

          {/* Command Palette */}
          <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
        </>
      )}

      {/* Main */}
      <div className={cn('flex flex-col min-h-screen min-w-0 relative z-10', user && 'md:ml-56')}>
        {user && <TopBar onMenuClick={() => setSidebarOpen(o => !o)} onOpenCmd={openCmd} />}
        <ScrollToTop />
        <main className="flex-1 p-5 md:p-8 min-w-0" style={{ overflowX: 'clip' }}>
          <ErrorBoundary>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<Login />} />

            {/* All other routes require authentication */}
            <Route element={<ProtectedRoute />}>
              <Route path="/"               element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard"      element={<Dashboard />} />
              <Route path="/value"          element={<ValueUS />} />
              <Route path="/value-eu"       element={<ValueEU />} />
              <Route path="/value-global"   element={<GlobalValue />} />
              <Route path="/momentum"       element={<Momentum />} />
              <Route path="/insiders"       element={<Insiders />} />
              <Route path="/options"        element={<OptionsFlow />} />
              <Route path="/mean-reversion" element={<MeanReversion />} />
              <Route path="/sectors"        element={<SectorRotation />} />
              <Route path="/portfolio"      element={<Portfolio />} />
              <Route path="/backtest"       element={<Backtest />} />
              <Route path="/industry-groups" element={<IndustryGroups />} />
              <Route path="/position-sizing" element={<PositionSizing />} />
              <Route path="/watchlist"      element={<Watchlist />} />
              <Route path="/search"         element={<TickerSearch />} />
              <Route path="/macro-radar"    element={<MacroRadar />} />
              <Route path="/earnings"       element={<EarningsCalendar />} />
              <Route path="/dividend-traps"   element={<DividendTraps />} />
              <Route path="/smart-portfolio" element={<SmartPortfolio />} />
              <Route path="/hedge-funds" element={<HedgeFunds />} />
              <Route path="/factor-status" element={<FactorStatus />} />
              <Route path="/my-portfolio"  element={<PersonalPortfolio />} />
              <Route path="/compare"        element={<Comparador />} />
              <Route path="/alerts"         element={<Alerts />} />
              <Route path="/screener"       element={<Screener />} />
              <Route path="/macro-calendar" element={<MacroCalendar />} />
              <Route path="/technical"      element={<TechnicalSignals />} />
              <Route path="/datos"           element={<Datos />} />
            </Route>
          </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </PersonalPortfolioProvider>
    </ThemeProvider>
  )
}
