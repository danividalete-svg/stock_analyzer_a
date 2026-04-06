/**
 * PortfolioStatsVideo — Animated portfolio performance summary
 * Lazy-loaded via MarketBriefingPlayer pattern.
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

export interface PortfolioStatsData {
  periods: Array<{
    label: string       // '7d', '14d', '30d'
    win_rate: number    // 0-100
    avg_return: number  // percent
    count: number
  }>
  score_correlation?: number
  best_period?: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function useSpring(frame: number, delay = 0) {
  const { fps } = useVideoConfig()
  return spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 120 } })
}

function CountUp({ target, frame, from, to, decimals = 1 }: { target: number; frame: number; from: number; to: number; decimals?: number }) {
  const val = interpolate(frame, [from, to], [0, target], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  })
  return <>{val.toFixed(decimals)}</>
}

// ─── Donut arc helper ─────────────────────────────────────────────────────────

function DonutArc({ pct, frame, delay, color, radius = 54, stroke = 10 }: {
  pct: number; frame: number; delay: number; color: string; radius?: number; stroke?: number
}) {
  const { fps } = useVideoConfig()
  const sp = spring({ frame: frame - delay, fps, config: { damping: 20, stiffness: 80 } })
  const animatedPct = pct * sp
  const c = 2 * Math.PI * radius
  const dash = (animatedPct / 100) * c
  const cx = radius + stroke
  const cy = radius + stroke

  return (
    <svg width={cx * 2} height={cy * 2} style={{ transform: 'rotate(-90deg)' }}>
      {/* Track */}
      <circle cx={cx} cy={cy} r={radius} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={stroke} />
      {/* Fill */}
      <circle
        cx={cx} cy={cy} r={radius}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={`${dash} ${c}`}
        strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 8px ${color}80)` }}
      />
    </svg>
  )
}

// ─── Single period card ───────────────────────────────────────────────────────

function PeriodCard({ period, index, frame, isBest }: {
  period: PortfolioStatsData['periods'][0]
  index: number
  frame: number
  isBest: boolean
}) {
  const delay = index * 15
  const sp = useSpring(frame, delay)
  const color = period.win_rate >= 50 ? '#10b981' : '#f97316'
  const retColor = period.avg_return >= 0 ? '#10b981' : '#ef4444'

  return (
    <div style={{
      transform: `scale(${sp}) translateY(${interpolate(sp, [0, 1], [40, 0])}px)`,
      background: isBest ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${isBest ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.08)'}`,
      borderRadius: 16,
      padding: '28px 24px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 16,
      flex: 1,
    }}>
      {/* Donut */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <DonutArc pct={period.win_rate} frame={frame} delay={delay + 8} color={color} />
        <div style={{ position: 'absolute', textAlign: 'center' }}>
          <div style={{ fontSize: 22, fontWeight: 900, color, lineHeight: 1 }}>
            <CountUp target={period.win_rate} frame={frame} from={delay + 8} to={delay + 40} />%
          </div>
          <div style={{ fontSize: 10, color: 'rgba(148,163,184,0.6)', marginTop: 2 }}>win rate</div>
        </div>
      </div>

      {/* Label */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span style={{ fontSize: 18, fontWeight: 800, color: '#f1f5f9' }}>{period.label}</span>
        {isBest && <span style={{ fontSize: 10, fontWeight: 700, color: '#10b981', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 6, padding: '2px 6px' }}>BEST</span>}
      </div>

      {/* Return */}
      <div style={{ fontSize: 15, fontWeight: 700, color: retColor }}>
        {period.avg_return >= 0 ? '+' : ''}
        <CountUp target={Math.abs(period.avg_return)} frame={frame} from={delay + 8} to={delay + 40} decimals={2} />%
        <span style={{ fontSize: 11, color: 'rgba(148,163,184,0.5)', fontWeight: 400, marginLeft: 4 }}>avg</span>
      </div>

      <div style={{ fontSize: 11, color: 'rgba(148,163,184,0.45)' }}>{period.count} señales</div>
    </div>
  )
}

// ─── Main composition ─────────────────────────────────────────────────────────

function PortfolioStatsComposition({ data }: { data: PortfolioStatsData }) {
  const frame = useCurrentFrame()

  const titleFade = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' })
  const corrSp = useSpring(frame, data.periods.length * 15 + 20)

  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(135deg, #0a0f1e 0%, #0d1a2d 50%, #070d1a 100%)',
      fontFamily: '"Inter", "SF Pro Display", system-ui, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '40px 52px',
      gap: 32,
    }}>
      {/* Grid */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(6,182,212,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(6,182,212,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      {/* Header */}
      <div style={{ opacity: titleFade }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'rgba(6,182,212,0.8)', textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 6 }}>
          Portfolio · Performance
        </div>
        <div style={{ fontSize: 30, fontWeight: 900, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
          Historial de señales
        </div>
      </div>

      {/* Period cards */}
      <div style={{ display: 'flex', gap: 20 }}>
        {data.periods.map((p, i) => (
          <PeriodCard
            key={p.label}
            period={p}
            index={i}
            frame={frame}
            isBest={p.label === data.best_period}
          />
        ))}
      </div>

      {/* Correlation */}
      {data.score_correlation != null && (
        <div style={{
          transform: `scale(${corrSp})`,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 12,
          padding: '14px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 13, color: 'rgba(148,163,184,0.7)' }}>Correlación Score → Retorno</span>
          <span style={{
            fontSize: 20, fontWeight: 800,
            color: data.score_correlation > 0.1 ? '#10b981' : '#f59e0b',
          }}>
            {data.score_correlation.toFixed(3)}
          </span>
        </div>
      )}
    </AbsoluteFill>
  )
}

// ─── Player wrapper ───────────────────────────────────────────────────────────

const RemotionPlayer = lazy(() =>
  import('@remotion/player').then(m => ({ default: m.Player }))
)

export function PortfolioStatsPlayer({ data }: { data: PortfolioStatsData }) {
  const totalFrames = 60 + data.periods.length * 15 + 60
  return (
    <Suspense fallback={
      <div className="glass border border-border/40 rounded-xl h-24 flex items-center justify-center text-sm text-muted-foreground">
        Cargando…
      </div>
    }>
      <RemotionPlayer
        component={PortfolioStatsComposition as React.ComponentType<Record<string, unknown>>}
        inputProps={{ data } as Record<string, unknown>}
        durationInFrames={totalFrames}
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
