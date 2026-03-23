import { test, expect } from './fixtures'
import { setupAuthMocks } from './helpers/api-mocks'

test.describe('Forgot Password Page', () => {
    test('renders forgot password form', async ({ guestPage: page }) => {
        await page.goto('/forgot-password')
        await expect(page.getByRole('heading', { name: /reset your password/i })).toBeVisible()
        await expect(page.locator('#email')).toBeVisible()
        await expect(page.getByRole('button', { name: /send reset link/i })).toBeVisible()
    })

    test('successful send shows confirmation message', async ({ guestPage: page }) => {
        await setupAuthMocks(page)

        await page.goto('/forgot-password')
        await page.locator('#email').fill('test@example.com')
        await page.getByRole('button', { name: /send reset link/i }).click()

        await expect(page.getByText(/a reset link has been sent/i)).toBeVisible()
    })

    test('server error shows error message', async ({ guestPage: page }) => {
        await page.route('**/api/v1/auth/forgot-password', (route) =>
            route.fulfill({ status: 500, json: { detail: 'Internal server error' } }),
        )

        await page.goto('/forgot-password')
        await page.locator('#email').fill('test@example.com')
        await page.getByRole('button', { name: /send reset link/i }).click()

        await expect(page.getByText('Internal server error')).toBeVisible()
    })
})

test.describe('Reset Password Page', () => {
    test('with token shows password form', async ({ guestPage: page }) => {
        await page.goto('/reset-password?token=abc123')
        await expect(page.getByRole('heading', { name: /set new password/i })).toBeVisible()
        await expect(page.locator('#password')).toBeVisible()
        await expect(page.getByRole('button', { name: /reset password/i })).toBeVisible()
    })

    test('without token shows error', async ({ guestPage: page }) => {
        await page.goto('/reset-password')
        await expect(page.getByText(/failed to reset password/i)).toBeVisible()
    })

    test('successful reset shows success message', async ({ guestPage: page }) => {
        await setupAuthMocks(page)

        await page.goto('/reset-password?token=abc123')
        await page.locator('#password').fill('newpassword123')
        await page.getByRole('button', { name: /reset password/i }).click()

        await expect(page.getByText(/password reset successfully/i)).toBeVisible()
    })
})

test.describe('Verify Email Page', () => {
    test('with valid token shows success', async ({ guestPage: page }) => {
        await setupAuthMocks(page)

        await page.goto('/verify-email?token=valid-token')
        await expect(page.getByText(/email verified successfully/i)).toBeVisible()
    })

    test('with invalid token shows error', async ({ guestPage: page }) => {
        await page.route('**/api/v1/auth/verify-email', (route) =>
            route.fulfill({ status: 400, json: { detail: 'Invalid token' } }),
        )

        await page.goto('/verify-email?token=bad-token')
        await expect(page.getByText(/verification failed/i)).toBeVisible()
    })

    test('without token shows error state', async ({ guestPage: page }) => {
        await page.goto('/verify-email')
        await expect(page.getByText(/verification failed/i)).toBeVisible()
    })
})
