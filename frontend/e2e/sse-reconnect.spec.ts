import { test, expect, type Page } from './fixtures'
import { mockSSEStream } from './helpers/sse-mocks'

/**
 * Advanced SSE mock that simulates error on first connection,
 * then succeeds on reconnection. Used to test useSSE retry logic.
 */
async function mockSSEWithReconnect(
    page: Page,
    eventsOnReconnect: Array<{ event_type: string; data: Record<string, unknown> }>,
): Promise<void> {
    const serialized = JSON.stringify(eventsOnReconnect)

    await page.addInitScript(`
        (() => {
            const _events = ${serialized};
            let connectionCount = 0;
            const MAX_POLLS = 200;

            class MockEventSource {
                constructor(url) {
                    this.url = url;
                    this.readyState = 0;
                    this.onopen = null;
                    this.onmessage = null;
                    this.onerror = null;
                    this._closed = false;
                    this._dispatched = false;

                    connectionCount++;
                    const thisConnection = connectionCount;
                    const self = this;
                    let pollCount = 0;

                    function tryDispatch() {
                        if (self._closed) return;
                        pollCount++;

                        if (!self._dispatched && self.onmessage) {
                            self._dispatched = true;
                            self.readyState = 1;

                            if (thisConnection === 1) {
                                // First connection: trigger error after open
                                if (self.onopen) self.onopen(new Event('open'));
                                setTimeout(() => {
                                    if (!self._closed && self.onerror) {
                                        self.onerror(new Event('error'));
                                    }
                                }, 100);
                            } else {
                                // Subsequent connections: deliver events normally
                                if (self.onopen) self.onopen(new Event('open'));
                                _events.forEach((evt, i) => {
                                    setTimeout(() => {
                                        if (self._closed) return;
                                        const msgEvent = new MessageEvent('message', {
                                            data: JSON.stringify(evt),
                                            lastEventId: String(i + 1),
                                        });
                                        self.onmessage(msgEvent);
                                    }, i * 100);
                                });
                            }
                        } else if (!self._dispatched && pollCount < MAX_POLLS) {
                            setTimeout(tryDispatch, 50);
                        }
                    }

                    setTimeout(tryDispatch, 50);
                }

                close() {
                    this._closed = true;
                    this.readyState = 2;
                }

                addEventListener() {}
                removeEventListener() {}
                dispatchEvent() { return true; }
            }

            MockEventSource.CONNECTING = 0;
            MockEventSource.OPEN = 1;
            MockEventSource.CLOSED = 2;

            window.EventSource = MockEventSource;
        })();
    `)
}

/**
 * SSE mock that always errors — simulates permanent connection failure.
 * Used to test max retry exhaustion and error toast.
 */
async function mockSSEAlwaysError(page: Page): Promise<void> {
    await page.addInitScript(`
        (() => {
            const MAX_POLLS = 200;

            class MockEventSource {
                constructor(url) {
                    this.url = url;
                    this.readyState = 0;
                    this.onopen = null;
                    this.onmessage = null;
                    this.onerror = null;
                    this._closed = false;
                    this._dispatched = false;

                    const self = this;
                    let pollCount = 0;

                    function tryDispatch() {
                        if (self._closed) return;
                        pollCount++;

                        if (!self._dispatched && (self.onmessage || self.onerror)) {
                            self._dispatched = true;
                            self.readyState = 1;
                            if (self.onopen) self.onopen(new Event('open'));
                            // Always error after brief open
                            setTimeout(() => {
                                if (!self._closed && self.onerror) {
                                    self.onerror(new Event('error'));
                                }
                            }, 50);
                        } else if (!self._dispatched && pollCount < MAX_POLLS) {
                            setTimeout(tryDispatch, 50);
                        }
                    }

                    setTimeout(tryDispatch, 50);
                }

                close() {
                    this._closed = true;
                    this.readyState = 2;
                }

                addEventListener() {}
                removeEventListener() {}
                dispatchEvent() { return true; }
            }

            MockEventSource.CONNECTING = 0;
            MockEventSource.OPEN = 1;
            MockEventSource.CLOSED = 2;

            window.EventSource = MockEventSource;
        })();
    `)
}

test.describe('SSE Reconnection', () => {
    test('SSE error triggers reconnect and delivers events', async ({ authedPage: page }) => {
        await mockSSEWithReconnect(page, [
            { event_type: 'assistant_message', data: { content: 'Recovered response' } },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Test')
        await page.getByRole('button', { name: 'Send message' }).click()

        // The first SSE connection errors, useSSE retries,
        // and the second connection delivers the events
        await expect(page.getByText('Recovered response')).toBeVisible({ timeout: 30000 })
    })

    test('run_end event stops streaming state', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            { event_type: 'node_start', data: { node_name: 'search', node_id: 'n1' } },
            { event_type: 'assistant_message', data: { content: 'Done' } },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        // After run_end, the stop button should disappear
        await expect(page.getByText('Done')).toBeVisible({ timeout: 15000 })
        // Stop button should not be visible after run ends
        await expect(page.getByRole('button', { name: 'Stop agent run' })).not.toBeVisible({ timeout: 5000 })
    })

    test('thread switch loads new thread history', async ({ authedPage: page }) => {
        // Mock a second thread with different messages
        await page.route('**/api/v1/agent/threads/th-2/messages', (route) =>
            route.fulfill({
                json: [
                    { id: 'msg-3', role: 'user', content: 'Thread 2 question', timestamp: '2025-01-02T00:00:00Z' },
                    { id: 'msg-4', role: 'assistant', content: 'Thread 2 answer', timestamp: '2025-01-02T00:01:00Z' },
                ],
            }),
        )

        // Start on thread 1
        await page.goto('/workspace/ws-1?thread=th-1')
        await expect(page.getByText('Previous question')).toBeVisible({ timeout: 5000 })

        // Navigate to thread 2 via URL
        await page.goto('/workspace/ws-1?thread=th-2')
        await expect(page.getByText('Thread 2 question')).toBeVisible({ timeout: 5000 })
        await expect(page.getByText('Thread 2 answer')).toBeVisible()

        // Thread 1 messages should no longer be visible
        await expect(page.getByText('Previous question')).not.toBeVisible()
    })

    test('streaming indicator during SSE connection', async ({ authedPage: page }) => {
        // Use events that keep streaming alive (no run_end)
        await mockSSEStream(page, [
            { event_type: 'node_start', data: { node_name: 'analysis', node_id: 'n1' } },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Analyze')
        await page.getByRole('button', { name: 'Send message' }).click()

        // Streaming indicator should be visible
        await expect(page.getByRole('button', { name: 'Stop agent run' })).toBeVisible({ timeout: 15000 })
        // The textarea should be disabled during streaming (or similarly indicate active streaming)
        await expect(page.getByText('analysis')).toBeVisible()
    })
})
