import { test, expect } from './fixtures'

test.describe('Workspace Dashboard Page', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        // Override summary mock to include thread_count
        await page.route('**/api/v1/workspaces/*/summary', (route) =>
            route.fulfill({
                json: {
                    workspace_id: 'ws-1',
                    name: 'Workspace 1',
                    document_count: 3,
                    thread_count: 2,
                    doc_status_counts: { uploading: 0, pending: 0, parsing: 1, completed: 2, failed: 0 },
                },
            }),
        )
    })

    test('renders dashboard with stat cards', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')

        // Header
        await expect(page.getByText('Workspace 1')).toBeVisible()
        await expect(page.getByText('研究工作区概览')).toBeVisible()

        // Stat cards
        await expect(page.getByText('文献总数')).toBeVisible()
        await expect(page.getByText('研究对话')).toBeVisible()
        await expect(page.getByText('工作流运行')).toBeVisible()
    })

    test('displays stat card values from API', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')

        // document_count from summary
        const docCard = page.locator('text=文献总数').locator('..')
        await expect(docCard.getByText('3')).toBeVisible()

        // thread_count from summary
        const threadCard = page.locator('text=研究对话').locator('..')
        await expect(threadCard.getByText('2')).toBeVisible()
    })

    test('shows thread list with entries', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')

        await expect(page.getByText('近期对话')).toBeVisible()
        await expect(page.getByText('Thread 1')).toBeVisible()
        await expect(page.getByText('Thread 2')).toBeVisible()
    })

    test('shows document list', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')

        await expect(page.getByText('文献库')).toBeVisible()
        await expect(page.getByText('Paper A')).toBeVisible()
    })

    test('empty threads shows empty state', async ({ authedPage: page }) => {
        // Override threads mock to return empty
        await page.route('**/api/v1/agent/threads*', (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({ json: [] })
            }
            return route.continue()
        })

        await page.goto('/workspace/ws-1')
        await expect(page.getByText('还没有对话')).toBeVisible()
        await expect(page.getByText('开始第一次对话')).toBeVisible()
    })

    test('empty documents shows empty state', async ({ authedPage: page }) => {
        // Override documents mock to return empty
        await page.route('**/api/v1/documents*', (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({ json: [] })
            }
            return route.continue()
        })

        await page.goto('/workspace/ws-1')
        await expect(page.getByText('还没有文献')).toBeVisible()
    })

    test('clicking thread navigates to chat', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await page.getByText('Thread 1').click()
        await page.waitForURL('**/workspace/ws-1/chat?thread=th-1')
    })

    test('back button navigates to workspaces list', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await page.getByText('所有工作区').click()
        await page.waitForURL('**/workspaces')
    })

    test('enter workbench button navigates to chat', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await page.getByText('进入工作台').click()
        await page.waitForURL('**/workspace/ws-1/chat')
    })

    test('new thread button navigates to chat', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await page.getByText('新建对话').click()
        await page.waitForURL('**/workspace/ws-1/chat')
    })
})
