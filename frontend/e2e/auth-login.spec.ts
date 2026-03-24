import { test, expect } from './fixtures'

test.describe('Login Page', () => {
    test('renders login form correctly', async ({ guestPage: page }) => {
        await page.goto('/login')
        await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
        await expect(page.locator('#email')).toBeVisible()
        await expect(page.locator('#password')).toBeVisible()
        await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible()
    })

    test('successful login redirects to /workspaces', async ({ guestPage: page }) => {
        // Mock login endpoint to return a token
        await page.route('**/api/v1/auth/login', (route) =>
            route.fulfill({
                json: { access_token: 'new-token', user: { id: 'user-1', email: 'test@example.com', display_name: 'Test User' } },
            }),
        )
        // After login, the app will call these endpoints — mock them for the authed state
        await page.route('**/api/v1/auth/me', (route) =>
            route.fulfill({ json: { id: 'user-1', email: 'test@example.com', display_name: 'Test User' } }),
        )
        await page.route('**/api/v1/workspaces', (route) =>
            route.fulfill({ json: [] }),
        )
        await page.route('**/api/v1/quota/status', (route) =>
            route.fulfill({ json: { total_used: 0, total_limit: 10000, remaining: 10000, usage_percent: 0, workspaces: [] } }),
        )

        await page.goto('/login')
        await page.locator('#email').fill('test@example.com')
        await page.locator('#password').fill('password123')
        await page.getByRole('button', { name: /sign in/i }).click()

        await page.waitForURL('**/workspaces')
    })

    test('invalid credentials shows error message', async ({ guestPage: page }) => {
        await page.route('**/api/v1/auth/login', (route) =>
            route.fulfill({ status: 401, json: { detail: 'Invalid email or password' } }),
        )

        await page.goto('/login')
        await page.locator('#email').fill('wrong@example.com')
        await page.locator('#password').fill('wrongpass')
        await page.getByRole('button', { name: /sign in/i }).click()

        await expect(page.getByText('Invalid email or password')).toBeVisible()
    })

    test('empty form submission is prevented by browser validation', async ({ guestPage: page }) => {
        await page.goto('/login')
        const emailInput = page.locator('#email')
        // HTML5 required attribute prevents submission
        await expect(emailInput).toHaveAttribute('required', '')
    })

    test('forgot password link navigates to /forgot-password', async ({ guestPage: page }) => {
        await page.goto('/login')
        await page.getByRole('link', { name: /forgot password/i }).click()
        await page.waitForURL('**/forgot-password')
    })

    test('sign up link navigates to /register', async ({ guestPage: page }) => {
        await page.goto('/login')
        await page.getByRole('link', { name: /sign up/i }).click()
        await page.waitForURL('**/register')
    })

    test('OAuth buttons are visible', async ({ guestPage: page }) => {
        await page.goto('/login')
        // OAuth buttons rendered by OAuthButtons component
        await expect(page.getByText(/continue with/i).first()).toBeVisible()
    })
})
