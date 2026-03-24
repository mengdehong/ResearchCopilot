import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { FadeIn } from '@/components/shared/MotionWrappers'

export default function VerifyEmailPage() {
    const { t } = useTranslation()
    const [searchParams] = useSearchParams()
    const token = searchParams.get('token')

    const [status, setStatus] = useState<'loading' | 'success' | 'error'>(() => {
        return token ? 'loading' : 'error'
    })

    useEffect(() => {
        if (!token) return

        const verify = async () => {
            try {
                await api.post('/auth/verify-email', { token })
                setStatus('success')
            } catch {
                setStatus('error')
            }
        }
        verify()
    }, [token])

    return (
        <>
            <div className="mb-10">
                <h2 className="text-3xl font-display font-bold mb-3 text-[var(--text-primary)] tracking-tight">
                    {t('auth.verify.title')}
                </h2>
            </div>

            <div className="text-center py-6">
                {status === 'loading' && (
                    <FadeIn>
                        <div className="flex flex-col items-center gap-4">
                            <Loader2 className="size-8 text-blue-500 animate-spin" />
                            <p className="text-sm text-[var(--text-secondary)]">{t('auth.verify.verifying')}</p>
                        </div>
                    </FadeIn>
                )}

                {status === 'success' && (
                    <FadeIn>
                        <div className="flex flex-col items-center gap-4">
                            <div className="flex items-center justify-center size-12 rounded-full bg-[var(--success-subtle)]">
                                <CheckCircle2 className="size-6 text-[var(--success)]" />
                            </div>
                            <p className="text-sm text-[var(--text-primary)] font-medium">{t('auth.verify.success')}</p>
                        </div>
                    </FadeIn>
                )}

                {status === 'error' && (
                    <FadeIn>
                        <div className="flex flex-col items-center gap-4">
                            <div className="flex items-center justify-center size-12 rounded-full bg-[var(--error-subtle)]">
                                <XCircle className="size-6 text-[var(--error)]" />
                            </div>
                            <p className="text-sm text-[var(--text-primary)] font-medium">{t('auth.verify.error')}</p>
                        </div>
                    </FadeIn>
                )}
            </div>

            <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
                <Link to="/login" className="text-blue-500 font-bold hover:text-blue-400 transition-colors">
                    {t('auth.verify.back_to_login')}
                </Link>
            </p>
        </>
    )
}
