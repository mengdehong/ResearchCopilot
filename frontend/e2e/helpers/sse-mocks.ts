import type { Page } from '@playwright/test'

interface SSEEvent {
    event_type: string
    data: Record<string, unknown>
}

/**
 * Mock EventSource in the browser context to simulate SSE streams.
 * Playwright's page.route() cannot intercept EventSource connections,
 * so we override the global EventSource constructor via addInitScript.
 *
 * Call this BEFORE navigating to the page that uses SSE.
 * Events are dispatched after onmessage is assigned, using polling.
 * Polling has a hard limit (MAX_POLLS ≈ 10s) to prevent infinite loops.
 */
export async function mockSSEStream(page: Page, events: SSEEvent[]): Promise<void> {
    const serialized = JSON.stringify(events)

    await page.addInitScript(`
        (() => {
            const _events = ${serialized};
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

                        if (!self._dispatched && self.onmessage) {
                            self._dispatched = true;
                            self.readyState = 1;
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
                        } else if (!self._dispatched && pollCount < MAX_POLLS) {
                            setTimeout(tryDispatch, 50);
                        } else if (!self._dispatched) {
                            // Polling exhausted — signal error
                            self.readyState = 2;
                            if (self.onerror) self.onerror(new Event('error'));
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
