import { test, expect } from './fixtures'

test.describe('Documents Page', () => {
    test('renders document list with title', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible()
        await expect(page.getByText('Paper A')).toBeVisible()
    })

    test('empty list shows empty state', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents?*', (route) =>
            route.fulfill({ json: [] }),
        )
        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText('No documents yet')).toBeVisible()
    })

    test('upload dropzone is visible', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText(/drag.*drop/i)).toBeVisible()
    })

    test('upload flow calls upload-url → PUT → confirm', async ({ authedPage: page }) => {
        let uploadUrlHit = false
        let confirmHit = false

        await page.route('**/api/v1/documents/upload-url', (route) => {
            uploadUrlHit = true
            return route.fulfill({
                json: { document_id: 'doc-new', upload_url: 'http://localhost:3000/mock-s3-upload', storage_key: 'key' },
            })
        })
        await page.route('**/mock-s3-upload', (route) =>
            route.fulfill({ status: 200, body: '' }),
        )
        await page.route(/\/api\/v1\/documents\/confirm/, (route) => {
            confirmHit = true
            return route.fulfill({
                json: {
                    id: 'doc-new', workspace_id: 'ws-1', title: 'Uploaded',
                    file_path: '/u.pdf', parse_status: 'pending', source: 'upload',
                    doi: null, abstract_text: null, year: null, include_appendix: false,
                    created_at: '2025-01-01', updated_at: '2025-01-01',
                },
            })
        })

        await page.goto('/workspace/ws-1/documents')

        // Use file chooser to upload
        const fileChooserPromise = page.waitForEvent('filechooser')
        await page.getByText(/drag.*drop/i).click()
        const fileChooser = await fileChooserPromise
        await fileChooser.setFiles({
            name: 'test-paper.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('fake pdf content'),
        })

        // Wait for upload flow to complete (upload-url → S3 PUT → confirm)
        await page.waitForTimeout(3000)
        expect(uploadUrlHit).toBe(true)
        expect(confirmHit).toBe(true)
    })

    test('completed document shows Completed badge', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText('Paper A')).toBeVisible()
        await expect(page.getByText('Completed')).toBeVisible()
    })

    test('delete document calls API', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText('Paper A')).toBeVisible()

        // Hover the document row — group class is on the flex parent
        const docRow = page.locator('div.group').filter({ hasText: 'Paper A' })
        await docRow.hover()

        const deletePromise = page.waitForRequest(
            (req) => req.url().includes('/documents/') && req.method() === 'DELETE',
        )
        await docRow.getByRole('button', { name: /delete/i }).click()
        await deletePromise
    })

    test('failed document shows retry button', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents?*', (route) =>
            route.fulfill({
                json: [
                    {
                        id: 'doc-fail',
                        workspace_id: 'ws-1',
                        title: 'Failed Paper',
                        file_path: '/fail.pdf',
                        parse_status: 'failed',
                        source: 'upload',
                        doi: null,
                        abstract_text: null,
                        year: null,
                        include_appendix: false,
                        created_at: '2025-01-01',
                        updated_at: '2025-01-01',
                    },
                ],
            }),
        )

        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText('Failed Paper')).toBeVisible()

        // Hover to reveal retry button
        const docRow = page.locator('div.group').filter({ hasText: 'Failed Paper' })
        await docRow.hover()

        await expect(docRow.getByRole('button', { name: /retry/i })).toBeVisible()

        const retryPromise = page.waitForRequest(
            (req) => req.url().includes('/retry'),
        )
        await docRow.getByRole('button', { name: /retry/i }).click()
        await retryPromise
    })

    test('loading state shows spinner text', async ({ authedPage: page }) => {
        await page.route('**/api/v1/documents?*', async (route) => {
            await new Promise((r) => setTimeout(r, 3000))
            return route.fulfill({ json: [] })
        })

        await page.goto('/workspace/ws-1/documents')
        await expect(page.getByText('Loading documents')).toBeVisible()
    })
})
