import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { useAuth } from '../useAuth'
import { OAuthButtons } from '../components/OAuthButtons'
import { PasswordInput } from '../components/PasswordInput'
import api from '@/lib/api'
import { Loader2, AlertCircle, Sparkles, ArrowRight } from 'lucide-react'

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
        } catch (err: unknown) {
            let errorMsg = t('auth.login_error')
            const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg: string }> } }; message?: string }
            const detail = axiosErr.response?.data?.detail
            if (typeof detail === 'string') {
                errorMsg = detail
            } else if (Array.isArray(detail)) {
                errorMsg = detail.map((d) => d.msg).join(', ')
            } else if (axiosErr.message) {
                errorMsg = axiosErr.message
            }
            setError(errorMsg)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <>
            <div className="mb-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-500 text-[10px] font-bold uppercase tracking-widest mb-6">
                    <Sparkles className="w-3 h-3" />
                    <span>{t('auth.brand.badge')}</span>
                </div>

                <h2 className="text-4xl font-display font-bold mb-3 text-[var(--text-primary)] tracking-tight">
                    {t('auth.login.title')}
                </h2>
                <p className="text-base text-[var(--text-secondary)] font-light">
                    {t('auth.login.subtitle')}
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

                <div className="space-y-1.5">
                    <div className="flex justify-between items-center ml-1">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-secondary)]/60">
                            {t('auth.password')}
                        </label>
                        <Link
                            to="/forgot-password"
                            className="text-[10px] text-blue-500 hover:text-blue-400 font-bold uppercase tracking-wider transition-colors"
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
                        placeholder="••••••••"
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
                    className="w-full mt-4 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-bold py-4 rounded-2xl shadow-xl shadow-blue-500/20 hover:shadow-blue-500/30 transition-all flex items-center justify-center gap-3 group active:scale-[0.98] disabled:opacity-60 disabled:pointer-events-none"
                >
                    {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                    <span className="text-base">{isSubmitting ? t('auth.signing_in') : t('auth.login.submit')}</span>
                    {!isSubmitting && <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />}
                </button>
            </form>

            <div className="relative my-10">
                <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-[var(--border)]" />
                </div>
                <div className="relative flex justify-center text-[10px] uppercase tracking-[0.3em] font-bold">
                    <span className="bg-[var(--background)] px-6 text-[var(--text-muted)]/50">
                        {t('auth.or_continue_with')}
                    </span>
                </div>
            </div>

            <OAuthButtons />

            <p className="mt-10 text-center text-sm text-[var(--text-secondary)]">
                {t('auth.no_account')}{' '}
                <Link to="/register" className="text-blue-500 font-bold hover:text-blue-400 transition-colors">
                    {t('auth.register_link')}
                </Link>
            </p>
        </>
    )
}
