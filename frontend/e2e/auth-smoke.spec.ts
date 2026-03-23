import { test, expect } from '@playwright/test'

function getRequiredEnv(name: string): string {
    const value = process.env[name]
    if (!value) {
        throw new Error(`Missing required smoke test env: ${name}`)
    }
    return value
}

async function loginWithRealBackend(
    email: string,
    password: string,
    page: import('@playwright/test').Page,
): Promise<void> {
    await page.goto('/login')
    await page.locator('#email').fill(email)
    await page.locator('#password').fill(password)
    await page.getByRole('button', { name: /sign in/i }).click()
    await page.waitForURL('**/workspaces')
}

test.describe('Auth Smoke Tests', () => {
    test.skip(!process.env.SMOKE_ENABLED, 'Skipped: set SMOKE_ENABLED=1 for smoke runs')

    const smokeEmail = getRequiredEnv('SMOKE_TEST_EMAIL')
    const smokePassword = getRequiredEnv('SMOKE_TEST_PASSWORD')
    const workspaceName = `Smoke Workspace ${Date.now()}`

    test('login survives reload and can create a workspace', async ({ page }) => {
        await loginWithRealBackend(smokeEmail, smokePassword, page)

        await expect(page.getByRole('heading', { name: 'Workspaces', exact: true })).toBeVisible()
        await page.reload()
        await expect(page.getByRole('heading', { name: 'Workspaces', exact: true })).toBeVisible()

        await page.getByRole('button', { name: 'New Workspace', exact: true }).first().click()
        await page.getByPlaceholder('Workspace name').fill(workspaceName)
        await page.getByRole('button', { name: /^create$/i }).click()

        await expect(page.getByText(workspaceName)).toBeVisible()
    })

    test('wrong password is rejected', async ({ page }) => {
        await page.goto('/login')
        await page.locator('#email').fill(smokeEmail)
        await page.locator('#password').fill('WrongPassword999!')
        await page.getByRole('button', { name: /sign in/i }).click()

        await expect(page.getByText('密码错误')).toBeVisible()
        await expect(page).toHaveURL(/.*login/)
    })
})
