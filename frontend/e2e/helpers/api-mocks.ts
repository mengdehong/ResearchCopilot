import type { Page } from '@playwright/test'

export const MOCK_USER = {
    id: 'user-1',
    email: 'test@example.com',
    display_name: 'Test User',
} as const

/**
 * Mock all default API routes used by AuthGuard-protected pages.
 * Mirrors the data shapes from `src/test/handlers.ts` (MSW).
 */
export async function setupDefaultMocks(page: Page): Promise<void> {
    // Auth
    await page.route('**/api/v1/auth/refresh', (route) =>
        route.fulfill({ json: { access_token: 'test-access-token' } }),
    )
    await page.route('**/api/v1/auth/me', (route) =>
        route.fulfill({ json: MOCK_USER }),
    )
    await page.route('**/api/v1/auth/logout', (route) =>
        route.fulfill({ json: { ok: true } }),
    )

    // Workspaces
    await page.route('**/api/v1/workspaces', (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({
                json: {
                    id: 'ws-new',
                    name: 'New Workspace',
                    discipline: 'computer_science',
                    owner_id: 'user-1',
                    is_deleted: false,
                    created_at: '2025-01-01',
                    updated_at: '2025-01-01',
                },
            })
        }
        return route.fulfill({
            json: [
                {
                    id: 'ws-1',
                    name: 'Workspace 1',
                    discipline: 'computer_science',
                    owner_id: 'user-1',
                    is_deleted: false,
                    created_at: '2025-01-01',
                    updated_at: '2025-01-01',
                },
            ],
        })
    })
    await page.route('**/api/v1/workspaces/ws-1', (route) => {
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.fulfill({
            json: {
                id: 'ws-1',
                name: 'Workspace 1',
                discipline: 'computer_science',
                owner_id: 'user-1',
                is_deleted: false,
                created_at: '2025-01-01',
                updated_at: '2025-01-01',
            },
        })
    })
    await page.route('**/api/v1/workspaces/*/summary', (route) =>
        route.fulfill({
            json: {
                workspace_id: 'ws-1',
                name: 'Workspace 1',
                document_count: 3,
                doc_status_counts: { uploading: 0, pending: 0, parsing: 0, completed: 3, failed: 0 },
            },
        }),
    )

    // Threads (GET /agent/threads?workspace_id=... and POST /agent/threads?workspace_id=&title=)
    await page.route(/\/api\/v1\/agent\/threads(\?|$)/, (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({
                json: { thread_id: 'th-new', title: 'New Thread', status: 'active', workspace_id: 'ws-1' },
            })
        }
        return route.fulfill({
            json: [{ thread_id: 'th-1', title: 'Thread 1', status: 'active', updated_at: '2025-01-01', workspace_id: 'ws-1' }],
        })
    })

    // Documents (GET /documents?workspace_id=...)
    await page.route('**/api/v1/documents?*', (route) =>
        route.fulfill({
            json: [
                {
                    id: 'doc-1',
                    workspace_id: 'ws-1',
                    title: 'Paper A',
                    file_path: '/a.pdf',
                    parse_status: 'completed',
                    source: 'upload',
                    doi: null,
                    abstract_text: null,
                    year: null,
                    include_appendix: false,
                    created_at: '2025-01-01',
                    updated_at: '2025-01-01',
                },
            ],
        }),
    )

    // Quota
    await page.route('**/api/v1/quota/status', (route) =>
        route.fulfill({
            json: { total_used: 1000, total_limit: 10000, remaining: 9000, usage_percent: 10, workspaces: [] },
        }),
    )

    // Editor / Draft - GET uses path param: /editor/draft/th-1
    await page.route('**/api/v1/editor/draft/*', (route) =>
        route.fulfill({
            json: { thread_id: 'th-1', content: '# Draft', updated_at: '2025-01-01' },
        }),
    )
    // Editor / Draft - PUT uses query param: /editor/draft?thread_id=th-1
    await page.route(/\/api\/v1\/editor\/draft(\?|$)/, (route) => {
        if (route.request().method() === 'PUT') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.continue()
    })

    // Messages (thread history)
    await page.route('**/api/v1/agent/threads/*/messages', (route) =>
        route.fulfill({
            json: [
                { id: 'msg-1', role: 'user', content: 'Previous question', timestamp: '2025-01-01T00:00:00Z' },
                { id: 'msg-2', role: 'assistant', content: 'Previous answer', timestamp: '2025-01-01T00:01:00Z' },
            ],
        }),
    )

    // Runs
    await page.route('**/api/v1/agent/threads/*/runs', (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({
                json: { run_id: 'run-1', status: 'running' },
            })
        }
        return route.continue()
    })

    // Resume run
    await page.route('**/api/v1/agent/threads/*/runs/*/resume', (route) =>
        route.fulfill({
            json: { run_id: 'run-2', status: 'running' },
        }),
    )

    // Cancel run (POST /agent/threads/:id/runs/:id/cancel)
    await page.route('**/api/v1/agent/threads/*/runs/*/cancel', (route) =>
        route.fulfill({ json: { ok: true } }),
    )

    // Document upload flow
    await page.route('**/api/v1/documents/upload-url', (route) =>
        route.fulfill({
            json: { document_id: 'doc-new', upload_url: 'http://localhost:3000/mock-s3-upload', storage_key: 'key' },
        }),
    )
    await page.route('**/mock-s3-upload', (route) =>
        route.fulfill({ status: 200, body: '' }),
    )
    await page.route(/\/api\/v1\/documents\/confirm/, (route) =>
        route.fulfill({ json: { id: 'doc-new', title: 'Uploaded', parse_status: 'pending' } }),
    )
    await page.route('**/api/v1/documents/*/retry', (route) =>
        route.fulfill({ json: { id: 'doc-fail', title: 'Failed Paper', parse_status: 'pending' } }),
    )
    await page.route('**/api/v1/documents/*', (route) => {
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.continue()
    })

    // Delete thread
    await page.route('**/api/v1/agent/threads/*', (route) => {
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.continue()
    })
}

/**
 * Mock auth-specific API routes for guest (GuestGuard) pages.
 * Each test can override individual routes via page.route() before navigating.
 */
export async function setupAuthMocks(page: Page): Promise<void> {
    await page.route('**/api/v1/auth/login', (route) =>
        route.fulfill({
            json: { access_token: 'new-token', user: MOCK_USER },
        }),
    )
    await page.route('**/api/v1/auth/register', (route) =>
        route.fulfill({ status: 200, json: { message: 'ok' } }),
    )
    await page.route('**/api/v1/auth/forgot-password', (route) =>
        route.fulfill({ status: 200, json: { message: 'ok' } }),
    )
    await page.route('**/api/v1/auth/reset-password', (route) =>
        route.fulfill({ status: 200, json: { message: 'ok' } }),
    )
    await page.route('**/api/v1/auth/verify-email', (route) =>
        route.fulfill({ status: 200, json: { message: 'ok' } }),
    )
}
