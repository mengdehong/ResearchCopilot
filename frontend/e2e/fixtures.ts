import { test as base, type Page } from '@playwright/test'
import { setupDefaultMocks, injectAuthToken } from './helpers/api-mocks'

/**
 * 扩展 Playwright test，提供已认证 + 已 mock 的 page。
 *
 * 注：如果测试不需要自定义 SSE 事件，fixture 自动注入一个空的
 * EventSource mock（立即发送 run_end）。如果测试调用了 mockSSEStream()，
 * 它会覆盖此默认行为（因为 addInitScript 按注册顺序执行，后注册的覆盖前面的）。
 */
export const test = base.extend<{ authedPage: Page; guestPage: Page }>({
    authedPage: async ({ page }, use) => {
        // 强制 locale = 'en'，确保所有测试使用英文 UI 文本
        await page.addInitScript(() => {
            localStorage.setItem('locale', 'en')
        })

        await injectAuthToken(page)
        await setupDefaultMocks(page)

        // 默认 EventSource mock：立即发送 run_end，避免连接真实后端。
        // 如果测试调用了 mockSSEStream()，其 addInitScript 会覆盖此版本。
        await page.addInitScript(() => {
            // @ts-expect-error override
            window.EventSource = class NoopEventSource {
                readonly url: string
                readonly readyState: number = 1
                onmessage: ((e: MessageEvent) => void) | null = null
                onerror: ((e: Event) => void) | null = null
                onopen: ((e: Event) => void) | null = null
                constructor(url: string) {
                    this.url = url
                    queueMicrotask(() => {
                        if (this.onopen) this.onopen(new Event('open'))
                        queueMicrotask(() => {
                            if (this.onmessage) {
                                this.onmessage(new MessageEvent('message', {
                                    data: JSON.stringify({ event_type: 'run_end', data: {} }),
                                }))
                            }
                        })
                    })
                }
                close() { /* noop */ }
                addEventListener() { /* noop */ }
                removeEventListener() { /* noop */ }
                dispatchEvent() { return true }
            }
        })

        await use(page)
    },

    guestPage: async ({ page }, use) => {
        await page.addInitScript(() => {
            localStorage.setItem('locale', 'en')
        })
        await page.route('**/api/v1/auth/refresh', (route) =>
            route.fulfill({ status: 401, json: { detail: 'No token' } }),
        )
        await use(page)
    },
})

export { expect } from '@playwright/test'

/**
 * 展开侧边栏以显示 thread 列表。
 * 需要在 page.goto() 之后调用。
 *
 * AppLayout DOM 结构：
 *   <motion.nav>
 *     <NavLink> (logo — 不是 button)
 *     <SidebarButton> (expand/collapse toggle — 第一个 button)
 *     ...
 *   </motion.nav>
 */
export async function expandSidebar(page: Page): Promise<void> {
    const toggle = page.getByTestId('sidebar-toggle')
    const isExpanded = await page.getByText('New Thread')
        .isVisible({ timeout: 500 }).catch(() => false)
    if (!isExpanded) {
        await toggle.click()
        await page.waitForTimeout(400)
    }
}
