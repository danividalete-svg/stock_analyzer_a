import { useState, useEffect, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/context/AuthContext'

const KEY = 'sa-watchlist-v1'

export interface WatchlistEntry {
  ticker: string
  company_name?: string
  sector?: string
  added_at: string
  value_score?: number
  conviction_grade?: string
  analyst_upside_pct?: number
  fcf_yield_pct?: number
  current_price?: number
  note?: string
}

function loadLocal(): WatchlistEntry[] {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as WatchlistEntry[]) : []
  } catch {
    return []
  }
}

function saveLocal(entries: WatchlistEntry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries))
  } catch {
    // storage quota exceeded — fail silently
  }
}

// Module-level flag so migration only runs once per page load
let _migrationDone = false

export function useWatchlist() {
  const { user } = useAuth()
  const [entries, setEntries] = useState<WatchlistEntry[]>(loadLocal)

  // Sync from Supabase on login / user change
  useEffect(() => {
    if (!user) return

    let cancelled = false

    // One-time migration: push existing localStorage entries to Supabase
    if (!_migrationDone) {
      _migrationDone = true
      const local = loadLocal()
      if (local.length > 0) {
        const rows = local.map(e => ({ user_id: user.id, ticker: e.ticker }))
        supabase.from('watchlist').upsert(rows, { onConflict: 'user_id,ticker' })
          .then(({ error }) => { if (error) console.error('[watchlist] migration error', error) })
      }
    }

    // Load tickers from Supabase and merge with local metadata
    supabase
      .from('watchlist')
      .select('ticker, added_at')
      .eq('user_id', user.id)
      .order('added_at', { ascending: false })
      .then(({ data, error }) => {
        if (cancelled) return
        if (error) { console.error('[watchlist] load error', error); return }
        if (!data) return
        const localMap = new Map(loadLocal().map(e => [e.ticker, e]))
        const merged: WatchlistEntry[] = data.map(row => {
          const meta = localMap.get(row.ticker)
          return meta
            ? { ...meta, ticker: row.ticker, added_at: row.added_at as string }
            : { ticker: row.ticker, added_at: row.added_at as string }
        })
        setEntries(merged)
        saveLocal(merged)
      })

    return () => { cancelled = true }
  }, [user?.id])

  const add = useCallback((entry: Omit<WatchlistEntry, 'added_at'>) => {
    const newEntry: WatchlistEntry = { ...entry, added_at: new Date().toISOString() }
    setEntries(prev => {
      if (prev.some(e => e.ticker === entry.ticker)) return prev
      const next = [newEntry, ...prev]
      saveLocal(next)
      return next
    })
    if (user) {
      supabase.from('watchlist').insert({ user_id: user.id, ticker: entry.ticker })
        .then(({ error }) => { if (error) console.error('[watchlist] add error', error) })
    }
  }, [user])

  const remove = useCallback((ticker: string) => {
    setEntries(prev => {
      const next = prev.filter(e => e.ticker !== ticker)
      saveLocal(next)
      return next
    })
    if (user) {
      supabase.from('watchlist').delete().match({ user_id: user.id, ticker })
        .then(({ error }) => { if (error) console.error('[watchlist] remove error', error) })
    }
  }, [user])

  const toggle = useCallback((entry: Omit<WatchlistEntry, 'added_at'>) => {
    setEntries(prev => {
      const exists = prev.some(e => e.ticker === entry.ticker)
      if (exists) {
        if (user) supabase.from('watchlist').delete().match({ user_id: user.id, ticker: entry.ticker })
          .then(({ error }) => { if (error) console.error('[watchlist] toggle-remove error', error) })
        const next = prev.filter(e => e.ticker !== entry.ticker)
        saveLocal(next)
        return next
      } else {
        if (user) supabase.from('watchlist').insert({ user_id: user.id, ticker: entry.ticker })
          .then(({ error }) => { if (error) console.error('[watchlist] toggle-add error', error) })
        const newEntry: WatchlistEntry = { ...entry, added_at: new Date().toISOString() }
        const next = [newEntry, ...prev]
        saveLocal(next)
        return next
      }
    })
  }, [user])

  const has = useCallback((ticker: string) => entries.some(e => e.ticker === ticker), [entries])

  const updateNote = useCallback((ticker: string, note: string) => {
    setEntries(prev => {
      const next = prev.map(e => e.ticker === ticker ? { ...e, note } : e)
      saveLocal(next)
      return next
    })
  }, [])

  return { entries, add, remove, toggle, has, updateNote }
}
