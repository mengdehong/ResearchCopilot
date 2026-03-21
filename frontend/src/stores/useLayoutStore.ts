import { create } from 'zustand'
import type { CanvasTab } from '@/types'

export type SaveStatus = 'idle' | 'saving' | 'saved'

interface LayoutState {
    sidebarCollapsed: boolean
    navExpanded: boolean
    sidebarWidth: number
    splitRatio: number
    activeCanvasTab: CanvasTab
    saveStatus: SaveStatus

    toggleSidebar: () => void
    toggleNav: () => void
    setNavExpanded: (expanded: boolean) => void
    setSidebarWidth: (width: number) => void
    setSplitRatio: (ratio: number) => void
    setActiveCanvasTab: (tab: CanvasTab) => void
    setSaveStatus: (status: SaveStatus) => void
}

export const useLayoutStore = create<LayoutState>((set) => ({
    sidebarCollapsed: false,
    navExpanded: false,
    sidebarWidth: 240,
    splitRatio: 0.4,
    activeCanvasTab: 'editor',
    saveStatus: 'idle',

    toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

    toggleNav: () =>
        set((state) => ({ navExpanded: !state.navExpanded })),

    setNavExpanded: (expanded) => set({ navExpanded: expanded }),

    setSidebarWidth: (width) => set({ sidebarWidth: width }),

    setSplitRatio: (ratio) => set({ splitRatio: ratio }),

    setActiveCanvasTab: (tab) => set({ activeCanvasTab: tab }),

    setSaveStatus: (status) => set({ saveStatus: status }),
}))
