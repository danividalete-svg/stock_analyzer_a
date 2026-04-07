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
    <div className="flex flex-col items-center justify-center py-16 text-center px-6">
      <div
        className="text-4xl mb-4 opacity-45"
        style={{ animation: 'emptyIconIn 0.5s cubic-bezier(0.34,1.56,0.64,1) both' }}
      >
        {icon}
      </div>
      <p
        className="font-medium text-foreground"
        style={{ animation: 'fadeInUp 0.3s ease both 0.1s' }}
      >
        {title}
      </p>
      {subtitle && (
        <p
          className="text-xs text-muted-foreground mt-1.5 max-w-xs"
          style={{ animation: 'fadeInUp 0.3s ease both 0.18s' }}
        >
          {subtitle}
        </p>
      )}
      {action && (
        <div style={{ animation: 'fadeInUp 0.3s ease both 0.26s' }}>
          <Button
            variant="outline"
            size="sm"
            onClick={action.onClick}
            className="mt-4 text-xs px-3 py-1.5"
          >
            {action.label}
          </Button>
        </div>
      )}
    </div>
  )
}
