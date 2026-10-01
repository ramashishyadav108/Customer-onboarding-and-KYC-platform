import { expect, test, type Page } from '@playwright/test';

// Pixel baselines in `__screenshots__/` are captured on the author's Windows machine. Linux CI
// renders text slightly differently, so there the screenshot is saved as a test artifact instead of
// compared; every functional assertion in the test still runs. Locally the comparison is strict.
export async function expectVisual(page: Page, name: string, options: { fullPage?: boolean } = {}): Promise<void> {
  if (process.env.CI) {
    await page.screenshot({ path: test.info().outputPath(name), fullPage: options.fullPage });
    return;
  }
  await expect(page).toHaveScreenshot(name, options);
}
