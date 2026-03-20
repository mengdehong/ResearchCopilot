import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { useAuth } from '../useAuth'
import { OAuthButtons } from '../components/OAuthButtons'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'

export default function LoginPage() {
    const { t } = useTranslation()
    const { login } = useAuth()
    const location = useLocation()

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const from = location.state?.from?.pathname || '/workspaces'

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            const res = await api.post('/auth/login', { email, password })
            const { access_token, user } = res.data
            login(access_token, user)
            // Redirect will be handled by GuestGuard basically,
            // but we can manually redirect to where they came from
            window.location.href = from
        } catch (err: any) {
            setError(err.response?.data?.detail || t('auth.login_error'))
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <>
            <div className="auth-header">
                <h2>{t('auth.login.title')}</h2>
                <p>{t('auth.login.subtitle')}</p>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label" htmlFor="email">
                        {t('auth.email')}
                    </label>
                    <input
                        id="email"
                        type="email"
                        className="form-input"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoComplete="email"
                    />
                </div>

                <div className="form-group">
                    <div className="flex justify-between items-center mb-1">
                        <label className="form-label mb-0" htmlFor="password">
                            {t('auth.password')}
                        </label>
                        <Link to="/forgot-password" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
                            {t('auth.forgot_password_link')}
                        </Link>
                    </div>
                    <PasswordInput
                        id="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        autoComplete="current-password"
                    />
                </div>

                {error && <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">{error}</div>}

                <button type="submit" className="btn-primary" disabled={isSubmitting}>
                    {isSubmitting ? (
                        <span className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            {t('auth.signing_in')}
                        </span>
                    ) : (
                        t('auth.login.submit')
                    )}
                </button>
            </form>

            <div className="auth-divider">
                <span>{t('auth.or_continue_with')}</span>
            </div>

            <OAuthButtons />

            <div className="auth-links">
                {t('auth.no_account')}{' '}
                <Link to="/register">{t('auth.register_link')}</Link>
            </div>
        </>
    )
}
