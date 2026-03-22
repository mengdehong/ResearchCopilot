/**
 * 轻量前端日志工具。
 *
 * - debug / info：仅开发环境输出
 * - warn / error：所有环境输出
 * - time / timeEnd：仅开发环境，输出操作耗时
 * - 格式：[HH:mm:ss.SSS][namespace] message {data}
 *
 * 运行时过滤：
 *   localStorage.setItem('LOG_FILTER', 'SSE,API')
 *   设置后仅匹配的 namespace 输出 debug/info，warn/error 始终输出。
 *   清除过滤：localStorage.removeItem('LOG_FILTER')
 */

type LogData = Record<string, unknown>

export interface Logger {
    debug: (message: string, data?: LogData) => void
    info: (message: string, data?: LogData) => void
    warn: (message: string, data?: LogData) => void
    error: (message: string, data?: LogData) => void
    time: (label: string) => void
    timeEnd: (label: string) => void
}

function timestamp(): string {
    const d = new Date()
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    const s = String(d.getSeconds()).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${h}:${m}:${s}.${ms}`
}

function noop(): void {
    // intentionally empty — production no-op for debug/info/time
}

function isNamespaceEnabled(namespace: string): boolean {
    try {
        const filter = localStorage.getItem('LOG_FILTER')
        if (!filter) return true
        return filter.split(',').some((ns) => ns.trim() === namespace)
    } catch {
        return true
    }
}

function makeMethod(
    level: 'debug' | 'info' | 'warn' | 'error',
    namespace: string,
): (message: string, data?: LogData) => void {
    return (message: string, data?: LogData) => {
        const prefix = `[${timestamp()}][${namespace}]`
        if (data !== undefined) {
            console[level](prefix, message, data)
        } else {
            console[level](prefix, message)
        }
    }
}

function makeFilteredMethod(
    level: 'debug' | 'info',
    namespace: string,
): (message: string, data?: LogData) => void {
    const method = makeMethod(level, namespace)
    return (message: string, data?: LogData) => {
        if (!isNamespaceEnabled(namespace)) return
        method(message, data)
    }
}

const IS_DEV = import.meta.env.DEV

export function createLogger(namespace: string): Logger {
    const timers = new Map<string, number>()

    const timeStart = IS_DEV
        ? (label: string) => {
              timers.set(label, performance.now())
          }
        : noop

    const timeEnd = IS_DEV
        ? (label: string) => {
              const start = timers.get(label)
              if (start === undefined) return
              timers.delete(label)
              const duration = Math.round(performance.now() - start)
              console.debug(`[${timestamp()}][${namespace}]`, `${label}: ${duration}ms`)
          }
        : noop

    return {
        debug: IS_DEV ? makeFilteredMethod('debug', namespace) : noop,
        info: IS_DEV ? makeFilteredMethod('info', namespace) : noop,
        warn: makeMethod('warn', namespace),
        error: makeMethod('error', namespace),
        time: timeStart,
        timeEnd,
    }
}
