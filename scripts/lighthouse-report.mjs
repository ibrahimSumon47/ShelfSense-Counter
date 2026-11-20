// Runs Lighthouse against the deployed site twice (mobile and desktop throttling) and writes
// the raw reports plus a small summary into docs/reports/, so the numbers in the README can be
// traced back to a file. CLI: node scripts/lighthouse-report.mjs [url]
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from '@playwright/test';
import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';

const url = process.argv[2] ?? process.env.SHELFSENSE_URL ?? 'https://shelfsense-counter.vercel.app';
const categories = ['performance', 'accessibility', 'best-practices', 'seo'];

// Reuses the Chromium that Playwright already downloaded, so no extra browser install is needed.
async function launchChrome() {
  const installed = chromium.executablePath();
  return launch({
    chromePath: installed,
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'],
  });
}

function preset(formFactor) {
  if (formFactor === 'desktop') {
    return {
      formFactor: 'desktop',
      screenEmulation: { mobile: false, width: 1350, height: 940, deviceScaleFactor: 1, disabled: false },
      throttling: { rttMs: 40, throughputKbps: 10240, cpuSlowdownMultiplier: 1, requestLatencyMs: 0, downloadThroughputKbps: 0, uploadThroughputKbps: 0 },
    };
  }
  return {
    formFactor: 'mobile',
    screenEmulation: { mobile: true, width: 412, height: 823, deviceScaleFactor: 1.75, disabled: false },
    throttling: { rttMs: 150, throughputKbps: 1638.4, cpuSlowdownMultiplier: 4, requestLatencyMs: 562.5, downloadThroughputKbps: 1474.56, uploadThroughputKbps: 675 },
  };
}

const chrome = await launchChrome();
const summary = { url, ran_at: new Date().toISOString(), lighthouse: lighthouse.version, runs: {} };

try {
  for (const formFactor of ['mobile', 'desktop']) {
    const options = {
      port: chrome.port,
      output: 'json',
      logLevel: 'error',
      onlyCategories: categories,
      ...preset(formFactor),
    };
    const result = await lighthouse(url, options);
    if (!result) throw new Error(`lighthouse returned nothing for ${formFactor}`);
    // A blocked or unreachable page still returns an LHR whose four scores are 0; that is a failed
    // load, not a measurement, and writing it would overwrite good numbers in docs/reports.
    if (result.lhr.runtimeError) {
      const err = result.lhr.runtimeError;
      throw new Error(`${formFactor}: ${err.code} for ${url} - ${err.message}`);
    }

    const scores = {};
    for (const key of categories) scores[key] = Math.round(result.lhr.categories[key].score * 100);
    const audits = result.lhr.audits;
    summary.runs[formFactor] = {
      scores,
      first_contentful_paint_ms: audits['first-contentful-paint']?.numericValue ?? null,
      largest_contentful_paint_ms: audits['largest-contentful-paint']?.numericValue ?? null,
      total_blocking_time_ms: audits['total-blocking-time']?.numericValue ?? null,
      cumulative_layout_shift: audits['cumulative-layout-shift']?.numericValue ?? null,
    };

    const out = resolve(`docs/reports/lighthouse-${formFactor}.json`);
    writeFileSync(out, `${JSON.stringify(result.lhr, null, 2)}\n`);
    console.log(`${formFactor}: ${JSON.stringify(scores)} -> ${out}`);
  }
} finally {
  await chrome.kill();
}

writeFileSync(resolve('docs/reports/lighthouse-summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log(JSON.stringify(summary.runs));
