import { useEffect } from 'react'
import { X, Keyboard } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
}

const SHORTCUTS: { keys: string[]; desc: string }[] = [
  { keys: ['⌘', 'K'],       desc: 'Abrir buscador / paleta de comandos' },
  { keys: ['?'],             desc: 'Mostrar atajos de teclado' },
  { keys: ['Esc'],           desc: 'Cerrar modal / paleta' },
  { keys: ['↑', '↓'],       desc: 'Navegar resultados en la paleta' },
  { keys: ['Enter'],         desc: 'Ir a la selección / buscar ticker' },
]

export default function ShortcutsModal({ open, onClose }: Readonly<Props>) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative z-10 w-full max-w-sm glass rounded-2xl border border-border/50 shadow-2xl p-5 animate-fade-in-up"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Keyboard size={15} className="text-primary" />
            <span className="text-sm font-bold text-foreground">Atajos de teclado</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Shortcuts list */}
        <ul className="space-y-2">
          {SHORTCUTS.map(s => (
            <li key={s.desc} className="flex items-center justify-between gap-4">
              <span className="text-xs text-muted-foreground">{s.desc}</span>
              <div className="flex items-center gap-1 shrink-0">
                {s.keys.map(k => (
                  <kbd
                    key={k}
                    className="inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-md bg-white/8 border border-border/50 text-[0.62rem] font-semibold text-foreground/80 font-mono"
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-4 text-[0.65rem] text-muted-foreground/40 text-center">
          Pulsa <kbd className="inline px-1 py-0.5 rounded bg-white/8 border border-border/40 text-[0.6rem]">?</kbd> en cualquier momento para abrir este panel
        </p>
      </div>
    </div>
  )
}
