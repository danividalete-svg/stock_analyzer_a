/**
 * MarketBriefingVideo — Animated market briefing using Remotion
 *
 * Embed with <MarketBriefingPlayer /> — lazy-loads @remotion/player
 * so it doesn't bloat the main bundle.
 */

import React, { lazy, Suspense } from 'react'
import {
  AbsoluteFill,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from 'remotion'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BriefingData {
  regime: string
  regime_color: string
  composite_score: number
  max_score: number
  date: string
  top_picks: Array<{
    ticker: string
    company_name: string
    value_score: number
    conviction_grade?: string
    sector?: string
    analyst_upside_pct?: number
  }>
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function useSpring(frame: number, delay = 0, damping = 14) {
  const { fps } = useVideoConfig()
  return spring({ frame: frame - delay, fps, config: { damping, stiffness: 120 } })
}

function CountUp({ target, frame, startFrame, duration }: { target: number; frame: number; startFrame: number; duration: number }) {
  const progress = interpolate(frame, [startFrame, startFrame + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  })
  return <>{Math.round(progress * target)}</>
}

function gradeColor(grade?: string) {
  if (!grade) return '#94a3b8'
  if (grade.startsWith('A')) return '#10b981'
  if (grade.startsWith('B')) return '#22d3ee'
  if (grade.startsWith('C')) return '#f59e0b'
  return '#ef4444'
}

// ─── Scene 1: Regime Header (0-60 frames = 2s) ───────────────────────────────

function RegimeScene({ data }: { data: BriefingData }) {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const titleSpring = useSpring(frame, 5)
  const scoreSpring = useSpring(frame, 20, 10)
  const dotPulse = interpolate(Math.sin((frame / fps) * Math.PI * 2), [-1, 1], [0.6, 1])

  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(135deg, #0a0f1e 0%, #0d1a2d 50%, #070d1a 100%)',
      fontFamily: '"Inter", "SF Pro Display", system-ui, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 32,
    }}>
      {/* Grid background */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(6,182,212,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(6,182,212,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      {/* Logo / date */}
      <div style={{
        position: 'absolute', top: 32, left: 48,
        opacity: interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' }),
        color: 'rgba(148,163,184,0.7)',
        fontSize: 14,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
      }}>
        Stock Analyzer · {data.date}
      </div>

      {/* Regime dot + name */}
      <div style={{
        transform: `scale(${titleSpring}) translateY(${interpolate(titleSpring, [0, 1], [30, 0])}px)`,
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <div style={{
          width: 20, height: 20,
          borderRadius: '50%',
          backgroundColor: data.regime_color,
          opacity: dotPulse,
          boxShadow: `0 0 24px ${data.regime_color}`,
        }} />
        <span style={{
          fontSize: 48, fontWeight: 900,
          color: '#f1f5f9',
          letterSpacing: '-0.02em',
        }}>
          {data.regime}
        </span>
      </div>

      {/* Score */}
      <div style={{
        transform: `scale(${scoreSpring})`,
        display: 'flex', alignItems: 'baseline', gap: 8,
      }}>
        <span style={{ fontSize: 80, fontWeight: 900, color: data.regime_color, lineHeight: 1 }}>
          <CountUp target={data.composite_score} frame={frame} startFrame={20} duration={35} />
        </span>
        <span style={{ fontSize: 32, color: 'rgba(148,163,184,0.6)' }}>/ {data.max_score}</span>
      </div>

      {/* Score bar */}
      <div style={{
        width: 320, height: 6,
        backgroundColor: 'rgba(255,255,255,0.08)',
        borderRadius: 3,
        overflow: 'hidden',
        transform: `scaleX(${interpolate(frame, [25, 55], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })})`,
        transformOrigin: 'left',
      }}>
        <div style={{
          width: `${(data.composite_score / data.max_score) * 100}%`,
          height: '100%',
          background: `linear-gradient(90deg, ${data.regime_color}, #06b6d4)`,
          borderRadius: 3,
        }} />
      </div>
    </AbsoluteFill>
  )
}

// ─── Scene 2: Top Picks (60-150 frames = 3s) ─────────────────────────────────

function PickCard({ pick, index, frame }: {
  pick: BriefingData['top_picks'][0]
  index: number
  frame: number
}) {
  const { fps } = useVideoConfig()
  const delay = index * 12
  const cardSpring = spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 130 } })
  const slideIn = interpolate(cardSpring, [0, 1], [60, 0])
  const upside = pick.analyst_upside_pct ?? 0

  return (
    <div style={{
      transform: `translateX(${slideIn}px)`,
      opacity: cardSpring,
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 12,
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: 20,
    }}>
      {/* Rank */}
      <div style={{
        width: 36, height: 36,
        borderRadius: '50%',
        background: 'rgba(6,182,212,0.15)',
        border: '1px solid rgba(6,182,212,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16, fontWeight: 700, color: '#06b6d4',
        flexShrink: 0,
      }}>
        {index + 1}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ fontSize: 22, fontWeight: 800, color: '#f1f5f9' }}>{pick.ticker}</span>
          {pick.conviction_grade && (
            <span style={{
              fontSize: 12, fontWeight: 700,
              color: gradeColor(pick.conviction_grade),
              background: `${gradeColor(pick.conviction_grade)}20`,
              border: `1px solid ${gradeColor(pick.conviction_grade)}40`,
              borderRadius: 6, padding: '2px 8px',
            }}>
              {pick.conviction_grade}
            </span>
          )}
        </div>
        <div style={{ fontSize: 13, color: 'rgba(148,163,184,0.8)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {pick.company_name}
        </div>
        {pick.sector && (
          <div style={{ fontSize: 11, color: 'rgba(100,116,139,0.9)', marginTop: 2 }}>{pick.sector}</div>
        )}
      </div>

      {/* Score + upside */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 24, fontWeight: 800, color: '#f1f5f9' }}>
          {pick.value_score}<span style={{ fontSize: 13, color: 'rgba(148,163,184,0.5)', fontWeight: 400 }}>pts</span>
        </div>
        {upside > 0 && (
          <div style={{ fontSize: 13, color: '#10b981', fontWeight: 600 }}>+{upside.toFixed(0)}% upside</div>
        )}
      </div>
    </div>
  )
}

function TopPicksScene({ data }: { data: BriefingData }) {
  const frame = useCurrentFrame()
  const titleFade = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' })

  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(135deg, #0a0f1e 0%, #0d1a2d 50%, #070d1a 100%)',
      fontFamily: '"Inter", "SF Pro Display", system-ui, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      padding: '40px 60px',
      gap: 20,
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `
          linear-gradient(rgba(6,182,212,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(6,182,212,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '40px 40px',
      }} />

      <div style={{
        opacity: titleFade,
        fontSize: 13, fontWeight: 600,
        color: 'rgba(6,182,212,0.8)',
        textTransform: 'uppercase', letterSpacing: '0.15em',
        marginBottom: 4,
      }}>
        Top VALUE Picks · Hoy
      </div>

      {data.top_picks.slice(0, 5).map((pick, i) => (
        <PickCard key={pick.ticker} pick={pick} index={i} frame={frame} />
      ))}
    </AbsoluteFill>
  )
}

// ─── Scene 3: Outro (150-180 frames = 1s) ────────────────────────────────────

function OutroScene() {
  const frame = useCurrentFrame()
  const opacity = interpolate(frame, [0, 20, 60, 80], [0, 1, 1, 0], { extrapolateRight: 'clamp' })

  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(135deg, #0a0f1e 0%, #070d1a 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 12,
      opacity,
    }}>
      <div style={{ fontSize: 28, fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.02em' }}>
        Stock Analyzer
      </div>
      <div style={{ fontSize: 13, color: 'rgba(148,163,184,0.5)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        Daily Briefing
      </div>
    </AbsoluteFill>
  )
}

// ─── Root Composition ─────────────────────────────────────────────────────────

export function MarketBriefingComposition({ data }: { data: BriefingData }) {
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={65}>
        <RegimeScene data={data} />
      </Sequence>
      <Sequence from={60} durationInFrames={95}>
        <TopPicksScene data={data} />
      </Sequence>
      <Sequence from={150} durationInFrames={30}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  )
}

// ─── Player wrapper (lazy-loaded) ─────────────────────────────────────────────

const RemotionPlayer = lazy(() =>
  import('@remotion/player').then(m => ({ default: m.Player }))
)

export function MarketBriefingPlayer({ data }: { data: BriefingData }) {
  return (
    <Suspense fallback={
      <div style={{
        width: '100%', aspectRatio: '16/9',
        background: 'rgba(0,0,0,0.3)',
        borderRadius: 12,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'rgba(148,163,184,0.5)', fontSize: 14,
      }}>
        Cargando animación…
      </div>
    }>
      <RemotionPlayer
        component={MarketBriefingComposition as React.ComponentType<Record<string, unknown>>}
        inputProps={{ data } as Record<string, unknown>}
        durationInFrames={180}
        compositionWidth={800}
        compositionHeight={450}
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
