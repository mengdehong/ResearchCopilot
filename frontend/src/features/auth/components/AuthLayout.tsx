import { Outlet } from 'react-router-dom'
import { useTranslation } from '@/i18n/useTranslation'
import { SlideUp, StaggerContainer, StaggerItem } from '@/components/shared/MotionWrappers'
import { Cpu, Zap, Layers, ShieldCheck, Send } from 'lucide-react'
import type { ElementType } from 'react'

interface Feature {
    readonly icon: ElementType
    readonly titleKey: 'planning' | 'parsing' | 'sandbox' | 'delivery'
    readonly color: string
}

const FEATURES: readonly Feature[] = [
    { icon: Zap, titleKey: 'planning', color: 'text-blue-500' },
    { icon: Layers, titleKey: 'parsing', color: 'text-purple-500' },
    { icon: ShieldCheck, titleKey: 'sandbox', color: 'text-emerald-500' },
    { icon: Send, titleKey: 'delivery', color: 'text-orange-500' },
] as const

export function AuthLayout() {
    const { t } = useTranslation()

    return (
        <div className="flex min-h-screen w-full flex-col lg:flex-row bg-[var(--background)] overflow-hidden font-sans transition-colors duration-500">
            {/* Dynamic Background Blobs */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[120px] animate-pulse" />
                <div
                    className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[120px] animate-pulse"
                    style={{ animationDelay: '2s' }}
                />
            </div>

            {/* Left: Brand & Feature Panel */}
            <div className="relative hidden lg:flex lg:w-1/2 flex-col justify-center lg:p-16 xl:p-24 bg-gradient-to-br from-blue-600/5 via-transparent to-purple-600/5 border-r border-[var(--border)]">
                {/* Dot Grid Background */}
                <div
                    className="absolute inset-0 opacity-[0.03] dark:opacity-[0.07] pointer-events-none"
                    style={{ backgroundImage: 'radial-gradient(var(--text-primary) 1px, transparent 1px)', backgroundSize: '32px 32px' }}
                />

                <div className="relative z-10 mb-16 xl:mb-20">
                    <SlideUp>
                        <div className="flex items-center gap-4 mb-2">
                            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-700 rounded-2xl flex items-center justify-center shadow-xl shadow-blue-500/20 animate-float">
                                <Cpu className="text-white w-7 h-7" />
                            </div>
                            <span className="text-3xl font-display font-bold tracking-tight text-[var(--text-primary)]">
                                {t('auth.brand.title')}
                            </span>
                        </div>
                    </SlideUp>

                    <SlideUp delay={0.1}>
                        <p className="text-lg text-[var(--text-secondary)] leading-relaxed font-light mt-6 max-w-lg">
                            {t('auth.brand.slogan')}
                        </p>
                    </SlideUp>
                </div>

                <StaggerContainer className="relative z-10 grid grid-cols-2 gap-6" staggerDelay={0.1}>
                    {FEATURES.map((feature) => {
                        const Icon = feature.icon
                        return (
                            <StaggerItem key={feature.titleKey}>
                                <div className="p-6 rounded-3xl glass-card shadow-sm hover:shadow-md transition-all group cursor-default">
                                    <Icon className={`w-6 h-6 ${feature.color} mb-4 group-hover:scale-110 transition-transform`} />
                                    <h3 className="text-base font-bold mb-2 text-[var(--text-primary)]">
                                        {t(`auth.brand.features.${feature.titleKey}.title`)}
                                    </h3>
                                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed opacity-80">
                                        {t(`auth.brand.features.${feature.titleKey}.desc`)}
                                    </p>
                                </div>
                            </StaggerItem>
                        )
                    })}
                </StaggerContainer>
            </div>

            {/* Right: Auth Form */}
            <div className="flex-1 flex flex-col justify-center items-center p-8 lg:p-20 relative">
                {/* Mobile Logo */}
                <div className="lg:hidden absolute top-10 left-10 flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-700 rounded-xl flex items-center justify-center shadow-lg">
                        <Cpu className="text-white w-6 h-6" />
                    </div>
                    <span className="text-2xl font-display font-bold tracking-tight text-[var(--text-primary)]">
                        {t('auth.brand.title')}
                    </span>
                </div>

                {/* Form Container */}
                <SlideUp>
                    <div className="w-full max-w-md relative">
                        {/* Subtle glow behind form */}
                        <div className="absolute inset-0 bg-blue-500/5 blur-[100px] -z-10" />
                        <Outlet />
                    </div>
                </SlideUp>
            </div>
        </div>
    )
}
