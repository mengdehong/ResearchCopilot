import React, { useCallback, useEffect, useState } from 'react'
import api, { clearToken, setToken } from '@/lib/api'
import { AuthContext, type User } from './useAuth'

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [isAuthenticated, setIsAuthenticated] = useState(false)
    const [isLoading, setIsLoading] = useState(true)

    // Init: try to fetch current user or refresh token
    useEffect(() => {
        let mounted = true

        const initAuth = async () => {
            try {
                // If we have a valid session in backend (e.g. cookie),
                // calling /me should work if access token works, OR 401 triggers refresh
                // But wait, if access_token is purely in memory, we start with no token!
                // So calling /me directly will 401. The interceptor might refresh it.
                // Or we can explicitly call /refresh first.
                const res = await api.post('/auth/refresh')
                if (res.data?.access_token && mounted) {
                    setToken(res.data.access_token)
                    // Fetch user info
                    const userRes = await api.get('/auth/me')
                    setUser(userRes.data)
                    setIsAuthenticated(true)
                }
            } catch (err: unknown) {
                // Not authenticated or refresh token expired
                console.debug('Session restore failed or no session:', err)
                if (mounted) {
                    setUser(null)
                    setIsAuthenticated(false)
                    clearToken()
                }
            } finally {
                if (mounted) setIsLoading(false)
            }
        }

        initAuth()

        return () => {
            mounted = false
        }
    }, [])

    const login = useCallback((access_token: string, newUser: User) => {
        setToken(access_token)
        setUser(newUser)
        setIsAuthenticated(true)
    }, [])

    const logout = useCallback(async () => {
        try {
            await api.post('/auth/logout')
        } catch (error: unknown) {
            console.error('Failed to restore session:', error)
        } finally {
            clearToken()
            setUser(null)
            setIsAuthenticated(false)
        }
    }, [])

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}
