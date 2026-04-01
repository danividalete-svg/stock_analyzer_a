import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'

interface EmptyStateProps {
  icon: string | ReactNode
  title: string
  subtitle?: string
  action?: { label: string; onClick: () => void }
}

export default function EmptyState({ icon, title, subtitle, action }: EmptyStateProps) {
  return (
    <div className="animate-in fade-in duration-300 flex flex-col items-center justify-center py-16 text-center px-6">
      <div className="text-4xl mb-4 opacity-30">{icon}</div>
      <p className="font-medium text-foreground">{title}</p>
      {subtitle && (
        <p className="text-xs text-muted-foreground mt-1.5 max-w-xs">{subtitle}</p>
      )}
      {action && (
        <Button
          variant="outline"
          size="sm"
          onClick={action.onClick}
          className="mt-4 text-xs px-3 py-1.5"
        >
          {action.label}
        </Button>
      )}
    </div>
  )
}
