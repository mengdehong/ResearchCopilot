import { useEffect, useRef, useCallback } from 'react'
import { useAgentStore } from '@/stores/useAgentStore'
import { getToken } from '@/lib/api'
import type { RunEvent } from '@/types'

interface UseSSEOptions {
    threadId: string
    runId: string
    enabled?: boolean
}

const MAX_RETRIES = 5

/**
 * EventSource wrapper with auto-reconnect and Last-Event-ID support.
 * Feeds events into useAgentStore.handleSSEEvent.
 */
export function useSSE({ threadId, runId, enabled = true }: UseSSEOptions) {
    const eventSourceRef = useRef<EventSource | null>(null)
    const lastEventIdRef = useRef('')
    const retryCountRef = useRef(0)
    const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const connectRef = useRef<() => void>(() => { })

    const connect = useCallback(() => {
        if (!threadId || !runId || !enabled) return

        const { setStreaming } = useAgentStore.getState()

        const token = getToken()
        const params = new URLSearchParams()
        if (token) params.set('token', token)
        if (lastEventIdRef.current) params.set('last_event_id', lastEventIdRef.current)

        const url = `/api/agent/threads/${threadId}/runs/${runId}/stream?${params}`
        const es = new EventSource(url)
        eventSourceRef.current = es

        setStreaming(true)

        es.onmessage = (event) => {
            retryCountRef.current = 0

            if (event.lastEventId) {
                lastEventIdRef.current = event.lastEventId
            }

            try {
                const parsed = JSON.parse(event.data) as RunEvent
                useAgentStore.getState().handleSSEEvent(parsed)

                if (parsed.event_type === 'run_end' || parsed.event_type === 'error') {
                    es.close()
                    useAgentStore.getState().setStreaming(false)
                }
            } catch {
                // Ignore unparseable events
            }
        }

        es.onerror = () => {
            es.close()
            useAgentStore.getState().setStreaming(false)

            if (retryCountRef.current < MAX_RETRIES) {
                retryCountRef.current += 1
                const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000)
                retryTimerRef.current = setTimeout(() => connectRef.current(), delay)
            }
        }
    }, [threadId, runId, enabled])

    // Keep ref in sync so retry timer always calls the latest connect
    useEffect(() => {
        connectRef.current = connect
    }, [connect])

    useEffect(() => {
        connect()

        return () => {
            eventSourceRef.current?.close()
            eventSourceRef.current = null
            if (retryTimerRef.current) {
                clearTimeout(retryTimerRef.current)
                retryTimerRef.current = null
            }
            useAgentStore.getState().setStreaming(false)
        }
    }, [connect])

    const disconnect = useCallback(() => {
        eventSourceRef.current?.close()
        eventSourceRef.current = null
        if (retryTimerRef.current) {
            clearTimeout(retryTimerRef.current)
            retryTimerRef.current = null
        }
        useAgentStore.getState().setStreaming(false)
    }, [])

    return { disconnect }
}
