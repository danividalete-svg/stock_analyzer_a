const SIZE_MAP = { sm: 36, md: 52, lg: 72 }
const STROKE_MAP = { sm: 3, md: 4, lg: 5 }

function scoreColor(s: number) {
  if (s >= 70) return 'hsl(142 76% 46%)'
  if (s >= 55) return 'hsl(217 91% 60%)'
  if (s >= 40) return 'hsl(38 92% 50%)'
  return 'hsl(0 72% 51%)'
}

export default function ScoreRing({ score, size = 'md', showLabel = true }: {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}) {
  const px = SIZE_MAP[size]
  const stroke = STROKE_MAP[size]
  const r = (px - stroke * 2) / 2
  const cx = px / 2
  const circumference = 2 * Math.PI * r
  const pct = Math.min(Math.max(score, 0), 100) / 100
  const offset = circumference * (1 - pct)
  const color = scoreColor(score)
  const fontSize = size === 'lg' ? 18 : size === 'md' ? 13 : 10

  return (
    <div style={{ width: px, height: px, position: 'relative', flexShrink: 0 }}>
      <svg width={px} height={px} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-muted/20"
        />
        {/* Arc */}
        <circle
          cx={cx} cy={cx} r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.22, 1, 0.36, 1)' }}
        />
      </svg>
      {showLabel && (
        <span style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
          color, lineHeight: 1,
        }}>
          {Math.round(score)}
        </span>
      )}
    </div>
  )
}
