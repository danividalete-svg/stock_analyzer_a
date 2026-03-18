interface Props {
  page: number
  totalPages: number
  onPage: (p: number) => void
}

export default function PaginationBar({ page, totalPages, onPage }: Props) {
  if (totalPages <= 1) return null

  const goTo = (p: number) => {
    onPage(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Show at most 7 page buttons, with ellipsis
  const pages: (number | '...')[] = []
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i)
  } else {
    pages.push(1)
    if (page > 3) pages.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pages.push(i)
    if (page < totalPages - 2) pages.push('...')
    pages.push(totalPages)
  }

  return (
    <div className="flex items-center justify-center gap-2 pt-4">
      <button
        onClick={() => goTo(page - 1)}
        disabled={page === 1}
        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-border/40 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
      >
        ← Anterior
      </button>
      <div className="flex gap-1">
        {pages.map((p, i) =>
          p === '...'
            ? <span key={`e${i}`} className="w-8 h-8 flex items-center justify-center text-xs text-muted-foreground/50">…</span>
            : (
              <button
                key={p}
                onClick={() => goTo(p as number)}
                className={`w-8 h-8 rounded-lg text-xs font-bold transition-all border ${
                  p === page
                    ? 'bg-primary/20 border-primary/50 text-primary'
                    : 'border-border/30 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60'
                }`}
              >
                {p}
              </button>
            )
        )}
      </div>
      <button
        onClick={() => goTo(page + 1)}
        disabled={page === totalPages}
        className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-border/40 bg-muted/20 text-muted-foreground hover:text-foreground hover:border-border/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
      >
        Siguiente →
      </button>
    </div>
  )
}
