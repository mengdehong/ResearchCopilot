import { Outlet } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import '../auth.css'

export function AuthLayout() {
    const { t } = useTranslation()

    return (
        <div className="auth-layout">
            <div className="auth-brand">
                <div className="auth-brand-content">
                    <h1>{t('auth.brand.title')}</h1>
                    <p>{t('auth.brand.slogan')}</p>
                </div>
            </div>
            <div className="auth-content">
                <main className="auth-card">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
