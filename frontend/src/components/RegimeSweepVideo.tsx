/**
 * RegimeSweepVideo — Animated regime score sweep for MacroRadar
 * Shows gauge needle sweeping to composite score + top signals sliding in.
 */

import React, { lazy, Suspense } from 'react'
import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from 'remotion'

export interface RegimeSweepData {
  regime: string
  regime_color: string
  composite_score: number
  max_score: number
  date: string
  top_signals: Array<{ name: string; value: number; label: string }>
}

// ─── Gauge ────────────────────────────────────────────────────────────────────

function GaugeMeter({ score, max, color, frame }: { score: number; max: number; color: string; frame: number }) {
  const { fps } = useVideoConfig()
  const sp = spring({ frame: frame - 10, fps, config: { damping: 18, stiffness: 60, mass: 1.2 } })

  const W = 320, H = 180
  const cx = W / 2, cy = H - 10
  const r = 130
  const startAngle = -180
  const endAngle = 0
  const pct = ((score + max) / (2 * max)) * sp  // normalize -max..+max → 0..1
  const angleDeg = startAngle + pct * (endAngle - startAngle)
  const rad = (angleDeg * Math.PI) / 180
  const needleX = cx + r * 0.85 * Math.cos(rad)
  const needleY = cy + r * 0.85 * Math.sin(rad)

  // Arc path from startAngle to current angle
  function arcPath(from: number, to: number, radius: number) {
    const toRad = (deg: number) => (deg * Math.PI) / 180
    const x1 = cx + radius * Math.cos(toRad(from))
    const y1 = cy + radius * Math.sin(toRad(from))
    const x2 = cx + radius * Math.cos(toRad(to))
    const y2 = cy + radius * Math.sin(toRad(to))
    const large = to - from > 180 ? 1 : 0
    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2}`
  }

  const currentAngle = startAngle + pct * (endAngle - startAngle)

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      {/* Track */}
      <path d={arcPath(-180, 0, r)} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={14} strokeLinecap="round" />
      {/* Negative zone (red) */}
      <path d={arcPath(-180, -90, r)} fill="none" stroke="rgba(239,68,68,0.25)" strokeWidth={14} strokeLinecap="round" />
      {/* Positive zone (green) */}
      <path d={arcPath(-90, 0, r)} fill="none" stroke="rgba(16,185,129,0.2)" strokeWidth={14} strokeLinecap="round" />
      {/* Active fill */}
      {pct > 0.01 && <path d={arcPath(-180, currentAngle, r)} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 12px ${color})` }} />}
      {/* Needle */}
      <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke={color} strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={8} fill={color} style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
      {/* Center label */}
      <text x={cx} y={cy - 20} textAnchor="middle" fontSize={28} fontWeight={900} fill="#f1f5f9" fontFamily="Inter,system-ui">
        {score > 0 ? '+' : ''}{score.toFixed(1)}
      </text>
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize={11} fill="rgba(148,163,184,0.5)" fontFamily="Inter,system-ui">
        / {max}
      </text>
    </svg>
  )
}

// ─── Signal bar ───────────────────────────────────────────────────────────────

function SignalBar({ signal, index, frame, regimeColor }: {
  signal: RegimeSweepData['top_signals'][0]
  index: number
  frame: number
  regimeColor: string
}) {
  const { fps } = useVideoConfig()
  const delay = 35 + index * 10
  const sp = spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 130 } })
  const slideX = interpolate(sp, [0, 1], [50, 0])
  const barWidth = interpolate(frame, [delay + 5, delay + 30], [0, (signal.value / 100) * 100], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  })

  return (
    <div style={{
      transform: `translateX(${slideX}px)`,
      opacity: sp,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    }}>
      <div style={{ width: 120, fontSize: 11, color: 'rgba(148,163,184,0.8)', textAlign: 'right', flexShrink: 0 }}>
        {signal.name}
      </div>
      <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${barWidth}%`, height: '100%', background: signal.value > 60 ? '#10b981' : signal.value > 40 ? regimeColor : '#ef4444', borderRadius: 3 }} />
      </div>
      <div style={{ width: 36, fontSize: 11, fontWeight: 700, color: '#f1f5f9', textAlign: 'right', flexShrink: 0 }}>
        {signal.value}
      </div>
    </div>
  )
}

// ─── Composition ──────────────────────────────────────────────────────────────

function RegimeSweepComposition({ data }: { data: RegimeSweepData }) {
  const frame = useCurrentFrame()

  const headerSp = spring({ frame, fps: 30, config: { damping: 16, stiffness: 120 } })
  const titleY = interpolate(headerSp, [0, 1], [-20, 0])

  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(135deg, #0a0f1e 0%, #0d1a2d 60%, #070d1a 100%)',
      fontFamily: '"Inter", "SF Pro Display", system-ui, sans-serif',
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      padding: '36px 52px',
      gap: 48,
    }}>
      {/* Grid bg */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(6,182,212,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(6,182,212,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      {/* Left: gauge + regime name */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        transform: `translateY(${titleY}px)`, opacity: headerSp,
        gap: 16, flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{
            width: 12, height: 12, borderRadius: '50%',
            backgroundColor: data.regime_color,
            boxShadow: `0 0 16px ${data.regime_color}`,
          }} />
          <span style={{ fontSize: 22, fontWeight: 900, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
            {data.regime}
          </span>
        </div>
        <GaugeMeter score={data.composite_score} max={data.max_score} color={data.regime_color} frame={frame} />
        <div style={{ fontSize: 11, color: 'rgba(148,163,184,0.4)', marginTop: -8 }}>{data.date}</div>
      </div>

      {/* Right: signal bars */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{
          fontSize: 10, fontWeight: 700, color: 'rgba(6,182,212,0.7)',
          textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 4,
          opacity: interpolate(frame, [5, 20], [0, 1], { extrapolateRight: 'clamp' }),
        }}>
          Señales del mercado
        </div>
        {data.top_signals.slice(0, 8).map((s, i) => (
          <SignalBar key={s.name} signal={s} index={i} frame={frame} regimeColor={data.regime_color} />
        ))}
      </div>
    </AbsoluteFill>
  )
}

// ─── Player wrapper ───────────────────────────────────────────────────────────

const RemotionPlayer = lazy(() =>
  import('@remotion/player').then(m => ({ default: m.Player }))
)

export function RegimeSweepPlayer({ data }: { data: RegimeSweepData }) {
  return (
    <Suspense fallback={
      <div className="glass border border-border/40 rounded-xl h-24 flex items-center justify-center text-sm text-muted-foreground">
        Cargando…
      </div>
    }>
      <RemotionPlayer
        component={RegimeSweepComposition as React.ComponentType<Record<string, unknown>>}
        inputProps={{ data } as Record<string, unknown>}
        durationInFrames={150}
        compositionWidth={900}
        compositionHeight={380}
        fps={30}
        style={{ width: '100%', borderRadius: 12, overflow: 'hidden' }}
        controls
        loop
        autoPlay
        showVolumeControls={false}
      />
    </Suspense>
  )
}
