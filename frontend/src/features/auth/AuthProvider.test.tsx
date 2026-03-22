import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import React from 'react'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/server'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'
import { getToken } from '@/lib/api'

function wrapper({ children }: { children: React.ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>
}

describe('AuthProvider', () => {
    it('initializes as authenticated when refresh succeeds', async () => {
        const { result } = renderHook(() => useAuth(), { wrapper })

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user).toMatchObject({
            id: 'user-1',
            email: 'test@example.com',
        })
        expect(getToken()).toBe('test-access-token')
    })

    it('initializes as unauthenticated when refresh fails', async () => {
        server.use(
            http.post('/api/auth/refresh', () =>
                HttpResponse.json({ error: 'expired' }, { status: 401 }),
            ),
        )

        const { result } = renderHook(() => useAuth(), { wrapper })

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBeNull()
    })

    it('login sets user and token', async () => {
        server.use(
            http.post('/api/auth/refresh', () =>
                HttpResponse.json({ error: 'no session' }, { status: 401 }),
            ),
        )

        const { result } = renderHook(() => useAuth(), { wrapper })

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        act(() => {
            result.current.login('new-token', {
                id: 'user-2',
                email: 'new@example.com',
                display_name: 'New User',
            })
        })

        expect(result.current.isAuthenticated).toBe(true)
        expect(result.current.user?.id).toBe('user-2')
        expect(getToken()).toBe('new-token')
    })

    it('logout clears state and calls API', async () => {
        const logoutSpy = vi.fn()
        server.use(
            http.post('/api/auth/logout', () => {
                logoutSpy()
                return HttpResponse.json({ ok: true })
            }),
        )

        const { result } = renderHook(() => useAuth(), { wrapper })

        await waitFor(() => {
            expect(result.current.isLoading).toBe(false)
        })

        await act(async () => {
            await result.current.logout()
        })

        expect(result.current.isAuthenticated).toBe(false)
        expect(result.current.user).toBeNull()
        expect(getToken()).toBeNull()
        expect(logoutSpy).toHaveBeenCalledOnce()
    })
})
