/* eslint-disable react-refresh/only-export-components */
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2",
    {
        variants: {
            variant: {
                default:
                    "border-transparent bg-[var(--accent)] text-white",
                secondary:
                    "border-transparent bg-[var(--surface-raised)] text-[var(--text-primary)]",
                destructive:
                    "border-transparent bg-[var(--error)] text-white",
                outline: "text-[var(--text-primary)] border-[var(--border)]",
                success:
                    "border-transparent bg-[var(--success)]/15 text-[var(--success)]",
                warning:
                    "border-transparent bg-[var(--warning)]/15 text-[var(--warning)]",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
)

function Badge({
    className,
    variant,
    ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
    return (
        <div className={cn(badgeVariants({ variant }), className)} {...props} />
    )
}

export { Badge, badgeVariants }
