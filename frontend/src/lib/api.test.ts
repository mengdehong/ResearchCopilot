import { describe, it, expect, beforeEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import api, { setToken, clearToken, getToken } from './api'

// toast 已在 setup.ts 中全局 mock

describe('api module', () => {
    beforeEach(() => {
        clearToken()
    })

    // ── token 管理 ──
    describe('token management', () => {
        it('getToken returns null initially', () => {
            expect(getToken()).toBeNull()
        })

        it('setToken / getToken round-trips', () => {
            setToken('abc-123')
            expect(getToken()).toBe('abc-123')
        })

        it('clearToken resets to null', () => {
            setToken('abc-123')
            clearToken()
            expect(getToken()).toBeNull()
        })
    })

    // ── 请求拦截器：注入 Authorization ──
    describe('request interceptor', () => {
        it('adds Bearer token to request headers', async () => {
            let capturedAuth: string | undefined
            server.use(
                http.get('/api/v1/test-auth', ({ request }) => {
                    capturedAuth = request.headers.get('Authorization') ?? undefined
                    return HttpResponse.json({ ok: true })
                }),
            )
            setToken('my-token')
            await api.get('/test-auth')
            expect(capturedAuth).toBe('Bearer my-token')
        })

        it('does not add Authorization when no token is set', async () => {
            let capturedAuth: string | null = null
            server.use(
                http.get('/api/v1/test-no-auth', ({ request }) => {
                    capturedAuth = request.headers.get('Authorization')
                    return HttpResponse.json({ ok: true })
                }),
            )
            await api.get('/test-no-auth')
            expect(capturedAuth).toBeNull()
        })
    })

    // ── 401 → token refresh ──
    describe('401 token refresh', () => {
        it('refreshes token and retries original request on 401', async () => {
            let callCount = 0
            server.use(
                http.get('/api/v1/protected', () => {
                    callCount++
                    if (callCount === 1) {
                        return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 })
                    }
                    return HttpResponse.json({ data: 'success' })
                }),
                http.post('/api/v1/auth/refresh', () =>
                    HttpResponse.json({ access_token: 'refreshed-token' }),
                ),
            )
            setToken('expired-token')
            const response = await api.get('/protected')
            expect(response.data).toEqual({ data: 'success' })
            expect(getToken()).toBe('refreshed-token')
        })

        it('rejects when refresh itself fails', async () => {
            server.use(
                http.get('/api/v1/protected-fail', () =>
                    HttpResponse.json({ error: 'Unauthorized' }, { status: 401 }),
                ),
                http.post('/api/v1/auth/refresh', () =>
                    HttpResponse.json({ error: 'expired' }, { status: 401 }),
                ),
            )
            setToken('expired-token')
            await expect(api.get('/protected-fail')).rejects.toThrow()
            expect(getToken()).toBeNull()
        })

        it('does not attempt refresh on login endpoint 401', async () => {
            server.use(
                http.post('/api/v1/auth/login', () =>
                    HttpResponse.json({ error: 'bad credentials' }, { status: 401 }),
                ),
            )
            await expect(api.post('/auth/login', {})).rejects.toThrow()
        })

        it('concurrent 401s trigger only one refresh and retry all requests', async () => {
            let refreshCallCount = 0
            let protectedCallCount = 0

            server.use(
                http.get('/api/v1/concurrent-protected', () => {
                    const call = ++protectedCallCount
                    if (call <= 2) {
                        // First two calls (original requests) → 401
                        return HttpResponse.json({ error: 'Unauthorized' }, { status: 401 })
                    }
                    // Retries succeed
                    return HttpResponse.json({ data: 'success' })
                }),
                http.post('/api/v1/auth/refresh', () => {
                    refreshCallCount++
                    return HttpResponse.json({ access_token: 'concurrent-refreshed-token' })
                }),
            )

            setToken('expired-token')

            // Fire two requests concurrently
            const [r1, r2] = await Promise.all([
                api.get('/concurrent-protected'),
                api.get('/concurrent-protected'),
            ])

            expect(r1.data).toEqual({ data: 'success' })
            expect(r2.data).toEqual({ data: 'success' })
            // Only one refresh should have been called despite two concurrent 401s
            expect(refreshCallCount).toBe(1)
            expect(getToken()).toBe('concurrent-refreshed-token')
        })
    })

    // ── 错误状态 toast ──
    describe('error status handling', () => {
        it('handles 403 response', async () => {
            const { toast } = await import('sonner')
            server.use(
                http.get('/api/v1/forbidden', () =>
                    HttpResponse.json({ error: 'forbidden' }, { status: 403 }),
                ),
            )
            await expect(api.get('/forbidden')).rejects.toThrow()
            expect(toast.error).toHaveBeenCalledWith('Permission denied', expect.any(Object))
        })

        it('handles 429 response', async () => {
            const { toast } = await import('sonner')
            server.use(
                http.get('/api/v1/rate-limited', () =>
                    HttpResponse.json({ error: 'too many' }, { status: 429 }),
                ),
            )
            await expect(api.get('/rate-limited')).rejects.toThrow()
            expect(toast.error).toHaveBeenCalledWith('Rate limit exceeded', expect.any(Object))
        })

        it('handles 500 response', async () => {
            const { toast } = await import('sonner')
            server.use(
                http.get('/api/v1/server-err', () =>
                    HttpResponse.json({ error: 'internal' }, { status: 500 }),
                ),
            )
            await expect(api.get('/server-err')).rejects.toThrow()
            expect(toast.error).toHaveBeenCalledWith('Server error', expect.any(Object))
        })
    })
})
