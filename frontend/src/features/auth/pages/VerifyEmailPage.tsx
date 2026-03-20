import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import api from '@/lib/api'

export default function VerifyEmailPage() {
    const { t } = useTranslation()
    const [searchParams] = useSearchParams()
    const token = searchParams.get('token')

    const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
        'loading',
    )

    useEffect(() => {
        if (!token) {
            setStatus('error')
            return
        }

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
            <div className="auth-header">
                <h2>{t('auth.verify.title')}</h2>
            </div>

            <div style={{ textAlign: 'center', padding: '2rem 0' }}>
                {status === 'loading' && (
                    <div className="flex flex-col items-center gap-4">
                        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                        <p>{t('auth.verify.verifying')}</p>
                    </div>
                )}

                {status === 'success' && (
                    <div className="flex flex-col items-center gap-4">
                        <p style={{ fontSize: '3rem' }}>✅</p>
                        <p>{t('auth.verify.success')}</p>
                    </div>
                )}

                {status === 'error' && (
                    <div className="flex flex-col items-center gap-4">
                        <p style={{ fontSize: '3rem' }}>❌</p>
                        <p>{t('auth.verify.error')}</p>
                    </div>
                )}
            </div>

            <div className="auth-links">
                <Link to="/login">{t('auth.verify.back_to_login')}</Link>
            </div>
        </>
    )
}
