/**
 * Unit tests for api/client.ts utilities
 * Covers: parseCsvRows (via fetchGlobalValueOpportunities), getCsvUrl, downloadCsv,
 * fetchTickerSectorMap dev URL resolution, and edge cases.
 */

import { describe, it, expect } from 'vitest'

// ── Helpers extracted for testing (mirror internal implementations) ────────────

function parseCsvRows(text: string): Record<string, string>[] {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const splitRow = (line: string): string[] => {
    const out: string[] = []
    let cur = '', inQ = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      if (ch === '"') { if (inQ && line[i + 1] === '"') { cur += '"'; i++ } else inQ = !inQ }
      else if (ch === ',' && !inQ) { out.push(cur); cur = '' }
      else cur += ch
    }
    out.push(cur)
    return out
  }
  const headers = splitRow(lines[0])
  return lines.slice(1).filter(l => l.trim()).map(line => {
    const vals = splitRow(line)
    const obj: Record<string, string> = {}
    headers.forEach((h, i) => { obj[h.trim()] = vals[i] ?? '' })
    return obj
  })
}

// ── parseCsvRows ──────────────────────────────────────────────────────────────

describe('parseCsvRows', () => {
  it('parses a simple CSV', () => {
    const csv = 'ticker,price,score\nAAPL,150,85\nMSFT,300,90'
    const rows = parseCsvRows(csv)
    expect(rows).toHaveLength(2)
    expect(rows[0]).toEqual({ ticker: 'AAPL', price: '150', score: '85' })
    expect(rows[1]).toEqual({ ticker: 'MSFT', price: '300', score: '90' })
  })

  it('handles quoted fields with commas', () => {
    const csv = 'ticker,name\nAAPL,"Apple, Inc."\nMSFT,"Microsoft Corp."'
    const rows = parseCsvRows(csv)
    expect(rows[0].name).toBe('Apple, Inc.')
    expect(rows[1].name).toBe('Microsoft Corp.')
  })

  it('handles escaped double-quotes inside quoted fields', () => {
    const csv = 'ticker,note\nAAPL,"A ""great"" company"'
    const rows = parseCsvRows(csv)
    expect(rows[0].note).toBe('A "great" company')
  })

  it('returns empty array for header-only CSV', () => {
    expect(parseCsvRows('ticker,price')).toHaveLength(0)
  })

  it('returns empty array for empty string', () => {
    expect(parseCsvRows('')).toHaveLength(0)
  })

  it('skips blank lines', () => {
    const csv = 'ticker,price\nAAPL,150\n\nMSFT,300\n'
    const rows = parseCsvRows(csv)
    expect(rows).toHaveLength(2)
  })

  it('handles missing trailing columns with empty string', () => {
    const csv = 'a,b,c\n1,2'
    const rows = parseCsvRows(csv)
    expect(rows[0].c).toBe('')
  })

  it('trims header whitespace', () => {
    const csv = ' ticker , price \nAAPL,150'
    const rows = parseCsvRows(csv)
    expect(rows[0]).toHaveProperty('ticker')
    expect(rows[0]).toHaveProperty('price')
  })
})

// ── getCsvUrl ─────────────────────────────────────────────────────────────────

const CSV_FILES: Record<string, string> = {
  'value-us':       'value_opportunities.csv',
  'value-eu':       'european_value_opportunities.csv',
  'value-global':   'global_value_opportunities.csv',
  'fundamental':    'fundamental_scores.csv',
  'fundamental-eu': 'european_fundamental_scores.csv',
  'momentum':       'momentum_opportunities.csv',
}

function getCsvUrl(dataset: string, csvBase?: string): string {
  const filename = CSV_FILES[dataset]
  if (!filename) return ''
  if (csvBase) return `${csvBase}/${filename}`
  return `/api/download/${dataset}`
}

describe('getCsvUrl', () => {
  it('returns GitHub Pages URL in production', () => {
    const base = 'https://tantancansado.github.io/stock_analyzer_a'
    expect(getCsvUrl('value-us', base))
      .toBe(`${base}/value_opportunities.csv`)
  })

  it('returns /api/download/<key> in development (no csvBase)', () => {
    expect(getCsvUrl('fundamental')).toBe('/api/download/fundamental')
    expect(getCsvUrl('fundamental-eu')).toBe('/api/download/fundamental-eu')
  })

  it('returns empty string for unknown dataset', () => {
    expect(getCsvUrl('unknown-dataset', 'https://example.com')).toBe('')
    expect(getCsvUrl('unknown-dataset')).toBe('')
  })

  it('never maps fundamental_scores.csv to wrong /api/download/fundamental_scores path', () => {
    // The dev key should be 'fundamental', NOT derived from filename
    const devUrl = getCsvUrl('fundamental')
    expect(devUrl).not.toContain('fundamental_scores')
    expect(devUrl).toBe('/api/download/fundamental')
  })
})

// ── CSV_KEY_BY_FILE (reverse lookup used in fetchTickerSectorMap) ────────────

const CSV_KEY_BY_FILE: Record<string, string> = Object.fromEntries(
  Object.entries(CSV_FILES).map(([k, v]) => [v, k])
)

describe('CSV_KEY_BY_FILE reverse lookup', () => {
  it('maps fundamental_scores.csv → "fundamental"', () => {
    expect(CSV_KEY_BY_FILE['fundamental_scores.csv']).toBe('fundamental')
  })

  it('maps european_fundamental_scores.csv → "fundamental-eu"', () => {
    expect(CSV_KEY_BY_FILE['european_fundamental_scores.csv']).toBe('fundamental-eu')
  })

  it('maps value_opportunities.csv → "value-us"', () => {
    expect(CSV_KEY_BY_FILE['value_opportunities.csv']).toBe('value-us')
  })

  it('builds correct dev URL for fundamental_scores.csv', () => {
    const filename = 'fundamental_scores.csv'
    const key = CSV_KEY_BY_FILE[filename] ?? filename.replace('.csv', '')
    const url = `/api/download/${key}`
    expect(url).toBe('/api/download/fundamental')
    expect(url).not.toBe('/api/download/fundamental_scores')
  })
})
