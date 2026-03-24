import type { Page } from '@playwright/test'

/**
 * 创建一个 URL 谓词函数，匹配 API pathname 以指定后缀结尾的请求。
 * 解决 page.route() glob 不匹配带查询参数 URL 的问题。
 *
 * 额外约束：pathname 必须包含 '/api/v1/' 前缀，避免拦截前端路由
 * （如 /workspace/ws-1/documents 也以 /documents 结尾）。
 *
 * 例: pathEndsWith('/documents') 匹配:
 *   ✅ http://localhost:5173/api/v1/documents?workspace_id=ws-1
 *   ❌ http://localhost:5173/workspace/ws-1/documents
 */
export function pathEndsWith(suffix: string): (url: URL) => boolean {
    return (url: URL) => url.pathname.includes('/api/v1/') && url.pathname.endsWith(suffix)
}

/* ─── Mock 数据（与 src/test/handlers.ts 对齐）─── */

export const MOCK_USER = {
    id: 'user-1',
    email: 'test@example.com',
    display_name: 'Test User',
}

export const MOCK_WORKSPACE = {
    id: 'ws-1',
    name: 'Workspace 1',
    discipline: 'computer_science',
    owner_id: 'user-1',
    is_deleted: false,
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
}

export const MOCK_THREAD = {
    thread_id: 'th-1',
    title: 'Thread 1',
    status: 'active',
    updated_at: '2025-01-01',
    workspace_id: 'ws-1',
}

export const MOCK_THREAD_2 = {
    thread_id: 'th-2',
    title: 'Thread 2',
    status: 'active',
    updated_at: '2025-01-02',
    workspace_id: 'ws-1',
}

export const MOCK_RUN_RESULT = {
    run_id: 'run-1',
    thread_id: 'th-1',
    status: 'running',
    stream_url: '/api/v1/agent/threads/th-1/runs/run-1/stream',
}

export const MOCK_DOCUMENT = {
    id: 'doc-1',
    workspace_id: 'ws-1',
    title: 'Paper A',
    file_path: '/a.pdf',
    parse_status: 'completed',
    source: 'upload',
    doi: null,
    abstract_text: null,
    year: 2024,
    include_appendix: false,
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
}

export const MOCK_DOCUMENT_FAILED = {
    ...MOCK_DOCUMENT,
    id: 'doc-2',
    title: 'Failed Paper',
    parse_status: 'failed',
}

export const MOCK_DRAFT = {
    thread_id: 'th-1',
    content: '<h1>Draft Content</h1><p>Some research notes.</p>',
    updated_at: '2025-01-01',
}

export const MOCK_MESSAGES = {
    messages: [
        { id: 'msg-1', role: 'user', content: 'Previous question', timestamp: '2025-01-01T00:00:00Z' },
        { id: 'msg-2', role: 'assistant', content: 'Previous answer', timestamp: '2025-01-01T00:00:01Z' },
    ],
    pending_interrupt: null,
    cot_nodes: null,
}

/**
 * 注册所有默认 API mock。每个测试的 beforeEach 应调用此函数。
 * 返回后可通过 page.route() 覆盖个别路由。
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

    // Workspaces — 可能带 query params
    await page.route(pathEndsWith('/workspaces'), (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({ json: { ...MOCK_WORKSPACE, id: 'ws-new' } })
        }
        return route.fulfill({ json: [MOCK_WORKSPACE] })
    })
    await page.route((url) => /^\/api\/v1\/workspaces\/[^/]+$/.test(url.pathname), (route) => {
        const pathParts = new URL(route.request().url()).pathname.split('/')
        const workspaceId = pathParts[pathParts.length - 1]
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.fulfill({ json: { ...MOCK_WORKSPACE, id: workspaceId } })
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

    // Threads — GET 带 ?workspace_id=...&limit=... 查询参数
    await page.route(pathEndsWith('/agent/threads'), (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({ json: { thread_id: 'th-new', title: 'New Thread', status: 'active', workspace_id: 'ws-1' } })
        }
        return route.fulfill({ json: [MOCK_THREAD, MOCK_THREAD_2] })
    })

    // Messages
    await page.route((url) => {
        const pathname = url.pathname
        return pathname.includes('/api/v1/agent/threads/') && pathname.endsWith('/messages')
    }, (route) =>
        route.fulfill({ json: MOCK_MESSAGES }),
    )

    // Runs
    await page.route('**/api/v1/agent/threads/*/runs', (route) => {
        if (route.request().method() === 'POST') {
            return route.fulfill({ json: MOCK_RUN_RESULT })
        }
        return route.fulfill({ json: [] })
    })
    await page.route('**/api/v1/agent/threads/*/runs/*/resume', (route) =>
        route.fulfill({ json: { run_id: 'run-2', status: 'running' } }),
    )
    await page.route('**/api/v1/agent/threads/*/runs/*/cancel', (route) =>
        route.fulfill({ json: { ok: true } }),
    )

    // SSE stream — handled by browser-level EventSource mock (see sse-mock.ts)
    // Tests that need SSE call mockSSEStream() which injects via addInitScript.

    // Documents — GET 带 ?workspace_id=... 查询参数
    await page.route(pathEndsWith('/documents'), (route) => {
        if (route.request().method() === 'GET') {
            return route.fulfill({ json: [MOCK_DOCUMENT] })
        }
        return route.fulfill({ json: MOCK_DOCUMENT })
    })
    await page.route('**/api/v1/documents/upload-url', (route) =>
        route.fulfill({ json: { document_id: 'doc-new', upload_url: 'https://s3.example.com/upload', storage_key: 'key-1' } }),
    )
    // Documents confirm — POST 带 ?document_id=... 查询参数
    await page.route(pathEndsWith('/documents/confirm'), (route) =>
        route.fulfill({ json: { ...MOCK_DOCUMENT, id: 'doc-new', parse_status: 'pending' } }),
    )
    await page.route('**/api/v1/documents/*/retry', (route) =>
        route.fulfill({ json: { ...MOCK_DOCUMENT, parse_status: 'pending' } }),
    )
    await page.route('**/api/v1/documents/*', (route) => {
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.fulfill({ json: MOCK_DOCUMENT })
    })

    // S3 upload URL mock
    await page.route('https://s3.example.com/**', (route) =>
        route.fulfill({ status: 200, body: '' }),
    )

    // Quota — 可能带查询参数
    await page.route(pathEndsWith('/quota/status'), (route) =>
        route.fulfill({ json: { total_used: 1000, total_limit: 10000, remaining: 9000, usage_percent: 10, workspaces: [] } }),
    )

    // Draft
    await page.route('**/api/v1/editor/draft/*', (route) =>
        route.fulfill({ json: MOCK_DRAFT }),
    )
    await page.route('**/api/v1/editor/draft', (route) => {
        if (route.request().method() === 'PUT') {
            return route.fulfill({ json: { thread_id: 'th-1', content: '# Updated', updated_at: '2025-01-01' } })
        }
        return route.fulfill({ json: MOCK_DRAFT })
    })

    // Thread detail / delete — exact /agent/threads/:id only
    await page.route((url) => {
        const pathname = url.pathname
        return pathname.includes('/api/v1/agent/threads/') && /^\/api\/v1\/agent\/threads\/[^/]+$/.test(pathname)
    }, (route) => {
        const pathParts = new URL(route.request().url()).pathname.split('/')
        const threadId = pathParts[pathParts.length - 1]
        if (route.request().method() === 'DELETE') {
            return route.fulfill({ json: { ok: true } })
        }
        return route.fulfill({
            json: {
                thread_id: threadId,
                title: threadId === 'th-2' ? 'Thread 2' : 'Thread 1',
                status: 'idle',
                active_run_id: null,
            },
        })
    })
}

/**
 * 在 localStorage 注入认证 token 绕过 AuthGuard。
 * 需要在 page.goto() 之前调用。
 */
export async function injectAuthToken(page: Page): Promise<void> {
    await page.addInitScript(() => {
        localStorage.setItem('access_token', 'test-access-token')
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
