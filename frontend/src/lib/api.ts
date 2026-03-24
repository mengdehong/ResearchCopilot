import axios from 'axios'
import { toast } from 'sonner'
import { createLogger } from './logger'

const log = createLogger('API')

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

export const API_BASE = '/api/v1'

const api = axios.create({
    baseURL: API_BASE,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true, // required for httpOnly cookies like refresh_token
})

import type { InternalAxiosRequestConfig } from 'axios'

interface TimedRequestConfig extends InternalAxiosRequestConfig {
    _startTime?: number
    _retry?: boolean
}

api.interceptors.request.use((config: TimedRequestConfig) => {
    if (currentToken) {
        config.headers.Authorization = `Bearer ${currentToken}`
    }
    config._startTime = Date.now()
    log.debug('request', { method: config.method?.toUpperCase(), url: config.url })
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
    (response) => {
        const config = response.config as TimedRequestConfig
        const duration = config._startTime ? Date.now() - config._startTime : undefined
        log.debug('response', {
            method: config.method?.toUpperCase(),
            url: config.url,
            status: response.status,
            duration_ms: duration,
        })
        return response
    },
    async (error: unknown) => {
        const err = error as { response?: { status?: number }; config?: TimedRequestConfig; message?: string }
        const originalRequest = err.config
        const status = err.response?.status
        const duration = originalRequest?._startTime ? Date.now() - originalRequest._startTime : undefined

        // ── 网络断开（无 response 对象）──
        if (!err.response) {
            log.error('network error', { url: originalRequest?.url, message: err.message, duration_ms: duration })
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
                const response = await axios.post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
                const { access_token } = response.data
                setToken(access_token)
                isRefreshing = false
                onRefreshed(access_token)
                log.info('token refreshed')

                if (originalRequest) {
                    originalRequest.headers.Authorization = `Bearer ${access_token}`
                    return api(originalRequest)
                }
                return Promise.reject(error)
            } catch (refreshError) {
                isRefreshing = false
                clearToken()
                log.warn('token refresh failed')
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
            log.error('server error', { status, url: originalRequest?.url, duration_ms: duration })
            toast.error('Server error', {
                description: 'The service is temporarily unavailable. Please try again later.',
                id: 'server-error',
            })
        }

        return Promise.reject(error)
    },
)

export default api
