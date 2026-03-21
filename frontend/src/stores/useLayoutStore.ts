import { create } from 'zustand'
import type { CanvasTab } from '@/types'

export type SaveStatus = 'idle' | 'saving' | 'saved'

interface LayoutState {
    sidebarCollapsed: boolean
    splitRatio: number
    activeCanvasTab: CanvasTab
    saveStatus: SaveStatus

    toggleSidebar: () => void
    setSplitRatio: (ratio: number) => void
    setActiveCanvasTab: (tab: CanvasTab) => void
    setSaveStatus: (status: SaveStatus) => void
}

export const useLayoutStore = create<LayoutState>((set) => ({
    sidebarCollapsed: false,
    splitRatio: 0.4,
    activeCanvasTab: 'editor',
    saveStatus: 'idle',

    toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

    setSplitRatio: (ratio) => set({ splitRatio: ratio }),

    setActiveCanvasTab: (tab) => set({ activeCanvasTab: tab }),

    setSaveStatus: (status) => set({ saveStatus: status }),
}))
