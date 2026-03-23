import { defineConfig, devices } from '@playwright/test'

const PLAYWRIGHT_PORT = 4173

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',

    use: {
        baseURL: `http://localhost:${PLAYWRIGHT_PORT}`,
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },

    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],

    webServer: {
        command: `npm run dev -- --port ${PLAYWRIGHT_PORT}`,
        url: `http://localhost:${PLAYWRIGHT_PORT}`,
        reuseExistingServer: false,
        timeout: 30_000,
    },
})
