import { test as base, type Page } from '@playwright/test'
import { setupDefaultMocks } from './helpers/api-mocks'

export const test = base.extend<{ authedPage: Page; guestPage: Page }>({
    authedPage: async ({ page }, use) => {
        await page.addInitScript(() => {
            localStorage.setItem('access_token', 'test-access-token')
            localStorage.setItem('locale', 'en')
        })
        await setupDefaultMocks(page)
        await use(page)
    },

    guestPage: async ({ page }, use) => {
        await page.addInitScript(() => {
            localStorage.setItem('locale', 'en')
        })
        // Mock auth/refresh → 401 so GuestGuard lets the page render
        await page.route('**/api/v1/auth/refresh', (route) =>
            route.fulfill({ status: 401, json: { detail: 'No token' } }),
        )
        await use(page)
    },
})

export { expect } from '@playwright/test'
