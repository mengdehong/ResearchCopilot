import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createLogger } from './logger'

describe('createLogger', () => {
    beforeEach(() => {
        vi.restoreAllMocks()
        localStorage.removeItem('LOG_FILTER')
    })

    afterEach(() => {
        localStorage.removeItem('LOG_FILTER')
    })

    it('returns an object with debug, info, warn, error, time, timeEnd methods', () => {
        const log = createLogger('Test')
        expect(typeof log.debug).toBe('function')
        expect(typeof log.info).toBe('function')
        expect(typeof log.warn).toBe('function')
        expect(typeof log.error).toBe('function')
        expect(typeof log.time).toBe('function')
        expect(typeof log.timeEnd).toBe('function')
    })

    it('warn calls console.warn with namespace prefix', () => {
        const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        const log = createLogger('SSE')
        log.warn('reconnecting', { attempt: 2 })

        expect(spy).toHaveBeenCalledOnce()
        const [prefix, msg, data] = spy.mock.calls[0]
        expect(prefix).toMatch(/^\[\d{2}:\d{2}:\d{2}\.\d{3}\]\[SSE\]$/)
        expect(msg).toBe('reconnecting')
        expect(data).toEqual({ attempt: 2 })
    })

    it('error calls console.error with namespace prefix', () => {
        const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
        const log = createLogger('API')
        log.error('request failed')

        expect(spy).toHaveBeenCalledOnce()
        const [prefix, msg] = spy.mock.calls[0]
        expect(prefix).toMatch(/\[API\]/)
        expect(msg).toBe('request failed')
    })

    it('omits data argument when not provided', () => {
        const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        const log = createLogger('Auth')
        log.warn('no data')

        expect(spy).toHaveBeenCalledOnce()
        expect(spy.mock.calls[0]).toHaveLength(2)
    })

    it('debug calls console.debug in dev environment', () => {
        const spy = vi.spyOn(console, 'debug').mockImplementation(() => {})
        const log = createLogger('Store')
        log.debug('state change', { key: 'value' })

        expect(spy).toHaveBeenCalledOnce()
        const [prefix, msg, data] = spy.mock.calls[0]
        expect(prefix).toMatch(/\[Store\]/)
        expect(msg).toBe('state change')
        expect(data).toEqual({ key: 'value' })
    })

    it('info calls console.info in dev environment', () => {
        const spy = vi.spyOn(console, 'info').mockImplementation(() => {})
        const log = createLogger('API')
        log.info('token refreshed')

        expect(spy).toHaveBeenCalledOnce()
    })

    // ── LOG_FILTER tests ──

    it('LOG_FILTER suppresses debug/info for non-matching namespace', () => {
        localStorage.setItem('LOG_FILTER', 'SSE,Auth')

        const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
        const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {})

        const log = createLogger('API')
        log.debug('should be suppressed')
        log.info('should also be suppressed')

        expect(debugSpy).not.toHaveBeenCalled()
        expect(infoSpy).not.toHaveBeenCalled()
    })

    it('LOG_FILTER allows matching namespace', () => {
        localStorage.setItem('LOG_FILTER', 'SSE,API')

        const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {})
        const log = createLogger('API')
        log.debug('should output')

        expect(debugSpy).toHaveBeenCalledOnce()
    })

    it('LOG_FILTER does not suppress warn/error', () => {
        localStorage.setItem('LOG_FILTER', 'Other')

        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

        const log = createLogger('API')
        log.warn('always visible')
        log.error('always visible')

        expect(warnSpy).toHaveBeenCalledOnce()
        expect(errorSpy).toHaveBeenCalledOnce()
    })

    // ── time / timeEnd tests ──

    it('timeEnd outputs duration via console.debug', () => {
        const spy = vi.spyOn(console, 'debug').mockImplementation(() => {})
        vi.spyOn(performance, 'now')
            .mockReturnValueOnce(100)
            .mockReturnValueOnce(350)

        const log = createLogger('Perf')
        log.time('operation')
        log.timeEnd('operation')

        expect(spy).toHaveBeenCalledOnce()
        const [prefix, msg] = spy.mock.calls[0]
        expect(prefix).toMatch(/\[Perf\]/)
        expect(msg).toBe('operation: 250ms')
    })

    it('timeEnd does nothing for unknown label', () => {
        const spy = vi.spyOn(console, 'debug').mockImplementation(() => {})
        const log = createLogger('Perf')
        log.timeEnd('unknown')

        expect(spy).not.toHaveBeenCalled()
    })
})
