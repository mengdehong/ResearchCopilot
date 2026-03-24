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
        it('pushes contentBlock to contentBlocks queue', () => {
            dispatch('content_block', { content: '# Report', workflow: 'publish' })
            expect(useAgentStore.getState().contentBlocks).toEqual([
                { content: '# Report', workflow: 'publish' },
            ])
        })

        it('ignores empty content', () => {
            dispatch('content_block', { content: '', workflow: 'publish' })
            expect(useAgentStore.getState().contentBlocks).toEqual([])
        })

        it('accumulates multiple content blocks', () => {
            dispatch('content_block', { content: '# Part 1', workflow: 'discovery' })
            dispatch('content_block', { content: '# Part 2', workflow: 'extraction' })
            expect(useAgentStore.getState().contentBlocks).toHaveLength(2)
        })
    })

    // ── researchBlocks ──
    describe('researchBlocks', () => {
        it('content_block populates both contentBlocks and researchBlocks', () => {
            dispatch('content_block', { content: '# Report', workflow: 'discovery' })
            const state = useAgentStore.getState()
            expect(state.contentBlocks).toHaveLength(1)
            expect(state.researchBlocks).toHaveLength(1)
            expect(state.researchBlocks[0]).toEqual({ content: '# Report', workflow: 'discovery' })
        })

        it('researchBlocks accumulates across multiple events', () => {
            dispatch('content_block', { content: 'A', workflow: 'discovery' })
            dispatch('content_block', { content: 'B', workflow: 'extraction' })
            expect(useAgentStore.getState().researchBlocks).toHaveLength(2)
        })

        it('consumeContentBlock does not affect researchBlocks', () => {
            dispatch('content_block', { content: 'A', workflow: 'w1' })
            dispatch('content_block', { content: 'B', workflow: 'w2' })
            useAgentStore.getState().consumeContentBlock()
            expect(useAgentStore.getState().contentBlocks).toHaveLength(1)
            expect(useAgentStore.getState().researchBlocks).toHaveLength(2)
        })

        it('loadResearchBlocks replaces existing blocks', () => {
            dispatch('content_block', { content: 'live', workflow: 'w1' })
            useAgentStore.getState().loadResearchBlocks([
                { content: 'historic-1', workflow: 'discovery' },
                { content: 'historic-2', workflow: 'extraction' },
            ])
            const blocks = useAgentStore.getState().researchBlocks
            expect(blocks).toHaveLength(2)
            expect(blocks[0].content).toBe('historic-1')
        })

        it('reset clears researchBlocks', () => {
            dispatch('content_block', { content: 'data', workflow: 'w1' })
            useAgentStore.getState().reset()
            expect(useAgentStore.getState().researchBlocks).toEqual([])
        })
    })

    // ── consumeContentBlock ──
    describe('consumeContentBlock', () => {
        it('returns first block and removes it from queue', () => {
            dispatch('content_block', { content: 'A', workflow: 'w1' })
            dispatch('content_block', { content: 'B', workflow: 'w2' })
            const block = useAgentStore.getState().consumeContentBlock()
            expect(block).toEqual({ content: 'A', workflow: 'w1' })
            expect(useAgentStore.getState().contentBlocks).toHaveLength(1)
        })

        it('returns null when queue is empty', () => {
            expect(useAgentStore.getState().consumeContentBlock()).toBeNull()
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
        it('appends to sandboxHistory with all fields including images', () => {
            dispatch('sandbox_result', {
                code: 'print("hi")',
                stdout: 'hi\n',
                stderr: '',
                exit_code: 0,
                duration_ms: 123,
                artifacts: ['plot.png'],
                images: [{ name: 'plot.png', data: 'abc123' }],
            })
            const history = useAgentStore.getState().sandboxHistory
            expect(history).toHaveLength(1)
            expect(history[0]).toEqual({
                code: 'print("hi")',
                stdout: 'hi\n',
                stderr: '',
                exit_code: 0,
                duration_ms: 123,
                artifacts: ['plot.png'],
                images: [{ name: 'plot.png', data: 'abc123' }],
            })
        })

        it('accumulates multiple executions in order', () => {
            dispatch('sandbox_result', { code: 'run1', stdout: '', stderr: '', exit_code: 0, duration_ms: 1, artifacts: [], images: [] })
            dispatch('sandbox_result', { code: 'run2', stdout: '', stderr: '', exit_code: 0, duration_ms: 2, artifacts: [], images: [] })
            const history = useAgentStore.getState().sandboxHistory
            expect(history).toHaveLength(2)
            expect(history[0].code).toBe('run1')
            expect(history[1].code).toBe('run2')
        })

        it('defaults images to [] when field is missing', () => {
            dispatch('sandbox_result', { code: '', stdout: '', stderr: '', exit_code: 0, duration_ms: 0, artifacts: [] })
            expect(useAgentStore.getState().sandboxHistory[0].images).toEqual([])
        })
    })

    // ── unknown event ──
    describe('unknown event', () => {
        it('does not throw for unknown event types', () => {
            expect(() => dispatch('some_future_event', {})).not.toThrow()
        })
    })

    // ── download_ready ──
    describe('download_ready event', () => {
        it('sets downloadUrl from event data', () => {
            dispatch('download_ready', { download_url: '/api/v1/agent/threads/t/runs/r/download' })
            expect(useAgentStore.getState().downloadUrl).toBe('/api/v1/agent/threads/t/runs/r/download')
        })

        it('ignores empty download_url', () => {
            dispatch('download_ready', { download_url: '' })
            expect(useAgentStore.getState().downloadUrl).toBeNull()
        })

        it('is cleared by reset', () => {
            dispatch('download_ready', { download_url: '/some/url' })
            useAgentStore.getState().reset()
            expect(useAgentStore.getState().downloadUrl).toBeNull()
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
            expect(state.contentBlocks).toEqual([])
            expect(state.activePdf).toBeNull()
            expect(state.researchBlocks).toEqual([])
            expect(state.sandboxHistory).toEqual([])
            expect(state.downloadUrl).toBeNull()
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
