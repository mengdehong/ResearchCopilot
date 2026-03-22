import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { server } from './server'

// ── MSW lifecycle ──
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => {
    server.resetHandlers()
    cleanup()
})
afterAll(() => server.close())

// ── jsdom 中缺少 crypto.randomUUID ──
if (typeof globalThis.crypto?.randomUUID !== 'function') {
    Object.defineProperty(globalThis, 'crypto', {
        value: {
            ...globalThis.crypto,
            randomUUID: () =>
                'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
                    const r = (Math.random() * 16) | 0
                    const v = c === 'x' ? r : (r & 0x3) | 0x8
                    return v.toString(16)
                }),
        },
        configurable: true,
    })
}

// ── mock sonner toast（避免 DOM 渲染错误）──
vi.mock('sonner', () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
        warning: vi.fn(),
        info: vi.fn(),
    },
}))
