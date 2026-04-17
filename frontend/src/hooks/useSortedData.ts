import { useState, useMemo, type ReactElement } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { createElement } from 'react'

type SortDir = 'asc' | 'desc'

interface UseSortedDataResult<T, K extends keyof T> {
  sorted: T[]
  sortKey: K
  sortDir: SortDir
  onSort: (key: K) => void
  SortIcon: (props: { k: K }) => ReactElement | null
}

/**
 * Generic sort hook for table data.
 * Handles string (localeCompare) and numeric sorting with null-safety.
 * SortIcon renders ChevronDown/Up next to the active column header.
 */
export function useSortedData<T, K extends keyof T>(
  data: T[],
  defaultKey: K,
  defaultDir: SortDir = 'desc'
): UseSortedDataResult<T, K> {
  const [sortKey, setSortKey] = useState<K>(defaultKey)
  const [sortDir, setSortDir] = useState<SortDir>(defaultDir)

  const sorted = useMemo(() => [...data].sort((a, b) => {
    const av = a[sortKey] ?? (sortDir === 'asc' ? (Infinity as unknown as T[K]) : (-Infinity as unknown as T[K]))
    const bv = b[sortKey] ?? (sortDir === 'asc' ? (Infinity as unknown as T[K]) : (-Infinity as unknown as T[K]))
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    const an = Number(av)
    const bn = Number(bv)
    return sortDir === 'asc' ? an - bn : bn - an
  }), [data, sortKey, sortDir])

  const onSort = (key: K) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function SortIcon({ k }: { k: K }): ReactElement | null {
    if (sortKey !== k) return null
    return sortDir === 'asc'
      ? createElement(ChevronUp, { size: 12, className: 'inline ml-0.5' })
      : createElement(ChevronDown, { size: 12, className: 'inline ml-0.5' })
  }

  return { sorted, sortKey, sortDir, onSort, SortIcon }
}
