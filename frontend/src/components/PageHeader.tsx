import React from 'react'

interface PageHeaderProps {
  title: React.ReactNode
  subtitle?: React.ReactNode
  children?: React.ReactNode  // right-side actions (buttons, badges, etc.)
}

export default function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <div className="mb-7 animate-fade-in-up flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <h1 className="text-2xl font-extrabold tracking-tight gradient-title mb-1 leading-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children && (
        <div className="flex items-center gap-2 shrink-0 mt-0.5">{children}</div>
      )}
    </div>
  )
}
