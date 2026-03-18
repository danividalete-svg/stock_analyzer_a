interface Props {
  narrative: string | null | undefined
  label?: string
  className?: string
}

/** Parse numbered lines (1. ..., 2. ...) and bold headers (**text**) */
function parseNarrative(text: string) {
  const lines = text.split('\n').filter(l => l.trim())
  const elements: { type: 'title' | 'point' | 'quote' | 'text'; content: string; num?: number }[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    // Bold title: **Análisis de la cartera**
    const boldMatch = trimmed.match(/^\*\*(.+?)\*\*$/)
    if (boldMatch) {
      elements.push({ type: 'title', content: boldMatch[1] })
      continue
    }
    // Numbered point: 1. text, 2. text
    const numMatch = trimmed.match(/^(\d+)\.\s+(.+)/)
    if (numMatch) {
      elements.push({ type: 'point', content: numMatch[2], num: parseInt(numMatch[1]) })
      continue
    }
    // Quoted text (starts/ends with ")
    if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
      elements.push({ type: 'quote', content: trimmed.slice(1, -1) })
      continue
    }
    // Bullet points
    const bulletMatch = trimmed.match(/^[•\-]\s+(.+)/)
    if (bulletMatch) {
      elements.push({ type: 'point', content: bulletMatch[1] })
      continue
    }
    elements.push({ type: 'text', content: trimmed })
  }

  return elements
}

/** Render inline bold **text** within a string */
function renderInlineBold(text: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g)
  return parts.map((part, i) =>
    i % 2 === 1 ? <strong key={i} className="font-semibold text-foreground">{part}</strong> : part
  )
}

export default function AiNarrativeCard({ narrative, label = 'Análisis IA', className = '' }: Props) {
  if (!narrative) return null

  const elements = parseNarrative(narrative)
  const hasStructure = elements.some(e => e.type !== 'text')

  return (
    <div className={`rounded-xl border border-indigo-500/25 bg-gradient-to-r from-indigo-500/8 to-transparent overflow-hidden ${className}`}>
      <div className="flex items-center gap-2 px-4 py-2 border-b border-indigo-500/15 bg-indigo-500/8">
        <span className="text-sm leading-none">🤖</span>
        <span className="text-[0.62rem] font-bold text-indigo-400 uppercase tracking-widest">{label}</span>
      </div>
      {hasStructure ? (
        <div className="px-4 py-3 space-y-2.5">
          {elements.map((el, i) => {
            if (el.type === 'title') return (
              <div key={i} className="text-xs font-bold text-primary uppercase tracking-wide">{el.content}</div>
            )
            if (el.type === 'point') return (
              <div key={i} className="flex gap-2.5 items-start">
                {el.num != null && (
                  <span className="flex-shrink-0 w-5 h-5 rounded-md bg-primary/15 text-primary text-[0.6rem] font-bold flex items-center justify-center mt-0.5">
                    {el.num}
                  </span>
                )}
                {el.num == null && (
                  <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-primary/50 mt-1.5" />
                )}
                <p className="text-sm text-foreground/85 leading-relaxed">{renderInlineBold(el.content)}</p>
              </div>
            )
            if (el.type === 'quote') return (
              <blockquote key={i} className="border-l-2 border-primary/40 pl-3 italic text-sm text-foreground/70 leading-relaxed">
                {renderInlineBold(el.content)}
              </blockquote>
            )
            return <p key={i} className="text-sm text-foreground/85 leading-relaxed">{renderInlineBold(el.content)}</p>
          })}
        </div>
      ) : (
        <p className="px-4 py-3 text-sm text-foreground/85 leading-relaxed">{narrative}</p>
      )}
    </div>
  )
}
