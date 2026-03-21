import type { HTMLAttributes } from 'react'

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
    readonly className?: string
}

/**
 * Animated skeleton placeholder with shimmer effect.
 */
export function Skeleton({ className = '', ...props }: SkeletonProps) {
    return (
        <div
            className={`animate-pulse rounded-[var(--radius-sm)] bg-[var(--surface-raised)] ${className}`}
            {...props}
        />
    )
}

/**
 * Pre-built skeleton card matching the workspace card layout.
 */
export function SkeletonCard() {
    return (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3">
            <Skeleton className="h-5 w-3/5" />
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-3 w-1/3" />
        </div>
    )
}
