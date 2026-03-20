import { create } from 'zustand'
import type { CanvasTab } from '@/types'

interface LayoutState {
    sidebarCollapsed: boolean
    splitRatio: number
    activeCanvasTab: CanvasTab

    toggleSidebar: () => void
    setSplitRatio: (ratio: number) => void
    setActiveCanvasTab: (tab: CanvasTab) => void
}

export const useLayoutStore = create<LayoutState>((set) => ({
    sidebarCollapsed: false,
    splitRatio: 0.4,
    activeCanvasTab: 'editor',

    toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

    setSplitRatio: (ratio) => set({ splitRatio: ratio }),

    setActiveCanvasTab: (tab) => set({ activeCanvasTab: tab }),
}))
