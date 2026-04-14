import { useState, useEffect } from 'react'
import { fetchMeanReversion, fetchUnusualFlow } from '../api/client'

export interface ConfluenceSignals {
  bounce: boolean   // RSI<30, conf≥40
  value:  boolean   // in value_opportunities_filtered
  flow:   'BULLISH' | 'PUT_COVERING' | null
}

type ConfluenceMap = Record<string, ConfluenceSignals>

// Session cache — fetched once, shared across consumers
let _cache: ConfluenceMap | null = null
let _promise: Promise<ConfluenceMap> | null = null

const csvBase = (): string => (import.meta.env.VITE_CSV_BASE as string | undefined) || ''

function unwrap(v: unknown): Record<string, unknown> {
  const obj = v as Record<string, unknown>
  return (obj?.data as Record<string, unknown>) ?? obj ?? {}
}

function ensure(map: ConfluenceMap, t: string): void {
  if (!map[t]) map[t] = { bounce: false, value: false, flow: null }
}

async function loadCsvTickers(filename: string): Promise<Set<string>> {
  const base = csvBase()
  const url  = base ? `${base}/${filename}` : `/docs/${filename}`
  try {
    const res  = await fetch(url)
    if (!res.ok) return new Set()
    const text = await res.text()
    const [header, ...lines] = text.trim().split('\n')
    const cols = header.split(',').map(h => h.trim().replaceAll('"', ''))
    const ti   = cols.indexOf('ticker')
    if (ti < 0) return new Set()
    const tickers = new Set<string>()
    for (const l of lines) {
      const val = (l.split(',')[ti] ?? '').trim().replaceAll('"', '').toUpperCase()
      if (val) tickers.add(val)
    }
    return tickers
  } catch {
    return new Set()
  }
}

function applyBounce(map: ConfluenceMap, raw: unknown): void {
  const ops = (unwrap(raw)?.opportunities ?? []) as Record<string, unknown>[]
  for (const o of ops) {
    if (o.strategy !== 'Oversold Bounce') continue
    const rsi   = Number(o.rsi ?? 0)
    const conf  = Number(o.bounce_confidence ?? 0)
    const dp    = o.dark_pool_signal as string
    const price = Number(o.current_price ?? 0)
    const rr    = Number(o.risk_reward ?? 0)
    if (rsi >= 30 || rsi === 0 || conf < 40 || price < 1) continue
    if (dp === 'DISTRIBUTION' && conf < 60) continue
    if (rr !== 0 && rr < 1) continue
    const t = (o.ticker as string).toUpperCase()
    ensure(map, t); map[t].bounce = true
  }
}

function applyFlow(map: ConfluenceMap, raw: unknown): void {
  const results = (unwrap(raw)?.results ?? []) as Record<string, unknown>[]
  for (const r of results) {
    const sig    = r.signal as string
    const interp = (r.flow_interpretation as string) || 'STANDARD'
    const prem   = Number(r.total_premium ?? 0)
    if (prem < 25_000) continue
    if (sig !== 'BULLISH' && interp !== 'PUT_COVERING') continue
    const t = (r.ticker as string).toUpperCase()
    ensure(map, t)
    map[t].flow = interp === 'PUT_COVERING' ? 'PUT_COVERING' : 'BULLISH'
  }
}

function fetchAll(): Promise<ConfluenceMap> {
  if (_promise !== null) return _promise
  _promise = Promise.allSettled([
    fetchMeanReversion(),
    fetchUnusualFlow(),
    loadCsvTickers('value_opportunities_filtered.csv'),
    loadCsvTickers('european_value_opportunities_filtered.csv'),
  ]).then(([mr, uf, usVal, euVal]) => {
    const map: ConfluenceMap = {}

    if (mr.status === 'fulfilled') applyBounce(map, mr.value)
    if (usVal.status === 'fulfilled') for (const t of usVal.value) { ensure(map, t); map[t].value = true }
    if (euVal.status === 'fulfilled') for (const t of euVal.value) { ensure(map, t); map[t].value = true }
    if (uf.status === 'fulfilled')  applyFlow(map, uf.value)

    _cache = map
    return map
  })
  return _promise
}

export function usePortfolioConfluence(): ConfluenceMap {
  const [map, setMap] = useState<ConfluenceMap>(_cache ?? {})

  useEffect(() => {
    if (_cache !== null) { setMap(_cache); return }
    fetchAll().then(setMap)
  }, [])

  return map
}
