import { http, HttpResponse } from 'msw'

/** 默认的 happy-path handler，各测试文件可通过 server.use() 覆盖 */
export const handlers = [
    // ── Auth ──
    http.post('/api/auth/refresh', () =>
        HttpResponse.json({ access_token: 'test-access-token' }),
    ),
    http.get('/api/auth/me', () =>
        HttpResponse.json({
            id: 'user-1',
            email: 'test@example.com',
            display_name: 'Test User',
        }),
    ),
    http.post('/api/auth/login', () =>
        HttpResponse.json({
            access_token: 'login-token',
            user: { id: 'user-1', email: 'test@example.com', display_name: 'Test User' },
        }),
    ),
    http.post('/api/auth/logout', () => HttpResponse.json({ ok: true })),

    // ── Workspaces ──
    http.get('/api/workspaces', () =>
        HttpResponse.json([
            { id: 'ws-1', name: 'Workspace 1', discipline: 'computer_science', owner_id: 'user-1', is_deleted: false, created_at: '2025-01-01', updated_at: '2025-01-01' },
        ]),
    ),
    http.get('/api/workspaces/:id', ({ params }) =>
        HttpResponse.json({ id: params.id, name: 'Workspace 1', discipline: 'computer_science', owner_id: 'user-1', is_deleted: false, created_at: '2025-01-01', updated_at: '2025-01-01' }),
    ),
    http.get('/api/workspaces/:id/summary', ({ params }) =>
        HttpResponse.json({ workspace_id: params.id, name: 'Workspace 1', document_count: 3, doc_status_counts: { uploading: 0, pending: 0, parsing: 0, completed: 3, failed: 0 } }),
    ),
    http.post('/api/workspaces', async ({ request }) => {
        const body = await request.json() as Record<string, string>
        return HttpResponse.json({ id: 'ws-new', name: body.name, discipline: body.discipline ?? 'other', owner_id: 'user-1', is_deleted: false, created_at: '2025-01-01', updated_at: '2025-01-01' })
    }),
    http.delete('/api/workspaces/:id', () => HttpResponse.json({ ok: true })),

    // ── Documents ──
    http.get('/api/documents', () =>
        HttpResponse.json([
            { id: 'doc-1', workspace_id: 'ws-1', title: 'Paper A', file_path: '/a.pdf', parse_status: 'completed', source: 'upload', doi: null, abstract_text: null, year: null, include_appendix: false, created_at: '2025-01-01', updated_at: '2025-01-01' },
        ]),
    ),
    http.get('/api/documents/:id/status', ({ params }) =>
        HttpResponse.json({ id: params.id, parse_status: 'completed', updated_at: '2025-01-01' }),
    ),
    http.post('/api/documents/upload-url', () =>
        HttpResponse.json({ document_id: 'doc-new', upload_url: 'https://s3.example.com/upload', storage_key: 'key-1' }),
    ),
    http.post('/api/documents/confirm', () =>
        HttpResponse.json({ id: 'doc-new', workspace_id: 'ws-1', title: 'New Doc', file_path: '/new.pdf', parse_status: 'pending', source: 'upload', doi: null, abstract_text: null, year: null, include_appendix: false, created_at: '2025-01-01', updated_at: '2025-01-01' }),
    ),
    http.post('/api/documents/:id/retry', ({ params }) =>
        HttpResponse.json({ id: params.id, workspace_id: 'ws-1', title: 'Retry Doc', file_path: '/retry.pdf', parse_status: 'pending', source: 'upload', doi: null, abstract_text: null, year: null, include_appendix: false, created_at: '2025-01-01', updated_at: '2025-01-01' }),
    ),
    http.delete('/api/documents/:id', () => HttpResponse.json({ ok: true })),

    // ── Agent / Threads ──
    http.get('/api/agent/threads', () =>
        HttpResponse.json([
            { thread_id: 'th-1', title: 'Thread 1', status: 'active', updated_at: '2025-01-01', workspace_id: 'ws-1' },
        ]),
    ),
    http.post('/api/agent/threads', () =>
        HttpResponse.json({ thread_id: 'th-new', title: 'New Thread', status: 'active', workspace_id: 'ws-1' }),
    ),
    http.post('/api/agent/threads/:threadId/runs', () =>
        HttpResponse.json({ run_id: 'run-1', thread_id: 'th-1', status: 'running', stream_url: '/api/agent/threads/th-1/runs/run-1/stream' }),
    ),
    http.post('/api/agent/threads/:threadId/runs/:runId/resume', () =>
        HttpResponse.json({ run_id: 'run-1', status: 'running' }),
    ),
    http.post('/api/agent/threads/:threadId/runs/:runId/cancel', () =>
        HttpResponse.json({ ok: true }),
    ),
    http.delete('/api/agent/threads/:threadId', () => HttpResponse.json({ ok: true })),

    // ── Quota ──
    http.get('/api/quota/status', () =>
        HttpResponse.json({ total_used: 1000, total_limit: 10000, remaining: 9000, usage_percent: 10, workspaces: [] }),
    ),

    // ── Editor / Draft ──
    http.get('/api/editor/draft/:threadId', ({ params }) =>
        HttpResponse.json({ thread_id: params.threadId, content: '# Draft', updated_at: '2025-01-01' }),
    ),
    http.put('/api/editor/draft', () =>
        HttpResponse.json({ thread_id: 'th-1', content: '# Updated', updated_at: '2025-01-01' }),
    ),
]
