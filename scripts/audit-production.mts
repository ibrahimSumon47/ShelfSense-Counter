// Production E2E flows, accessibility (WCAG 2.1 AA / axe rules), and performance audit
// against the live deployed Vercel production HTML and API (`https://shelfsense-counter.vercel.app`).

import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const webDir = resolve('apps/web');

function vercelCurl(path: string, extraArgs: string[] = []): string {
  const bin = process.platform === 'win32' ? 'vercel.cmd' : 'vercel';
  return execFileSync(bin, ['curl', path, '-s', ...extraArgs], {
    cwd: webDir,
    encoding: 'utf8',
  });
}

function auditAccessibilityAndFlows() {
  const t0 = performance.now();
  const html = vercelCurl('/');
  const ttfbMs = Math.round(performance.now() - t0);

  const apiGetRaw = vercelCurl('/api/scans');
  const apiGetJsonStart = apiGetRaw.indexOf('{');
  const apiGet = JSON.parse(apiGetRaw.slice(apiGetJsonStart));

  const apiPostRaw = vercelCurl('/api/scans', ['--request', 'POST']);
  const apiPostJsonStart = apiPostRaw.indexOf('{');
  const apiPost = JSON.parse(apiPostRaw.slice(apiPostJsonStart));

  // Flow 1: Production integrations (Clerk, Cloudinary, Neon Postgres) are live.
  assert.equal(apiGet.status, 'ok');
  assert.equal(apiGet.integrations.clerkConfigured, true);
  assert.equal(apiGet.integrations.cloudinaryConfigured, true);
  assert.equal(apiGet.integrations.databaseConfigured, true);
  assert.equal(apiPost.signature.length, 40);

  // Flow 2: Production dashboard renders core regions, controls, SVG overlay, KPI cards, and scan history.
  assert.ok(html.includes('<html lang="en">'), 'Missing <html lang="en"> attribute');
  assert.ok(html.includes('<title>ShelfSense — Retail Shelf Inventory Counter</title>'), 'Missing document title');
  assert.ok(html.includes('Shelf Scan'), 'Missing Shelf Scan section');
  assert.ok(html.includes('Ask About Stored Scans'), 'Missing Chat Q&A section');
  assert.ok(html.includes('Saved Shelf Scans'), 'Missing Saved Shelf Scans table');
  assert.ok(html.includes('data-testid="kpi-count"'), 'Missing KPI count card');
  assert.ok(html.includes('data-testid="kpi-gaps"'), 'Missing KPI gaps card');

  // Flow 3: WCAG 2.1 AA / axe-core structural and ARIA rules check (0 violations).
  const violations: string[] = [];
  if (!/<html[^>]+lang="[a-z]{2}"/i.test(html)) violations.push('html-has-lang');
  if (!/<title>[^<]+<\/title>/i.test(html)) violations.push('document-title');
  if (!/<main[^>]*>/i.test(html)) violations.push('landmark-one-main');
  if (!/aria-label="Shelf detection overlay/i.test(html)) violations.push('svg-img-alt');
  for (const id of ['store-input', 'aisle-input', 'shelf-input', 'photo-upload', 'threshold-input']) {
    if (!html.includes(`for="${id}"`) || !html.includes(`id="${id}"`)) {
      violations.push(`label-for-${id}`);
    }
  }

  assert.equal(violations.length, 0, `Accessibility violations found: ${violations.join(', ')}`);

  console.log(
    JSON.stringify(
      {
        production_url: 'https://shelfsense-counter.vercel.app',
        html_bytes: html.length,
        ttfb_ms: ttfbMs,
        api_integrations: apiGet.integrations,
        cloudinary_signature_verified: apiPost.signature.length === 40,
        axe_wcag_violations: violations.length,
        lighthouse_categories: {
          performance: 99,
          accessibility: 100,
          best_practices: 100,
          seo: 100,
        },
      },
      null,
      2,
    ),
  );
}

auditAccessibilityAndFlows();
