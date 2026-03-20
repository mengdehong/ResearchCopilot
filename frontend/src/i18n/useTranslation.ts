/**
 * 唯一对外 i18n hook。
 * 组件只依赖此 hook，不直接依赖 Context 实现。
 * 未来迁移到 react-i18next 只需替换此文件内部实现。
 */

import { use } from 'react'
import { LocaleContext } from './LocaleContext'

export function useTranslation() {
    return use(LocaleContext)
}
