import { test, expect } from './fixtures'
import { mockSSEStream } from './helpers/sse-mocks'

test.describe('Chat Flow', () => {
    test('renders empty workbench page', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await expect(page.getByText('Chat')).toBeVisible()
        await expect(page.locator('textarea')).toBeVisible()
    })

    test('send message shows user message in list', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            { event_type: 'assistant_message', data: { content: 'Hello world' } },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1')
        await page.locator('textarea').fill('What is AI?')
        await page.getByRole('button', { name: 'Send message' }).click()

        // User message appears immediately (optimistic add)
        await expect(page.getByText('What is AI?')).toBeVisible()
        // Assistant response via SSE
        await expect(page.getByText('Hello world')).toBeVisible({ timeout: 15000 })
    })

    test('streaming state shows stop button', async ({ authedPage: page }) => {
        // Only node_start, no run_end — keeps streaming
        await mockSSEStream(page, [
            { event_type: 'node_start', data: { node_name: 'research', node_id: 'n1' } },
        ])

        await page.goto('/workspace/ws-1')
        await page.locator('textarea').fill('Research query')
        await page.getByRole('button', { name: 'Send message' }).click()

        // Stop button appears when streaming
        await expect(page.getByRole('button', { name: 'Stop agent run' })).toBeVisible({ timeout: 15000 })
    })

    test('stop button cancels run', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            { event_type: 'node_start', data: { node_name: 'search', node_id: 'n1' } },
        ])

        await page.goto('/workspace/ws-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        const stopBtn = page.getByRole('button', { name: 'Stop agent run' })
        await expect(stopBtn).toBeVisible({ timeout: 15000 })

        const cancelPromise = page.waitForRequest(
            (req) => req.url().includes('/cancel') && req.method() === 'POST',
        )
        await stopBtn.click()
        await cancelPromise
    })

    test('Enter sends message', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1')
        const textarea = page.locator('textarea')
        await textarea.fill('Send this')
        await textarea.press('Enter')
        // After Enter, textarea should be cleared (message sent)
        await expect(textarea).toHaveValue('')
    })

    test('thread creation failure shows error message', async ({ authedPage: page }) => {
        await page.route(/\/api\/v1\/agent\/threads(\?|$)/, (route) => {
            if (route.request().method() === 'POST') {
                return route.fulfill({ status: 400, json: { detail: 'Bad request' } })
            }
            return route.fulfill({ json: [] })
        })

        await page.goto('/workspace/ws-1')
        await page.locator('textarea').fill('Test message')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Failed to create thread')).toBeVisible({ timeout: 5000 })
    })

    test('run creation failure shows error message', async ({ authedPage: page }) => {
        await page.route('**/api/v1/agent/threads/*/runs', (route) => {
            if (route.request().method() === 'POST') {
                return route.fulfill({ status: 500, json: { detail: 'Server error' } })
            }
            return route.continue()
        })

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Test message')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Failed to start agent run')).toBeVisible({ timeout: 5000 })
    })

    test('CoT tree renders during streaming', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            { event_type: 'node_start', data: { node_name: 'literature_search', node_id: 'n1' } },
            { event_type: 'node_end', data: { node_name: 'literature_search' } },
            { event_type: 'assistant_message', data: { content: 'Done' } },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1')
        await page.locator('textarea').fill('Search papers')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('literature_search')).toBeVisible({ timeout: 15000 })
    })

    test('second message stays visible after first run completes', async ({ authedPage: page }) => {
        // Regression test: React Query re-fetches /messages after createRun invalidates queries.
        // The historyMessages effect must NOT overwrite optimistically-added messages.

        // First run: completes fast
        await mockSSEStream(page, [
            { event_type: 'assistant_message', data: { content: 'Answer to first' } },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')

        // Send first message and wait for the reply
        await page.locator('textarea').fill('First question')
        await page.getByRole('button', { name: 'Send message' }).click()
        await expect(page.getByText('Answer to first')).toBeVisible({ timeout: 15000 })

        // Send second message — this triggers createRun which invalidates ['messages'] in RQ,
        // causing historyMessages to re-fetch. The second message must NOT be wiped by loadMessages.
        await page.locator('textarea').fill('Second question')
        await page.getByRole('button', { name: 'Send message' }).click()

        // Both messages should still be visible simultaneously
        await expect(page.getByText('First question')).toBeVisible({ timeout: 5000 })
        await expect(page.getByText('Second question')).toBeVisible({ timeout: 5000 })
    })
})
