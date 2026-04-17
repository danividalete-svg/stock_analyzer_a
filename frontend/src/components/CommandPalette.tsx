import { useEffect, useRef, useState, useCallback } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { Search, ArrowRight, TrendingUp } from 'lucide-react'
import { NAV_LINKS } from '@/lib/nav'

interface Props {
  open: boolean
  onClose: () => void
}

// Regex: looks like a ticker (1-5 uppercase letters, optionally with a dot for EU)
const TICKER_RE = /^[A-Z]{1,5}(\.[A-Z]{1,2})?$/

function looksLikeTicker(q: string): boolean {
  return TICKER_RE.test(q.trim().toUpperCase())
}

export default function CommandPalette({ open, onClose }: Props) {
  const [query, setQuery]       = useState('')
  const navigate                = useNavigate()
  const inputRef                = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setQuery('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const go = useCallback((path: string) => {
    navigate(path)
    onClose()
  }, [navigate, onClose])

  const goTicker = useCallback((ticker: string) => {
    navigate(`/search?q=${encodeURIComponent(ticker.trim().toUpperCase())}`)
    onClose()
  }, [navigate, onClose])

  const q      = query.trim()
  const upper  = q.toUpperCase()
  const isLikelyTicker = looksLikeTicker(q)

  const filtered = NAV_LINKS.filter(item => {
    if (!q) return true
    const ql = q.toLowerCase()
    return (
      item.label.toLowerCase().includes(ql) ||
      item.path.toLowerCase().includes(ql) ||
      (item.keywords ?? []).some(k => k.toLowerCase().includes(ql))
    )
  })

  // If query looks like a ticker, show it first as a direct action
  const showTickerAction = q.length >= 1 && q.length <= 6

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Palette */}
      <div className="fixed inset-x-0 top-[15vh] z-[201] mx-auto w-full max-w-lg px-4">
        <Command
          className="cmd-palette glass rounded-2xl border border-border/80 shadow-2xl overflow-clip"
          shouldFilter={false}
        >
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border/50">
            <Search size={15} className="text-muted-foreground flex-shrink-0" strokeWidth={1.75} />
            <Command.Input
              ref={inputRef}
              value={query}
              onValueChange={setQuery}
              onKeyDown={e => {
                // Enter on empty or ticker-like query → go to search
                if (e.key === 'Enter' && q && filtered.length === 0) {
                  goTicker(q)
                }
              }}
              placeholder="Página o ticker (AAPL, MSFT…)"
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/60 outline-none"
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                className="text-muted-foreground/50 hover:text-muted-foreground text-xs px-1.5 py-0.5 rounded border border-border/40 transition-colors"
              >
                esc
              </button>
            )}
            {!query && (
              <kbd className="hidden sm:flex items-center gap-0.5 text-[0.6rem] text-muted-foreground/40 font-mono">
                <span className="text-xs">⌘</span>K
              </kbd>
            )}
          </div>

          <Command.List className="max-h-[420px] overflow-y-auto p-2">
            {/* Ticker quick-jump — shown whenever query looks like a ticker */}
            {showTickerAction && (
              <Command.Group heading="Analizar ticker" className="cmd-group">
                <Command.Item
                  value={`ticker-${upper}`}
                  onSelect={() => goTicker(q)}
                  className="cmd-item flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-all"
                >
                  <span className="flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 bg-primary/15 text-primary">
                    <TrendingUp size={13} strokeWidth={1.75} />
                  </span>
                  <span className="flex-1 text-foreground font-medium">
                    Analizar <span className="font-mono text-primary">{upper}</span>
                  </span>
                  {isLikelyTicker && (
                    <span className="text-[0.6rem] text-muted-foreground/50 border border-border/30 px-1.5 py-0.5 rounded">
                      ticker
                    </span>
                  )}
                  <ArrowRight size={12} className="text-muted-foreground/30 flex-shrink-0" />
                </Command.Item>
              </Command.Group>
            )}

            {/* Navigation items */}
            {filtered.length === 0 && !showTickerAction && (
              <Command.Empty className="py-10 text-center text-sm text-muted-foreground">
                Sin resultados para "<span className="text-foreground">{query}</span>"
              </Command.Empty>
            )}

            {filtered.length > 0 && (
              <Command.Group heading="Navegación" className="cmd-group">
                {filtered.map(item => (
                  <Command.Item
                    key={item.path}
                    value={item.path}
                    onSelect={() => go(item.path)}
                    className="cmd-item flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-all"
                  >
                    <span
                      className="flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0"
                      style={{ background: `${item.color}1a`, color: item.color }}
                    >
                      <item.icon size={13} strokeWidth={1.75} />
                    </span>
                    <span className="flex-1 text-foreground font-medium">{item.label}</span>
                    <ArrowRight size={12} className="text-muted-foreground/30 flex-shrink-0" />
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>

          {/* Footer */}
          <div className="flex items-center gap-4 px-4 py-2.5 border-t border-border/40 text-[0.6rem] text-muted-foreground/50 font-mono">
            <span><kbd className="mr-0.5">↑↓</kbd> navegar</span>
            <span><kbd className="mr-0.5">↵</kbd> abrir</span>
            <span><kbd className="mr-0.5">esc</kbd> cerrar</span>
            <span className="ml-auto opacity-60">escribe un ticker para ir directo al análisis</span>
          </div>
        </Command>
      </div>
    </>
  )
}
