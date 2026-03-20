import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'

export default function ForgotPasswordPage() {
    const { t } = useTranslation()

    const [email, setEmail] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            await api.post('/auth/forgot-password', { email })
            setSuccess(true)
        } catch (err: any) {
            setError(
                err.response?.data?.detail || t('auth.forgot.error'),
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    if (success) {
        return (
            <>
                <div className="auth-header">
                    <h2>📧</h2>
                    <p>{t('auth.forgot.success')}</p>
                </div>
                <div className="auth-links">
                    <Link to="/login">{t('auth.verify.back_to_login')}</Link>
                </div>
            </>
        )
    }

    return (
        <>
            <div className="auth-header">
                <h2>{t('auth.forgot.title')}</h2>
                <p>{t('auth.forgot.subtitle')}</p>
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
                            {t('auth.forgot.sending')}
                        </span>
                    ) : (
                        t('auth.forgot.submit')
                    )}
                </button>
            </form>

            <div className="auth-links">
                <Link to="/login">{t('auth.login_link')}</Link>
            </div>
        </>
    )
}
