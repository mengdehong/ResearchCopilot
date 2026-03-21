import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { useAuth } from '../useAuth'
import { OAuthButtons } from '../components/OAuthButtons'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, AlertCircle } from 'lucide-react'

export default function LoginPage() {
    const { t } = useTranslation()
    const { login } = useAuth()
    const location = useLocation()
    const navigate = useNavigate()

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
            navigate(from, { replace: true })
        } catch (err: any) {
            setError(err.response?.data?.detail || t('auth.login_error'))
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <>
            <div className="text-center mb-6">
                <h2 className="text-xl font-bold text-[var(--text-primary)]">
                    {t('auth.login.title')}
                </h2>
                <p className="text-sm text-[var(--text-secondary)] mt-1">
                    {t('auth.login.subtitle')}
                </p>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                    <Label htmlFor="email">{t('auth.email')}</Label>
                    <Input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoComplete="email"
                    />
                </div>

                <div className="space-y-1.5">
                    <div className="flex justify-between items-center">
                        <Label htmlFor="password">{t('auth.password')}</Label>
                        <Link
                            to="/forgot-password"
                            className="text-xs text-[var(--accent)] hover:text-[var(--accent-hover)]"
                        >
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

                {error && (
                    <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-[var(--error-subtle)] text-[var(--error)] text-sm">
                        <AlertCircle className="size-4 shrink-0" />
                        {error}
                    </div>
                )}

                <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                    {isSubmitting ? t('auth.signing_in') : t('auth.login.submit')}
                </Button>
            </form>

            <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-[var(--border)]" />
                </div>
                <div className="relative flex justify-center">
                    <span className="bg-[var(--surface)] px-2 text-xs text-[var(--text-muted)]">
                        {t('auth.or_continue_with')}
                    </span>
                </div>
            </div>

            <OAuthButtons />

            <div className="text-center text-sm text-[var(--text-secondary)] mt-4">
                {t('auth.no_account')}{' '}
                <Link to="/register" className="text-[var(--accent)] hover:text-[var(--accent-hover)] font-medium">
                    {t('auth.register_link')}
                </Link>
            </div>
        </>
    )
}
