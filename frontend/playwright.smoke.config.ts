import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
    testDir: './e2e',
    testMatch: '**/*-smoke.spec.ts',
    fullyParallel: false,
    forbidOnly: !!process.env.CI,
    retries: 0,
    reporter: 'html',
    timeout: 60_000,
    use: {
        baseURL: 'http://127.0.0.1:4173',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },
    projects: [
        {
            name: 'smoke',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    webServer: [
        {
            command: 'uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000',
            url: 'http://127.0.0.1:8000/api/health',
            cwd: '..',
            timeout: 120_000,
            reuseExistingServer: true,
            name: 'backend',
        },
        {
            command: 'npm run dev -- --host 127.0.0.1 --port 4173',
            url: 'http://127.0.0.1:4173',
            cwd: '.',
            timeout: 120_000,
            reuseExistingServer: true,
            name: 'frontend',
        },
    ],
})
