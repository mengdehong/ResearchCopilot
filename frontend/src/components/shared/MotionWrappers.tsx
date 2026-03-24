import type { ReactNode } from "react"
import { motion, AnimatePresence } from "framer-motion"

/* ─── Shared config ─── */
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"
const STAGGER_ITEM_LIMIT = 50

function prefersReducedMotion(): boolean {
    if (typeof window === "undefined") return false
    return window.matchMedia(REDUCED_MOTION_QUERY).matches
}

/* ─── FadeIn ─── */
interface FadeInProps {
    readonly children: ReactNode
    readonly className?: string
    readonly duration?: number
    readonly delay?: number
}

export function FadeIn({ children, className, duration = 0.2, delay = 0 }: FadeInProps) {
    if (prefersReducedMotion()) {
        return <div className={className}>{children}</div>
    }
    return (
        <motion.div
            className={className}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration, delay, ease: "easeOut" }}
        >
            {children}
        </motion.div>
    )
}

/* ─── SlideUp ─── */
interface SlideUpProps {
    readonly children: ReactNode
    readonly className?: string
    readonly duration?: number
    readonly delay?: number
    readonly y?: number
}

export function SlideUp({ children, className, duration = 0.2, delay = 0, y = 8 }: SlideUpProps) {
    if (prefersReducedMotion()) {
        return <div className={className}>{children}</div>
    }
    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, y }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y }}
            transition={{ duration, delay, ease: "easeOut" }}
        >
            {children}
        </motion.div>
    )
}

/* ─── ScaleIn ─── */
interface ScaleInProps {
    readonly children: ReactNode
    readonly className?: string
    readonly duration?: number
}

export function ScaleIn({ children, className, duration = 0.2 }: ScaleInProps) {
    if (prefersReducedMotion()) {
        return <div className={className}>{children}</div>
    }
    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration, ease: "easeOut" }}
        >
            {children}
        </motion.div>
    )
}

/* ─── StaggerContainer + StaggerItem ─── */
interface StaggerContainerProps {
    readonly children: ReactNode
    readonly className?: string
    readonly staggerDelay?: number
    readonly itemCount?: number
}

export function StaggerContainer({
    children,
    className,
    staggerDelay = 0.05,
    itemCount = 0,
}: StaggerContainerProps) {
    const shouldDisableStagger = prefersReducedMotion() || itemCount > STAGGER_ITEM_LIMIT

    return (
        <motion.div
            className={className}
            initial="hidden"
            animate="visible"
            variants={{
                hidden: {},
                visible: {
                    transition: {
                        staggerChildren: shouldDisableStagger ? 0 : staggerDelay,
                    },
                },
            }}
        >
            {children}
        </motion.div>
    )
}

interface StaggerItemProps {
    readonly children: ReactNode
    readonly className?: string
}

export function StaggerItem({ children, className }: StaggerItemProps) {
    if (prefersReducedMotion()) {
        return <div className={className}>{children}</div>
    }
    return (
        <motion.div
            className={className}
            variants={{
                hidden: { opacity: 0, y: 12 },
                visible: { opacity: 1, y: 0 },
            }}
            transition={{ duration: 0.2, ease: "easeOut" }}
        >
            {children}
        </motion.div>
    )
}

/* ─── PresenceWrapper ─── */
interface PresenceWrapperProps {
    readonly children: ReactNode
}

export function PresenceWrapper({ children }: PresenceWrapperProps) {
    return <AnimatePresence mode="wait">{children}</AnimatePresence>
}
