/**
 * LocaleProvider — i18n 的 React Context 实现。
 *
 * 语言检测优先级: localStorage → navigator.language → 'en'
 * 支持 {{param}} 插值语法，对齐 i18next 惯例。
 */

import { useState, useCallback, type ReactNode } from 'react'
import { en } from './locales/en'
import { zh } from './locales/zh'
import { LocaleContext } from './LocaleContext'
import type { Locale, FlatKeys } from './types'
import type { TranslationDict } from './locales/en'

const dictionaries: Record<Locale, TranslationDict> = { en, zh }

function detectLocale(): Locale {
    const stored = localStorage.getItem('locale')
    if (stored === 'en' || stored === 'zh') return stored
    return navigator.language.startsWith('zh') ? 'zh' : 'en'
}

/** 运行时按 dot-path 取值，支持 {{param}} 插值。 */
function resolve(
    dict: TranslationDict,
    key: string,
    params?: Record<string, string>,
): string {
    const value = key
        .split('.')
        .reduce<unknown>(
            (obj, k) => (obj as Record<string, unknown>)?.[k],
            dict,
        )
    if (typeof value !== 'string') return key
    if (!params) return value
    return value.replace(
        /\{\{(\w+)\}\}/g,
        (_, k: string) => params[k] ?? `{{${k}}}`,
    )
}

export function LocaleProvider({ children }: { children: ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>(detectLocale)

    const setLocale = useCallback((next: Locale) => {
        setLocaleState(next)
        localStorage.setItem('locale', next)
        document.documentElement.lang = next
    }, [])

    const t = useCallback(
        (
            key: FlatKeys<TranslationDict>,
            params?: Record<string, string>,
        ) => resolve(dictionaries[locale], key, params),
        [locale],
    )

    return (
        <LocaleContext value={{ locale, setLocale, t }}>
            {children}
        </LocaleContext>
    )
}
