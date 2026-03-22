import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../useAuth'
import api from '@/lib/api'
import { setToken } from '@/lib/api'
import { Loader2, AlertCircle } from 'lucide-react'

/**
 * OAuth 回调页面 — 从 URL query 中提取 access_token，
 * 调用 /api/auth/me 获取用户信息并完成登录。
 */
export default function OAuthCallbackPage() {
    const [searchParams] = useSearchParams()
    const { login } = useAuth()
    const navigate = useNavigate()
    const [error, setError] = useState('')

    useEffect(() => {
        const accessToken = searchParams.get('access_token')
        let mounted = true

        const finishLogin = async () => {
            if (!accessToken) {
                if (mounted) setError('OAuth 回调缺少 access_token 参数')
                return
            }

            try {
                // Set token first so /me request is authenticated
                setToken(accessToken)
                const res = await api.get('/auth/me')
                if (mounted) {
                    login(accessToken, res.data)
                    navigate('/workspaces', { replace: true })
                }
            } catch (err: unknown) {
                if (mounted) {
                    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string }
                    setError(
                        axiosErr.response?.data?.detail
                        || axiosErr.message
                        || 'OAuth 登录失败'
                    )
                }
            }
        }

        finishLogin()

        return () => {
            mounted = false
        }
    }, [searchParams, login, navigate])

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
                <div className="text-center space-y-4">
                    <AlertCircle className="w-12 h-12 text-[var(--error)] mx-auto" />
                    <p className="text-[var(--text-primary)] text-lg font-medium">{error}</p>
                    <a
                        href="/login"
                        className="inline-block text-blue-500 hover:text-blue-400 font-medium transition-colors"
                    >
                        返回登录
                    </a>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
            <div className="text-center space-y-4">
                <Loader2 className="w-10 h-10 animate-spin text-blue-500 mx-auto" />
                <p className="text-[var(--text-secondary)] text-sm">正在完成登录...</p>
            </div>
        </div>
    )
}
