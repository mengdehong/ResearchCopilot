import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
                "flex h-9 w-full min-w-0 rounded-[var(--radius-sm)] border border-[var(--border)] bg-transparent px-3 py-1 text-sm shadow-xs transition-colors",
                "file:border-0 file:bg-transparent file:text-sm file:font-medium",
                "placeholder:text-[var(--text-muted)]",
                "focus-visible:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--accent-subtle)]",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "aria-invalid:border-[var(--error)] aria-invalid:ring-[var(--error)]/20",
                className
            )}
            {...props}
        />
    )
}

export { Input }
