import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAgentStore } from '@/stores/useAgentStore'

// ── Mock EventSource ──
type EventSourceListener = ((event: MessageEvent) => void) | null
type ErrorListener = (() => void) | null

class MockEventSource {
    static instances: MockEventSource[] = []
    url: string
    onmessage: EventSourceListener = null
    onerror: ErrorListener = null
    readyState = 0
    closed = false

    constructor(url: string) {
        this.url = url
        MockEventSource.instances.push(this)
    }

    close() {
        this.closed = true
        this.readyState = 2
    }

    /** 模拟服务端推送一条消息 */
    simulateMessage(data: string, lastEventId?: string) {
        const event = new MessageEvent('message', {
            data,
            lastEventId: lastEventId ?? '',
        })
        this.onmessage?.(event)
    }

    /** 模拟连接失败 */
    simulateError() {
        this.onerror?.()
    }

    static reset() {
        MockEventSource.instances = []
    }
}

// 替换全局 EventSource
const OriginalEventSource = globalThis.EventSource
beforeEach(() => {
    MockEventSource.reset()
        ; (globalThis as Record<string, unknown>).EventSource = MockEventSource as unknown as typeof EventSource
    useAgentStore.getState().reset()
})
afterEach(() => {
    ; (globalThis as Record<string, unknown>).EventSource = OriginalEventSource
})

// 动态导入以获取 mock 后的模块
async function importUseSSE() {
    // 清除模块缓存确保重新加载
    return await import('@/hooks/useSSE')
}

describe('useSSE - EventSource behavior', () => {
    it('constructs EventSource with correct URL including token', async () => {
        const { setToken } = await import('@/lib/api')
        setToken('test-sse-token')

        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        expect(MockEventSource.instances).toHaveLength(1)
        const es = MockEventSource.instances[0]
        expect(es.url).toContain('/api/agent/threads/th-1/runs/run-1/stream')
        expect(es.url).toContain('token=test-sse-token')

        setToken(null)
    })

    it('does not connect when enabled is false', async () => {
        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1', enabled: false }))

        expect(MockEventSource.instances).toHaveLength(0)
    })

    it('does not connect when threadId is empty', async () => {
        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: '', runId: 'run-1' }))

        expect(MockEventSource.instances).toHaveLength(0)
    })

    it('dispatches parsed events to agent store', async () => {
        const handleSpy = vi.spyOn(useAgentStore.getState(), 'handleSSEEvent')

        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        const es = MockEventSource.instances[0]
        es.simulateMessage(JSON.stringify({ event_type: 'token', data: { content: 'hello' } }))

        // handleSSEEvent 被调用（spy 可能在旧引用上，直接检查 store 状态）
        expect(useAgentStore.getState().generatedContent).toBe('hello')
        handleSpy.mockRestore()
    })

    it('closes EventSource on run_end event', async () => {
        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        const es = MockEventSource.instances[0]
        es.simulateMessage(JSON.stringify({ event_type: 'run_end', data: {} }))

        expect(es.closed).toBe(true)
        expect(useAgentStore.getState().isStreaming).toBe(false)
    })

    it('retries on error with exponential backoff (multi-level)', async () => {
        vi.useFakeTimers()

        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        // Retry 1: delay = min(1000 * 2^1, 30000) = 2000ms
        const es1 = MockEventSource.instances[0]
        es1.simulateError()
        expect(MockEventSource.instances).toHaveLength(1)
        vi.advanceTimersByTime(1999)
        expect(MockEventSource.instances).toHaveLength(1) // Not yet
        vi.advanceTimersByTime(1)
        expect(MockEventSource.instances).toHaveLength(2) // Reconnected

        // Retry 2: delay = min(1000 * 2^2, 30000) = 4000ms
        const es2 = MockEventSource.instances[1]
        es2.simulateError()
        vi.advanceTimersByTime(3999)
        expect(MockEventSource.instances).toHaveLength(2) // Not yet at 4000ms
        vi.advanceTimersByTime(1)
        expect(MockEventSource.instances).toHaveLength(3) // Reconnected

        // Retry 3: delay = min(1000 * 2^3, 30000) = 8000ms
        const es3 = MockEventSource.instances[2]
        es3.simulateError()
        vi.advanceTimersByTime(7999)
        expect(MockEventSource.instances).toHaveLength(3) // Not yet at 8000ms
        vi.advanceTimersByTime(1)
        expect(MockEventSource.instances).toHaveLength(4) // Reconnected

        vi.useRealTimers()
    })

    it('cleans up EventSource on unmount', async () => {
        const { renderHook } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        const { unmount } = renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        const es = MockEventSource.instances[0]
        expect(es.closed).toBe(false)

        unmount()
        expect(es.closed).toBe(true)
    })

    it('disconnect function closes EventSource', async () => {
        const { renderHook, act } = await import('@testing-library/react')
        const { useSSE } = await importUseSSE()

        const { result } = renderHook(() => useSSE({ threadId: 'th-1', runId: 'run-1' }))

        const es = MockEventSource.instances[0]
        act(() => {
            result.current.disconnect()
        })

        expect(es.closed).toBe(true)
        expect(useAgentStore.getState().isStreaming).toBe(false)
    })
})
