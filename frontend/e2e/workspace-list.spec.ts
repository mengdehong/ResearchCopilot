import { test, expect } from './fixtures'

test.describe('Workspace List Page', () => {
    test('renders workspace list with cards', async ({ authedPage: page }) => {
        await page.goto('/workspaces')
        await expect(page.getByRole('heading', { name: 'Workspaces' })).toBeVisible()
        await expect(page.getByText('Workspace 1')).toBeVisible()
        await expect(page.getByText('Computer Science')).toBeVisible()
    })

    test('empty list shows empty state', async ({ authedPage: page }) => {
        await page.route('**/api/v1/workspaces', (route) => {
            if (route.request().method() === 'GET') {
                return route.fulfill({ json: [] })
            }
            return route.continue()
        })

        await page.goto('/workspaces')
        await expect(page.getByText(/no workspaces yet/i)).toBeVisible()
    })

    test('new workspace button opens create dialog', async ({ authedPage: page }) => {
        await page.goto('/workspaces')
        await page.getByRole('button', { name: /new workspace/i }).click()
        await expect(page.getByRole('heading', { name: /create workspace/i })).toBeVisible()
        await expect(page.getByPlaceholder('Workspace name')).toBeVisible()
    })

    test('creating workspace closes dialog', async ({ authedPage: page }) => {
        await page.goto('/workspaces')
        await page.getByRole('button', { name: /new workspace/i }).click()
        await page.getByPlaceholder('Workspace name').fill('My Research')
        await page.getByRole('button', { name: /^create$/i }).click()

        // Dialog should close after successful creation
        await expect(page.getByRole('heading', { name: /create workspace/i })).not.toBeVisible()
    })

    test('clicking workspace card navigates to workspace', async ({ authedPage: page }) => {
        await page.goto('/workspaces')
        await page.getByText('Workspace 1').click()
        await page.waitForURL('**/workspace/ws-1')
    })

    test('delete workspace calls API', async ({ authedPage: page }) => {
        await page.route('**/api/v1/workspaces/ws-1', (route) => {
            if (route.request().method() === 'DELETE') {
                return route.fulfill({ json: { ok: true } })
            }
            return route.fulfill({
                json: {
                    id: 'ws-1',
                    name: 'Workspace 1',
                    discipline: 'computer_science',
                    owner_id: 'user-1',
                    is_deleted: false,
                    created_at: '2025-01-01',
                    updated_at: '2025-01-01',
                },
            })
        })

        await page.goto('/workspaces')
        // Hover to reveal the delete button
        const card = page.getByText('Workspace 1').locator('..')
        await card.hover()

        // Wait for the DELETE request to be sent
        const deletePromise = page.waitForRequest(
            (req) => req.url().includes('/workspaces/ws-1') && req.method() === 'DELETE',
        )
        await page.getByTitle(/delete workspace/i).click()
        await deletePromise
    })

    test('loading state shows skeleton cards', async ({ authedPage: page }) => {
        // Delay the workspaces API to simulate loading
        await page.route('**/api/v1/workspaces', async (route) => {
            if (route.request().method() === 'GET') {
                await new Promise((r) => setTimeout(r, 2000))
                return route.fulfill({
                    json: [
                        {
                            id: 'ws-1',
                            name: 'Workspace 1',
                            discipline: 'computer_science',
                            owner_id: 'user-1',
                            is_deleted: false,
                            created_at: '2025-01-01',
                            updated_at: '2025-01-01',
                        },
                    ],
                })
            }
            return route.continue()
        })

        await page.goto('/workspaces')
        // Loading state shows skeleton/pulse indicators
        const skeleton = page.locator('[class*="animate-pulse"]').first()
        await expect(skeleton).toBeVisible({ timeout: 2000 })
    })
})
