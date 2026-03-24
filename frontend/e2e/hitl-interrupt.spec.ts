import { test, expect } from './fixtures'
import { mockSSEStream, interruptEvent, nodeStart, nodeEnd, runEnd } from './helpers/sse-mock'
import { pathEndsWith } from './helpers/api-mocks'

/**
 * 链路 3：HITL 中断 → 用户交互 → 恢复执行
 *
 * 覆盖审计项：#1, #2 及正常行为
 */

const WORKBENCH_URL = '/workspace/ws-1'

test.describe('HITL Interrupt — Chain 3', () => {
    test('SSE interrupt select_papers → SelectPapersCard 渲染', async ({ authedPage: page }) => {
        const events = [
            nodeStart('supervisor', 'n1'),
            interruptEvent('select_papers', 'th-1', 'run-1', {
                title: 'Select relevant papers',
                papers: [
                    { id: 'p1', title: 'Quantum Computing Survey', year: 2024, relevance_score: 0.95 },
                    { id: 'p2', title: 'Machine Learning Basics', year: 2023, relevance_score: 0.72 },
                ],
            }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Search papers')
        await page.locator('button[aria-label="Send message"]').click()

        // SelectPapersCard 应出现在 ChatPanel
        await expect(page.getByText(/paper.*right|论文列表/i)).toBeVisible({ timeout: 5000 })
    })

    test('SSE interrupt confirm_execute → ConfirmExecuteCard 渲染', async ({ authedPage: page }) => {
        // AUDIT: #1 — code 字段在翻译时被丢弃，前端 payload.code 可能为空
        const events = [
            nodeStart('executor', 'n1'),
            interruptEvent('confirm_execute', 'th-1', 'run-1', {
                title: 'Confirm code execution',
                code: 'print("hello world")',
            }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Execute code')
        await page.locator('button[aria-label="Send message"]').click()

        // ConfirmExecuteCard 应出现
        await expect(page.getByText(/Confirm.*Execute|确认执行/i)).toBeVisible({ timeout: 5000 })

        // AUDIT: #1 — 如果后端修复了翻译，此断言应验证 code 内容
        // 检查代码预览区域存在
        const codePreview = page.locator('pre')
        await expect(codePreview).toBeVisible()
    })

    test('SSE interrupt confirm_finalize → ConfirmFinalizeCard 渲染', async ({ authedPage: page }) => {
        // AUDIT: #1 — content 字段在翻译时被丢弃
        const events = [
            nodeStart('finalizer', 'n1'),
            interruptEvent('confirm_finalize', 'th-1', 'run-1', {
                title: 'Confirm finalization',
                content: '# Final Report\n\nThis is the final output.',
            }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Finalize output')
        await page.locator('button[aria-label="Send message"]').click()

        // ConfirmFinalizeCard 应出现
        // t('hitl.confirmFinalize') = 'Confirm Finalization'
        await expect(page.getByText('Confirm Finalization')).toBeVisible({ timeout: 5000 })
    })

    test('SSE interrupt wait_for_ingestion → WaitForIngestionCard 渲染', async ({ authedPage: page }) => {
        const events = [
            nodeStart('ingestion', 'n1'),
            interruptEvent('wait_for_ingestion', 'th-1', 'run-1', {}),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Upload and wait')
        await page.locator('button[aria-label="Send message"]').click()

        // WaitForIngestionCard 应出现 — 含 loading spinner
        // t('hitl.waitForIngestion') = 'Waiting for papers to be parsed...'
        await expect(page.getByText('Waiting for papers to be parsed...')).toBeVisible({ timeout: 5000 })
    })

    test('PaperSelectOverlay 勾选论文并确认', async ({ authedPage: page }) => {
        // 通过 pending_interrupt 加载 PaperSelectOverlay（从 CanvasPanel 路径触发）
        const messagesWithPaperInterrupt = {
            messages: [],
            pending_interrupt: {
                action: 'select_papers',
                run_id: 'run-1',
                thread_id: 'th-1',
                payload: {
                    papers: [
                        { id: 'p1', title: 'Paper A', year: 2024, relevance_score: 0.9, relevance_comment: 'Highly relevant' },
                        { id: 'p2', title: 'Paper B', year: 2023, relevance_score: 0.6 },
                        { id: 'p3', title: 'Paper C', year: 2022 },
                    ],
                },
            } as const,
        }

        await page.route(pathEndsWith('/agent/threads/th-1/messages'), (route) =>
            route.fulfill({ json: messagesWithPaperInterrupt }),
        )

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // PaperSelectOverlay 应出现（在 CanvasPanel 中）— 使用 heading 角色避免与 HITLCard 中的 paperListOnRight 文本冲突
        const overlayHeading = page.getByRole('heading', { name: 'Select Papers' })
        await expect(overlayHeading).toBeVisible({ timeout: 5000 })

        // 勾选第一篇论文（第一个 checkbox 是 select all，第二个才是论文）
        const paperCheckboxes = page.locator('input[type="checkbox"]')
        await expect(paperCheckboxes).toHaveCount(4, { timeout: 3000 }) // 1 select-all + 3 papers
        await paperCheckboxes.nth(1).check()

        // t('hitl.confirmSelection') format: 'Confirm Selection (N)'
        const confirmBtn = page.locator('button', { hasText: /Confirm Selection|确认选择/ })
        await expect(confirmBtn).toBeEnabled({ timeout: 3000 })
    })

    test('PaperSelectOverlay select all 切换', async ({ authedPage: page }) => {
        const messagesWithPaperInterrupt = {
            messages: [],
            pending_interrupt: {
                action: 'select_papers',
                run_id: 'run-1',
                thread_id: 'th-1',
                payload: {
                    papers: [
                        { id: 'p1', title: 'Paper A' },
                        { id: 'p2', title: 'Paper B' },
                    ],
                },
            } as const,
        }

        await page.route(pathEndsWith('/agent/threads/th-1/messages'), (route) =>
            route.fulfill({ json: messagesWithPaperInterrupt }),
        )

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        // PaperSelectOverlay heading — 使用 heading 角色避免与 HITLCard 文本冲突
        await expect(page.getByRole('heading', { name: 'Select Papers' })).toBeVisible({ timeout: 5000 })

        // Select All checkbox
        const selectAllLabel = page.locator('label', { hasText: /Select All|全选/ })
        await expect(selectAllLabel).toBeVisible({ timeout: 3000 })
        await selectAllLabel.click()

        // t('hitl.selectedCount', { count: '2' }) = '2 selected'
        await expect(page.getByText('2 selected')).toBeVisible()

        // 再点一次取消
        await selectAllLabel.click()
    })

    test('ConfirmExecuteCard approve → resume API 调用', async ({ authedPage: page }) => {
        let resumeBody: Record<string, unknown> | null = null
        await page.route('**/api/v1/agent/threads/*/runs/*/resume', async (route) => {
            resumeBody = await route.request().postDataJSON()
            return route.fulfill({ json: { run_id: 'run-2', status: 'running' } })
        })

        const events = [
            nodeStart('executor', 'n1'),
            interruptEvent('confirm_execute', 'th-1', 'run-1', { code: 'x = 1' }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Run code')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 card 出现
        const approveBtn = page.locator('button', { hasText: /Approve|批准|执行/ })
        await approveBtn.waitFor({ state: 'visible', timeout: 5000 })
        await approveBtn.click()

        // 验证 resume API 被调用
        await page.waitForTimeout(1000)
        expect(resumeBody).not.toBeNull()
        expect(resumeBody!.action).toBe('approve')
    })

    test('ConfirmExecuteCard reject → popover confirm → resume API 调用', async ({ authedPage: page }) => {
        let resumeBody: Record<string, unknown> | null = null
        await page.route('**/api/v1/agent/threads/*/runs/*/resume', async (route) => {
            resumeBody = await route.request().postDataJSON()
            return route.fulfill({ json: { run_id: 'run-2', status: 'running' } })
        })

        const events = [
            nodeStart('executor', 'n1'),
            interruptEvent('confirm_execute', 'th-1', 'run-1', { code: 'rm -rf /' }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Dangerous code')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 reject 按钮出现
        const rejectBtn = page.locator('button', { hasText: /Reject|拒绝/ })
        await rejectBtn.waitFor({ state: 'visible', timeout: 5000 })
        await rejectBtn.click()

        // Popover 确认
        const confirmReject = page.locator('button', { hasText: /Confirm.*Reject|确定拒绝/i })
        await confirmReject.waitFor({ state: 'visible', timeout: 3000 })
        await confirmReject.click()

        await page.waitForTimeout(1000)
        expect(resumeBody).not.toBeNull()
        expect(resumeBody!.action).toBe('reject')
    })

    test('ConfirmFinalizeCard approve/reject', async ({ authedPage: page }) => {
        let resumeCalls: Record<string, unknown>[] = []
        await page.route('**/api/v1/agent/threads/*/runs/*/resume', async (route) => {
            resumeCalls.push(await route.request().postDataJSON())
            return route.fulfill({ json: { run_id: 'run-2', status: 'running' } })
        })

        const events = [
            nodeStart('finalizer', 'n1'),
            interruptEvent('confirm_finalize', 'th-1', 'run-1', { content: 'Final draft' }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Finalize')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 approve 按钮出现
        const approveBtn = page.locator('button', { hasText: /Approve|批准/ })
        await approveBtn.waitFor({ state: 'visible', timeout: 5000 })
        await approveBtn.click()

        await page.waitForTimeout(1000)
        expect(resumeCalls.length).toBeGreaterThan(0)
        expect(resumeCalls[0].action).toBe('approve')
    })

    test('resume 成功后 interrupt 清空', async ({ authedPage: page }) => {
        await page.route('**/api/v1/agent/threads/*/runs/*/resume', (route) =>
            route.fulfill({ json: { run_id: 'run-2', status: 'running' } }),
        )

        // 注入带 stream 的 mock，第二次 run 有新的 SSE
        const events = [
            nodeStart('supervisor', 'n1'),
            interruptEvent('confirm_execute', 'th-1', 'run-1', { code: 'x = 1' }),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Execute')
        await page.locator('button[aria-label="Send message"]').click()

        // 等待 HITL card
        const approveBtn = page.locator('button', { hasText: /Approve|批准|执行/ })
        await approveBtn.waitFor({ state: 'visible', timeout: 5000 })
        await approveBtn.click()

        // HITL card 应消失
        await expect(approveBtn).not.toBeVisible({ timeout: 5000 })
    })

    test('未知 action → 显示 unknown action 提示', async ({ authedPage: page }) => {
        const events = [
            nodeStart('supervisor', 'n1'),
            interruptEvent('unknown_action_xyz', 'th-1', 'run-1', {}),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Trigger unknown')
        await page.locator('button[aria-label="Send message"]').click()

        // 防御性 UI — 应显示 unknown action 相关提示
        await expect(page.getByText(/unknown.*action|未知.*操作/i)).toBeVisible({ timeout: 5000 })
    })
})
