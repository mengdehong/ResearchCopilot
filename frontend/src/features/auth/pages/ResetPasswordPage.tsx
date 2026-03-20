import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'

export default function ResetPasswordPage() {
    const { t } = useTranslation()
    const [searchParams] = useSearchParams()
    const token = searchParams.get('token')

    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            await api.post('/auth/reset-password', {
                token,
                new_password: password,
            })
            setSuccess(true)
        } catch (err: any) {
            setError(
                err.response?.data?.detail || t('auth.reset.error'),
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    if (success) {
        return (
            <>
                <div className="auth-header">
                    <h2>✅</h2>
                    <p>{t('auth.reset.success')}</p>
                </div>
                <div className="auth-links">
                    <Link to="/login">{t('auth.verify.back_to_login')}</Link>
                </div>
            </>
        )
    }

    if (!token) {
        return (
            <>
                <div className="auth-header">
                    <h2>❌</h2>
                    <p>{t('auth.reset.error')}</p>
                </div>
                <div className="auth-links">
                    <Link to="/forgot-password">
                        {t('auth.forgot.submit')}
                    </Link>
                </div>
            </>
        )
    }

    return (
        <>
            <div className="auth-header">
                <h2>{t('auth.reset.title')}</h2>
                <p>{t('auth.reset.subtitle')}</p>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
                <PasswordInput
                    id="password"
                    label={t('auth.password')}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    minLength={8}
                />

                {error && (
                    <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    className="btn-primary"
                    disabled={isSubmitting}
                >
                    {isSubmitting ? (
                        <span className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            {t('auth.reset.resetting')}
                        </span>
                    ) : (
                        t('auth.reset.submit')
                    )}
                </button>
            </form>

            <div className="auth-links">
                <Link to="/login">{t('auth.login_link')}</Link>
            </div>
        </>
    )
}
