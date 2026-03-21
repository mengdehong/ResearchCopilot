import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'
import { Loader2, AlertCircle, CheckCircle2, XCircle } from 'lucide-react'
import { FadeIn } from '@/components/shared/MotionWrappers'

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
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } } }
            setError(axiosErr.response?.data?.detail || t('auth.reset.error'))
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
                        {t('auth.reset.success')}
                    </h2>
                    <Link
                        to="/login"
                        className="text-sm text-blue-500 hover:text-blue-400 font-bold transition-colors"
                    >
                        {t('auth.verify.back_to_login')}
                    </Link>
                </div>
            </FadeIn>
        )
    }

    if (!token) {
        return (
            <FadeIn>
                <div className="text-center py-4">
                    <div className="flex items-center justify-center size-12 rounded-full bg-[var(--error-subtle)] mx-auto mb-4">
                        <XCircle className="size-6 text-[var(--error)]" />
                    </div>
                    <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                        {t('auth.reset.error')}
                    </h2>
                    <Link
                        to="/forgot-password"
                        className="text-sm text-blue-500 hover:text-blue-400 font-bold transition-colors"
                    >
                        {t('auth.forgot.submit')}
                    </Link>
                </div>
            </FadeIn>
        )
    }

    return (
        <>
            <div className="mb-10">
                <h2 className="text-3xl font-display font-bold mb-3 text-[var(--text-primary)] tracking-tight">
                    {t('auth.reset.title')}
                </h2>
                <p className="text-base text-[var(--text-secondary)] font-light">
                    {t('auth.reset.subtitle')}
                </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
                <PasswordInput
                    id="password"
                    label={t('auth.password')}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    minLength={8}
                    placeholder="••••••••"
                />

                {error && (
                    <div className="flex items-center gap-2 p-3 rounded-2xl bg-[var(--error-subtle)] text-[var(--error)] text-sm">
                        <AlertCircle className="size-4 shrink-0" />
                        {error}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full mt-4 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-bold py-4 rounded-2xl shadow-xl shadow-blue-500/20 hover:shadow-blue-500/30 transition-all flex items-center justify-center gap-3 active:scale-[0.98] disabled:opacity-60 disabled:pointer-events-none"
                >
                    {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                    <span className="text-base">{isSubmitting ? t('auth.reset.resetting') : t('auth.reset.submit')}</span>
                </button>
            </form>

            <p className="mt-10 text-center text-sm text-[var(--text-secondary)]">
                <Link to="/login" className="text-blue-500 font-bold hover:text-blue-400 transition-colors">
                    {t('auth.login_link')}
                </Link>
            </p>
        </>
    )
}
