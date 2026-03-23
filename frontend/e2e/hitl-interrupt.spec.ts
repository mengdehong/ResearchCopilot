import { test, expect } from './fixtures'
import { mockSSEStream } from './helpers/sse-mocks'

test.describe('HITL - Select Papers', () => {
    test('select_papers interrupt shows PaperSelectOverlay', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'select_papers',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    papers: [
                        { id: 'p1', title: 'Deep Learning Survey', relevance_score: 0.95, year: 2024 },
                        { id: 'p2', title: 'Transformer Architecture', relevance_score: 0.88 },
                    ],
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Find papers')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Deep Learning Survey')).toBeVisible({ timeout: 15000 })
        await expect(page.getByText('Transformer Architecture')).toBeVisible()
    })

    test('select papers and confirm sends resume', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'select_papers',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    papers: [
                        { id: 'p1', title: 'Paper A' },
                        { id: 'p2', title: 'Paper B' },
                    ],
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Find papers')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Paper A')).toBeVisible({ timeout: 15000 })
        // Select Paper A
        await page.getByText('Paper A').click()

        const resumePromise = page.waitForRequest(
            (req) => req.url().includes('/resume'),
        )
        // Click "Confirm Selection (1)" button
        await page.getByRole('button', { name: /Confirm Selection/i }).click()
        await resumePromise
    })

    test('select all toggle selects all papers', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'select_papers',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    papers: [
                        { id: 'p1', title: 'Paper A' },
                        { id: 'p2', title: 'Paper B' },
                    ],
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Paper A')).toBeVisible({ timeout: 15000 })

        // Click Select All
        await page.getByText('Select All').click()
        // Confirm button should show (2)
        await expect(page.getByRole('button', { name: /Confirm Selection \(2\)/i })).toBeVisible()
    })
})

test.describe('HITL - Confirm Execute', () => {
    test('confirm_execute shows code and approve/reject', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'confirm_execute',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    code: 'print("hello world")',
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Run code')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('print("hello world")')).toBeVisible({ timeout: 15000 })
        await expect(page.getByText('Approve & Execute')).toBeVisible()
        await expect(page.getByText('Reject')).toBeVisible()
    })

    test('approve execute calls resume API', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'confirm_execute',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    code: 'x = 1',
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Run')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('x = 1')).toBeVisible({ timeout: 15000 })

        const resumePromise = page.waitForRequest(
            (req) => req.url().includes('/resume'),
        )
        await page.getByText('Approve & Execute').click()
        await resumePromise
    })

    test('reject execute opens popover confirmation', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'confirm_execute',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    code: 'danger()',
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Run')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('danger()')).toBeVisible({ timeout: 15000 })

        // Click Reject — should open popover
        await page.getByRole('button', { name: 'Reject' }).click()
        // Popover asks for confirmation
        await expect(page.getByText('Are you sure you want to reject?')).toBeVisible()
    })
})

test.describe('HITL - Confirm Finalize', () => {
    test('confirm_finalize shows content and approve', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'confirm_finalize',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                    content: 'Final research summary here',
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Finalize')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Final research summary here')).toBeVisible({ timeout: 15000 })
        await expect(page.getByText('Approve')).toBeVisible()
    })
})

test.describe('HITL - Wait For Ingestion', () => {
    test('wait_for_ingestion shows loading state', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'interrupt',
                data: {
                    action: 'wait_for_ingestion',
                    run_id: 'run-1',
                    thread_id: 'th-1',
                },
            },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Wait')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Waiting for papers to be parsed...')).toBeVisible({ timeout: 15000 })
    })
})
