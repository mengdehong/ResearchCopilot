import { describe, it, expect, beforeEach } from 'vitest'
import { useLayoutStore } from './useLayoutStore'

describe('useLayoutStore', () => {
    beforeEach(() => {
        // Reset to defaults
        useLayoutStore.setState({
            sidebarCollapsed: false,
            navExpanded: false,
            sidebarWidth: 240,
            splitRatio: 0.4,
            activeCanvasTab: 'editor',
            saveStatus: 'idle',
        })
    })

    describe('toggleSidebar', () => {
        it('toggles sidebarCollapsed', () => {
            expect(useLayoutStore.getState().sidebarCollapsed).toBe(false)
            useLayoutStore.getState().toggleSidebar()
            expect(useLayoutStore.getState().sidebarCollapsed).toBe(true)
            useLayoutStore.getState().toggleSidebar()
            expect(useLayoutStore.getState().sidebarCollapsed).toBe(false)
        })
    })

    describe('toggleNav', () => {
        it('toggles navExpanded', () => {
            expect(useLayoutStore.getState().navExpanded).toBe(false)
            useLayoutStore.getState().toggleNav()
            expect(useLayoutStore.getState().navExpanded).toBe(true)
        })
    })

    describe('setNavExpanded', () => {
        it('sets navExpanded directly', () => {
            useLayoutStore.getState().setNavExpanded(true)
            expect(useLayoutStore.getState().navExpanded).toBe(true)
            useLayoutStore.getState().setNavExpanded(false)
            expect(useLayoutStore.getState().navExpanded).toBe(false)
        })
    })

    describe('setSidebarWidth', () => {
        it('updates sidebarWidth', () => {
            useLayoutStore.getState().setSidebarWidth(300)
            expect(useLayoutStore.getState().sidebarWidth).toBe(300)
        })
    })

    describe('setSplitRatio', () => {
        it('updates splitRatio', () => {
            useLayoutStore.getState().setSplitRatio(0.6)
            expect(useLayoutStore.getState().splitRatio).toBe(0.6)
        })
    })

    describe('setActiveCanvasTab', () => {
        it('changes active tab', () => {
            useLayoutStore.getState().setActiveCanvasTab('pdf')
            expect(useLayoutStore.getState().activeCanvasTab).toBe('pdf')
            useLayoutStore.getState().setActiveCanvasTab('sandbox')
            expect(useLayoutStore.getState().activeCanvasTab).toBe('sandbox')
        })
    })

    describe('setSaveStatus', () => {
        it('cycles through save statuses', () => {
            useLayoutStore.getState().setSaveStatus('saving')
            expect(useLayoutStore.getState().saveStatus).toBe('saving')
            useLayoutStore.getState().setSaveStatus('saved')
            expect(useLayoutStore.getState().saveStatus).toBe('saved')
            useLayoutStore.getState().setSaveStatus('idle')
            expect(useLayoutStore.getState().saveStatus).toBe('idle')
        })
    })
})
