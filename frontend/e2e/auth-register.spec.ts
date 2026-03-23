import { test, expect } from './fixtures'
import { setupAuthMocks } from './helpers/api-mocks'

test.describe('Register Page', () => {
    test('renders registration form correctly', async ({ guestPage: page }) => {
        await page.goto('/register')
        await expect(page.getByRole('heading', { name: /start your research journey/i })).toBeVisible()
        await expect(page.locator('#displayName')).toBeVisible()
        await expect(page.locator('#email')).toBeVisible()
        await expect(page.locator('#password')).toBeVisible()
    })

    test('successful registration shows verify email screen', async ({ guestPage: page }) => {
        await setupAuthMocks(page)

        await page.goto('/register')
        await page.locator('#displayName').fill('New User')
        await page.locator('#email').fill('new@example.com')
        await page.locator('#password').fill('password123')
        await page.getByRole('button', { name: /create research account/i }).click()

        await expect(page.getByRole('heading', { name: /verify your email/i })).toBeVisible()
    })

    test('duplicate email shows error', async ({ guestPage: page }) => {
        await page.route('**/api/v1/auth/register', (route) =>
            route.fulfill({ status: 409, json: { detail: 'Email already registered' } }),
        )

        await page.goto('/register')
        await page.locator('#displayName').fill('Test')
        await page.locator('#email').fill('existing@example.com')
        await page.locator('#password').fill('password123')
        await page.getByRole('button', { name: /create research account/i }).click()

        await expect(page.getByText('Email already registered')).toBeVisible()
    })

    test('sign in link navigates to /login', async ({ guestPage: page }) => {
        await page.goto('/register')
        await page.getByRole('link', { name: /sign in/i }).click()
        await page.waitForURL('**/login')
    })

    test('back to login link works after successful registration', async ({ guestPage: page }) => {
        await setupAuthMocks(page)

        await page.goto('/register')
        await page.locator('#displayName').fill('New User')
        await page.locator('#email').fill('new@example.com')
        await page.locator('#password').fill('password123')
        await page.getByRole('button', { name: /create research account/i }).click()

        await expect(page.getByRole('heading', { name: /verify your email/i })).toBeVisible()
        await page.getByRole('link', { name: /back to login/i }).click()
        await page.waitForURL('**/login')
    })
})
