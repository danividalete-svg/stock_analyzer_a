/**
 * Shared color/class utilities for consistent styling across the frontend.
 */

/**
 * Tailwind text color class for analyst upside percentage.
 * Positive → emerald, negative → red, null → muted.
 */
export function upsideColor(pct: number | null): string {
  if (pct == null) return 'text-muted-foreground'
  return pct >= 0 ? 'text-emerald-400' : 'text-red-400'
}

/**
 * Tailwind text + border color classes for conviction grade.
 * A+/A → emerald, B → blue, C → amber, D/F → red, default → muted.
 */
export function gradeColor(grade: string | null | undefined): string {
  if (!grade) return 'text-muted-foreground'
  const g = grade.toUpperCase()
  if (g === 'A+' || g === 'A' || g === 'EXCELLENT') return 'text-emerald-400'
  if (g === 'B' || g === 'STRONG') return 'text-blue-400'
  if (g === 'C' || g === 'MODERATE') return 'text-amber-400'
  if (g === 'D' || g === 'F' || g === 'WEAK') return 'text-red-400'
  return 'text-muted-foreground'
}

/**
 * Tailwind text color class for a signal string (BUY/WATCH/HOLD/OVERVALUED/NO_DATA).
 */
export function signalColor(signal: string): string {
  switch (signal.toUpperCase()) {
    case 'BUY':        return 'text-emerald-400'
    case 'WATCH':      return 'text-amber-400'
    case 'HOLD':       return 'text-sky-400'
    case 'OVERVALUED': return 'text-red-400'
    default:           return 'text-muted-foreground'
  }
}

/**
 * Full Tailwind class strings for signal badge backgrounds.
 * Suitable for use in className on badge/span elements.
 */
export const SIGNAL_COLORS: Record<string, string> = {
  BUY:        'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  WATCH:      'bg-amber-500/15 text-amber-400 border-amber-500/30',
  HOLD:       'bg-sky-500/15 text-sky-400 border-sky-500/30',
  OVERVALUED: 'bg-red-500/15 text-red-400 border-red-500/30',
  NO_DATA:    'bg-muted/20 text-muted-foreground border-border/30',
}
