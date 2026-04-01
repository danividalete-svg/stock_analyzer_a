import { Star } from 'lucide-react'
import { useWatchlist, type WatchlistEntry } from '../hooks/useWatchlist'
import { useToast } from './Toast'
import { cn } from '@/lib/utils'

type Props = Omit<WatchlistEntry, 'added_at'>

export default function WatchlistButton({ ticker, ...rest }: Props) {
  const { has, toggle } = useWatchlist()
  const { toast } = useToast()
  const active = has(ticker)

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation()
    toggle({ ticker, ...rest })
    if (active) {
      toast(`${ticker} eliminado`, 'info')
    } else {
      toast(`${ticker} añadido a watchlist`, 'success')
    }
  }

  return (
    <button
      onClick={handleClick}
      title={active ? 'Quitar de watchlist' : 'Añadir a watchlist'}
      className={cn(
        'transition-colors shrink-0',
        active ? 'text-amber-400' : 'text-muted-foreground/30 hover:text-amber-400/70'
      )}
    >
      <Star size={13} strokeWidth={active ? 2.5 : 1.75} fill={active ? 'currentColor' : 'none'} />
    </button>
  )
}
