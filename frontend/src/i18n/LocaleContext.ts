import { createContext } from 'react'
import type { Locale, FlatKeys } from './types'
import type { TranslationDict } from './locales/en'

export interface LocaleContextValue {
    locale: Locale
    setLocale: (locale: Locale) => void
    t: (
        key: FlatKeys<TranslationDict>,
        params?: Record<string, string>,
    ) => string
}

export const LocaleContext = createContext<LocaleContextValue>(null!)
