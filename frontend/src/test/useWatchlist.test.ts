/**
 * Unit tests for useWatchlist hook
 * Mocks supabase + AuthContext to test localStorage logic in isolation
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// Mock supabase before hook import
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: { onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })) },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      upsert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      match: vi.fn().mockReturnThis(),
      order: vi.fn().mockReturnThis(),
      then: vi.fn((cb: (v: unknown) => unknown) => cb({ data: [], error: null })),
    })),
  },
}))

// No logged-in user → pure localStorage path
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: null }),
}))

import { useWatchlist } from '@/hooks/useWatchlist'
import type { WatchlistEntry } from '@/hooks/useWatchlist'

const KEY = 'sa-watchlist-v1'

const makeEntry = (ticker: string): Omit<WatchlistEntry, 'added_at'> => ({ ticker })

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('useWatchlist (no auth — localStorage only)', () => {
  it('initializes with empty list when localStorage is empty', () => {
    const { result } = renderHook(() => useWatchlist())
    expect(result.current.entries).toEqual([])
  })

  it('loads existing watchlist from localStorage', () => {
    const existing: WatchlistEntry[] = [
      { ticker: 'AAPL', added_at: '2026-01-01T00:00:00.000Z' },
      { ticker: 'MSFT', added_at: '2026-01-02T00:00:00.000Z' },
    ]
    localStorage.setItem(KEY, JSON.stringify(existing))
    const { result } = renderHook(() => useWatchlist())
    expect(result.current.entries.map(e => e.ticker)).toEqual(['AAPL', 'MSFT'])
  })

  it('adds a ticker', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('AAPL')) })
    expect(result.current.has('AAPL')).toBe(true)
  })

  it('does not add duplicate tickers', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => {
      result.current.add(makeEntry('AAPL'))
      result.current.add(makeEntry('AAPL'))
    })
    expect(result.current.entries.filter(e => e.ticker === 'AAPL')).toHaveLength(1)
  })

  it('removes a ticker', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('AAPL')) })
    act(() => { result.current.add(makeEntry('MSFT')) })
    act(() => { result.current.remove('AAPL') })
    expect(result.current.has('AAPL')).toBe(false)
    expect(result.current.has('MSFT')).toBe(true)
  })

  it('toggle adds when not present', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.toggle(makeEntry('NVDA')) })
    expect(result.current.has('NVDA')).toBe(true)
  })

  it('toggle removes when already present', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('NVDA')) })
    act(() => { result.current.toggle(makeEntry('NVDA')) })
    expect(result.current.has('NVDA')).toBe(false)
  })

  it('has() returns false for untracked ticker', () => {
    const { result } = renderHook(() => useWatchlist())
    expect(result.current.has('UNKNOWN')).toBe(false)
  })

  it('persists entries to localStorage after add', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('TSLA')) })
    const stored: WatchlistEntry[] = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    expect(stored.some(e => e.ticker === 'TSLA')).toBe(true)
  })

  it('persists removal to localStorage', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('TSLA')) })
    act(() => { result.current.remove('TSLA') })
    const stored: WatchlistEntry[] = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    expect(stored.some(e => e.ticker === 'TSLA')).toBe(false)
  })

  it('updateNote stores note on entry', () => {
    const { result } = renderHook(() => useWatchlist())
    act(() => { result.current.add(makeEntry('AAPL')) })
    act(() => { result.current.updateNote('AAPL', 'Buy on dip') })
    const entry = result.current.entries.find(e => e.ticker === 'AAPL')
    expect(entry?.note).toBe('Buy on dip')
  })

  it('handles corrupted localStorage gracefully', () => {
    localStorage.setItem(KEY, 'not-valid-json{{{')
    expect(() => renderHook(() => useWatchlist())).not.toThrow()
  })
})
