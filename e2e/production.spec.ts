import { expect, test, type Page } from '@playwright/test';

// A real CC0 shelf photo with its ground-truth boxes drawn on it, and a screenshot that is
// definitely not a shelf. Both are committed, so the run needs no dataset download.
const SHELF_PHOTO = 'docs/reports/failure-gallery/005-overlay.png';
const NOT_A_SHELF = 'docs/reports/live-site.png';

// Reads the count out of the KPI card; the locale formatter may insert separators.
async function readCount(page: Page): Promise<number> {
  const text = (await page.getByTestId('kpi-count').textContent()) ?? '';
  return Number(text.replace(/[^0-9]/g, ''));
}

// The upload input is disabled until the model manifest has been fetched, and a file dropped in
// before that is ignored without an error. Waiting for it to enable is the app's own ready signal,
// and the blob preview then proves the change handler actually ran.
async function uploadPhoto(page: Page, file: string) {
  const input = page.locator('#photo-upload');
  await expect(input).toBeEnabled({ timeout: 90_000 });
  await input.setInputFiles(file);
  await page.locator('img[src^="blob:"]').waitFor({ state: 'attached', timeout: 30_000 });
}

test('loads with the trained detector available', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'ShelfSense' })).toBeVisible();
  await expect(page.locator('#photo-upload')).toBeEnabled();
  // The page must not be showing its "no model in this build" state.
  await expect(page.getByText('Detector not published in this build')).toHaveCount(0);
  await expect(page.getByTestId('kpi-count')).toHaveText('—');
});

// A photo that arrives before /models/manifest.json has resolved has nothing to run it on. The
// input is disabled until then, so a file can only get here from a drop, an extension or an
// automation; the page must say why nothing happened rather than dropping it silently.
test('explains a photo chosen before the detector has loaded', async ({ page }) => {
  let releaseManifest = () => {};
  const held = new Promise<void>((resolve) => {
    releaseManifest = resolve;
  });
  // Hold the manifest request so the page stays in its pre-load state for the whole check.
  await page.route('**/models/manifest.json', async (route) => {
    await held;
    await route.continue();
  });

  await page.goto('/');
  const input = page.locator('#photo-upload');
  await expect(input).toBeDisabled();

  await page.evaluate(() => {
    const field = document.getElementById('photo-upload') as HTMLInputElement;
    const data = new DataTransfer();
    data.items.add(new File([new Uint8Array([137, 80, 78, 71])], 'shelf.png', { type: 'image/png' }));
    field.files = data.files;
    field.dispatchEvent(new Event('change', { bubbles: true }));
  });

  // Scoped to the page's own alert: Next also renders an empty route announcer with role="alert".
  await expect(page.locator('p[role="alert"]')).toContainText('still loading');
  // Nothing was analysed, so the KPI cards keep their empty state.
  await expect(page.getByTestId('kpi-count')).toHaveText('—');

  // Releasing the manifest returns the page to its normal ready state.
  releaseManifest();
  await expect(input).toBeEnabled();
});

test('counts the products in a shelf photo and draws the boxes', async ({ page }) => {
  await page.goto('/');
  await uploadPhoto(page, SHELF_PHOTO);

  await expect(page.getByTestId('kpi-count')).not.toHaveText('—');
  const count = await readCount(page);
  // This photo has 251 ground-truth items; the model over-counts it, but it must find a shelf.
  expect(count).toBeGreaterThan(100);

  await expect(page.getByTestId('inference-info')).toContainText('products in');
  await expect(page.getByTestId('inference-info')).toContainText('on WASM');
  await expect(page.getByTestId('kpi-gaps')).not.toHaveText('—');

  const boxes = page.locator('svg[role="img"] rect');
  expect(await boxes.count()).toBeGreaterThan(50);
});

test('does not invent a shelf where there is none', async ({ page }) => {
  await page.goto('/');
  await uploadPhoto(page, NOT_A_SHELF);
  await expect(page.getByTestId('kpi-count')).not.toHaveText('—');
  const count = await readCount(page);
  expect(count).toBeLessThan(100);
});

test('saves a scan to history and exports it as CSV', async ({ page }) => {
  await page.goto('/');
  await uploadPhoto(page, SHELF_PHOTO);
  await expect(page.getByTestId('kpi-count')).not.toHaveText('—');
  const count = await readCount(page);

  await page.fill('#store-input', 'Store 7');
  await page.fill('#aisle-input', 'Aisle 3');
  await page.fill('#shelf-input', 'Shelf B');
  await page.getByRole('button', { name: 'Save scan to history' }).click();

  const row = page.locator('tbody tr').first();
  await expect(row).toContainText('Store 7');
  await expect(row).toContainText('Aisle 3');
  await expect(row).toContainText('Shelf B');
  await expect(row).toContainText(String(count));

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toBe('shelfsense-scans.csv');
});

test('switches language without losing the page', async ({ page }) => {
  await page.goto('/');
  const toggle = page.getByRole('button', { name: /Toggle language/ });
  const scanHeading = page.getByRole('heading', { name: 'Shelf Scan', exact: true });
  await expect(scanHeading).toBeVisible();

  await toggle.click();
  // The button now offers English back, and the English section heading is gone.
  await expect(toggle).toContainText('English');
  await expect(scanHeading).toHaveCount(0);
  await expect(page.locator('#photo-upload')).toBeEnabled();

  await toggle.click();
  await expect(scanHeading).toBeVisible();
});

test('only the owner can edit the low-stock threshold', async ({ page }) => {
  await page.goto('/');
  const threshold = page.locator('#threshold-input');
  const roleButton = page.getByRole('button', { name: /Switch user role/ });
  await expect(threshold).toBeEnabled();
  await expect(roleButton).toContainText('Store Owner');

  await roleButton.click();
  await expect(threshold).toBeDisabled();

  await roleButton.click();
  await expect(threshold).toBeEnabled();
});

test('chat refuses to invent numbers when nothing is stored', async ({ page }) => {
  await page.goto('/');
  const input = page.getByRole('textbox', { name: 'Ask About Stored Scans (Database Tool Grounded)' });
  await input.fill('Which shelf is lowest today?');
  await page.getByRole('button', { name: 'Ask' }).click();

  const log = page.locator('.chat-log');
  await expect(log).toContainText('Which shelf is lowest today?');
  // The tool layer answers from stored rows only, so with no rows it must refuse.
  await expect(log).toContainText('refusal_missing_data');
});
