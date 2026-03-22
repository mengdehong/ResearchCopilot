import axios from 'axios'
import { toast } from 'sonner'

let currentToken: string | null = null

export function getToken(): string | null {
    return currentToken
}

export function setToken(token: string | null): void {
    currentToken = token
}

export function clearToken(): void {
    currentToken = null
}

const api = axios.create({
    baseURL: '/api',
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true, // required for httpOnly cookies like refresh_token
})

import type { InternalAxiosRequestConfig } from 'axios'

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    if (currentToken) {
        config.headers.Authorization = `Bearer ${currentToken}`
    }
    return config
})

// Create a flag to prevent infinite refresh loops
let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function subscribeTokenRefresh(cb: (token: string) => void) {
    refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
    refreshSubscribers.forEach((cb) => cb(token))
    refreshSubscribers = []
}

api.interceptors.response.use(
    (response) => response,
    async (error: unknown) => {
        const err = error as { response?: { status?: number }; config?: InternalAxiosRequestConfig & { _retry?: boolean }; message?: string }
        const originalRequest = err.config
        const status = err.response?.status

        // ── 网络断开（无 response 对象）──
        if (!err.response) {
            toast.error('Network error', {
                description: 'Unable to connect to the server. Please check your network.',
                id: 'network-error', // 去重
            })
            return Promise.reject(error)
        }

        // ── 401: Token refresh ──
        if (status === 401 && !originalRequest?._retry) {
            // Prevent attempting to refresh if the refresh endpoint itself or login fails
            if (originalRequest?.url === '/auth/refresh' || originalRequest?.url === '/auth/login') {
                return Promise.reject(error)
            }

            if (isRefreshing) {
                return new Promise((resolve) => {
                    subscribeTokenRefresh((token: string) => {
                        if (originalRequest) {
                            originalRequest.headers.Authorization = `Bearer ${token}`
                            resolve(api(originalRequest))
                        } else {
                            resolve(Promise.reject(error))
                        }
                    })
                })
            }

            if (originalRequest) {
                originalRequest._retry = true
            }
            isRefreshing = true

            try {
                const response = await axios.post('/api/auth/refresh', {}, { withCredentials: true })
                const { access_token } = response.data
                setToken(access_token)
                isRefreshing = false
                onRefreshed(access_token)

                if (originalRequest) {
                    originalRequest.headers.Authorization = `Bearer ${access_token}`
                    return api(originalRequest)
                }
                return Promise.reject(error)
            } catch (refreshError) {
                isRefreshing = false
                clearToken()
                // Do not redirect blindly here to allow AuthGuard to handle navigation Reactively
                refreshSubscribers = []
                return Promise.reject(refreshError)
            }
        }

        // ── 403: 权限不足 ──
        if (status === 403) {
            toast.error('Permission denied', {
                description: 'You do not have permission to perform this action.',
                id: 'permission-denied',
            })
        }

        // ── 429: 请求频率过高 ──
        if (status === 429) {
            toast.error('Rate limit exceeded', {
                description: 'Too many requests. Please wait a moment and try again.',
                id: 'rate-limit',
            })
        }

        // ── 5xx: 服务端错误 ──
        if (status && status >= 500) {
            toast.error('Server error', {
                description: 'The service is temporarily unavailable. Please try again later.',
                id: 'server-error',
            })
        }

        return Promise.reject(error)
    },
)

export default api
