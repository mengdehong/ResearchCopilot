import { test, expect } from './fixtures'
import { mockSSEStream } from './helpers/sse-mocks'

test.describe('Editor Canvas', () => {
    test('canvas shows Editor, PDF, Sandbox tabs', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        await expect(page.getByText('Editor')).toBeVisible()
        await expect(page.getByText('PDF')).toBeVisible()
        await expect(page.getByText('Sandbox')).toBeVisible()
    })

    test('editor tab shows TipTap editor by default', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        await expect(page.locator('.ProseMirror')).toBeVisible({ timeout: 10000 })
    })

    test('draft content loads into editor', async ({ authedPage: page }) => {
        await page.route('**/api/v1/editor/draft/*', (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({
                    json: {
                        thread_id: 'th-1',
                        content: '<h1>My Research</h1><p>Introduction paragraph</p>',
                        updated_at: '2025-01-01',
                    },
                })
            }
            return route.fulfill({ json: { ok: true } })
        })

        await page.goto('/workspace/ws-1?thread=th-1')
        await expect(page.locator('.ProseMirror')).toContainText('My Research', { timeout: 10000 })
    })

    test('Ctrl+S triggers draft save API', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        const editor = page.locator('.ProseMirror')
        await expect(editor).toBeVisible({ timeout: 10000 })
        await editor.click()
        await editor.pressSequentially('Test content')

        // Set up request listener BEFORE pressing Ctrl+S
        const savePromise = page.waitForRequest(
            (req) => req.url().includes('/editor/draft') && req.method() === 'PUT',
        )
        await editor.press('Control+s')
        await savePromise
    })

    test('editor toolbar Bold button toggles formatting', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        const editor = page.locator('.ProseMirror')
        await expect(editor).toBeVisible({ timeout: 10000 })
        await editor.click()
        await editor.pressSequentially('Hello')
        // Select all text
        await editor.press('Control+a')
        // Click the Bold button by aria-label
        await page.getByRole('button', { name: 'Bold' }).click()
        await expect(editor.locator('strong')).toBeVisible()
    })

    test('content_block SSE event injects content into editor', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'content_block',
                data: { content: '# Generated Title\n\nGenerated paragraph.', workflow: 'summarize' },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Generate')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.locator('.ProseMirror')).toContainText('Generated Title', { timeout: 15000 })
    })

    test('sandbox_result SSE event switches to Sandbox tab', async ({ authedPage: page }) => {
        await mockSSEStream(page, [
            {
                event_type: 'sandbox_result',
                data: {
                    code: 'print(1+1)',
                    stdout: '2',
                    stderr: '',
                    exit_code: 0,
                    duration_ms: 100,
                    artifacts: [],
                },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Run code')
        await page.getByRole('button', { name: 'Send message' }).click()

        // Sandbox tab should auto-activate and show the code
        await expect(page.getByText('print(1+1)')).toBeVisible({ timeout: 15000 })
    })
})
