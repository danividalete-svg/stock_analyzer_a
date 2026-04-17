import { useState } from 'react'
import { cn } from '@/lib/utils'
import { getLogoUrl, getClearbitUrl } from '@/lib/logos'

export type LogoSize = 'xs' | 'sm' | 'md' | 'lg'

const SIZE: Record<LogoSize, { px: number; text: string; rounded: string }> = {
  xs: { px: 18, text: 'text-[0.42rem]', rounded: 'rounded' },
  sm: { px: 22, text: 'text-[0.5rem]',  rounded: 'rounded-md' },
  md: { px: 32, text: 'text-[0.6rem]',  rounded: 'rounded-lg' },
  lg: { px: 44, text: 'text-[0.72rem]', rounded: 'rounded-xl' },
}

const PALETTE = [
  'bg-indigo-500/15 text-indigo-300 border-indigo-500/25',
  'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  'bg-violet-500/15 text-violet-300 border-violet-500/25',
  'bg-sky-500/15 text-sky-300 border-sky-500/25',
  'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'bg-teal-500/15 text-teal-300 border-teal-500/25',
]

function paletteColor(ticker: string): string {
  let h = 0
  for (let i = 0; i < ticker.length; i++) h = (h * 31 + (ticker.codePointAt(i) ?? 0)) & 0x7fffffff
  return PALETTE[h % PALETTE.length]
}

// Two-stage source: Parqet first, Clearbit second, initials last
type Stage = 'parqet' | 'clearbit' | 'initials'

interface Props {
  readonly ticker: string
  readonly size?: LogoSize
  readonly className?: string
}

export default function TickerLogo({ ticker, size = 'sm', className }: Props) {
  const [stage, setStage] = useState<Stage>('parqet')
  const { px, text, rounded } = SIZE[size]

  const safe = ticker ?? ''
  const initials = safe.replaceAll(/\.[A-Z]{1,3}$/g, '').replaceAll(/[^A-Z0-9]/g, '').slice(0, 2)

  const base = cn(
    'flex-shrink-0 border inline-flex items-center justify-center overflow-hidden',
    rounded,
    className,
  )

  if (stage === 'initials' || !safe) {
    return (
      <span
        className={cn(base, paletteColor(safe))}
        style={{ width: px, height: px }}
        aria-hidden="true"
      >
        <span className={cn('font-mono font-bold leading-none select-none', text)}>
          {initials}
        </span>
      </span>
    )
  }

  const src = stage === 'parqet' ? getLogoUrl(safe) : (getClearbitUrl(safe) ?? '')

  const handleError = () => {
    if (stage === 'parqet') {
      const fallback = getClearbitUrl(safe)
      setStage(fallback ? 'clearbit' : 'initials')
    } else {
      setStage('initials')
    }
  }

  return (
    <span
      className={cn(base, 'bg-white/90 border-border/30')}
      style={{ width: px, height: px }}
      aria-hidden="true"
    >
      <img
        src={src}
        alt=""
        width={px}
        height={px}
        onError={handleError}
        className="w-full h-full object-contain p-[2px]"
        loading="lazy"
        decoding="async"
      />
    </span>
  )
}
