import { Outlet } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { ScaleIn } from '@/components/shared/MotionWrappers'

export function AuthLayout() {
    const { t } = useTranslation()

    return (
        <div className="flex min-h-screen bg-[var(--background)]">
            {/* Brand Panel */}
            <div className="hidden lg:flex lg:flex-1 items-center justify-center bg-gradient-to-br from-[var(--accent)] to-[var(--accent-hover)] p-12">
                <div className="text-center text-white max-w-md">
                    <div className="flex items-center justify-center size-16 rounded-[var(--radius-lg)] bg-white/20 backdrop-blur-sm mx-auto mb-6">
                        <span className="text-2xl font-bold">R</span>
                    </div>
                    <h1 className="text-3xl font-bold mb-3">
                        {t('auth.brand.title')}
                    </h1>
                    <p className="text-white/80 text-base leading-relaxed">
                        {t('auth.brand.slogan')}
                    </p>
                </div>
            </div>

            {/* Form Panel */}
            <div className="flex-1 flex items-center justify-center p-6">
                <ScaleIn>
                    <main className="w-full max-w-sm rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-lg">
                        <Outlet />
                    </main>
                </ScaleIn>
            </div>
        </div>
    )
}
