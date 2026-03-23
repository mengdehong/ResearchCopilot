import { test, expect } from './fixtures'

test.describe('Settings Page', () => {
    test('renders settings page with title', async ({ authedPage: page }) => {
        await page.goto('/settings')
        await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
    })

    test('displays account information', async ({ authedPage: page }) => {
        await page.goto('/settings')
        const main = page.locator('main')
        await expect(main).toContainText('Test User')
        await expect(main).toContainText('test@example.com')
    })

    test('dark theme toggle adds .dark class', async ({ authedPage: page }) => {
        await page.goto('/settings')
        await page.getByRole('button', { name: 'Dark' }).click()
        await expect(page.locator('html')).toHaveClass(/dark/)
    })

    test('language switch to Chinese changes text', async ({ authedPage: page }) => {
        await page.goto('/settings')

        // Find the language select trigger by its label context
        const languageSection = page.getByText('Language').locator('..')
        const selectTrigger = languageSection.getByRole('combobox')
        await selectTrigger.click()
        await page.getByRole('option', { name: '中文' }).click()

        // After switching to Chinese, the settings title should change
        await expect(page.getByRole('heading', { name: '设置', exact: true })).toBeVisible()
    })

    test('saving API key shows saved confirmation', async ({ authedPage: page }) => {
        await page.goto('/settings')
        await page.locator('#api-key').fill('my-secret-key')
        await page.getByRole('button', { name: /save/i }).click()

        await expect(page.getByText('✓ Saved')).toBeVisible()
    })

    test('quota usage is displayed', async ({ authedPage: page }) => {
        await page.goto('/settings')
        // Quota shows "1.0K / 10.0K" based on mock data (1000/10000)
        await expect(page.getByText('1.0K / 10.0K')).toBeVisible()
    })

    test('sign out navigates to login', async ({ authedPage: page }) => {
        await page.goto('/settings')
        await page.getByRole('button', { name: /sign out/i }).click()
        await page.waitForURL('**/login')
    })
})
