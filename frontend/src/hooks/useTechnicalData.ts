import { fetchTechnicalSignals } from '../api/client'
import type { TechnicalSignal, TechnicalSummary } from '../api/client'

export type TechnicalData = { signals: TechnicalSignal[]; summary: TechnicalSummary[] }

let cache: TechnicalData | null = null
let failed = false
let promise: Promise<void> | null = null
const listeners: Array<(d: TechnicalData) => void> = []

export function subscribeToTechnicalData(cb: (d: TechnicalData) => void): () => void {
  // Already loaded — call back async so it doesn't fire during render
  if (cache !== null) {
    const d = cache
    let cancelled = false
    const id = setTimeout(() => { if (!cancelled) cb(d) }, 0)
    return () => { cancelled = true; clearTimeout(id) }
  }

  // Permanently failed — don't retry endlessly
  if (failed) return () => {}

  listeners.push(cb)
  if (promise === null) {
    promise = fetchTechnicalSignals()
      .then(d => {
        cache = d
        const fns = listeners.splice(0)
        for (const fn of fns) fn(d)
      })
      .catch(() => {
        failed = true
        promise = null
        listeners.splice(0)
      })
  }
  return () => {
    const idx = listeners.indexOf(cb)
    if (idx !== -1) listeners.splice(idx, 1)
  }
}

export function getTechnicalCache(): TechnicalData | null {
  return cache
}

/** Reset for testing or manual retry */
export function resetTechnicalCache() {
  cache = null
  failed = false
  promise = null
  listeners.splice(0)
}
