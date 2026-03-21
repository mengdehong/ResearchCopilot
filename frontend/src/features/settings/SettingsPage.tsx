import { useState } from 'react'
import { getToken, setToken, clearToken } from '@/lib/api'
import { useTranslation } from '@/i18n/useTranslation'
import { DISCIPLINES } from '@/types'
import type { Locale } from '@/i18n/types'
import { useTheme, type Theme } from '@/hooks/useTheme'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { FadeIn } from '@/components/shared/MotionWrappers'
import { Sun, Moon, Monitor, Check } from 'lucide-react'

export default function SettingsPage() {
    const [apiKey, setApiKey] = useState(getToken() ?? '')
    const [saved, setSaved] = useState(false)
    const { t, locale, setLocale } = useTranslation()
    const { theme, setTheme } = useTheme()

    const handleSave = () => {
        if (apiKey.trim()) {
            setToken(apiKey.trim())
        } else {
            clearToken()
        }
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
    }

    return (
        <FadeIn>
            <div className="h-full overflow-auto bg-[var(--background)]">
                <div className="p-8 md:p-12 max-w-3xl mx-auto">
                    <div className="mb-10 border-b border-[var(--border)] pb-6">
                        <h1 className="text-3xl font-semibold tracking-tight text-[var(--text-primary)] mb-2">
                            {t('settings.title')}
                        </h1>
                        <p className="text-[15px] text-[var(--text-secondary)]">
                            {t('settings.subtitle')}
                        </p>
                    </div>

                    {/* Theme */}
                    <SettingsCard title="Theme" description="Choose your preferred appearance">
                        <div className="grid grid-cols-3 gap-3">
                            {([
                                { value: 'light' as Theme, icon: Sun, label: 'Light' },
                                { value: 'dark' as Theme, icon: Moon, label: 'Dark' },
                                { value: 'system' as Theme, icon: Monitor, label: 'System' },
                            ]).map(({ value, icon: Icon, label }) => (
                                <button
                                    key={value}
                                    onClick={() => setTheme(value)}
                                    className={`
                                    relative flex flex-col items-center gap-2 p-4 rounded-[var(--radius-md)] border transition-all cursor-pointer
                                    ${theme === value
                                            ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                                            : 'border-[var(--border)] hover:border-[var(--border-hover)] bg-[var(--surface-raised)]'
                                        }
                                `}
                                >
                                    <Icon className={`size-5 ${theme === value ? 'text-[var(--accent)]' : 'text-[var(--text-muted)]'}`} />
                                    <span className={`text-xs font-medium ${theme === value ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]'}`}>
                                        {label}
                                    </span>
                                    {theme === value && (
                                        <Check className="absolute top-2 right-2 size-3.5 text-[var(--accent)]" />
                                    )}
                                </button>
                            ))}
                        </div>
                    </SettingsCard>

                    {/* Auth */}
                    <SettingsCard title={t('settings.auth')} description={t('settings.apiKeyHint')}>
                        <div className="space-y-3">
                            <div className="space-y-1.5">
                                <Label htmlFor="api-key">{t('settings.apiKeyLabel')}</Label>
                                <Input
                                    id="api-key"
                                    type="password"
                                    placeholder="Enter your API key"
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                />
                            </div>
                            <div className="flex justify-end">
                                <Button onClick={handleSave} size="sm">
                                    {saved && <Check className="size-3.5" />}
                                    {saved ? t('common.saved') : t('common.save')}
                                </Button>
                            </div>
                        </div>
                    </SettingsCard>

                    {/* Preferences */}
                    <SettingsCard title={t('settings.preferences')}>
                        <div className="space-y-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="language">{t('settings.language')}</Label>
                                <Select value={locale} onValueChange={(v) => setLocale(v as Locale)}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="en">English</SelectItem>
                                        <SelectItem value="zh">中文</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="discipline">{t('settings.defaultDiscipline')}</Label>
                                <Select defaultValue="computer_science">
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {DISCIPLINES.map((d) => (
                                            <SelectItem key={d} value={d}>
                                                {t(`discipline.${d}`)}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </SettingsCard>
                </div>
            </div>
        </FadeIn>
    )
}

/* ─── Settings Card ─── */
interface SettingsCardProps {
    readonly title: string
    readonly description?: string
    readonly children: React.ReactNode
}

function SettingsCard({ title, description, children }: SettingsCardProps) {
    return (
        <section className="mb-10">
            <div className="mb-4">
                <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--text-primary)] mb-1">{title}</h2>
                {description && <p className="text-[13px] text-[var(--text-muted)]">{description}</p>}
            </div>
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)] p-5">
                {children}
            </div>
        </section>
    )
}
