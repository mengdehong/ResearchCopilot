import { useState } from 'react'
import { getToken, setToken, clearToken } from '@/lib/api'
import { useTranslation } from '@/i18n/useTranslation'
import { DISCIPLINES } from '@/types'
import type { Locale } from '@/i18n/types'
import './SettingsPage.css'

export default function SettingsPage() {
    const [apiKey, setApiKey] = useState(getToken() ?? '')
    const [saved, setSaved] = useState(false)
    const { t, locale, setLocale } = useTranslation()

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
        <div className="settings-page">
            <h1>{t('settings.title')}</h1>
            <p className="text-muted">{t('settings.subtitle')}</p>

            <section className="settings-section card">
                <h2>{t('settings.auth')}</h2>
                <div className="settings-field">
                    <label htmlFor="api-key">{t('settings.apiKeyLabel')}</label>
                    <input
                        id="api-key"
                        className="settings-input"
                        type="password"
                        placeholder="Enter your API key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                    />
                    <p className="settings-hint text-muted">
                        {t('settings.apiKeyHint')}
                    </p>
                </div>
                <div className="settings-actions">
                    <button className="btn btn--primary" onClick={handleSave}>
                        {saved ? t('common.saved') : t('common.save')}
                    </button>
                </div>
            </section>

            <section className="settings-section card">
                <h2>{t('settings.preferences')}</h2>

                <div className="settings-field">
                    <label htmlFor="language">{t('settings.language')}</label>
                    <select
                        id="language"
                        className="settings-input"
                        value={locale}
                        onChange={(e) => setLocale(e.target.value as Locale)}
                    >
                        <option value="en">English</option>
                        <option value="zh">中文</option>
                    </select>
                </div>

                <div className="settings-field">
                    <label htmlFor="discipline">{t('settings.defaultDiscipline')}</label>
                    <select id="discipline" className="settings-input">
                        {DISCIPLINES.map((d) => (
                            <option key={d} value={d}>
                                {t(`discipline.${d}`)}
                            </option>
                        ))}
                    </select>
                </div>
            </section>
        </div>
    )
}
