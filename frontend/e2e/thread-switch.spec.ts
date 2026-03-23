import { test, expect } from './fixtures'

/**
 * Helper: expand sidebar by clicking the toggle button.
 * Uses data-testid="sidebar-toggle" for reliable targeting.
 */
async function expandSidebar(page: import('@playwright/test').Page): Promise<void> {
    await page.locator('[data-testid="sidebar-toggle"]').click()
    await page.waitForTimeout(400)
}

test.describe('Thread Switch', () => {
    test('sidebar shows thread list when expanded', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await expandSidebar(page)
        await expect(page.getByText('Thread 1')).toBeVisible()
    })

    test('clicking thread updates URL', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await expandSidebar(page)
        await page.getByText('Thread 1').click()
        await page.waitForURL('**/workspace/ws-1?thread=th-1')
    })

    test('new thread button navigates without thread param', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        await expandSidebar(page)
        await page.getByText('New Thread').click()
        await page.waitForURL('**/workspace/ws-1')
        expect(page.url()).not.toContain('thread=')
    })

    test('switching thread loads history messages', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1?thread=th-1')
        await expect(page.getByText('Previous question')).toBeVisible({ timeout: 5000 })
        await expect(page.getByText('Previous answer')).toBeVisible()
    })

    test('delete thread shows confirm dialog', async ({ authedPage: page }) => {
        await page.goto('/workspace/ws-1')
        await expandSidebar(page)

        const threadGroup = page.locator('div.group').filter({ hasText: 'Thread 1' })
        await threadGroup.hover()

        await threadGroup.locator('button[title="Delete Thread"]').click()
        await expect(page.getByText('This action cannot be undone')).toBeVisible()
    })

    test('empty thread list shows empty state', async ({ authedPage: page }) => {
        await page.route(/\/api\/v1\/agent\/threads(\?|$)/, (route) =>
            route.fulfill({ json: [] }),
        )
        await page.goto('/workspace/ws-1')
        await expandSidebar(page)
        await expect(page.getByText('No threads yet')).toBeVisible()
    })
})
