import type { TrapInfo, SmartInfo, ExitInfo, DivRiskInfo, PiotrInfo, SqueezeInfo, DecayInfo, SectorRVInfo, EntryInfo } from '../hooks/useCerebroSignals'

interface Props {
  trapInfo?:    TrapInfo
  smInfo?:      SmartInfo
  exitInfo?:    ExitInfo
  divInfo?:     DivRiskInfo
  piotrInfo?:   PiotrInfo
  squeezeInfo?: SqueezeInfo
  decayInfo?:   DecayInfo
  sectorInfo?:  SectorRVInfo
  entryInfo?:   EntryInfo
}

export default function CerebroBadges({ trapInfo, smInfo, exitInfo, divInfo, piotrInfo, squeezeInfo, decayInfo, sectorInfo, entryInfo }: Props) {
  if (!trapInfo && !smInfo && !exitInfo && !divInfo && !piotrInfo && !squeezeInfo && !decayInfo && !sectorInfo && !entryInfo) return null

  return (
    <div className="flex items-center gap-0.5 flex-wrap mt-0.5">

      {/* CEREBRO ENTRY — positive signal, shown first */}
      {entryInfo && (
        <span
          title={`Cerebro señal de ENTRADA (${entryInfo.signal.replace('_', ' ')}): entry score ${entryInfo.entry_score}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            entryInfo.signal === 'STRONG_BUY'
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
          }`}
        >
          ⚡ {entryInfo.signal === 'STRONG_BUY' ? 'STRONG BUY' : 'BUY'}
        </span>
      )}

      {/* EXIT — highest priority, most alarming */}
      {exitInfo && (
        <span
          title={`Cerebro recomienda SALIDA de posición (${exitInfo.severity}): ${exitInfo.reasons.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide animate-pulse ${
            exitInfo.severity === 'HIGH'
              ? 'bg-red-500/25 text-red-300 border-red-500/50'
              : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
          }`}
        >
          ⬆ EXIT
        </span>
      )}

      {/* QUALITY DECAY — early warning before trap */}
      {decayInfo && (
        <span
          title={`Deterioro de calidad fundamental (${decayInfo.severity}): ${decayInfo.flags.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            decayInfo.severity === 'HIGH'
              ? 'bg-orange-500/20 text-orange-400 border-orange-500/35'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/25'
          }`}
        >
          ↘ DETERIORO
        </span>
      )}

      {/* TRAP — value trap warning */}
      {trapInfo && (
        <span
          title={`Cerebro detecta señal TRAMPA — evitar entrada (score ${trapInfo.trap_score}/10): ${trapInfo.flags.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            trapInfo.severity === 'HIGH'
              ? 'bg-red-500/20 text-red-400 border-red-500/35'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
          }`}
        >
          ⚠ TRAP
        </span>
      )}

      {/* SQUEEZE — short squeeze setup */}
      {squeezeInfo && (
        <span
          title={`Potencial SHORT SQUEEZE detectado (${squeezeInfo.severity}): ${squeezeInfo.short_pct_float.toFixed(1)}% short · ${squeezeInfo.flags.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            squeezeInfo.severity === 'HIGH'
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
              : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/25'
          }`}
        >
          ↑ SHORT SQZ
        </span>
      )}

      {/* SMART MONEY — hedge funds + insiders buying */}
      {smInfo && (
        <span
          title={`Smart Money convergente: ${smInfo.n_hedge_funds} hedge funds + ${smInfo.n_insiders} insiders comprando · conv ${smInfo.convergence_score}`}
          className="inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide bg-purple-500/20 text-purple-300 border-purple-500/35"
        >
          ◆ SMART MONEY
        </span>
      )}

      {/* BEST IN SECTOR / PRICEY VS PEERS */}
      {sectorInfo && (
        <span
          title={
            sectorInfo.label === 'BEST_IN_SECTOR'
              ? `Mejor FCF en ${sectorInfo.sector}: rank ${sectorInfo.fcf_rank}/${sectorInfo.fcf_rank_of} (${sectorInfo.fcf_yield_pct.toFixed(1)}% FCF yield)`
              : `Caro vs peers en ${sectorInfo.sector}: rank ${sectorInfo.fcf_rank}/${sectorInfo.fcf_rank_of}`
          }
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            sectorInfo.label === 'BEST_IN_SECTOR'
              ? 'bg-teal-500/15 text-teal-400 border-teal-500/30'
              : 'bg-slate-500/15 text-slate-400 border-slate-500/25'
          }`}
        >
          {sectorInfo.label === 'BEST_IN_SECTOR' ? '★ BEST' : '↑ PRICEY'}
        </span>
      )}

      {/* DIVIDEND AT RISK */}
      {divInfo && (
        <span
          title={`Dividendo ${divInfo.rating}: yield ${divInfo.div_yield.toFixed(1)}% — safety score ${divInfo.safety_score}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            divInfo.rating === 'AT_RISK'
              ? 'bg-red-500/15 text-red-400 border-red-500/30'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/25'
          }`}
        >
          ⚠ DIV RIESGO
        </span>
      )}

      {/* PIOTROSKI IMPROVING */}
      {piotrInfo && (
        <span
          title={`Piotroski F${piotrInfo.piotroski_current}/9 · ${piotrInfo.trend.replace('_', ' ')}${piotrInfo.delta !== 0 ? ` (${piotrInfo.delta > 0 ? '+' : ''}${piotrInfo.delta})` : ''}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            piotrInfo.trend === 'IMPROVING'
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
              : piotrInfo.piotroski_current >= 7
              ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
              : 'bg-blue-500/10 text-blue-300 border-blue-500/20'
          }`}
        >
          ▲ F-Score {piotrInfo.piotroski_current}/9
        </span>
      )}
    </div>
  )
}
