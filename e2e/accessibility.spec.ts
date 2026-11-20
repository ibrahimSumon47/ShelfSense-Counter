import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync } from 'node:fs';

// Every state a visitor reaches on this page: with no photo yet, and with an analysed one, each in
// both themes and both languages. The analysed state is scanned separately because it needs the
// 32.8 MB model and a real detection: the box overlay, the filled KPI cards, the history table and
// its stock badges do not exist on the empty page.
const STATES = [
  { name: 'dark-en', theme: 'dark', lang: 'en' },
  { name: 'light-en', theme: 'light', lang: 'en' },
  { name: 'dark-bn', theme: 'dark', lang: 'bn' },
  { name: 'light-bn', theme: 'light', lang: 'bn' },
] as const;

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'];

// A committed CC0 shelf photo with its ground-truth boxes drawn on it; hundreds of real items.
const SHELF_PHOTO = 'docs/reports/failure-gallery/005-overlay.png';

// Puts the page into the requested theme and language using the same toggles a visitor uses.
async function applyState(page: Page, theme: string, lang: string) {
  const themeButton = page.getByRole('button', { name: /Toggle color theme/ });
  const langButton = page.getByRole('button', { name: /Toggle language/ });
  const current = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
  if ((current ?? 'dark') !== theme) await themeButton.click();
  if (lang === 'bn') await langButton.click();
}

const REPORT = 'docs/reports/axe-production.json';

// Playwright restarts the worker after a failing test, so the module state does not survive the
// whole run. Merging into the file keeps one honest record per state across those restarts.
function record(entry: Record<string, unknown>) {
  let all: Array<Record<string, unknown>> = [];
  try {
    all = JSON.parse(readFileSync(REPORT, 'utf8'));
  } catch {
    all = [];
  }
  const kept = all.filter((item) => item.state !== entry.state);
  kept.push(entry);
  kept.sort((a, b) => String(a.state).localeCompare(String(b.state)));
  writeFileSync(REPORT, `${JSON.stringify(kept, null, 2)}\n`);
}

// Scans whatever is on the page now, records the result and fails with the rule list when the
// scan found anything. `extra` carries the context the rules ran against (count, boxes, rows).
async function scan(page: Page, state: string, extra: Record<string, unknown> = {}) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  record({
    state,
    url: page.url(),
    engine: `axe-core ${results.testEngine.version}`,
    passes: results.passes.length,
    incomplete: results.incomplete.length,
    ...extra,
    violations: results.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.map((n) => n.target.join(' ')),
    })),
  });

  expect(
    results.violations,
    results.violations
      .map((v) => `${v.id} (${v.impact}): ${v.help} -> ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)
      .join('\n'),
  ).toEqual([]);
}

for (const state of STATES) {
  test(`axe finds no violations (${state.name})`, async ({ page }) => {
    await page.goto('/');
    await page.getByRole('heading', { level: 1, name: 'ShelfSense' }).waitFor();
    await applyState(page, state.theme, state.lang);

    await scan(page, state.name);
  });
}

// The result state, on one page: the photo with its boxes, both KPI cards filled, and two saved
// rows so the history table carries a healthy badge and a low-stock badge. The detector is
// downloaded once and all four theme/language states are scanned on that same result.
test('axe finds no violations after a photo is analysed (all themes and languages)', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('heading', { level: 1, name: 'ShelfSense' }).waitFor();

  // The upload input is enabled only once /models/manifest.json resolves; that is the ready signal.
  const input = page.locator('#photo-upload');
  await expect(input).toBeEnabled({ timeout: 90_000 });
  await input.setInputFiles(SHELF_PHOTO);
  await expect(page.getByTestId('kpi-count')).not.toHaveText('—', { timeout: 150_000 });

  const boxes = page.locator('svg[role="img"] rect');
  expect(await boxes.count()).toBeGreaterThan(50);
  const count = Number(((await page.getByTestId('kpi-count').textContent()) ?? '').replace(/[^0-9]/g, ''));
  // Raising the threshold above this count is what renders the low-stock badge below.
  expect(count).toBeGreaterThan(100);
  expect(count).toBeLessThan(500);

  // Default threshold 15: this shelf clears it, so the first row is healthy stock.
  await page.getByRole('button', { name: 'Save scan to history' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await expect(page.locator('tbody .badge-ok')).toHaveCount(1);

  // Threshold 500: the same count is now below the limit, so the second row is a low-stock alert.
  await page.locator('#threshold-input').fill('500');
  await page.getByRole('button', { name: 'Save scan to history' }).click();
  await expect(page.locator('tbody tr')).toHaveCount(2);
  await expect(page.locator('tbody .badge-warn')).toHaveCount(1);
  await expect(page.locator('tbody .badge-ok')).toHaveCount(1);

  const boxCount = await boxes.count();
  for (const state of STATES) {
    await applyState(page, state.theme, state.lang);
    await expect(page.getByTestId('kpi-count')).not.toHaveText('—');

    await scan(page, `scan-${state.name}`, { count, boxes: boxCount, rows: 2 });
  }
});
