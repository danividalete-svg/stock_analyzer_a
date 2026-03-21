import { useState, useEffect } from 'react'
import {
  fetchCerebroValueTraps, fetchCerebroSmartMoney,
  fetchCerebroExitSignals, fetchCerebroDividendSafety, fetchCerebroPiotroski,
} from '../api/client'

export interface TrapInfo    { severity: 'HIGH' | 'MEDIUM'; trap_score: number; flags: string[] }
export interface SmartInfo   { n_hedge_funds: number; n_insiders: number; convergence_score: number }
export interface ExitInfo    { severity: 'HIGH' | 'MEDIUM' | 'LOW'; reasons: string[] }
export interface DivRiskInfo { rating: 'AT_RISK' | 'WATCH'; safety_score: number; div_yield: number }
export interface PiotrInfo   { trend: string; piotroski_current: number; delta: number }

export interface CerebroMaps {
  trapMap:  Record<string, TrapInfo>
  smMap:    Record<string, SmartInfo>
  exitMap:  Record<string, ExitInfo>
  divMap:   Record<string, DivRiskInfo>
  piotrMap: Record<string, PiotrInfo>
}

const EMPTY: CerebroMaps = { trapMap: {}, smMap: {}, exitMap: {}, divMap: {}, piotrMap: {} }

export function useCerebroSignals(): CerebroMaps {
  const [maps, setMaps] = useState<CerebroMaps>(EMPTY)

  useEffect(() => {
    Promise.allSettled([
      fetchCerebroValueTraps(),
      fetchCerebroSmartMoney(),
      fetchCerebroExitSignals(),
      fetchCerebroDividendSafety(),
      fetchCerebroPiotroski(),
    ]).then(([traps, sm, exits, div, piotr]) => {
      const trapMap:  Record<string, TrapInfo>    = {}
      const smMap:    Record<string, SmartInfo>   = {}
      const exitMap:  Record<string, ExitInfo>    = {}
      const divMap:   Record<string, DivRiskInfo> = {}
      const piotrMap: Record<string, PiotrInfo>   = {}

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

      setMaps({ trapMap, smMap, exitMap, divMap, piotrMap })
    })
  }, [])

  return maps
}
