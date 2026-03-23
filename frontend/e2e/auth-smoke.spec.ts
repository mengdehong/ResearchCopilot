import { test, expect } from '@playwright/test'

/**
 * Smoke tests require a real backend running (npm run dev + make dev).
 * These are isolated in the 'smoke' Playwright project and excluded
 * from the default 'chromium' project runs.
 */
test.describe('Auth Smoke Tests', () => {
    test.skip(
        !process.env.SMOKE_ENABLED,
        'Skipped: set SMOKE_ENABLED=1 and run with --project=smoke',
    )

    const testEmail = `smoke-${Date.now()}@example.com`
    const testPassword = 'SmokeTest123!'

    test('register → login full flow', async ({ page }) => {
        // Register
        await page.goto('/register')
        await page.locator('#displayName').fill('Smoke Tester')
        await page.locator('#email').fill(testEmail)
        await page.locator('#password').fill(testPassword)
        await page.getByRole('button', { name: /create research account/i }).click()

        // Should see verify email screen
        await expect(page.getByText(/verify your email/i)).toBeVisible()

        // Login with the registered credentials
        await page.goto('/login')
        await page.locator('#email').fill(testEmail)
        await page.locator('#password').fill(testPassword)
        await page.getByRole('button', { name: /sign in/i }).click()

        await page.waitForURL('**/workspaces')
    })

    test('wrong password is rejected', async ({ page }) => {
        await page.goto('/login')
        await page.locator('#email').fill(testEmail)
        await page.locator('#password').fill('WrongPassword999!')
        await page.getByRole('button', { name: /sign in/i }).click()

        // Should show error, not navigate
        await expect(page.getByText(/invalid|error|failed/i)).toBeVisible()
        await expect(page).toHaveURL(/.*login/)
    })
})
