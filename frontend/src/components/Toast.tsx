import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'

type ToastType = 'success' | 'info' | 'error'

interface ToastItem {
  id: number
  message: string
  type: ToastType
  exiting: boolean
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastType, string> = {
  success: '✓',
  info: 'ℹ',
  error: '✕',
}

const COLORS: Record<ToastType, string> = {
  success: 'hsl(142 76% 46%)',
  info: 'hsl(217 91% 60%)',
  error: 'hsl(0 72% 51%)',
}

let nextId = 1

function ToastRenderer({ items, onRemove }: { items: ToastItem[]; onRemove: (id: number) => void }) {
  return createPortal(
    <div
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '0.5rem',
        pointerEvents: 'none',
      }}
    >
      {items.map((item) => (
        <div
          key={item.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.45rem 0.9rem',
            borderRadius: '999px',
            background: 'hsl(var(--background) / 0.95)',
            backdropFilter: 'blur(12px)',
            border: '1px solid hsl(var(--border) / 0.6)',
            boxShadow: '0 4px 24px hsl(0 0% 0% / 0.35)',
            fontSize: '0.75rem',
            fontWeight: 500,
            pointerEvents: 'auto',
            whiteSpace: 'nowrap',
            animation: item.exiting
              ? 'toastOut 0.22s cubic-bezier(0.22, 1, 0.36, 1) forwards'
              : 'toastIn 0.28s cubic-bezier(0.22, 1, 0.36, 1) forwards',
          }}
          onClick={() => onRemove(item.id)}
        >
          <span style={{ color: COLORS[item.type], fontWeight: 700, fontSize: '0.8rem', lineHeight: 1 }}>
            {ICONS[item.type]}
          </span>
          <span style={{ color: 'hsl(var(--foreground))' }}>{item.message}</span>
        </div>
      ))}
    </div>,
    document.body
  )
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())

  const removeToast = useCallback((id: number) => {
    setItems(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t))
    setTimeout(() => {
      setItems(prev => prev.filter(t => t.id !== id))
    }, 230)
  }, [])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = nextId++
    setItems(prev => {
      const updated = [...prev, { id, message, type, exiting: false }]
      // Keep max 3
      if (updated.length > 3) {
        const oldest = updated[0]
        const timer = timers.current.get(oldest.id)
        if (timer) clearTimeout(timer)
        timers.current.delete(oldest.id)
        return updated.slice(-3)
      }
      return updated
    })
    const timer = setTimeout(() => removeToast(id), 2500)
    timers.current.set(id, timer)
  }, [removeToast])

  useEffect(() => {
    return () => {
      timers.current.forEach(t => clearTimeout(t))
    }
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastRenderer items={items} onRemove={removeToast} />
      <style>{`
        @keyframes toastIn {
          from { opacity: 0; transform: translateY(12px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes toastOut {
          from { opacity: 1; transform: translateY(0) scale(1); }
          to   { opacity: 0; transform: translateY(8px) scale(0.95); }
        }
      `}</style>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
