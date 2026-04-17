import { useState, useEffect, useRef } from 'react'

interface UseKeyboardNavOptions<T> {
  onEnter?: (item: T, index: number) => void
  onEscape?: () => void
  disabled?: boolean
}

interface UseKeyboardNavResult {
  focused: number
  setFocused: (fn: ((i: number) => number) | number) => void
}

/**
 * Keyboard navigation hook for table/list rows.
 * j/ArrowDown → next row, k/ArrowUp → prev row, Enter → onEnter, Escape → reset + onEscape.
 * Uses focusedIdx as a number (-1 = none), matching the existing pages' convention.
 */
export function useKeyboardNav<T>(
  items: T[],
  options: UseKeyboardNavOptions<T> = {}
): UseKeyboardNavResult {
  const { onEnter, onEscape, disabled = false } = options
  const [focused, setFocused] = useState(-1)

  // Keep a ref so the event handler always sees the latest items without re-binding
  const itemsRef = useRef<T[]>(items)
  itemsRef.current = items

  const focusedRef = useRef(focused)
  focusedRef.current = focused

  useEffect(() => {
    if (disabled) return

    const handler = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return

      if (e.key === 'Escape') {
        setFocused(-1)
        onEscape?.()
        return
      }

      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault()
        setFocused(i => {
          const next = Math.min(i + 1, itemsRef.current.length - 1)
          setTimeout(() => document.querySelector(`[data-row-idx="${next}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 0)
          return next
        })
        return
      }

      if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault()
        setFocused(i => {
          const prev = Math.max(i - 1, 0)
          setTimeout(() => document.querySelector(`[data-row-idx="${prev}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 0)
          return prev
        })
        return
      }

      if (e.key === 'Enter' && onEnter) {
        setFocused(i => {
          if (i >= 0 && itemsRef.current[i] != null) {
            onEnter(itemsRef.current[i], i)
          }
          return i
        })
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [disabled, onEnter, onEscape])

  return { focused, setFocused }
}
