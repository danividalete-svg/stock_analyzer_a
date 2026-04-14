import { Skeleton } from '@/components/ui/skeleton'
import { Card } from '@/components/ui/card'

function SkeletonStatCard({ delay = 0 }: { delay?: number }) {
  return (
    <Card className="glass p-5" style={{ animationDelay: `${delay}ms` }}>
      {/* label */}
      <Skeleton className="h-2 w-1/3 mb-4 rounded-sm" />
      {/* big number */}
      <Skeleton className="h-9 w-2/5 mb-2 rounded" />
      {/* sub-label */}
      <Skeleton className="h-2 w-3/5 mb-1 rounded-sm" />
      <Skeleton className="h-2 w-1/2 rounded-sm" />
    </Card>
  )
}

// Randomised-looking row widths — avoids uniform appearance
const ROW_WIDTHS = [
  [52, 128, 52, 44, 36, 56, 60, 44, 38, 52, 36],
  [44, 112, 48, 52, 36, 72, 56, 36, 44, 60, 42],
  [56, 136, 56, 36, 36, 64, 68, 48, 32, 48, 38],
  [48, 120, 52, 48, 36, 80, 60, 40, 40, 56, 44],
  [52, 108, 44, 56, 36, 68, 52, 52, 36, 44, 36],
  [44, 124, 50, 40, 36, 76, 64, 44, 42, 52, 40],
]

const COL_HEADERS = [56, 80, 54, 54, 44, 70, 64, 44, 36, 54, 40]

function SkeletonTableRow({ cols, delay }: { cols: number[]; delay: number }) {
  return (
    <tr
      className="border-b border-border/20"
      style={{ animation: `rowEnter 0.25s cubic-bezier(0.22,1,0.36,1) ${delay}ms both` }}
    >
      {cols.map((w, i) => (
        <td key={i} className="px-3 py-3">
          {i === 0 ? (
            /* Ticker cell — logo + text */
            <div className="flex items-center gap-2">
              <Skeleton className="h-6 w-6 rounded-full flex-shrink-0" />
              <div className="space-y-1">
                <Skeleton style={{ width: 36, height: 11 }} className="rounded-sm" />
                <Skeleton style={{ width: 56, height: 8 }} className="rounded-sm" />
              </div>
            </div>
          ) : i === 2 ? (
            /* Score cell — bar + number */
            <div className="flex items-center gap-2">
              <Skeleton style={{ width: 52, height: 5 }} className="rounded-full" />
              <Skeleton style={{ width: 24, height: 11 }} className="rounded-sm" />
            </div>
          ) : (
            <Skeleton style={{ width: w, height: 12 }} className="rounded-sm" />
          )}
        </td>
      ))}
    </tr>
  )
}

function SkeletonTable() {
  return (
    <Card className="glass overflow-clip animate-fade-in-up" style={{ animationDelay: '80ms' }}>
      {/* Filter bar skeleton */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/20">
        <Skeleton className="h-6 w-16 rounded" />
        <Skeleton className="h-6 w-20 rounded" />
        <Skeleton className="h-6 w-14 rounded" />
        <Skeleton className="h-6 w-18 rounded" />
        <div className="ml-auto">
          <Skeleton className="h-6 w-24 rounded" />
        </div>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/40">
            {COL_HEADERS.map((w, i) => (
              <th key={i} className="px-3 py-3">
                <Skeleton style={{ width: w, height: 9 }} className="rounded-sm" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROW_WIDTHS.map((cols, r) => (
            <SkeletonTableRow key={r} cols={cols} delay={r * 40} />
          ))}
        </tbody>
      </table>
    </Card>
  )
}

export default function Loading() {
  return (
    <div>
      {/* Page header */}
      <div className="mb-7 animate-fade-in-up">
        <Skeleton className="h-8 w-52 mb-2.5 rounded" />
        <Skeleton className="h-3.5 w-72 rounded-sm" />
      </div>
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <SkeletonStatCard delay={0} />
        <SkeletonStatCard delay={40} />
        <SkeletonStatCard delay={80} />
        <SkeletonStatCard delay={120} />
      </div>
      <SkeletonTable />
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  const isConnection =
    message.includes('Network') ||
    message.includes('ECONNREFUSED') ||
    message.includes('ERR_CONNECTION')

  return (
    <div className="animate-fade-in-up rounded-xl border border-destructive/30 bg-destructive/5 px-8 py-8 text-center">
      <div className="text-2xl mb-3 opacity-50">⚠️</div>
      <p className="text-sm font-semibold text-destructive mb-1">
        {isConnection ? 'No se puede conectar con la API' : 'Error al cargar datos'}
      </p>
      <p className="text-xs text-muted-foreground">
        {isConnection
          ? 'Ejecuta python3 ticker_api.py en otra terminal'
          : message}
      </p>
    </div>
  )
}
