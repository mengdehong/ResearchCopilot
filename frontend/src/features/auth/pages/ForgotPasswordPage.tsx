import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'
import { Loader2, AlertCircle, Mail } from 'lucide-react'
import { FadeIn } from '@/components/shared/MotionWrappers'

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
        } catch (err: unknown) {
            const axiosErr = err as { response?: { data?: { detail?: string } } }
            setError(axiosErr.response?.data?.detail || t('auth.forgot.error'))
        } finally {
            setIsSubmitting(false)
        }
    }

    if (success) {
        return (
            <FadeIn>
                <div className="text-center py-4">
                    <div className="flex items-center justify-center size-12 rounded-full bg-blue-500/10 mx-auto mb-4">
                        <Mail className="size-6 text-blue-500" />
                    </div>
                    <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">
                        📧
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)] mb-6">
                        {t('auth.forgot.success')}
                    </p>
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

    return (
        <>
            <div className="mb-10">
                <h2 className="text-3xl font-display font-bold mb-3 text-[var(--text-primary)] tracking-tight">
                    {t('auth.forgot.title')}
                </h2>
                <p className="text-base text-[var(--text-secondary)] font-light">
                    {t('auth.forgot.subtitle')}
                </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]/60 ml-1">
                        {t('auth.email')}
                    </label>
                    <input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@example.com"
                        required
                        autoComplete="email"
                        className="w-full px-5 py-3.5 rounded-2xl bg-[var(--surface)] border border-[var(--border)] focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/5 outline-none transition-all placeholder:text-[var(--text-muted)]/30 text-[var(--text-primary)] text-sm"
                    />
                </div>

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
                    <span className="text-base">{isSubmitting ? t('auth.forgot.sending') : t('auth.forgot.submit')}</span>
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
