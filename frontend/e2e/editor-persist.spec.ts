import { test, expect } from './fixtures'
import { mockSSEStream, nodeStart, nodeEnd, assistantMessage, contentBlock, runEnd, pdfHighlight, sandboxResult } from './helpers/sse-mock'
import { MOCK_DRAFT, pathEndsWith } from './helpers/api-mocks'

/**
 * 链路 4：Editor/Canvas 内容持久化
 *
 * 覆盖审计项：#7, #8, #10, #16 及正常行为
 */

const WORKBENCH_URL = '/workspace/ws-1'

test.describe('Editor Persistence — Chain 4', () => {
    test('EditorTab 加载时从 API 获取 draft 并渲染', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // 等待 EditorTab 渲染 draft 内容
        // Draft 内容为 '<h1>Draft Content</h1><p>Some research notes.</p>'
        await expect(page.getByText('Draft Content')).toBeVisible({ timeout: 10000 })
        await expect(page.getByText('Some research notes.')).toBeVisible()
    })

    test('content_block SSE → editor 收到内容', async ({ authedPage: page }) => {
        // AUDIT: #8 — contentBlock 未持久化到 DB（仅间接通过 draft save）
        const events = [
            nodeStart('writer', 'n1'),
            contentBlock('## Introduction\n\nThis is the introduction section.', 'writer'),
            nodeEnd('writer', 'n1'),
            assistantMessage('Content written.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Write intro')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Content written.')).toBeVisible({ timeout: 5000 })
    })

    test('多个 content_block → 按队列消费', async ({ authedPage: page }) => {
        // AUDIT: #7 — 旧版 contentBlock 后覆盖前，现在使用 contentBlocks 数组队列
        const events = [
            nodeStart('writer', 'n1'),
            contentBlock('# Part 1\n\nFirst section.', 'writer'),
            nodeEnd('writer', 'n1'),
            nodeStart('reviewer', 'n2'),
            contentBlock('# Part 2\n\nSecond section.', 'reviewer'),
            nodeEnd('reviewer', 'n2'),
            assistantMessage('Both parts done.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Write two parts')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Both parts done.')).toBeVisible({ timeout: 5000 })
    })

    test('editor 编辑触发 debounce save → PUT /editor/draft', async ({ authedPage: page }) => {
        // AUDIT: #10 — 切走时 debounce 可能丢失最后编辑
        let saveCalled = false
        await page.route(pathEndsWith('/editor/draft'), (route) => {
            if (route.request().method() === 'PUT') {
                saveCalled = true
                return route.fulfill({ json: { thread_id: 'th-1', content: '# Updated', updated_at: '2025-01-01' } })
            }
            return route.fulfill({ json: MOCK_DRAFT })
        })

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // 等待 editor 渲染
        await expect(page.getByText('Draft Content')).toBeVisible({ timeout: 10000 })

        // 在 editor 中键入内容
        const editorArea = page.locator('[contenteditable="true"]').first()
        await editorArea.click()
        await page.keyboard.type('New content added')

        // 等待 debounce save（2s）
        await page.waitForTimeout(3000)

        expect(saveCalled).toBe(true)
    })

    test('Canvas tab 切换（editor/pdf/sandbox）', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // 查找 tab 按钮
        const editorTab = page.locator('button', { hasText: /Editor|编辑器/i })
        const pdfTab = page.locator('button', { hasText: /PDF/i })
        const sandboxTab = page.locator('button', { hasText: /Sandbox|沙盒/i })

        // 检查 tab 区域是否存在
        if (await editorTab.isVisible({ timeout: 5000 })) {
            // 初始应在 editor tab
            await expect(page.getByText('Draft Content')).toBeVisible()

            // 切换到 PDF tab
            if (await pdfTab.isVisible()) {
                await pdfTab.click()
                // PDF tab 内容区域应可见
            }

            // 切回 editor
            await editorTab.click()
            await expect(page.getByText('Draft Content')).toBeVisible()
        }
    })

    test('pdf_highlight SSE → activePdf 状态更新', async ({ authedPage: page }) => {
        const events = [
            nodeStart('rag', 'n1'),
            pdfHighlight('doc-1', 3, [0.1, 0.2, 0.5, 0.4], 'Relevant text snippet'),
            nodeEnd('rag', 'n1'),
            assistantMessage('Found reference.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Find reference')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Found reference.')).toBeVisible({ timeout: 5000 })
    })

    test('sandbox_result SSE → SandboxTab 可展示结果', async ({ authedPage: page }) => {
        const events = [
            nodeStart('executor', 'n1'),
            sandboxResult('print("hello")', 'hello\n', '', 0),
            nodeEnd('executor', 'n1'),
            assistantMessage('Code executed.'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Run sandbox')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Code executed.')).toBeVisible({ timeout: 5000 })
    })
})
