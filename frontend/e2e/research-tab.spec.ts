import { test, expect } from './fixtures'
import { mockSSEStream, contentBlock, nodeStart, nodeEnd, assistantMessage, runEnd } from './helpers/sse-mock'

/**
 * Research Tab — 验证 content_block 事件后 ResearchTab 展示结构化产物。
 */

const WORKBENCH_URL = '/workspace/ws-1/chat'

test.describe('Research Tab', () => {
    test('content_block events populate research tab', async ({ authedPage: page }) => {
        const events = [
            nodeStart('extraction'),
            nodeEnd('extraction'),
            contentBlock('## Reading Notes\n- Key finding: model accuracy', 'extraction'),
            assistantMessage('Done'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // Send a message to trigger SSE stream
        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Analyze papers')
        await page.locator('button[aria-label="Send message"]').click()

        // Wait for stream to complete
        await expect(page.getByText('Done')).toBeVisible({ timeout: 5000 })

        // Switch to Research tab
        const researchTab = page.getByText('Research')
        await researchTab.click()

        // content_block should be rendered
        await expect(page.getByText('Reading Notes')).toBeVisible({ timeout: 5000 })
        await expect(page.getByText('Key finding: model accuracy')).toBeVisible()
    })

    test('multiple content_blocks group by workflow', async ({ authedPage: page }) => {
        const events = [
            nodeStart('extraction'),
            nodeEnd('extraction'),
            contentBlock('## Extraction Result\n- Note A', 'extraction'),
            nodeStart('ideation'),
            nodeEnd('ideation'),
            contentBlock('## Research Gaps\n- Gap 1', 'ideation'),
            assistantMessage('All done'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Run analysis')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('All done')).toBeVisible({ timeout: 5000 })

        // Switch to Research tab
        await page.getByText('Research').click()

        // Both workflow cards should be visible
        await expect(page.getByText('深度精读')).toBeVisible({ timeout: 3000 }) // extraction label
        await expect(page.getByText('研究构想')).toBeVisible() // ideation label
    })

    test('empty research tab shows placeholder', async ({ authedPage: page }) => {
        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        // Switch to Research tab (no content_block events received)
        const researchTab = page.getByText('Research')
        await researchTab.click()

        // Empty state message
        await expect(page.getByText('各工作流的结构化产物将在这里展示')).toBeVisible({ timeout: 3000 })
    })

    test('workflow card can be collapsed and expanded', async ({ authedPage: page }) => {
        const events = [
            nodeStart('extraction'),
            nodeEnd('extraction'),
            contentBlock('## Detailed Notes\nSome detailed analysis content here.', 'extraction'),
            assistantMessage('Done'),
            runEnd(),
        ]
        await mockSSEStream(page, events)

        await page.goto(`${WORKBENCH_URL}?thread=th-1`)

        const textarea = page.locator('textarea')
        await textarea.waitFor({ state: 'visible' })
        await textarea.fill('Test')
        await page.locator('button[aria-label="Send message"]').click()

        await expect(page.getByText('Done')).toBeVisible({ timeout: 5000 })
        await page.getByText('Research').click()

        // Content should be visible initially
        await expect(page.getByText('Detailed Notes')).toBeVisible({ timeout: 3000 })

        // Click workflow header to collapse
        await page.getByText('深度精读').click()

        // Content should be hidden after collapse
        await expect(page.getByText('Detailed Notes')).not.toBeVisible()

        // Click again to expand
        await page.getByText('深度精读').click()
        await expect(page.getByText('Detailed Notes')).toBeVisible()
    })
})
