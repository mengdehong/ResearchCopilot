import { test, expect } from './fixtures'
import { mockSSEStream } from './helpers/sse-mocks'

test.describe('PDF Viewer', () => {
    test('empty state shows placeholder text', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        // Click the PDF tab
        await page.getByText('PDF').click()

        // Empty state: no activePdf
        await expect(page.getByText('PDF Viewer')).toBeVisible()
        await expect(page.getByText('An Agent workflow will display a PDF here')).toBeVisible()
    })

    test('pdf_highlight SSE event auto-switches to PDF tab', async ({ authedPage: page }) => {
        // Mock PDF download endpoint to return a fake blob
        await page.route('**/api/v1/documents/doc-123/download', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/pdf',
                body: Buffer.from('%PDF-1.4 fake'),
            }),
        )

        await mockSSEStream(page, [
            {
                event_type: 'pdf_highlight',
                data: {
                    document_id: 'doc-123',
                    page: 3,
                    bbox: [0, 0, 100, 100],
                    text_snippet: 'Important finding',
                },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Read paper')
        await page.getByRole('button', { name: 'Send message' }).click()

        // PDF tab should auto-activate and show document info
        await expect(page.getByText(/Doc: doc/)).toBeVisible({ timeout: 15000 })
        await expect(page.getByText('Page 3')).toBeVisible()
    })

    test('pdf_highlight shows text snippet', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents/doc-456/download', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/pdf',
                body: Buffer.from('%PDF-1.4 fake'),
            }),
        )

        await mockSSEStream(page, [
            {
                event_type: 'pdf_highlight',
                data: {
                    document_id: 'doc-456',
                    page: 1,
                    bbox: [],
                    text_snippet: 'Deep learning transforms NLP',
                },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Show paper')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Deep learning transforms NLP')).toBeVisible({ timeout: 15000 })
    })

    test('loading state shows Loading PDF text', async ({ authedPage: page }) => {
        // Delay the PDF download response to observe loading state
        await page.route('**/api/v1/documents/doc-slow/download', async (route) => {
            await new Promise((r) => setTimeout(r, 3000))
            return route.fulfill({
                status: 200,
                contentType: 'application/pdf',
                body: Buffer.from('%PDF-1.4'),
            })
        })

        await mockSSEStream(page, [
            {
                event_type: 'pdf_highlight',
                data: { document_id: 'doc-slow', page: 1, bbox: [], text_snippet: '' },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Loading PDF...')).toBeVisible({ timeout: 15000 })
    })

    test('download failure shows failed message', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents/doc-fail/download', (route) =>
            route.fulfill({ status: 500, body: 'Server Error' }),
        )

        await mockSSEStream(page, [
            {
                event_type: 'pdf_highlight',
                data: { document_id: 'doc-fail', page: 1, bbox: [], text_snippet: '' },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        await expect(page.getByText('Failed to load PDF')).toBeVisible({ timeout: 15000 })
    })

    test('iframe renders with correct page anchor', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents/doc-page/download', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'application/pdf',
                body: Buffer.from('%PDF-1.4 content'),
            }),
        )

        await mockSSEStream(page, [
            {
                event_type: 'pdf_highlight',
                data: { document_id: 'doc-page', page: 5, bbox: [], text_snippet: '' },
            },
            { event_type: 'run_end', data: {} },
        ])

        await page.goto('/workspace/ws-1?thread=th-1')
        await page.locator('textarea').fill('Query')
        await page.getByRole('button', { name: 'Send message' }).click()

        // Wait for the PDF iframe to appear and verify it has the correct title
        const iframe = page.locator('iframe[title="PDF Viewer"]')
        await expect(iframe).toBeVisible({ timeout: 15000 })

        // Verify the iframe src contains page anchor
        const src = await iframe.getAttribute('src')
        expect(src).toContain('#page=5')
    })
})
