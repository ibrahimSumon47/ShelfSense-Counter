import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync, writeFileSync } from 'node:fs';

// Every state a visitor can reach without a photo: dark and light theme, English and Bangla.
// The upload result state is covered by the flow suite; scanning it again here would cost
// another 33 MB model download for no new accessibility surface.
const STATES = [
  { name: 'dark-en', theme: 'dark', lang: 'en' },
  { name: 'light-en', theme: 'light', lang: 'en' },
  { name: 'dark-bn', theme: 'dark', lang: 'bn' },
  { name: 'light-bn', theme: 'light', lang: 'bn' },
] as const;

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'];

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

for (const state of STATES) {
  test(`axe finds no violations (${state.name})`, async ({ page }) => {
    await page.goto('/');
    await page.getByRole('heading', { level: 1, name: 'ShelfSense' }).waitFor();
    await applyState(page, state.theme, state.lang);

    const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
    record({
      state: state.name,
      url: page.url(),
      engine: `axe-core ${results.testEngine.version}`,
      passes: results.passes.length,
      incomplete: results.incomplete.length,
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
  });
}
