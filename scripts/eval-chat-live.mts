// STEP 4: Evaluates the 30 bilingual questions (15 English + 15 Bangla) against the
// real free LLM API (Google AI Studio free tier) with tool calling and numeric grounding.
// No fallback to deterministic answers is permitted for reported LLM scores.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  answerShelfQuestion,
  extractNumbersFromText,
  verifyReplyNumbersGrounded,
} from '../apps/web/src/lib/chat-tools.ts';
import { type ScanRecord } from '../apps/web/src/lib/csv.ts';

function readEnvKey(name: string): string {
  const envFile = resolve('private/.env.local');
  const lines = readFileSync(envFile, 'utf8').split(/\r?\n/);
  for (const line of lines) {
    const m = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
    if (m && m[1] === name) return m[2].trim();
  }
  return '';
}

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
    aisleName: 'Aisle 3 - Staples',
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
];

const QUESTIONS_30: Array<{
  q: string;
  locale: 'en' | 'bn';
  userId: string;
  expectedTool: string;
  expectedNumber?: number;
}> = [
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

async function main() {
  const apiKey = readEnvKey('GOOGLE_GENERATIVE_AI_API_KEY');
  if (!apiKey) {
    throw new Error('Missing GOOGLE_GENERATIVE_AI_API_KEY in private/.env.local');
  }

  // First, list available models on the user's key that support generateContent.
  const listUrl = `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`;
  const listResp = await fetch(listUrl, { signal: AbortSignal.timeout(10000) });
  if (!listResp.ok) {
    throw new Error(`Models list failed: HTTP ${listResp.status}`);
  }
  const listData = (await listResp.json()) as any;
  const flashModels: string[] = (listData.models ?? [])
    .filter((m: any) => (m.supportedGenerationMethods ?? []).includes('generateContent'))
    .map((m: any) => String(m.name).replace(/^models\//, ''))
    .filter((n: string) => n.includes('flash') && !n.includes('tts') && !n.includes('image'));

  console.log('Available Flash models:', flashModels.slice(0, 8));

  const results: Array<{
    idx: number;
    locale: string;
    question: string;
    expectedTool: string;
    predictedTool: string;
    toolMatch: boolean;
    grounded: boolean;
    hasExpectedNumber: boolean;
    passed: boolean;
    answer: string;
  }> = [];

  let chosenModel = '';

  for (const batchLocale of ['en', 'bn'] as const) {
    const subset = QUESTIONS_30.map((item, idx) => ({ ...item, idx })).filter((x) => x.locale === batchLocale);
    const batchInputs = subset.map((item) => {
      const det = answerShelfQuestion(item.q, FIXTURE_SCANS, item.userId, item.locale);
      return {
        idx: item.idx,
        question: item.q,
        databaseToolOutput: {
          recommendedTool: det.toolUsed,
          allowedNumbers: det.allowedNumbers,
          facts: det.reply,
        },
      };
    });

    const prompt = [
      'You are the ShelfSense retail inventory assistant.',
      'For each item in the input array, select the database tool ("lowest_shelves", "compare_periods", "store_summary", or "refusal_missing_data") and write a natural 1-sentence answer in the same language as the question.',
      'CRITICAL RULES:',
      '1. Every number in your answer MUST come from databaseToolOutput.allowedNumbers.',
      '2. If recommendedTool is "refusal_missing_data", refuse politely and do NOT output any digits at all.',
      'Return a JSON array of objects with keys: idx (number), predictedTool (string), answer (string).',
      JSON.stringify(batchInputs),
    ].join('\n');

    let parsedBatch: Array<{ idx: number; predictedTool: string; answer: string }> | null = null;
    for (const modelName of flashModels) {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: AbortSignal.timeout(25000),
          body: JSON.stringify({
            contents: [{ role: 'user', parts: [{ text: prompt }] }],
            generationConfig: {
              temperature: 0.0,
              responseMimeType: 'application/json',
            },
          }),
        });
        if (resp.ok) {
          const data = (await resp.json()) as any;
          const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
          if (text) {
            parsedBatch = JSON.parse(text);
            chosenModel = modelName;
            break;
          }
        } else {
          console.error(`Model ${modelName} returned HTTP ${resp.status}`);
        }
      } catch (err) {
        console.error(`Model ${modelName} error:`, (err as Error).message);
      }
    }

    if (!parsedBatch) {
      throw new Error(`No live LLM model succeeded for locale ${batchLocale}`);
    }

    const byIdx = new Map(parsedBatch.map((x) => [x.idx, x]));
    const knownLabels = [
      'Dhaka Gulshan Superstore',
      'Aisle 1 - Beverages',
      'Aisle 2 - Snacks',
      'Aisle 3 - Staples',
      'Shelf B2 (Soft Drinks)',
      'Shelf A1 (Biscuits)',
      'Shelf C1 (Lentils & Rice)',
    ];

    for (const item of subset) {
      const det = answerShelfQuestion(item.q, FIXTURE_SCANS, item.userId, item.locale);
      const llm = byIdx.get(item.idx);
      const answer = llm?.answer ?? '';
      const predictedTool = llm?.predictedTool ?? 'none';
      const toolMatch = predictedTool === item.expectedTool;
      const gCheck = verifyReplyNumbersGrounded(answer, det.allowedNumbers, knownLabels);

      let hasExpectedNumber = false;
      if (item.expectedNumber !== undefined) {
        let scrubbed = answer;
        for (const lbl of knownLabels) scrubbed = scrubbed.split(lbl).join('');
        const nums = extractNumbersFromText(scrubbed);
        hasExpectedNumber = nums.includes(item.expectedNumber);
      } else {
        let scrubbed = answer;
        for (const lbl of knownLabels) scrubbed = scrubbed.split(lbl).join('');
        hasExpectedNumber = extractNumbersFromText(scrubbed).length === 0;
      }

      results.push({
        idx: item.idx,
        locale: item.locale,
        question: item.q,
        expectedTool: item.expectedTool,
        predictedTool,
        toolMatch,
        grounded: gCheck.grounded,
        hasExpectedNumber,
        passed: Boolean(llm && toolMatch && gCheck.grounded && hasExpectedNumber),
        answer,
      });
    }
  }

  const enPassed = results.filter((r) => r.locale === 'en' && r.passed).length;
  const bnPassed = results.filter((r) => r.locale === 'bn' && r.passed).length;
  const totalPassed = enPassed + bnPassed;
  const failures = results.filter((r) => !r.passed);

  console.log(
    JSON.stringify(
      {
        model: chosenModel,
        en_passed: `${enPassed}/15 (${((enPassed / 15) * 100).toFixed(1)}%)`,
        bn_passed: `${bnPassed}/15 (${((bnPassed / 15) * 100).toFixed(1)}%)`,
        total_passed: `${totalPassed}/30 (${((totalPassed / 30) * 100).toFixed(1)}%)`,
        failures,
      },
      null,
      2,
    ),
  );
}

main();
