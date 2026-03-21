import type { TrapInfo, SmartInfo, ExitInfo, DivRiskInfo, PiotrInfo } from '../hooks/useCerebroSignals'

interface Props {
  trapInfo?:  TrapInfo
  smInfo?:    SmartInfo
  exitInfo?:  ExitInfo
  divInfo?:   DivRiskInfo
  piotrInfo?: PiotrInfo
}

export default function CerebroBadges({ trapInfo, smInfo, exitInfo, divInfo, piotrInfo }: Props) {
  if (!trapInfo && !smInfo && !exitInfo && !divInfo && !piotrInfo) return null

  return (
    <div className="flex items-center gap-0.5 flex-wrap mt-0.5">

      {/* EXIT — highest priority, most alarming */}
      {exitInfo && (
        <span
          title={`Señal de salida ${exitInfo.severity}: ${exitInfo.reasons.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide animate-pulse ${
            exitInfo.severity === 'HIGH'
              ? 'bg-red-500/25 text-red-300 border-red-500/50'
              : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
          }`}
        >
          ⬆ EXIT
        </span>
      )}

      {/* TRAP — value trap warning */}
      {trapInfo && (
        <span
          title={`Value trap (${trapInfo.trap_score}/10): ${trapInfo.flags.slice(0, 2).join(' · ')}`}
          className={`inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide ${
            trapInfo.severity === 'HIGH'
              ? 'bg-red-500/20 text-red-400 border-red-500/35'
              : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
          }`}
        >
          ⚠ TRAP
        </span>
      )}

      {/* SMART MONEY — hedge funds + insiders buying */}
      {smInfo && (
        <span
          title={`Smart Money: ${smInfo.n_hedge_funds} HF + ${smInfo.n_insiders} insiders · conv ${smInfo.convergence_score}`}
          className="inline-flex items-center gap-0.5 text-[0.48rem] font-black px-1 py-px rounded border tracking-wide bg-purple-500/20 text-purple-300 border-purple-500/35"
        >
          ◆ SMART$
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
          💰 DIV⚠
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
          ▲ F{piotrInfo.piotroski_current}
        </span>
      )}
    </div>
  )
}
