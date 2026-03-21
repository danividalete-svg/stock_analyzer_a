import { createContext, useContext, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react'
import { supabase } from '@/lib/supabase'
import { useAuth } from './AuthContext'

interface OwnedPosition {
  id: string
  ticker: string
  shares: number
  avg_price: number
  currency: 'USD' | 'EUR'
}

interface PersonalPortfolioCtx {
  positions: OwnedPosition[]
  isOwned: (ticker: string) => boolean
  getPosition: (ticker: string) => OwnedPosition | undefined
  loading: boolean
}

const Ctx = createContext<PersonalPortfolioCtx>({
  positions: [],
  isOwned: () => false,
  getPosition: () => undefined,
  loading: false,
})

export function PersonalPortfolioProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [positions, setPositions] = useState<OwnedPosition[]>([])
  const [loading, setLoading]     = useState(false)

  useEffect(() => {
    if (!user) { setPositions([]); return }
    let cancelled = false
    setLoading(true)
    supabase
      .from('personal_portfolio_positions')
      .select('id, ticker, shares, avg_price, currency')
      .eq('user_id', user.id)
      .then(({ data }) => {
        if (cancelled) return
        setPositions((data ?? []) as OwnedPosition[])
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [user])

  const isOwned     = useCallback((ticker: string) => positions.some(p => p.ticker === ticker.toUpperCase()), [positions])
  const getPosition = useCallback((ticker: string) => positions.find(p => p.ticker === ticker.toUpperCase()), [positions])

  const value = useMemo(() => ({ positions, isOwned, getPosition, loading }), [positions, isOwned, getPosition, loading])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export const usePersonalPortfolio = () => useContext(Ctx)
