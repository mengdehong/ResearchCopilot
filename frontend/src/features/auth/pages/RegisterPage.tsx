import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { OAuthButtons } from '../components/OAuthButtons'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import { FadeIn } from '@/components/shared/MotionWrappers'

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
            <FadeIn>
                <div className="text-center py-4">
                    <div className="flex items-center justify-center size-12 rounded-full bg-[var(--success-subtle)] mx-auto mb-4">
                        <CheckCircle2 className="size-6 text-[var(--success)]" />
                    </div>
                    <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                        {t('auth.verify.title')}
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)] mb-6">
                        {t('auth.verify.verifying')}
                    </p>
                    <Link
                        to="/login"
                        className="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] font-medium"
                    >
                        {t('auth.verify.back_to_login')}
                    </Link>
                </div>
            </FadeIn>
        )
    }

    return (
        <>
            <div className="text-center mb-6">
                <h2 className="text-xl font-bold text-[var(--text-primary)]">
                    {t('auth.register.title')}
                </h2>
                <p className="text-sm text-[var(--text-secondary)] mt-1">
                    {t('auth.register.subtitle')}
                </p>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                    <Label htmlFor="displayName">{t('auth.display_name')}</Label>
                    <Input
                        id="displayName"
                        type="text"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        required
                        autoComplete="name"
                    />
                </div>

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
                    <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-[var(--error-subtle)] text-[var(--error)] text-sm">
                        <AlertCircle className="size-4 shrink-0" />
                        {error}
                    </div>
                )}

                <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                    {isSubmitting ? t('auth.signing_up') : t('auth.register.submit')}
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
                {t('auth.have_account')}{' '}
                <Link to="/login" className="text-[var(--accent)] hover:text-[var(--accent-hover)] font-medium">
                    {t('auth.login_link')}
                </Link>
            </div>
        </>
    )
}
