import { useState, useEffect } from 'react'
import {
  fetchCerebroValueTraps, fetchCerebroSmartMoney,
  fetchCerebroExitSignals, fetchCerebroDividendSafety, fetchCerebroPiotroski,
  fetchCerebroShortSqueeze, fetchCerebroQualityDecay, fetchCerebroSectorRV,
  fetchCerebroEntrySignals,
} from '../api/client'

export interface TrapInfo    { severity: 'HIGH' | 'MEDIUM'; trap_score: number; flags: string[] }
export interface SmartInfo   { n_hedge_funds: number; n_insiders: number; convergence_score: number }
export interface ExitInfo    { severity: 'HIGH' | 'MEDIUM' | 'LOW'; reasons: string[] }
export interface DivRiskInfo { rating: 'AT_RISK' | 'WATCH'; safety_score: number; div_yield: number }
export interface PiotrInfo   { trend: string; piotroski_current: number; delta: number }
export interface SqueezeInfo { severity: 'HIGH' | 'MEDIUM'; squeeze_score: number; short_pct_float: number; flags: string[] }
export interface DecayInfo   { severity: 'HIGH' | 'MEDIUM'; decay_score: number; flags: string[] }
export interface SectorRVInfo { label: 'BEST_IN_SECTOR' | 'PRICEY_VS_PEERS'; fcf_yield_pct: number; fcf_rank: number; fcf_rank_of: number; sector: string }
export interface EntryInfo   { signal: 'STRONG_BUY' | 'BUY'; entry_score: number }

export interface CerebroMaps {
  trapMap:    Record<string, TrapInfo>
  smMap:      Record<string, SmartInfo>
  exitMap:    Record<string, ExitInfo>
  divMap:     Record<string, DivRiskInfo>
  piotrMap:   Record<string, PiotrInfo>
  squeezeMap: Record<string, SqueezeInfo>
  decayMap:   Record<string, DecayInfo>
  sectorMap:  Record<string, SectorRVInfo>
  entryMap:   Record<string, EntryInfo>
}

const EMPTY: CerebroMaps = {
  trapMap: {}, smMap: {}, exitMap: {}, divMap: {}, piotrMap: {},
  squeezeMap: {}, decayMap: {}, sectorMap: {}, entryMap: {},
}

// Module-level cache: 9 requests fired once per session, shared across all consumers.
// Subsequent hook mounts get the resolved data immediately with no extra requests.
let _cache: CerebroMaps | null = null
let _promise: Promise<CerebroMaps> | null = null

function fetchAll(): Promise<CerebroMaps> {
  if (_promise) return _promise
  _promise = Promise.allSettled([
    fetchCerebroValueTraps(),
    fetchCerebroSmartMoney(),
    fetchCerebroExitSignals(),
    fetchCerebroDividendSafety(),
    fetchCerebroPiotroski(),
    fetchCerebroShortSqueeze(),
    fetchCerebroQualityDecay(),
    fetchCerebroSectorRV(),
    fetchCerebroEntrySignals(),
  ]).then(([traps, sm, exits, div, piotr, squeeze, decay, sectorRv, entry]) => {
    const trapMap:    Record<string, TrapInfo>    = {}
    const smMap:      Record<string, SmartInfo>   = {}
    const exitMap:    Record<string, ExitInfo>    = {}
    const divMap:     Record<string, DivRiskInfo> = {}
    const piotrMap:   Record<string, PiotrInfo>   = {}
    const squeezeMap: Record<string, SqueezeInfo> = {}
    const decayMap:   Record<string, DecayInfo>   = {}
    const sectorMap:  Record<string, SectorRVInfo>= {}
    const entryMap:   Record<string, EntryInfo>   = {}

    if (traps.status === 'fulfilled')
      for (const t of traps.value.data.traps ?? [])
        trapMap[t.ticker] = { severity: t.severity, trap_score: t.trap_score, flags: t.flags }

    if (sm.status === 'fulfilled')
      for (const s of sm.value.data.signals ?? [])
        smMap[s.ticker] = { n_hedge_funds: s.n_hedge_funds, n_insiders: s.n_insiders, convergence_score: s.convergence_score }

    if (exits.status === 'fulfilled')
      for (const e of exits.value.data.exits ?? [])
        exitMap[e.ticker] = { severity: e.severity, reasons: e.reasons }

    if (div.status === 'fulfilled')
      for (const d of div.value.data.dividends ?? [])
        if (d.rating !== 'SAFE')
          divMap[d.ticker] = { rating: d.rating as 'AT_RISK' | 'WATCH', safety_score: d.safety_score, div_yield: d.div_yield }

    if (piotr.status === 'fulfilled')
      for (const c of piotr.value.data.candidates ?? [])
        if (c.trend === 'IMPROVING' || c.trend === 'SLIGHT_UP' || c.signal === 'STRONG')
          piotrMap[c.ticker] = { trend: c.trend, piotroski_current: c.piotroski_current, delta: c.delta }

    if (squeeze.status === 'fulfilled')
      for (const s of squeeze.value.data.setups ?? [])
        squeezeMap[s.ticker] = { severity: s.severity, squeeze_score: s.squeeze_score, short_pct_float: s.short_pct_float, flags: s.flags }

    if (decay.status === 'fulfilled')
      for (const d of decay.value.data.decays ?? [])
        decayMap[d.ticker] = { severity: d.severity, decay_score: d.decay_score, flags: d.flags }

    if (sectorRv.status === 'fulfilled')
      for (const s of sectorRv.value.data.standouts ?? [])
        sectorMap[s.ticker] = { label: s.label, fcf_yield_pct: s.fcf_yield_pct, fcf_rank: s.fcf_rank, fcf_rank_of: s.fcf_rank_of, sector: s.sector }

    if (entry.status === 'fulfilled')
      for (const s of entry.value.data.signals ?? [])
        if (s.signal === 'STRONG_BUY' || s.signal === 'BUY')
          entryMap[s.ticker] = { signal: s.signal, entry_score: s.entry_score }

    const result = { trapMap, smMap, exitMap, divMap, piotrMap, squeezeMap, decayMap, sectorMap, entryMap }
    _cache = result
    return result
  })
  return _promise
}

export function useCerebroSignals(): CerebroMaps {
  const [maps, setMaps] = useState<CerebroMaps>(_cache ?? EMPTY)

  useEffect(() => {
    if (_cache) { setMaps(_cache); return }
    fetchAll().then(setMaps)
  }, [])

  return maps
}
