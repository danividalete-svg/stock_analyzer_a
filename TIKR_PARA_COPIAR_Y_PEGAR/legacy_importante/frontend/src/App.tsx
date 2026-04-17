import { useEffect } from 'react'
import OwnerEarnings from './pages/OwnerEarnings'

export default function App() {
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

  return (
    <>
      {/* Aurora top line */}
      <div className="aurora-line" aria-hidden="true" />

      {/* Animated gradient orbs */}
      <div className="bg-orbs" aria-hidden="true">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      {/* Neon grid overlay (from index.css dark body::after) is automatic */}

      {/* Main content — no sidebar, no topbar */}
      <main className="relative z-10 min-h-screen p-5 md:p-8">
        <OwnerEarnings />
      </main>
    </>
  )
}
