import { useState, useMemo, useEffect } from 'react'

interface UsePaginatedDataResult<T> {
  paged: T[]
  page: number
  setPage: (p: number) => void
  totalPages: number
  resetPage: () => void
}

/**
 * Generic pagination hook.
 * Auto-resets to page 1 when the input data reference changes (filter change).
 * Scrolls to top on page navigation.
 */
export function usePaginatedData<T>(
  data: T[],
  pageSize: number
): UsePaginatedDataResult<T> {
  const [page, setPage] = useState(1)

  // Auto-reset to page 1 when data reference changes (e.g. filter changes)
  useEffect(() => {
    setPage(1)
  }, [data])

  const totalPages = Math.max(1, Math.ceil(data.length / pageSize))

  const paged = useMemo(
    () => data.slice((page - 1) * pageSize, page * pageSize),
    [data, page, pageSize]
  )

  const handleSetPage = (p: number) => {
    setPage(p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const resetPage = () => {
    setPage(1)
  }

  return { paged, page, setPage: handleSetPage, totalPages, resetPage }
}
