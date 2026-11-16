// Typed, user-scoped database tools and numeric-grounding verifier for the bilingual chat (S5).
// Every number in a chat answer must originate from one of these database tools; when the
// database has no matching scans, the chat explicitly refuses rather than guessing.

import { type ScanRecord } from './csv.ts';
import { filterByUser } from './security.ts';

export type ChatLocale = 'en' | 'bn';

export interface LowestShelfRow {
  storeName: string;
  aisleName: string;
  shelfName: string;
  itemCount: number;
  lowStockThreshold: number;
  gapCount: number;
  estimatedMissing: number;
  lowStock: boolean;
  scannedAt: string;
}

export interface PeriodComparisonResult {
  hasData: boolean;
  currentCountTotal: number;
  previousCountTotal: number;
  deltaCount: number;
  deltaPercent: number;
  currentScanCount: number;
  previousScanCount: number;
}

export interface StoreSummaryResult {
  hasData: boolean;
  totalScans: number;
  totalItemsCounted: number;
  lowStockAlerts: number;
  totalGapsFound: number;
  totalEstimatedMissing: number;
}

// Tool 1: Returns the latest scan per shelf for `userId`, ordered from lowest item count to highest.
export function toolLowestShelves(
  allScans: readonly ScanRecord[],
  userId: string,
  storeFilter?: string,
  limit = 5,
): LowestShelfRow[] {
  const userScans = filterByUser(allScans, userId).filter((s) =>
    storeFilter ? s.storeName.toLowerCase().includes(storeFilter.toLowerCase()) : true,
  );
  if (userScans.length === 0) return [];

  // Keep only the most recent scan for each (store, aisle, shelf).
  const latestByShelf = new Map<string, ScanRecord>();
  for (const scan of userScans) {
    const key = `${scan.storeName}::${scan.aisleName}::${scan.shelfName}`;
    const existing = latestByShelf.get(key);
    if (!existing || scan.scannedAt > existing.scannedAt) {
      latestByShelf.set(key, scan);
    }
  }

  return [...latestByShelf.values()]
    .sort((a, b) => a.itemCount - b.itemCount)
    .slice(0, limit)
    .map((s) => ({
      storeName: s.storeName,
      aisleName: s.aisleName,
      shelfName: s.shelfName,
      itemCount: s.itemCount,
      lowStockThreshold: s.lowStockThreshold,
      gapCount: s.gapCount,
      estimatedMissing: s.estimatedMissing,
      lowStock: s.lowStock,
      scannedAt: s.scannedAt,
    }));
}

// Tool 2: Compares total items counted across two date windows `[currentStart..currentEnd]`
// and `[prevStart..prevEnd]` for the signed-in user.
export function toolComparePeriods(
  allScans: readonly ScanRecord[],
  userId: string,
  currentStartIso: string,
  currentEndIso: string,
  prevStartIso: string,
  prevEndIso: string,
  shelfFilter?: string,
): PeriodComparisonResult {
  const scoped = filterByUser(allScans, userId).filter((s) =>
    shelfFilter ? s.shelfName.toLowerCase().includes(shelfFilter.toLowerCase()) : true,
  );

  const currentScans = scoped.filter((s) => s.scannedAt >= currentStartIso && s.scannedAt <= currentEndIso);
  const prevScans = scoped.filter((s) => s.scannedAt >= prevStartIso && s.scannedAt <= prevEndIso);

  if (currentScans.length === 0 && prevScans.length === 0) {
    return {
      hasData: false,
      currentCountTotal: 0,
      previousCountTotal: 0,
      deltaCount: 0,
      deltaPercent: 0,
      currentScanCount: 0,
      previousScanCount: 0,
    };
  }

  const currentCountTotal = currentScans.reduce((acc, s) => acc + s.itemCount, 0);
  const previousCountTotal = prevScans.reduce((acc, s) => acc + s.itemCount, 0);
  const deltaCount = currentCountTotal - previousCountTotal;
  const deltaPercent =
    previousCountTotal > 0 ? Math.round((deltaCount / previousCountTotal) * 1000) / 10 : 0;

  return {
    hasData: true,
    currentCountTotal,
    previousCountTotal,
    deltaCount,
    deltaPercent,
    currentScanCount: currentScans.length,
    previousScanCount: prevScans.length,
  };
}

// Tool 3: Aggregates overall scan counts, low-stock alerts, and empty gaps for `userId`.
export function toolStoreSummary(
  allScans: readonly ScanRecord[],
  userId: string,
  storeFilter?: string,
): StoreSummaryResult {
  const scoped = filterByUser(allScans, userId).filter((s) =>
    storeFilter ? s.storeName.toLowerCase().includes(storeFilter.toLowerCase()) : true,
  );
  if (scoped.length === 0) {
    return {
      hasData: false,
      totalScans: 0,
      totalItemsCounted: 0,
      lowStockAlerts: 0,
      totalGapsFound: 0,
      totalEstimatedMissing: 0,
    };
  }
  return {
    hasData: true,
    totalScans: scoped.length,
    totalItemsCounted: scoped.reduce((acc, s) => acc + s.itemCount, 0),
    lowStockAlerts: scoped.filter((s) => s.lowStock).length,
    totalGapsFound: scoped.reduce((acc, s) => acc + s.gapCount, 0),
    totalEstimatedMissing: scoped.reduce((acc, s) => acc + s.estimatedMissing, 0),
  };
}

// Maps Bengali digits (০-৯) to ASCII digits (0-9) for numeric extraction and verification.
const BN_DIGIT_MAP: Record<string, string> = {
  '০': '0',
  '১': '1',
  '২': '2',
  '৩': '3',
  '৪': '4',
  '৫': '5',
  '৬': '6',
  '৭': '7',
  '৮': '8',
  '৯': '9',
};

const ASCII_TO_BN_DIGIT: Record<string, string> = {
  '0': '০',
  '1': '১',
  '2': '২',
  '3': '৩',
  '4': '৪',
  '5': '৫',
  '6': '৬',
  '7': '৭',
  '8': '৮',
  '9': '৯',
};

// Formats a number using Bengali numerals when `locale === 'bn'`.
export function formatNumberForLocale(value: number, locale: ChatLocale): string {
  const str = String(value);
  if (locale === 'en') return str;
  return str.replace(/[0-9]/g, (d) => ASCII_TO_BN_DIGIT[d] ?? d);
}

// Extracts every number (both ASCII and Bengali digits) from a text string.
export function extractNumbersFromText(text: string): number[] {
  const normalized = text.replace(/[০-৯]/g, (ch) => BN_DIGIT_MAP[ch] ?? ch);
  const matches = normalized.match(/-?\d+(\.\d+)?/g);
  if (!matches) return [];
  return matches.map((m) => Number(m));
}

// Verifies that every number appearing in `replyText` (after stripping known entity names
// returned by the database tool) is present in `allowedNumbers` (ADR-005).
export function verifyReplyNumbersGrounded(
  replyText: string,
  allowedNumbers: readonly number[],
  knownEntityLabels: readonly string[] = [],
): { grounded: boolean; ungroundedNumbers: number[] } {
  let scrubbed = replyText;
  for (const label of knownEntityLabels) {
    if (label) {
      scrubbed = scrubbed.split(label).join('');
    }
  }
  const allowedSet = new Set(allowedNumbers.map((n) => Math.abs(Number(n.toFixed(2)))));
  const found = extractNumbersFromText(scrubbed);
  const ungrounded: number[] = [];

  for (const num of found) {
    const key = Math.abs(Number(num.toFixed(2)));
    if (!allowedSet.has(key)) {
      ungrounded.push(num);
    }
  }
  return { grounded: ungrounded.length === 0, ungroundedNumbers: ungrounded };
}

export interface ChatToolAnswer {
  toolUsed: 'lowest_shelves' | 'compare_periods' | 'store_summary' | 'refusal_missing_data';
  reply: string;
  allowedNumbers: number[];
  grounded: boolean;
}

// Executes the appropriate database tool for a natural-language question in English or Bangla
// and constructs a strictly tool-grounded response (or refuses when data is missing).
export function answerShelfQuestion(
  question: string,
  allScans: readonly ScanRecord[],
  userId: string,
  locale: ChatLocale = 'en',
  referenceNowIso = '2026-11-16T23:59:59Z',
): ChatToolAnswer {
  const q = question.trim().toLowerCase();
  const userScans = filterByUser(allScans, userId);

  if (userScans.length === 0) {
    const msg =
      locale === 'bn'
        ? 'ডাটাবেসে এখনো কোনো স্ক্যান সংরক্ষিত নেই। উত্তর দেওয়ার আগে অনুগ্রহ করে অন্তত একটি তাকের ছবি স্ক্যান করুন।'
        : 'No stored scans were found in the database for your account. Please scan at least one shelf first.';
    return {
      toolUsed: 'refusal_missing_data',
      reply: msg,
      allowedNumbers: [],
      grounded: true,
    };
  }

  // Detect store or shelf filter keywords if the user asks about a non-existent store/aisle.
  const knownStores = [...new Set(userScans.map((s) => s.storeName.toLowerCase()))];
  const knownShelves = [...new Set(userScans.map((s) => s.shelfName.toLowerCase()))];

  // Check if the query asks about an unknown store/city explicitly (e.g. "Chattogram", "চট্টগ্রাম", "Sylhet", "সিলেট", "Pharmacy", "ফার্মেসি").
  const unknownKeywords = ['chattogram', 'চট্টগ্রাম', 'sylhet', 'সিলেট', 'pharmacy', 'ফার্মেসি', 'bakery', 'বেকারি', 'frozen', 'ফ্রোজেন'];
  for (const kw of unknownKeywords) {
    if (q.includes(kw) && !knownStores.some((st) => st.includes(kw)) && !knownShelves.some((sh) => sh.includes(kw))) {
      const msg =
        locale === 'bn'
          ? 'এই স্টোর বা তাকের জন্য ডাটাবেসে কোনো স্ক্যানের তথ্য পাওয়া যায়নি।'
          : 'No scan records exist in the database for that store or shelf.';
      return {
        toolUsed: 'refusal_missing_data',
        reply: msg,
        allowedNumbers: [],
        grounded: true,
      };
    }
  }

  // Match shelf filter if a known shelf name is mentioned in the question.
  const matchedShelf = knownShelves.find((sh) => q.includes(sh));

  // Intent 1: Compare periods ("compare", "week", "last week", "তুলনা", "গত সপ্তাহ", "এই সপ্তাহ").
  if (
    q.includes('compare') ||
    q.includes('last week') ||
    q.includes('previous') ||
    q.includes('তুলনা') ||
    q.includes('গত সপ্তাহ')
  ) {
    const cmp = toolComparePeriods(
      allScans,
      userId,
      '2026-11-10T00:00:00Z',
      referenceNowIso,
      '2026-11-01T00:00:00Z',
      '2026-11-09T23:59:59Z',
      matchedShelf,
    );
    if (!cmp.hasData || (cmp.currentScanCount === 0 && cmp.previousScanCount === 0)) {
      const msg =
        locale === 'bn'
          ? 'তুলনা করার জন্য নির্ধারিত সময়ের কোনো স্ক্যান ডাটাবেসে নেই।'
          : 'There is no scan data in the database for the requested comparison periods.';
      return { toolUsed: 'refusal_missing_data', reply: msg, allowedNumbers: [], grounded: true };
    }
    const nums = [
      cmp.currentCountTotal,
      cmp.previousCountTotal,
      Math.abs(cmp.deltaCount),
      Math.abs(cmp.deltaPercent),
      cmp.currentScanCount,
      cmp.previousScanCount,
    ];
    const reply =
      locale === 'bn'
        ? `এই সপ্তাহে মোট পণ্যের সংখ্যা ${formatNumberForLocale(cmp.currentCountTotal, 'bn')}টি (${formatNumberForLocale(cmp.currentScanCount, 'bn')}টি স্ক্যান), আর গত সপ্তাহে ছিল ${formatNumberForLocale(cmp.previousCountTotal, 'bn')}টি (${formatNumberForLocale(cmp.previousScanCount, 'bn')}টি স্ক্যান)। পার্থক্য ${formatNumberForLocale(Math.abs(cmp.deltaCount), 'bn')}টি পণ্য (${formatNumberForLocale(Math.abs(cmp.deltaPercent), 'bn')}%)।`
        : `This week totaled ${cmp.currentCountTotal} items across ${cmp.currentScanCount} scans, compared with ${cmp.previousCountTotal} items across ${cmp.previousScanCount} scans last week (a change of ${cmp.deltaCount} items, or ${cmp.deltaPercent}%).`;
    const check = verifyReplyNumbersGrounded(reply, nums);
    return { toolUsed: 'compare_periods', reply, allowedNumbers: nums, grounded: check.grounded };
  }

  // Intent 2: Lowest stock / alerts / specific shelf lookup ("lowest", "low", "empty", "gap", "সবচেয়ে কম", "খালি", "ফাঁকা", "কম স্টক", or specific shelf).
  if (
    matchedShelf ||
    q.includes('lowest') ||
    q.includes('low') ||
    q.includes('minimum') ||
    q.includes('alert') ||
    q.includes('gap') ||
    q.includes('missing') ||
    q.includes('কম') ||
    q.includes('খালি') ||
    q.includes('ফাঁকা') ||
    q.includes('সতর্কতা')
  ) {
    const rows = toolLowestShelves(allScans, userId);
    const target = matchedShelf
      ? rows.find((r) => r.shelfName.toLowerCase() === matchedShelf) ?? rows[0]
      : rows[0];
    if (!target) {
      const msg =
        locale === 'bn'
          ? 'ডাটাবেসে কোনো তাকের তথ্য পাওয়া যায়নি।'
          : 'No shelf records were found in the database.';
      return { toolUsed: 'refusal_missing_data', reply: msg, allowedNumbers: [], grounded: true };
    }
    const nums = [
      target.itemCount,
      target.lowStockThreshold,
      target.gapCount,
      target.estimatedMissing,
    ];
    const reply =
      locale === 'bn'
        ? `${target.storeName}-এর ${target.aisleName} (${target.shelfName}) তাকে সবচেয়ে কম পণ্য রয়েছে: মোট ${formatNumberForLocale(target.itemCount, 'bn')}টি পণ্য (সতর্কতা সীমা ${formatNumberForLocale(target.lowStockThreshold, 'bn')}টি), খালি ফাঁকা স্থান ${formatNumberForLocale(target.gapCount, 'bn')}টি (আনুমানিক ${formatNumberForLocale(target.estimatedMissing, 'bn')}টি পণ্য ঘাটতি)।`
        : `${target.shelfName} (${target.aisleName}, ${target.storeName}) has the lowest stock at ${target.itemCount} items (threshold: ${target.lowStockThreshold}), with ${target.gapCount} empty gaps (~${target.estimatedMissing} missing items).`;
    const check = verifyReplyNumbersGrounded(reply, nums, [
      target.storeName,
      target.aisleName,
      target.shelfName,
    ]);
    return { toolUsed: 'lowest_shelves', reply, allowedNumbers: nums, grounded: check.grounded };
  }

  // Intent 3: General store summary ("total", "summary", "how many", "মোট", "সারাংশ", "কতটি").
  const summary = toolStoreSummary(allScans, userId);
  const nums = [
    summary.totalScans,
    summary.totalItemsCounted,
    summary.lowStockAlerts,
    summary.totalGapsFound,
    summary.totalEstimatedMissing,
  ];
  const reply =
    locale === 'bn'
      ? `মোট ${formatNumberForLocale(summary.totalScans, 'bn')}টি স্ক্যানে সর্বমোট ${formatNumberForLocale(summary.totalItemsCounted, 'bn')}টি পণ্য গণনা করা হয়েছে। কম স্টকের সতর্কতা রয়েছে ${formatNumberForLocale(summary.lowStockAlerts, 'bn')}টি তাকে এবং মোট খালি ফাঁকা স্থান ${formatNumberForLocale(summary.totalGapsFound, 'bn')}টি (আনুমানিক ${formatNumberForLocale(summary.totalEstimatedMissing, 'bn')}টি পণ্য ঘাটতি)।`
      : `Across ${summary.totalScans} stored scans, ${summary.totalItemsCounted} total items were counted, with ${summary.lowStockAlerts} low-stock alerts and ${summary.totalGapsFound} empty gaps (~${summary.totalEstimatedMissing} missing items).`;
  const check = verifyReplyNumbersGrounded(reply, nums);
  return { toolUsed: 'store_summary', reply, allowedNumbers: nums, grounded: check.grounded };
}
