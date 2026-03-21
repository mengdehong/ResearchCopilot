/* eslint-disable react-refresh/only-export-components */
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive cursor-pointer",
    {
        variants: {
            variant: {
                default:
                    "bg-[var(--accent)] text-white shadow-xs hover:bg-[var(--accent-hover)]",
                destructive:
                    "bg-[var(--error)] text-white shadow-xs hover:bg-[var(--error)]/90 focus-visible:ring-[var(--error)]/20",
                outline:
                    "border border-[var(--border)] bg-transparent shadow-xs hover:bg-[var(--surface-raised)] hover:border-[var(--border-hover)]",
                secondary:
                    "bg-[var(--surface-raised)] text-[var(--text-primary)] shadow-xs hover:bg-[var(--surface-raised)]/80",
                ghost:
                    "hover:bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                link: "text-[var(--accent)] underline-offset-4 hover:underline",
            },
            size: {
                default: "h-9 px-4 py-2 has-[>svg]:px-3",
                sm: "h-8 rounded-[var(--radius-sm)] gap-1.5 px-3 has-[>svg]:px-2.5",
                lg: "h-10 rounded-[var(--radius-sm)] px-6 has-[>svg]:px-4",
                icon: "size-9",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
)

function Button({
    className,
    variant,
    size,
    asChild = false,
    ...props
}: React.ComponentProps<"button"> &
    VariantProps<typeof buttonVariants> & {
        asChild?: boolean
    }) {
    const Comp = asChild ? Slot : "button"

    return (
        <Comp
            data-slot="button"
            className={cn(buttonVariants({ variant, size, className }))}
            {...props}
        />
    )
}

export { Button, buttonVariants }
