import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getToken, setToken, clearToken } from '@/lib/api'
import { useTranslation } from '@/i18n/useTranslation'
import type { LocaleContextValue } from '@/i18n/LocaleContext'
import { DISCIPLINES } from '@/types'
import type { Locale } from '@/i18n/types'
import { useTheme, type Theme } from '@/hooks/useTheme'
import { useQuotaStatus } from '@/hooks/useQuotaStatus'
import { useAuth } from '@/features/auth/useAuth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { FadeIn } from '@/components/shared/MotionWrappers'
import { Sun, Moon, Monitor, Check, Zap, LogOut } from 'lucide-react'

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

/* ─── Token formatting ─── */
function formatTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
    return String(n)
}

function usageColor(pct: number): string {
    if (pct >= 90) return 'var(--destructive, #ef4444)'
    if (pct >= 70) return 'var(--warning, #f59e0b)'
    return 'var(--accent, #22c55e)'
}

/* ─── Quota Usage Card ─── */
interface QuotaData {
    readonly total_used: number
    readonly total_limit: number
    readonly remaining: number
    readonly usage_percent: number
    readonly workspaces: readonly {
        readonly workspace_id: string
        readonly workspace_name: string
        readonly used_tokens: number
        readonly limit_tokens: number
    }[]
}

interface QuotaUsageCardProps {
    readonly quota: QuotaData | undefined
    readonly loading: boolean
    readonly error: boolean
    readonly t: LocaleContextValue['t']
}

function QuotaUsageCard({ quota, loading, error, t }: QuotaUsageCardProps) {
    if (loading) {
        return (
            <SettingsCard title={t('settings.quotaTitle')} description={t('settings.quotaDesc')}>
                <div className="space-y-4 animate-pulse">
                    <div className="h-4 bg-[var(--surface-raised)] rounded-full w-full" />
                    <div className="h-3 bg-[var(--surface-raised)] rounded w-1/3" />
                    <div className="h-3 bg-[var(--surface-raised)] rounded w-1/2" />
                </div>
            </SettingsCard>
        )
    }

    if (error || !quota) {
        return (
            <SettingsCard title={t('settings.quotaTitle')} description={t('settings.quotaDesc')}>
                <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                    <Zap className="size-4" />
                    <span>0 / 1.0M</span>
                    <span className="text-xs ml-auto opacity-60">—</span>
                </div>
                <div className="h-2.5 rounded-full bg-[var(--surface-raised)] mt-2" />
            </SettingsCard>
        )
    }

    const pct = quota.usage_percent
    const color = usageColor(pct)

    return (
        <SettingsCard title={t('settings.quotaTitle')} description={t('settings.quotaDesc')}>
            <div className="space-y-5">
                {/* Overall progress */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                        <span className="flex items-center gap-1.5 text-[var(--text-secondary)] font-medium">
                            <Zap className="size-4" style={{ color }} />
                            {formatTokens(quota.total_used)} / {formatTokens(quota.total_limit)}
                        </span>
                        <span
                            className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{ backgroundColor: color, color: '#fff', opacity: 0.9 }}
                        >
                            {pct.toFixed(1)}%
                        </span>
                    </div>
                    <div className="h-2.5 rounded-full bg-[var(--surface-raised)] overflow-hidden">
                        <div
                            className="h-full rounded-full transition-all duration-700 ease-out"
                            style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }}
                        />
                    </div>
                    <p className="text-xs text-[var(--text-muted)]">
                        {t('settings.quotaRemaining')}: {formatTokens(quota.remaining)}
                    </p>
                </div>

                {/* Per-workspace breakdown */}
                {quota.workspaces.length > 0 && (
                    <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                            {t('settings.quotaByWorkspace')}
                        </h3>
                        <ul className="space-y-1.5">
                            {quota.workspaces.map((ws) => {
                                const wsPct = ws.limit_tokens > 0
                                    ? (ws.used_tokens / ws.limit_tokens) * 100
                                    : 0
                                return (
                                    <li key={ws.workspace_id} className="flex items-center gap-3 text-sm">
                                        <span className="text-[var(--text-secondary)] truncate flex-1 min-w-0">
                                            {ws.workspace_name}
                                        </span>
                                        <div className="w-24 h-1.5 rounded-full bg-[var(--surface-raised)] overflow-hidden flex-shrink-0">
                                            <div
                                                className="h-full rounded-full transition-all duration-500"
                                                style={{
                                                    width: `${Math.min(wsPct, 100)}%`,
                                                    backgroundColor: usageColor(wsPct),
                                                }}
                                            />
                                        </div>
                                        <span className="text-xs text-[var(--text-muted)] tabular-nums w-16 text-right flex-shrink-0">
                                            {formatTokens(ws.used_tokens)}
                                        </span>
                                    </li>
                                )
                            })}
                        </ul>
                    </div>
                )}
            </div>
        </SettingsCard>
    )
}

/* ─── Avatar Gradient ─── */
const AVATAR_HUES = [210, 250, 280, 320, 160, 30, 190, 140, 350, 50] as const

function avatarGradient(seed: string, dark: boolean): string {
    let hash = 0
    for (let i = 0; i < seed.length; i++) {
        hash = ((hash << 5) - hash + seed.charCodeAt(i)) | 0
    }
    const idx = Math.abs(hash) % AVATAR_HUES.length
    const hue = AVATAR_HUES[idx]
    const hue2 = (hue + 40) % 360
    // Light: muted pastels — Dark: slate / deep blue-gray
    const [sat, lit1, lit2] = dark ? [15, 42, 38] : [30, 78, 72]
    return `linear-gradient(135deg, hsl(${hue} ${sat}% ${lit1}%), hsl(${hue2} ${sat}% ${lit2}%))`
}

/* ─── Account Card ─── */
function AccountCard() {
    const { t } = useTranslation()
    const { user, logout } = useAuth()
    const { resolvedTheme } = useTheme()
    const navigate = useNavigate()

    if (!user) return null

    const initials = user.display_name
        .split(' ')
        .map((w) => w[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()

    const handleLogout = async () => {
        await logout()
        navigate('/login')
    }

    return (
        <section className="mb-10">
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)] p-5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 min-w-0">
                        <Avatar className="size-11 text-sm ring-1 ring-[var(--border)] ring-offset-2 ring-offset-[var(--surface)]">
                            {user.avatar_url && <AvatarImage src={user.avatar_url} alt={user.display_name} />}
                            <AvatarFallback
                                className="font-semibold text-white/80"
                                style={{ background: avatarGradient(user.email, resolvedTheme === 'dark') }}
                            >
                                {initials}
                            </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                            <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
                                {user.display_name}
                            </p>
                            <p className="text-xs text-[var(--text-muted)] truncate">
                                {user.email}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-2 px-4 py-2.5 rounded-[var(--radius-sm)] text-sm font-medium text-red-500 hover:bg-red-500/10 active:scale-[0.97] transition-all cursor-pointer shrink-0"
                    >
                        <LogOut className="size-4" />
                        {t('nav.logout')}
                    </button>
                </div>
            </div>
        </section>
    )
}

/* ─── Main Settings Page ─── */
export default function SettingsPage() {
    const [apiKey, setApiKey] = useState(getToken() ?? '')
    const [saved, setSaved] = useState(false)
    const { t, locale, setLocale } = useTranslation()
    const { theme, setTheme } = useTheme()
    const { data: quota, isLoading: quotaLoading, isError: quotaError } = useQuotaStatus()

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

                    {/* Account */}
                    <AccountCard />

                    {/* Token Usage */}
                    <QuotaUsageCard quota={quota} loading={quotaLoading} error={quotaError} t={t} />

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
