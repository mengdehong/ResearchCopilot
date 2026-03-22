import { describe, it, expect, beforeEach } from 'vitest'
import { useAgentStore } from './useAgentStore'
import type { RunEvent } from '@/types'

function dispatch(event_type: string, data: Record<string, unknown> = {}): void {
    const event: RunEvent = { event_type, data } as RunEvent
    useAgentStore.getState().handleSSEEvent(event)
}

describe('useAgentStore', () => {
    beforeEach(() => {
        useAgentStore.getState().reset()
    })

    // ── token 事件 ──
    describe('token event', () => {
        it('appends content to generatedContent', () => {
            dispatch('token', { content: 'Hello' })
            dispatch('token', { content: ' World' })
            expect(useAgentStore.getState().generatedContent).toBe('Hello World')
        })

        it('handles missing content gracefully', () => {
            dispatch('token', {})
            expect(useAgentStore.getState().generatedContent).toBe('')
        })
    })

    // ── node_start / node_end ──
    describe('node lifecycle', () => {
        it('adds a running node on node_start', () => {
            dispatch('node_start', { node_name: 'discovery', node_id: 'n-1' })
            const state = useAgentStore.getState()
            expect(state.currentNode).toBe('discovery')
            expect(state.isStreaming).toBe(true)
            expect(state.cotTree).toHaveLength(1)
            expect(state.cotTree[0]).toMatchObject({
                id: 'n-1',
                name: 'discovery',
                status: 'running',
                endTime: null,
            })
        })

        it('completes the node on node_end', () => {
            dispatch('node_start', { node_name: 'discovery', node_id: 'n-1' })
            dispatch('node_end', { node_name: 'discovery' })
            const state = useAgentStore.getState()
            expect(state.currentNode).toBeNull()
            expect(state.cotTree[0].status).toBe('completed')
            expect(state.cotTree[0].endTime).toBeTypeOf('number')
        })

        it('only completes the matching running node', () => {
            dispatch('node_start', { node_name: 'discovery', node_id: 'n-1' })
            dispatch('node_start', { node_name: 'extraction', node_id: 'n-2' })
            dispatch('node_end', { node_name: 'discovery' })
            const tree = useAgentStore.getState().cotTree
            expect(tree[0].status).toBe('completed')
            expect(tree[1].status).toBe('running')
        })
    })

    // ── interrupt ──
    describe('interrupt event', () => {
        it('sets interrupt data and stops streaming', () => {
            useAgentStore.getState().setStreaming(true)
            dispatch('interrupt', {
                action: 'select_papers',
                run_id: 'run-1',
                thread_id: 'th-1',
            })
            const state = useAgentStore.getState()
            expect(state.interrupt).toMatchObject({
                action: 'select_papers',
                run_id: 'run-1',
                thread_id: 'th-1',
            })
            expect(state.isStreaming).toBe(false)
        })
    })

    // ── assistant_message ──
    describe('assistant_message event', () => {
        it('creates message from accumulated generatedContent', () => {
            dispatch('token', { content: 'accumulated text' })
            dispatch('assistant_message', { content: 'fallback' })
            const state = useAgentStore.getState()
            expect(state.messages).toHaveLength(1)
            expect(state.messages[0].content).toBe('accumulated text')
            expect(state.messages[0].role).toBe('assistant')
            expect(state.generatedContent).toBe('')
        })

        it('falls back to data.content when generatedContent is empty', () => {
            dispatch('assistant_message', { content: 'direct content' })
            expect(useAgentStore.getState().messages[0].content).toBe('direct content')
        })
    })

    // ── error ──
    describe('error event', () => {
        it('adds a system message', () => {
            dispatch('error', { message: 'Something went wrong' })
            const msg = useAgentStore.getState().messages[0]
            expect(msg.role).toBe('system')
            expect(msg.content).toBe('Something went wrong')
        })

        it('uses fallback message when data.message is missing', () => {
            dispatch('error', {})
            expect(useAgentStore.getState().messages[0].content).toBe('Unknown error')
        })
    })

    // ── content_block ──
    describe('content_block event', () => {
        it('sets contentBlock with content and workflow', () => {
            dispatch('content_block', { content: '# Report', workflow: 'publish' })
            expect(useAgentStore.getState().contentBlock).toEqual({
                content: '# Report',
                workflow: 'publish',
            })
        })

        it('ignores empty content', () => {
            dispatch('content_block', { content: '', workflow: 'publish' })
            expect(useAgentStore.getState().contentBlock).toBeNull()
        })
    })

    // ── run_end ──
    describe('run_end event', () => {
        it('stops streaming and clears currentNode', () => {
            useAgentStore.getState().setStreaming(true)
            dispatch('run_end', {})
            const state = useAgentStore.getState()
            expect(state.isStreaming).toBe(false)
            expect(state.currentNode).toBeNull()
        })
    })

    // ── pdf_highlight ──
    describe('pdf_highlight event', () => {
        it('sets activePdf with correct shape', () => {
            dispatch('pdf_highlight', {
                document_id: 'doc-1',
                page: 3,
                bbox: [10, 20, 100, 200],
                text_snippet: 'important text',
            })
            expect(useAgentStore.getState().activePdf).toEqual({
                document_id: 'doc-1',
                page: 3,
                bbox: [10, 20, 100, 200],
                text_snippet: 'important text',
            })
        })
    })

    // ── sandbox_result ──
    describe('sandbox_result event', () => {
        it('sets sandboxResult with all fields', () => {
            dispatch('sandbox_result', {
                code: 'print("hi")',
                stdout: 'hi\n',
                stderr: '',
                exit_code: 0,
                duration_ms: 123,
                artifacts: ['plot.png'],
            })
            expect(useAgentStore.getState().sandboxResult).toEqual({
                code: 'print("hi")',
                stdout: 'hi\n',
                stderr: '',
                exit_code: 0,
                duration_ms: 123,
                artifacts: ['plot.png'],
            })
        })
    })

    // ── unknown event ──
    describe('unknown event', () => {
        it('does not throw for unknown event types', () => {
            expect(() => dispatch('some_future_event', {})).not.toThrow()
        })
    })

    // ── reset ──
    describe('reset', () => {
        it('restores all state to initial values', () => {
            dispatch('token', { content: 'text' })
            dispatch('node_start', { node_name: 'test', node_id: 'n-1' })
            dispatch('interrupt', { action: 'confirm_execute', run_id: 'r', thread_id: 't' })
            useAgentStore.getState().reset()
            const state = useAgentStore.getState()
            expect(state.messages).toEqual([])
            expect(state.cotTree).toEqual([])
            expect(state.interrupt).toBeNull()
            expect(state.isStreaming).toBe(false)
            expect(state.currentNode).toBeNull()
            expect(state.generatedContent).toBe('')
            expect(state.contentBlock).toBeNull()
            expect(state.activePdf).toBeNull()
            expect(state.sandboxResult).toBeNull()
        })
    })

    // ── addMessage ──
    describe('addMessage', () => {
        it('appends a message to the list', () => {
            useAgentStore.getState().addMessage({
                id: 'm-1',
                role: 'user',
                content: 'Hello',
                timestamp: '2025-01-01T00:00:00Z',
            })
            expect(useAgentStore.getState().messages).toHaveLength(1)
            expect(useAgentStore.getState().messages[0].content).toBe('Hello')
        })
    })

    // ── clearInterrupt ──
    describe('clearInterrupt', () => {
        it('nullifies interrupt', () => {
            dispatch('interrupt', { action: 'select_papers', run_id: 'r', thread_id: 't' })
            useAgentStore.getState().clearInterrupt()
            expect(useAgentStore.getState().interrupt).toBeNull()
        })
    })
})
