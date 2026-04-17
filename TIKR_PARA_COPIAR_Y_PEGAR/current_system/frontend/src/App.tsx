import React, { useState, useEffect, useCallback, Suspense, lazy } from 'react'
import { Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { LayoutDashboard, X, LogOut, ChevronDown } from 'lucide-react'
import { ThemeProvider } from './context/ThemeContext'
import { useAuth } from './context/AuthContext'
import { PersonalPortfolioProvider } from './context/PersonalPortfolioContext'
import { ToastProvider } from './components/Toast'
import { cn } from '@/lib/utils'
import { NAV_PRIMARY, NAV_SECONDARY } from '@/lib/nav'
import TopBar from './components/TopBar'
import ProtectedRoute from './components/ProtectedRoute'
import CommandPalette from './components/CommandPalette'
import ShortcutsModal from './components/ShortcutsModal'
import ErrorBoundary from './components/ErrorBoundary'
import ScrollToTop from './components/ScrollToTop'
import Loading from './components/Loading'
import Login from './pages/Login'

const Dashboard        = lazy(() => import('./pages/Dashboard'))
const Value            = lazy(() => import('./pages/Value'))
const EntrySetups      = lazy(() => import('./pages/EntrySetups'))
const Insiders         = lazy(() => import('./pages/Insiders'))
const OptionsFlow      = lazy(() => import('./pages/OptionsFlow'))
const SectorRotation   = lazy(() => import('./pages/SectorRotation'))
const MyPortfolio      = lazy(() => import('./pages/MyPortfolio'))
const Backtest         = lazy(() => import('./pages/Backtest'))
const TickerSearch     = lazy(() => import('./pages/TickerSearch'))
const Datos            = lazy(() => import('./pages/Datos'))
const PositionSizing   = lazy(() => import('./pages/PositionSizing'))
const Watchlist        = lazy(() => import('./pages/Watchlist'))
const Macro            = lazy(() => import('./pages/Macro'))
const Calendar         = lazy(() => import('./pages/Calendar'))
const DividendTraps    = lazy(() => import('./pages/DividendTraps'))
const Comparador       = lazy(() => import('./pages/Comparador'))
const Cerebro          = lazy(() => import('./pages/Cerebro'))
const Alerts           = lazy(() => import('./pages/Alerts'))
const BounceTrader     = lazy(() => import('./pages/BounceTrader'))
const Calibration      = lazy(() => import('./pages/Calibration'))
const OwnerEarnings    = lazy(() => import('./pages/OwnerEarnings'))

function NavItem({ item, onClose }: { item: (typeof NAV_PRIMARY)[0]; onClose: () => void }) {
  return (
    <NavLink
      to={item.path}
      onClick={onClose}
      style={{ '--nav-color': item.color } as React.CSSProperties}
      className={({ isActive }) => cn(
        'nav-link flex items-center gap-2.5 px-3 py-[7px] rounded-lg text-sm font-medium transition-all mb-0.5 relative',
        'text-muted-foreground',
        isActive
          ? 'nav-link-active bg-[color-mix(in_srgb,var(--nav-color)_12%,transparent)] text-foreground'
          : 'hover:bg-[color-mix(in_srgb,var(--nav-color)_8%,transparent)] hover:text-foreground'
      )}
    >
      <span className="nav-icon shrink-0"><item.icon size={15} strokeWidth={1.65} /></span>
      <span className="flex-1 truncate">{item.label}</span>
    </NavLink>
  )
}

function SidebarContent({ onClose, onSignOut }: Readonly<{ onClose: () => void; onSignOut: () => void }>) {
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <>
      {/* Header */}
      <div className="px-4 py-4 border-b border-border/40 relative flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="sidebar-logo-icon w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0">
            <LayoutDashboard size={14} color="white" strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-tight text-foreground leading-tight">Stock Analyzer</h1>
          </div>
        </div>
        <button
          className="absolute top-3.5 right-3.5 flex md:hidden items-center justify-center w-7 h-7 rounded-md text-muted-foreground hover:bg-accent/10 hover:text-foreground transition-colors"
          onClick={onClose}
          aria-label="Cerrar menú"
        >
          <X size={15} strokeWidth={1.75} />
        </button>
      </div>

      {/* Primary nav */}
      <nav className="flex-1 px-2 py-2 overflow-y-auto min-h-0">
        <div className="space-y-0.5">
          {NAV_PRIMARY.map(item => <NavItem key={item.path} item={item} onClose={onClose} />)}
        </div>

        {/* Más — collapsible */}
        <div className="mt-3">
          <button
            onClick={() => setMoreOpen(v => !v)}
            className="flex w-full items-center gap-2 px-3 py-1.5 rounded-lg text-[0.62rem] font-semibold uppercase tracking-widest text-muted-foreground/30 hover:text-muted-foreground/60 transition-colors"
          >
            <span className="flex-1 text-left">Más</span>
            <ChevronDown size={11} strokeWidth={1.75} className={cn('transition-transform duration-200', moreOpen ? 'rotate-180' : '')} />
          </button>

          <div className={cn('collapsible-panel', moreOpen && 'open')}>
            <div className="space-y-0.5 mt-0.5">
              {NAV_SECONDARY.map(item => <NavItem key={item.path} item={item} onClose={onClose} />)}
            </div>
          </div>
        </div>
      </nav>

      {/* Logout */}
      <div className="px-2 py-2 border-t border-border/30 flex-shrink-0">
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
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [cmdOpen, setCmdOpen]           = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const close = () => setSidebarOpen(false)
  const handleSignOut = () => { close(); signOut() }

  // ⌘K / Ctrl+K global shortcut + ? shortcuts modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (user) setCmdOpen(o => !o)
        return
      }
      // ? key — only when no input/textarea is focused
      if (e.key === '?' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault()
        if (user) setShortcutsOpen(o => !o)
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
    <ToastProvider>
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

          {/* Shortcuts Modal */}
          <ShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
        </>
      )}

      {/* Main */}
      <div className={cn('flex flex-col min-h-screen min-w-0 relative z-10', user && 'md:ml-56')}>
        {user && <TopBar onMenuClick={() => setSidebarOpen(o => !o)} onOpenCmd={openCmd} />}
        <ScrollToTop />
        <main className="flex-1 p-5 md:p-8 min-w-0" style={{ overflowX: 'clip' }}>
          <ErrorBoundary resetKey={location.pathname}>
          <Suspense fallback={<Loading />}>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<Login />} />

            {/* All other routes require authentication */}
            <Route element={<ProtectedRoute />}>
              <Route path="/"               element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard"      element={<Dashboard />} />
              <Route path="/value"          element={<Value />} />
              <Route path="/value-eu"       element={<Navigate to="/value?region=eu" replace />} />
              <Route path="/value-global"   element={<Navigate to="/value?region=global" replace />} />
              <Route path="/entry-setups"   element={<EntrySetups />} />
              <Route path="/momentum"       element={<Navigate to="/entry-setups?tab=momentum" replace />} />
              <Route path="/insiders"       element={<Insiders />} />
              <Route path="/options"        element={<OptionsFlow />} />
              <Route path="/mean-reversion" element={<Navigate to="/entry-setups?tab=mean-reversion" replace />} />
              <Route path="/sectors"        element={<SectorRotation />} />
              <Route path="/portfolio"      element={<Navigate to="/my-portfolio?tab=signals" replace />} />
              <Route path="/calibration"   element={<Calibration />} />
              <Route path="/backtest"       element={<Backtest />} />
              <Route path="/position-sizing" element={<PositionSizing />} />
              <Route path="/watchlist"      element={<Watchlist />} />
              <Route path="/search"         element={<TickerSearch />} />
              <Route path="/macro-radar"       element={<Macro />} />
              <Route path="/macro-countries"  element={<Navigate to="/macro-radar?tab=countries" replace />} />
              <Route path="/earnings"       element={<Calendar />} />
              <Route path="/catalysts"      element={<Navigate to="/earnings?tab=catalysts" replace />} />
              <Route path="/dividend-traps"   element={<DividendTraps />} />
              <Route path="/my-portfolio"  element={<MyPortfolio />} />
              <Route path="/compare"        element={<Comparador />} />
              <Route path="/cerebro"        element={<Cerebro />} />
              <Route path="/alerts"         element={<Alerts />} />
              <Route path="/bounce"         element={<BounceTrader />} />
              <Route path="/owner-earnings" element={<OwnerEarnings />} />
              <Route path="/datos"           element={<Datos />} />
            </Route>
          </Routes>
          </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </PersonalPortfolioProvider>
    </ToastProvider>
    </ThemeProvider>
  )
}
