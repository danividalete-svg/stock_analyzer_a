import { cn } from '@/lib/utils'
import { nlGrade } from '@/lib/nl'

interface Props {
  readonly grade?: string
  readonly score?: number
}

export default function GradeBadge({ grade, score }: Props) {
  if (!grade) return <span className="text-muted-foreground">—</span>
  const nlTitle = nlGrade(grade)
  const title = score ? `${nlTitle}\nConviction: ${score}/100` : nlTitle
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center px-2 py-0.5 rounded-md border text-xs font-bold tracking-wide min-w-[26px] cursor-help',
        `grade-${grade}`
      )}
      title={title}
    >
      {grade}
    </span>
  )
}
