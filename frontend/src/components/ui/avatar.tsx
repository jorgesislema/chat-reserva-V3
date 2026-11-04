'use client'

import * as React from 'react'
import { cn } from '@/utils'

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode
}

function getInitials(name?: string | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

export function Avatar({ className, children, ...props }: AvatarProps) {
  return (
    <div
      className={cn(
        'relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function AvatarImage({ src, alt }: { src?: string; alt?: string }) {
  if (!src) return null
  return <img src={src} alt={alt || ''} className="h-full w-full object-cover" />
}

export function AvatarFallback({
  name,
  className,
  children,
}: {
  name?: string | null
  className?: string
  children?: React.ReactNode
}) {
  return <div className={cn('flex h-full w-full items-center justify-center text-sm font-medium', className)}>{children ?? getInitials(name)}</div>
}
