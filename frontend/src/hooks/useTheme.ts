import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react"

type Theme = "light" | "dark" | "system"
type ResolvedTheme = "light" | "dark"

const STORAGE_KEY = "theme"
const DARK_CLASS = "dark"

function getSystemTheme(): ResolvedTheme {
    if (typeof window === "undefined") return "dark"
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function getStoredTheme(): Theme {
    if (typeof window === "undefined") return "system"
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === "light" || stored === "dark" || stored === "system") return stored
    return "system"
}

function resolveTheme(theme: Theme): ResolvedTheme {
    return theme === "system" ? getSystemTheme() : theme
}

function applyTheme(resolved: ResolvedTheme): void {
    const root = document.documentElement
    if (resolved === "dark") {
        root.classList.add(DARK_CLASS)
    } else {
        root.classList.remove(DARK_CLASS)
    }
}

// External store for cross-component sync
let currentTheme: Theme = getStoredTheme()
const listeners = new Set<() => void>()

function subscribe(listener: () => void): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
}

function getSnapshot(): Theme {
    return currentTheme
}

function setThemeInternal(theme: Theme): void {
    currentTheme = theme
    localStorage.setItem(STORAGE_KEY, theme)
    applyTheme(resolveTheme(theme))
    listeners.forEach((listener) => listener())
}

interface UseThemeReturn {
    readonly theme: Theme
    readonly resolvedTheme: ResolvedTheme
    readonly setTheme: (theme: Theme) => void
}

export function useTheme(): UseThemeReturn {
    const theme = useSyncExternalStore(subscribe, getSnapshot)
    const resolvedTheme = useMemo(() => resolveTheme(theme), [theme])

    const setTheme = useCallback((newTheme: Theme) => {
        setThemeInternal(newTheme)
    }, [])

    // Apply on mount and listen for system theme changes
    useEffect(() => {
        applyTheme(resolveTheme(currentTheme))

        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
        const handleChange = () => {
            if (currentTheme === "system") {
                applyTheme(getSystemTheme())
                listeners.forEach((listener) => listener())
            }
        }

        mediaQuery.addEventListener("change", handleChange)
        return () => mediaQuery.removeEventListener("change", handleChange)
    }, [])

    return { theme, resolvedTheme, setTheme }
}

export type { Theme, ResolvedTheme }
