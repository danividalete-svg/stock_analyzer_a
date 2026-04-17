/**
 * Shared formatting utilities for display values across the frontend.
 */

/**
 * Generic number formatter with prefix/suffix.
 * Returns '—' for null/undefined.
 */
export function fmt(
  v: number | null | undefined,
  prefix = '',
  suffix = '',
  decimals = 2
): string {
  if (v == null) return '—'
  return `${prefix}${v.toFixed(decimals)}${suffix}`
}

/**
 * Format a dollar amount in millions/billions.
 * e.g. 1_200_000_000 → "$1.2B", 450_000_000 → "$450M"
 */
export function fmtM(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(1)}B`
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(0)}M`
  return `${sign}$${abs.toFixed(0)}`
}

/**
 * Format a percentage value.
 * e.g. 12.345 → "12.3%"
 */
export function fmtPct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—'
  return `${v.toFixed(decimals)}%`
}

/**
 * Format an ISO date string using es-ES locale.
 * e.g. "2026-04-15" → "15/04/2026"
 */
export function fmtDate(s: string | null | undefined): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleDateString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  } catch {
    return s
  }
}
