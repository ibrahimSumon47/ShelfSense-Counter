import { test } from 'node:test';
import assert from 'node:assert/strict';

import { clusterShelfRows, detectShelfGaps, type BoundingBox } from './gaps.ts';
import { applyNms, buildDetectionResult, computeResizedDimensions, decodeYoloxOutput } from './detector.ts';
import { escapeCsvCell, scansToCsv, type ScanRecord } from './csv.ts';
import {
  SlidingWindowRateLimiter,
  canModifyThreshold,
  detectImageMimeFromBytes,
  filterByUser,
  validateImageUpload,
} from './security.ts';
import { resolveClerkSessionUser, signCloudinaryUpload } from './cloud.ts';
import {
  answerShelfQuestion,
  extractNumbersFromText,
  toolComparePeriods,
  toolLowestShelves,
  toolStoreSummary,
  verifyReplyNumbersGrounded,
} from './chat-tools.ts';

const FIXTURE_SCANS: ScanRecord[] = [
  {
    id: 'scan-101',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 1 - Beverages',
    shelfName: 'Shelf B2 (Soft Drinks)',
    scannedAt: '2026-11-15T10:00:00Z',
    itemCount: 8,
    gapCount: 3,
    estimatedMissing: 9,
    lowStockThreshold: 15,
    lowStock: true,
  },
  {
    id: 'scan-102',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 2 - Snacks',
    shelfName: 'Shelf A1 (Biscuits)',
    scannedAt: '2026-11-16T09:30:00Z',
    itemCount: 24,
    gapCount: 1,
    estimatedMissing: 2,
    lowStockThreshold: 18,
    lowStock: false,
  },
  {
    id: 'scan-103',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 3 -Staples',
    shelfName: 'Shelf C1 (Lentils & Rice)',
    scannedAt: '2026-11-16T11:15:00Z',
    itemCount: 12,
    gapCount: 2,
    estimatedMissing: 5,
    lowStockThreshold: 15,
    lowStock: true,
  },
  {
    id: 'scan-090',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 1 - Beverages',
    shelfName: 'Shelf B2 (Soft Drinks)',
    scannedAt: '2026-11-05T10:00:00Z',
    itemCount: 22,
    gapCount: 0,
    estimatedMissing: 0,
    lowStockThreshold: 15,
    lowStock: false,
  },
  {
    id: 'scan-091',
    userId: 'user-owner-1',
    storeName: 'Dhaka Gulshan Superstore',
    aisleName: 'Aisle 2 - Snacks',
    shelfName: 'Shelf A1 (Biscuits)',
    scannedAt: '2026-11-06T14:00:00Z',
    itemCount: 18,
    gapCount: 1,
    estimatedMissing: 3,
    lowStockThreshold: 18,
    lowStock: false,
  },
  // Another tenant's scan that must never leak into user-owner-1's results.
  {
    id: 'scan-other-999',
    userId: 'user-other-tenant',
    storeName: 'Other Tenant Store',
    aisleName: 'Aisle 9',
    shelfName: 'Shelf Z9',
    scannedAt: '2026-11-16T12:00:00Z',
    itemCount: 1,
    gapCount: 8,
    estimatedMissing: 20,
    lowStockThreshold: 30,
    lowStock: true,
  },
];

test('S4-06: clusterShelfRows and detectShelfGaps find horizontal voids accurately', () => {
  const boxes: BoundingBox[] = [
    { x1: 10, y1: 20, x2: 50, y2: 80, score: 0.92 },
    { x1: 58, y1: 22, x2: 98, y2: 82, score: 0.90 },
    // 122px gap between x=98 and x=220 (median width 40px -> ~3 missing items)
    { x1: 220, y1: 19, x2: 260, y2: 79, score: 0.88 },
    // Second shelf row
    { x1: 15, y1: 140, x2: 55, y2: 200, score: 0.94 },
    { x1: 62, y1: 141, x2: 102, y2: 201, score: 0.91 },
  ];
  const rows = clusterShelfRows(boxes);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].length, 3);
  assert.equal(rows[1].length, 2);

  const gaps = detectShelfGaps(boxes, 1.35);
  assert.equal(gaps.length, 1);
  assert.equal(gaps[0].rowIndex, 0);
  assert.equal(gaps[0].x1, 98);
  assert.equal(gaps[0].x2, 220);
  assert.equal(gaps[0].estimatedMissingItems, 3);
});

test('S4-04 & S4-05: client resize dimensions, YOLOX decode, NMS, and DetectionResult', () => {
  const resized = computeResizedDimensions(4000, 3000, 1280);
  assert.equal(resized.width, 1280);
  assert.equal(resized.height, 960);

  const raw = new Float32Array([
    320, 320, 80, 80, 0.95, 1.0,
    322, 322, 80, 80, 0.55, 1.0, // overlapping duplicate suppressed by NMS
  ]);
  const boxes = decodeYoloxOutput(raw, 2, 6, 800, 400, 0.8, 0, 160);
  assert.equal(boxes.length, 1);
  assert.equal(boxes[0].x1, 350);
  assert.equal(boxes[0].y1, 150);

  const det = buildDetectionResult(boxes, 800, 400, 5, 18, 'wasm');
  assert.equal(det.count, 1);
  assert.equal(det.lowStock, true);
  assert.equal(applyNms(boxes).length, 1);
});

test('S4-10: CSV export sanitizes spreadsheet formulas and formats all rows', () => {
  assert.equal(escapeCsvCell('=CMD()'), "'=CMD()");
  assert.equal(escapeCsvCell('Shelf, "Top"'), '"Shelf, ""Top"""');
  const csv = scansToCsv(FIXTURE_SCANS.slice(0, 2));
  const lines = csv.split('\n');
  assert.equal(lines.length, 3);
  assert.ok(lines[0].startsWith('scan_id,scanned_at,store'));
  assert.ok(lines[1].includes('Dhaka Gulshan Superstore'));
});

test('S7-03 & S7-04: upload magic-byte validation, rate limiter, roles, and per-user data isolation', () => {
  const validPng = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0, 1, 2]);
  const fakePng = new Uint8Array([0x00, 0x11, 0x22, 0x33, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

  assert.equal(detectImageMimeFromBytes(validPng), 'image/png');
  assert.equal(validateImageUpload(validPng, 'image/png').valid, true);
  assert.equal(validateImageUpload(fakePng, 'image/png').valid, false);
  assert.equal(validateImageUpload(validPng, 'application/pdf').valid, false);

  assert.equal(canModifyThreshold({ userId: 'u1', role: 'owner', displayName: 'Owner' }), true);
  assert.equal(canModifyThreshold({ userId: 'u2', role: 'staff', displayName: 'Staff' }), false);

  // Per-user data isolation: user-owner-1 must never see user-other-tenant's scan.
  const isolated = filterByUser(FIXTURE_SCANS, 'user-owner-1');
  assert.equal(isolated.length, 5);
  assert.ok(isolated.every((s) => s.userId === 'user-owner-1'));
  assert.deepEqual(filterByUser(FIXTURE_SCANS, 'unknown-user'), []);

  const limiter = new SlidingWindowRateLimiter(2, 10_000);
  assert.equal(limiter.check('ip-1', 1000).allowed, true);
  assert.equal(limiter.check('ip-1', 2000).allowed, true);
  const third = limiter.check('ip-1', 3000);
  assert.equal(third.allowed, false);
  assert.equal(third.retryAfterMs, 8000);
  assert.equal(limiter.check('ip-1', 12_000).allowed, true);

  // S4-02 & S4-07: Clerk session role resolver and Cloudinary SHA-1 upload signature.
  const sig = signCloudinaryUpload({ timestamp: 1700000000, folder: 'shelfsense/thumbnails' }, 'test_secret');
  assert.equal(sig.length, 40);
  const staffHeaders = new Headers({ 'x-clerk-user-id': 'user_staff_9', 'x-shelfsense-role': 'staff' });
  const resolvedStaff = resolveClerkSessionUser(staffHeaders);
  assert.equal(resolvedStaff.userId, 'user_staff_9');
  assert.equal(resolvedStaff.role, 'staff');
  assert.equal(canModifyThreshold(resolvedStaff), false);
});

test('S5-01..S5-03: 30-question bilingual evaluation (15 English + 15 Bangla) with 100% tool grounding', () => {
  // Verify individual tools first.
  const lowest = toolLowestShelves(FIXTURE_SCANS, 'user-owner-1');
  assert.equal(lowest[0].shelfName, 'Shelf B2 (Soft Drinks)');
  assert.equal(lowest[0].itemCount, 8);

  const cmp = toolComparePeriods(
    FIXTURE_SCANS,
    'user-owner-1',
    '2026-11-10T00:00:00Z',
    '2026-11-16T23:59:59Z',
    '2026-11-01T00:00:00Z',
    '2026-11-09T23:59:59Z',
  );
  assert.equal(cmp.currentCountTotal, 44);
  assert.equal(cmp.previousCountTotal, 40);
  assert.equal(cmp.deltaCount, 4);
  assert.equal(cmp.deltaPercent, 10);

  const summary = toolStoreSummary(FIXTURE_SCANS, 'user-owner-1');
  assert.equal(summary.totalScans, 5);
  assert.equal(summary.totalItemsCounted, 84);
  assert.equal(summary.lowStockAlerts, 2);

  // Guardrail catches hallucinated numbers not present in tool output.
  const badCheck = verifyReplyNumbersGrounded('There are 999 items on the shelf.', [8, 15]);
  assert.equal(badCheck.grounded, false);
  assert.deepEqual(badCheck.ungroundedNumbers, [999]);
  assert.deepEqual(extractNumbersFromText('মোট ৪৪টি পণ্য এবং ১০% বৃদ্ধি'), [44, 10]);

  const BENCHMARK_30: Array<{
    q: string;
    locale: 'en' | 'bn';
    userId: string;
    expectedTool: string;
    expectedNumber?: number;
  }> = [
    // 15 English questions
    { q: 'Which shelf is lowest today?', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'Show the shelf with the minimum stock right now.', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'Which shelf has the most low stock alert risk?', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'How many items are on Shelf B2 (Soft Drinks)?', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'Check the count and gaps on Shelf A1 (Biscuits).', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 24 },
    { q: 'What is the count on Shelf C1 (Lentils & Rice)?', locale: 'en', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 12 },
    { q: 'Compare this week with last week across all shelves.', locale: 'en', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 44 },
    { q: 'How does this week compare to the previous week?', locale: 'en', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 40 },
    { q: 'Compare Shelf B2 (Soft Drinks) this week vs last week.', locale: 'en', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 8 },
    { q: 'Compare Shelf A1 (Biscuits) with last week.', locale: 'en', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 24 },
    { q: 'Give me the overall store summary of all scans.', locale: 'en', userId: 'user-owner-1', expectedTool: 'store_summary', expectedNumber: 84 },
    { q: 'How many total items and scans do we have stored?', locale: 'en', userId: 'user-owner-1', expectedTool: 'store_summary', expectedNumber: 5 },
    { q: 'What is the stock count in our Chattogram branch?', locale: 'en', userId: 'user-owner-1', expectedTool: 'refusal_missing_data' },
    { q: 'How many items are in the Pharmacy aisle?', locale: 'en', userId: 'user-owner-1', expectedTool: 'refusal_missing_data' },
    { q: 'Which shelf is lowest for a brand new empty account?', locale: 'en', userId: 'user-empty-account', expectedTool: 'refusal_missing_data' },

    // 15 Bangla questions
    { q: 'আজ কোন তাকে সবচেয়ে কম পণ্য আছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'সবচেয়ে কম স্টক থাকা তাক কোনটি?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'কোন তাকে খালি ফাঁকা স্থান ও কম স্টকের সতর্কতা রয়েছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'Shelf B2 (Soft Drinks) তাকে কয়টি পণ্য আছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 8 },
    { q: 'Shelf A1 (Biscuits) তাকের বর্তমান স্টক কত?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 24 },
    { q: 'Shelf C1 (Lentils & Rice) তাকে কয়টি পণ্য ও ফাঁকা জায়গা আছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'lowest_shelves', expectedNumber: 12 },
    { q: 'এই সপ্তাহের সাথে গত সপ্তাহের তুলনা করুন।', locale: 'bn', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 44 },
    { q: 'গত সপ্তাহের তুলনায় এই সপ্তাহে পণ্যের সংখ্যা কত?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 40 },
    { q: 'Shelf B2 (Soft Drinks) তাকের এই সপ্তাহ ও গত সপ্তাহের তুলনা দেখাও।', locale: 'bn', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 8 },
    { q: 'Shelf A1 (Biscuits) তাকের গত সপ্তাহের সাথে তুলনা করুন।', locale: 'bn', userId: 'user-owner-1', expectedTool: 'compare_periods', expectedNumber: 24 },
    { q: 'স্টোরের মোট স্ক্যান ও পণ্যের সারাংশ দিন।', locale: 'bn', userId: 'user-owner-1', expectedTool: 'store_summary', expectedNumber: 84 },
    { q: 'সর্বমোট কতটি স্ক্যান এবং কতটি পণ্য গণনা করা হয়েছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'store_summary', expectedNumber: 5 },
    { q: 'চট্টগ্রাম শাখায় মোট কতটি পণ্য আছে?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'refusal_missing_data' },
    { q: 'ফার্মেসি তাকের স্টক কত?', locale: 'bn', userId: 'user-owner-1', expectedTool: 'refusal_missing_data' },
    { q: 'নতুন অ্যাকাউন্টে কোন তাকে কম স্টক আছে?', locale: 'bn', userId: 'user-empty-account', expectedTool: 'refusal_missing_data' },
  ];

  assert.equal(BENCHMARK_30.length, 30);

  for (const item of BENCHMARK_30) {
    const res = answerShelfQuestion(item.q, FIXTURE_SCANS, item.userId, item.locale);
    assert.equal(res.toolUsed, item.expectedTool, `Question failed tool match: ${item.q}`);
    assert.equal(res.grounded, true, `Ungrounded number in reply for: ${item.q}`);
    if (item.expectedNumber !== undefined) {
      const extracted = extractNumbersFromText(res.reply);
      assert.ok(
        extracted.includes(item.expectedNumber),
        `Expected ${item.expectedNumber} in [${extracted.join(', ')}] for question: ${item.q}`,
      );
    } else {
      assert.deepEqual(extractNumbersFromText(res.reply), [], `Refusal must not invent numbers: ${item.q}`);
    }
  }
});
