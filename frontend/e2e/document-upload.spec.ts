import { test, expect } from './fixtures'
import { MOCK_DOCUMENT, MOCK_DOCUMENT_FAILED, pathEndsWith } from './helpers/api-mocks'

/**
 * 链路 5：文档上传 → 解析 → 状态显示
 *
 * 覆盖审计项：#17 及正常行为
 */

const DOCUMENTS_URL = '/workspace/ws-1/documents'

test.describe('Document Upload — Chain 5', () => {
    test('DocumentsPage 显示文档列表 + 状态 Badge', async ({ authedPage: page }) => {
        await page.goto(DOCUMENTS_URL)

        // 文档标题应出现
        await expect(page.getByText('Paper A')).toBeVisible({ timeout: 5000 })

        // 状态 Badge 应出现
        // 状态 Badge: t('documents.status.completed') = 'Completed'
        await expect(page.getByText('Completed')).toBeVisible()
    })

    test('文档列表显示年份信息', async ({ authedPage: page }) => {
        await page.goto(DOCUMENTS_URL)

        // year 字段显示
        // year 字段显示（组件中为独立 span）
        await expect(page.getByText(/\(2024\)/)).toBeVisible({ timeout: 5000 })
    })

    test('文件上传三阶段 — initiate → PUT → confirm', async ({ authedPage: page }) => {
        let initiateUploadCalled = false
        let s3PutCalled = false
        let confirmCalled = false

        await page.route('**/api/v1/documents/upload-url', (route) => {
            initiateUploadCalled = true
            return route.fulfill({
                json: { document_id: 'doc-new', upload_url: 'https://s3.example.com/upload', storage_key: 'key-1' },
            })
        })

        await page.route('https://s3.example.com/**', (route) => {
            s3PutCalled = true
            return route.fulfill({ status: 200, body: '' })
        })

        // 注：POST /documents/confirm 带 ?document_id=... query params
        await page.route(pathEndsWith('/documents/confirm'), (route) => {
            confirmCalled = true
            return route.fulfill({
                json: { ...MOCK_DOCUMENT, id: 'doc-new', title: 'Uploaded Paper', parse_status: 'pending' },
            })
        })

        await page.goto(DOCUMENTS_URL)

        // 使用 file input 上传
        const fileInput = page.locator('input[type="file"]')
        await fileInput.setInputFiles({
            name: 'test-paper.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('fake pdf content'),
        })

        // 等待上传流程完成（事件驱动替代硬编码等待）
        await expect.poll(() => confirmCalled, { timeout: 5000 }).toBe(true)

        expect(initiateUploadCalled).toBe(true)
        expect(s3PutCalled).toBe(true)
    })

    test('上传过程中显示 spinner', async ({ authedPage: page }) => {
        // 延迟 S3 确认以看到 spinner
        await page.route('https://s3.example.com/**', async (route) => {
            await new Promise((r) => setTimeout(r, 1000))
            return route.fulfill({ status: 200, body: '' })
        })

        await page.goto(DOCUMENTS_URL)
        await page.waitForTimeout(500)

        const fileInput = page.locator('input[type="file"]')
        await fileInput.setInputFiles({
            name: 'uploading.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('fake pdf'),
        })

        // Spinner / uploading text 应出现
        // Spinner / uploading text: t('documents.uploading') = 'Uploading...'
        const uploadingText = page.getByText('Uploading...')
        await expect(uploadingText).toBeVisible({ timeout: 3000 })
    })

    test('上传失败 → 显示错误信息', async ({ authedPage: page }) => {
        // AUDIT: #17 — 上传错误 UI 反馈
        await page.route(pathEndsWith('/documents/upload-url'), (route) =>
            route.fulfill({ status: 500, json: { detail: 'Storage unavailable' } }),
        )

        await page.goto(DOCUMENTS_URL)
        await page.waitForTimeout(500)

        const fileInput = page.locator('input[type="file"]')
        await fileInput.setInputFiles({
            name: 'fail-upload.pdf',
            mimeType: 'application/pdf',
            buffer: Buffer.from('fake pdf'),
        })

        // 错误信息应出现
        await expect(page.getByText(/fail-upload\.pdf/i)).toBeVisible({ timeout: 5000 })
    })

    test('failed 文档显示 retry 按钮 → 点击 → API 调用', async ({ authedPage: page }) => {
        // 覆盖文档列表包含 failed 状态
        // 注：GET /documents 带 ?workspace_id=... query params
        await page.route(pathEndsWith('/documents'), (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({ json: [MOCK_DOCUMENT_FAILED] })
            }
            return route.fulfill({ json: MOCK_DOCUMENT })
        })

        let retryCalled = false
        await page.route('**/api/v1/documents/doc-2/retry', (route) => {
            retryCalled = true
            return route.fulfill({
                json: { ...MOCK_DOCUMENT_FAILED, parse_status: 'pending' },
            })
        })

        await page.goto(DOCUMENTS_URL)

        // failed 状态文档应出现
        await expect(page.getByText('Failed Paper')).toBeVisible({ timeout: 5000 })

        // 悬停显示 retry 按钮
        // hover 整个 card container 以触发 group-hover
        const docCard = page.locator('.group', { has: page.getByText('Failed Paper') })
        await docCard.hover()

        // t('common.retry') = 'Retry'
        const retryBtn = page.getByText('Retry')
        await expect(retryBtn).toBeVisible({ timeout: 3000 })
        await retryBtn.click()
        await expect.poll(() => retryCalled, { timeout: 3000 }).toBe(true)
    })

    test('删除文档 → API 调用', async ({ authedPage: page }) => {
        let deleteCalled = false
        await page.route('**/api/v1/documents/doc-1', (route) => {
            if (route.request().method() === 'DELETE') {
                deleteCalled = true
                return route.fulfill({ json: { ok: true } })
            }
            return route.fulfill({ json: MOCK_DOCUMENT })
        })

        await page.goto(DOCUMENTS_URL)
        await expect(page.getByText('Paper A')).toBeVisible({ timeout: 5000 })

        // 悬停显示 delete 按钮
        // hover 整个 card container 以触发 group-hover
        const docCard = page.locator('.group', { has: page.getByText('Paper A') })
        await docCard.hover()

        // t('common.delete') = 'Delete'
        const deleteBtn = page.getByText('Delete')
        await expect(deleteBtn).toBeVisible({ timeout: 3000 })
        await deleteBtn.click()
        await expect.poll(() => deleteCalled, { timeout: 3000 }).toBe(true)
    })

    test('空文档列表 → 显示 empty state', async ({ authedPage: page }) => {
        // 注：GET /documents 带 ?workspace_id=... query params
        await page.route(pathEndsWith('/documents'), (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({ json: [] })
            }
            return route.continue()
        })

        await page.goto(DOCUMENTS_URL)

        // Empty state 应出现
        // t('documents.empty') = 'No documents yet. Upload PDFs to get started.'
        await expect(page.getByText(/No documents yet/i)).toBeVisible({ timeout: 5000 })
    })

    test('拖拽区域存在且可点击', async ({ authedPage: page }) => {
        await page.goto(DOCUMENTS_URL)

        // Dropzone 文本应出现
        // t('documents.dropzone') = 'Drag & drop PDF files here, or click to upload'
        const dropzone = page.getByText(/Drag.*drop|click.*upload/i)
        await expect(dropzone).toBeVisible({ timeout: 5000 })
    })
})
