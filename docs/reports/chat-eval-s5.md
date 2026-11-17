# Bilingual Chat Tool-Call and Numeric Grounding Checks Report (S5-02 & S5-03)

- **Date:** 2026-11-17
- **Command:** `node --experimental-strip-types scripts/eval-chat-live.mts`
- **Model / Run ID:** `flash-lite-latest` (live free-tier LLM API via `generativelanguage.googleapis.com`, `temperature = 0.0`)
- **Benchmark size:** 30 questions (15 English, 15 Bangla) over 5 user-scoped scan records (`Dhaka Gulshan Superstore`) plus 1 cross-tenant scan record (`user-other-tenant`).

---

## 1. Live Free-LLM Tool-Call and Numeric Grounding Checks (`scripts/eval-chat-live.mts`)

| Metric | English (15) | Bangla (15) | Total (30) |
| --- | --- | --- | --- |
| **Correct database tool selected (`toolMatch`)** | **15 / 15 (100.0%)** | **15 / 15 (100.0%)** | **30 / 30 (100.0%)** |
| **Target metric present / missing-data refusal (`hasExpectedNumber`)** | **15 / 15 (100.0%)** | **15 / 15 (100.0%)** | **30 / 30 (100.0%)** |
| **Strict verbatim `verifyReplyNumbersGrounded` check (before stripping abbreviated shelf codes)** | **9 / 15 (60.0%)** | **15 / 15 (100.0%)** | **24 / 30 (80.0%)** |
| **Cross-tenant data leakage (`user-other-tenant`)** | 0 leaks | 0 leaks | **0 leaks** |

---

## 2. Analysis of the 6 Strict Verbatim Grounding Failures in English

All 6 failures in the strict `24/30 (80.0%)` check (`idx` 0, 1, 2, 3, 5, 8) had the **exact right tool** and the **exact right inventory numbers** (`8` items, threshold `15`, `3` gaps, `9` missing items; or `12` items, `2` gaps, `5` missing items), but the live LLM shortened the shelf name from `"Shelf B2 (Soft Drinks)"` to `"Shelf B2"` (or `"Shelf C1 (Lentils & Rice)"` to `"Shelf C1"`). Because the full string `"Shelf B2 (Soft Drinks)"` did not match the shortened `"Shelf B2"`, the regex number extractor saw the `"2"` in `"B2"` (or the `"1"` in `"C1"`) as an ungrounded standalone digit:

1. **`idx 0` ("Which shelf is lowest today?"):**
   - LLM output: `"Shelf B2 has the lowest stock at 8 items with 3 empty gaps and 9 missing items, falling below the threshold of 15."`
   - Why strict check flagged it: `"Shelf B2"` shortened `"Shelf B2 (Soft Drinks)"`, leaving `2` from `B2` outside `allowedNumbers = [8, 15, 3, 9]`.
2. **`idx 1` ("Show the shelf with the minimum stock right now."):**
   - LLM output: `"The shelf with the minimum stock right now is Shelf B2 at 8 items, which is under the 15 threshold and has 3 gaps."`
3. **`idx 2` ("Which shelf has the most low stock alert risk?"):**
   - LLM output: `"Shelf B2 presents the highest low stock risk with 8 items remaining against a threshold of 15 and 3 empty gaps."`
4. **`idx 3` ("How many items are on Shelf B2 (Soft Drinks)?"):**
   - LLM output: `"Shelf B2 currently holds 8 items with a threshold of 15 and features 3 empty gaps."`
5. **`idx 5` ("What is the count on Shelf C1 (Lentils & Rice)?"):**
   - LLM output: `"Shelf C1 has a stock count of 12 items with 2 empty gaps and about 5 missing items against a threshold of 15."` (`1` in `C1` flagged).
6. **`idx 8` ("Compare Shelf B2 (Soft Drinks) this week vs last week."):**
   - LLM output: `"Shelf B2 has 8 items across 1 scan this week compared to 22 items across 1 scan last week, a change of -14 items or -63.6 percent."` (`2` in `B2` flagged).

---

## 3. Deterministic Tool-Call and Numeric Grounding Unit Suite

Running `node --experimental-strip-types --test "apps/web/src/lib/shelfsense.test.ts"` verifies the deterministic database tools (`toolLowestShelves`, `toolComparePeriods`, `toolStoreSummary`) and `verifyReplyNumbersGrounded` guardrail on every CI push (`30/30` deterministic tool-call and numeric grounding checks).
