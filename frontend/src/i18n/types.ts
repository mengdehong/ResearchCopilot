/**
 * i18n 类型定义。
 *
 * Locale: 支持的语言联合类型。
 * FlatKeys: 递归展平嵌套翻译字典为 dot-path 联合类型，
 *           使 t('workspace.title') 在编译期校验 key 存在性。
 */

export type Locale = 'en' | 'zh'

/**
 * 递归将嵌套对象类型展平为 dot-path 字符串联合。
 * 示例: { common: { save: string } } → 'common.save'
 */
export type FlatKeys<T, Prefix extends string = ''> =
    T extends string
    ? Prefix
    : {
        [K in keyof T & string]: FlatKeys<
            T[K],
            Prefix extends '' ? K : `${Prefix}.${K}`
        >
    }[keyof T & string]
