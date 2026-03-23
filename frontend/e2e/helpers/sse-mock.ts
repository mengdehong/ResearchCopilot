import type { Page } from '@playwright/test'

/**
 * 一个 SSE 事件，对应 RunEvent 结构。
 */
export interface SSEEvent {
    event_type: string
    data: Record<string, unknown>
}

/**
 * 通过在浏览器上下文注入 EventSource mock 来模拟 SSE 流。
 *
 * 原理：通过 page.addInitScript 替换浏览器的 EventSource 构造函数，
 * 使其从 window.__SSE_EVENTS__ 数组读取事件并按序触发 onmessage。
 *
 * 必须在 page.goto() 之前调用。
 */
export async function mockSSEStream(
    page: Page,
    events: SSEEvent[],
): Promise<void> {
    const serializedEvents = JSON.stringify(events)

    await page.addInitScript((eventsStr: string) => {
        const events = JSON.parse(eventsStr) as Array<{ event_type: string; data: Record<string, unknown> }>

        // 只在第一次连接时发送完整事件，后续连接只发 run_end
        let hasFired = false

        // @ts-expect-error — 覆盖全局 EventSource
        window.EventSource = class MockEventSource {
            readonly url: string
            readonly readyState: number
            onmessage: ((event: MessageEvent) => void) | null = null
            onerror: ((event: Event) => void) | null = null
            onopen: ((event: Event) => void) | null = null

            static readonly CONNECTING = 0
            static readonly OPEN = 1
            static readonly CLOSED = 2

            constructor(url: string) {
                this.url = url
                this.readyState = 1 // OPEN

                const eventsToFire = hasFired
                    ? [{ event_type: 'run_end', data: {} }]
                    : events
                hasFired = true

                // 使用 microtask 延迟以确保 onmessage handler 已绑定
                queueMicrotask(() => {
                    if (this.onopen) {
                        this.onopen(new Event('open'))
                    }

                    // 逐个发送事件，每个之间 10ms 间隔
                    eventsToFire.forEach((evt, i) => {
                        setTimeout(() => {
                            if (this.onmessage) {
                                const messageEvent = new MessageEvent('message', {
                                    data: JSON.stringify(evt),
                                    lastEventId: String(i),
                                })
                                this.onmessage(messageEvent)
                            }
                        }, i * 10)
                    })
                })
            }

            close() {
                // @ts-expect-error — readyState is readonly
                this.readyState = 2
            }

            addEventListener() { /* noop */ }
            removeEventListener() { /* noop */ }
            dispatchEvent() { return true }
        }
    }, serializedEvents)
}

/* ─── 常用事件工厂 ─── */

export function nodeStart(name: string, id?: string): SSEEvent {
    return { event_type: 'node_start', data: { node_name: name, node_id: id ?? name } }
}

export function nodeEnd(name: string, id?: string): SSEEvent {
    return { event_type: 'node_end', data: { node_name: name, node_id: id ?? name } }
}

export function assistantMessage(content: string): SSEEvent {
    return { event_type: 'assistant_message', data: { content } }
}

export function contentBlock(content: string, workflow: string): SSEEvent {
    return { event_type: 'content_block', data: { content, workflow } }
}

export function interruptEvent(
    action: string,
    threadId: string,
    runId: string,
    extra?: Record<string, unknown>,
): SSEEvent {
    return {
        event_type: 'interrupt',
        data: { action, thread_id: threadId, run_id: runId, ...extra },
    }
}

export function errorEvent(message: string): SSEEvent {
    return { event_type: 'error', data: { message } }
}

export function runEnd(): SSEEvent {
    return { event_type: 'run_end', data: {} }
}

export function pdfHighlight(
    documentId: string,
    pageno: number,
    bbox: number[],
    snippet: string,
): SSEEvent {
    return {
        event_type: 'pdf_highlight',
        data: { document_id: documentId, page: pageno, bbox, text_snippet: snippet },
    }
}

export function sandboxResult(
    code: string,
    stdout: string,
    stderr: string,
    exitCode: number,
): SSEEvent {
    return {
        event_type: 'sandbox_result',
        data: { code, stdout, stderr, exit_code: exitCode, duration_ms: 100, artifacts: [] },
    }
}

export function tokenEvent(content: string): SSEEvent {
    return { event_type: 'token', data: { content } }
}
