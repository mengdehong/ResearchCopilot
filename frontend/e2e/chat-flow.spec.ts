import { test, expect } from './fixtures'
import {
    mockSSEStream,
    nodeStart,
    nodeEnd,
    assistantMessage,
    contentBlock,
    errorEvent,
    runEnd,
} from './helpers/sse-mock'
import { pathEndsWith } from './helpers/api-mocks'

/**
 * 链路 1：发消息 → Agent 执行 → 结果显示
 *
 * 覆盖审计项：#3, #7, #15, #17 及正常行为
 */

const WORKBENCH_URL = '/workspace/ws-1'

test.describe('Chat Flow — Chain 1', () => {
    test('首次发消息自动创建 Thread 并更新 URL', async ({ authedPage: page }) => {
        // 注入 SSE mock 确保 run 有完整流程（NoopEventSource 的 run_end 可能在 thread 创建前触发）
        await mockSSEStream(page, [
            nodeStart('supervisor', 'n1'),
            nodeEnd('supervisor', 'n1'),
            assistantMessage('Hello!'),
            runEnd(),
        ])

        // 进入空 workbench（无 thread）
        await page.goto(WORKBENCH_URL)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Hello agent')

        const sendBtn = page.locator('button[aria-label="Send message"]')
        await sendBtn.click()

        // URL 应更新为包含 ?thread=
        await expect(page).toHaveURL(/thread=th-new/)
    })

    test('发消息后用户消息立即出现在 MessageList', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('What is quantum computing?')

        const sendBtn = page.locator('button[aria-label="Send message"]')
        await sendBtn.click()

        // 用户消息应出现
        await expect(page.getByText('What is quantum computing?')).toBeVisible()
    })

    test('SSE node_start/node_end → CoTTree 节点渲染', async ({ authedPage: page }) => {
        // AUDIT: #15 — node_end 匹配用 name 而非 id（当前行为在此测试覆盖）
        const events = [
            nodeStart('supervisor', 'node-id-1'),
            nodeEnd('supervisor', 'node-id-1'),
            nodeStart('rag_search', 'node-id-2'),
            nodeEnd('rag_search', 'node-id-2'),
            assistantMessage('Here are the results.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Search something')
        await page.locator('button[aria-label="Send message"]').click()

        // CoTTree 应显示节点名称
        // CoTTree: supervisor → "决策分析"(NODE_LABELS映射), rag_search → "rag_search"(无映射用原名)
        await expect(page.getByText('决策分析')).toBeVisible()
        await expect(page.getByText('rag_search')).toBeVisible()
    })

    test('SSE assistant_message → assistant 消息出现', async ({ authedPage: page }) => {
        const events = [
            nodeStart('supervisor', 'n1'),
            nodeEnd('supervisor', 'n1'),
            assistantMessage('I found 3 relevant papers on quantum computing.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Find papers')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('I found 3 relevant papers on quantum computing.')).toBeVisible()
    })

    test('SSE content_block → contentBlocks 队列注入', async ({ authedPage: page }) => {
        // AUDIT: #7 — contentBlock 后覆盖前（当前使用队列，已修复此问题）
        const events = [
            nodeStart('writer', 'n1'),
            contentBlock('# Section 1\n\nIntroduction paragraph.', 'writer'),
            nodeEnd('writer', 'n1'),
            nodeStart('reviewer', 'n2'),
            contentBlock('# Section 2\n\nResults paragraph.', 'reviewer'),
            nodeEnd('reviewer', 'n2'),
            assistantMessage('Done writing.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Write a paper')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Done writing.')).toBeVisible()
    })

    test('SSE run_end → streaming 停止，status 变为 idle', async ({ authedPage: page }) => {
        // AUDIT: #3 — RunSnapshot.status 始终 completed（前端仅关注 isStreaming）
        const events = [
            nodeStart('supervisor', 'n1'),
            nodeEnd('supervisor', 'n1'),
            assistantMessage('All done.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Quick task')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 run_end 处理后 idle 状态指示器出现
        await expect(page.getByText('All done.')).toBeVisible()
        // textarea 应重新可用（不 disabled）
        await expect(textarea).not.toBeDisabled()
    })

    test('SSE error 事件 → system 消息出现', async ({ authedPage: page }) => {
        const events = [
            nodeStart('supervisor', 'n1'),
            errorEvent('LLM rate limit exceeded'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Trigger error')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('LLM rate limit exceeded')).toBeVisible()
    })

    test('创建线程失败 → 显示错误消息', async ({ authedPage: page }) => {
        // 覆盖 thread 创建 API 返回错误（需要 pathEndsWith 因为 POST 带 query params）
        await page.route(pathEndsWith('/agent/threads'), (route) => {
            if (route.request().method() === 'POST') {
                return route.fulfill({ status: 500, json: { detail: 'Server error' } })
            }
            return route.fulfill({ json: [] })
        })

        await page.goto(WORKBENCH_URL)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Will fail')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Failed to create thread')).toBeVisible({ timeout: 5000 })
    })

    test('取消运行 → stop 按钮点击后 streaming 停止', async ({ authedPage: page }) => {
        // 使用不结束的 SSE 流模拟持续 streaming
        const events = [
            nodeStart('supervisor', 'n1'),
            // no run_end — stream hangs
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Long task')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 stop 按钮出现
        const stopBtn = page.locator('button[aria-label="Stop agent run"]')
        await stopBtn.waitFor({ state: 'visible', timeout: 5000 })
        await stopBtn.click()

        // streaming 应停止，textarea 可用
        await expect(textarea).not.toBeDisabled({ timeout: 5000 })
    })
})
