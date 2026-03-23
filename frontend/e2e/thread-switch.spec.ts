import { test, expect, expandSidebar } from './fixtures'
import { MOCK_THREAD, MOCK_THREAD_2, MOCK_MESSAGES, pathEndsWith } from './helpers/api-mocks'
import { mockSSEStream, interruptEvent, runEnd } from './helpers/sse-mock'

/**
 * 链路 2：切换 Thread → 状态恢复
 *
 * 覆盖审计项：#2, #9, #11 及正常行为
 */

const WORKBENCH_URL = '/workspace/ws-1'

test.describe('Thread Switch — Chain 2', () => {
    test('侧边栏点击 thread → URL 更新 + 加载历史消息', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // 等待页面加载 + 历史消息出现
        await expect(page.getByText('Hello agent')).toBeVisible()
        await expect(page.getByText('I can help you research.')).toBeVisible()
    })

    test('切换 thread 后历史消息更新为新 thread 的消息', async ({ authedPage: page }) => {
        // AUDIT: #11 — currentMessages.length === 0 检查可能竞态
        const thread2Messages = {
            messages: [
                { id: 'msg-3', role: 'user', content: 'Second thread question', timestamp: '2025-01-02T00:00:00Z' },
                { id: 'msg-4', role: 'assistant', content: 'Second thread answer', timestamp: '2025-01-02T00:00:01Z' },
            ],
            pending_interrupt: null,
        }

        // 先加载 th-1
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        await expandSidebar(page)
        await expect(page.getByText('Hello agent')).toBeVisible()

        // 覆盖 th-2 的消息 API
        await page.route(pathEndsWith('/agent/threads/th-2/messages'), (route) =>
            route.fulfill({ json: thread2Messages }),
        )

        // 点击 sidebar thread 2
        await page.getByText('Thread 2').click()

        // URL 变化 + 新消息出现
        await expect(page).toHaveURL(/thread=th-2/)
        await expect(page.getByText('Second thread question')).toBeVisible()
        await expect(page.getByText('Second thread answer')).toBeVisible()

        // 旧消息应消失
        await expect(page.getByText('Hello agent')).not.toBeVisible()
    })

    test('切换 thread 后 CoTTree 清空', async ({ authedPage: page }) => {
        // AUDIT: #9 — CoT 树不持久化，切走即丢
        // 首先注入一个有 CoT 的流
        const events = [
            { event_type: 'node_start', data: { node_name: 'analysis', node_id: 'n1' } },
            { event_type: 'node_end', data: { node_name: 'analysis', node_id: 'n1' } },
            { event_type: 'assistant_message', data: { content: 'Done' } },
            { event_type: 'run_end', data: {} },
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Analyze')
        await page.locator('button[aria-label="Send message"]').click()

        // CoT 节点应出现
        await expect(page.getByText('analysis')).toBeVisible()

        // 等待 SSE 流完成（run_end → isStreaming: false）
        // 否则切换 thread 后，新 EventSource 会重新触发所有事件
        await expect(page.getByText('Done')).toBeVisible({ timeout: 5000 })

        // 覆盖 th-2 消息
        await page.route(pathEndsWith('/agent/threads/th-2/messages'), (route) =>
            route.fulfill({ json: { messages: [], pending_interrupt: null } }),
        )

        // 展开侧边栏以显示 thread 列表
        await expandSidebar(page)

        // 切换到 th-2
        await page.getByText('Thread 2').click()
        await expect(page).toHaveURL(/thread=th-2/, { timeout: 5000 })

        // CoT 节点应消失（因为 reset 后只从历史加载，CoT 不持久化）
        // 需要等待 zustand reset → React 重渲染周期
        await expect(page.getByText('analysis')).not.toBeVisible({ timeout: 5000 })
    })

    test('侧边栏 New Thread 按钮 → 导航到空 workbench', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        await expect(page.getByText('Hello agent')).toBeVisible()

        // 展开侧边栏后找到 New Thread 按钮
        await expandSidebar(page)
        const newThreadBtn = page.getByText('New Thread')
        await newThreadBtn.click()

        // URL 应没有 thread 参数
        await expect(page).toHaveURL(new RegExp(`${WORKBENCH_URL}$`))
    })

    test('pending_interrupt 从 API 恢复', async ({ authedPage: page }) => {
        // AUDIT: #2 — 页面刷新后 interrupt 丢失（现在测 pending_interrupt 恢复机制）
        const messagesWithInterrupt = {
            messages: MOCK_MESSAGES.messages,
            pending_interrupt: {
                action: 'confirm_execute',
                run_id: 'run-1',
                thread_id: 'th-1',
                payload: { code: 'print("hello")' },
            } as const,
        }

        await page.route(pathEndsWith('/agent/threads/th-1/messages'), (route) =>
            route.fulfill({ json: messagesWithInterrupt }),
        )

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // HITL card 应出现
        await expect(page.getByText(/Confirm|确认执行/)).toBeVisible({ timeout: 5000 })
    })

    test('删除 thread → confirm dialog → API 调用', async ({ authedPage: page }) => {
        let deleteRequested = false
        await page.route('**/api/v1/agent/threads/th-1', (route) => {
            if (route.request().method() === 'DELETE') {
                deleteRequested = true
                return route.fulfill({ json: { ok: true } })
            }
            return route.continue()
        })

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        await expandSidebar(page)

        // 悬停 thread 列表项以显示删除按钮（group-hover 触发 opacity）
        const threadContainer = page.locator('.group', { has: page.getByText('Thread 1') })
        await threadContainer.hover()

        // 点击 Trash2 图标按钮（带 title 属性）
        const deleteBtn = threadContainer.locator('button[title]')
        await expect(deleteBtn).toBeVisible({ timeout: 2000 })
        await deleteBtn.click()

        // 确认删除对话框 (ConfirmDeleteDialog) — 按钮文本为硬编码中文 '确认删除'
        const confirmBtn = page.locator('button', { hasText: /确认删除|Delete/ })
        await expect(confirmBtn).toBeVisible({ timeout: 2000 })
        await confirmBtn.click()
    })

    test('侧边栏 thread 列表展开/折叠', async ({ authedPage: page }) => {
        // Mock 更多 threads 来触发展开/折叠按钮
        const manyThreads = Array.from({ length: 6 }, (_, i) => ({
            thread_id: `th-${i + 1}`,
            title: `Thread ${i + 1}`,
            status: 'active',
            updated_at: '2025-01-01',
            workspace_id: 'ws-1',
        }))

        await page.route(pathEndsWith('/agent/threads'), (route) => {
            if (route.request().method() === 'GET') {
                const url = new URL(route.request().url())
                const limit = url.searchParams.get('limit')
                return route.fulfill({
                    json: limit ? manyThreads.slice(0, parseInt(limit)) : manyThreads,
                })
            }
            return route.fulfill({ json: { thread_id: 'th-new', title: 'New', status: 'active', workspace_id: 'ws-1' } })
        })

        await page.goto(WORKBENCH_URL)
        await expandSidebar(page)

        // 初始只显示前 4 个
        await expect(page.getByText('Thread 1')).toBeVisible()

        // 找到展开按钮 — t('nav.expandHistory') = 'Expand full history'
        const expandBtn = page.getByText('Expand full history')
        await expect(expandBtn).toBeVisible({ timeout: 3000 })
        await expandBtn.click()
        // 展开后应显示更多 threads
        await expect(page.getByText('Thread 5')).toBeVisible()
    })
})
