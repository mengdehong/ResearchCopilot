import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { OAuthButtons } from '../components/OAuthButtons'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'

export default function RegisterPage() {
    const { t } = useTranslation()

    const [email, setEmail] = useState('')
    const [displayName, setDisplayName] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        setIsSubmitting(true)

        try {
            await api.post('/auth/register', {
                email,
                password,
                display_name: displayName,
            })
            setSuccess(true)
        } catch (err: any) {
            setError(
                err.response?.data?.detail ||
                'Registration failed. Please try again.',
            )
        } finally {
            setIsSubmitting(false)
        }
    }

    if (success) {
        return (
            <>
                <div className="auth-header">
                    <h2>🎉</h2>
                    <p>{t('auth.verify.title')}</p>
                </div>
                <p style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
                    {t('auth.verify.verifying')}
                </p>
                <div className="auth-links">
                    <Link to="/login">{t('auth.verify.back_to_login')}</Link>
                </div>
            </>
        )
    }

    return (
        <>
            <div className="auth-header">
                <h2>{t('auth.register.title')}</h2>
                <p>{t('auth.register.subtitle')}</p>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
                <div className="form-group">
                    <label className="form-label" htmlFor="displayName">
                        {t('auth.display_name')}
                    </label>
                    <input
                        id="displayName"
                        type="text"
                        className="form-input"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        required
                        autoComplete="name"
                    />
                </div>

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
                            {t('auth.signing_up')}
                        </span>
                    ) : (
                        t('auth.register.submit')
                    )}
                </button>
            </form>

            <div className="auth-divider">
                <span>{t('auth.or_continue_with')}</span>
            </div>

            <OAuthButtons />

            <div className="auth-links">
                {t('auth.have_account')}{' '}
                <Link to="/login">{t('auth.login_link')}</Link>
            </div>
        </>
    )
}
