# Bilingual Chat Tool-Calling Evaluation Report (S5-03)

- **Date:** 2026-11-17
- **Command:** `node --experimental-strip-types --test "apps/web/src/lib/shelfsense.test.ts"`
- **Benchmark size:** 30 questions (15 English, 15 Bangla)
- **Dataset:** 5 user-scoped scan records across 3 shelves (`Shelf B2 (Soft Drinks)`, `Shelf A1 (Biscuits)`, `Shelf C1 (Lentils & Rice)`) plus 1 cross-tenant scan record (`user-other-tenant`) to verify strict data isolation.

## Measured Results

| Metric | English (15) | Bangla (15) | Total (30) |
| --- | --- | --- | --- |
| Correct database tool invoked (`lowest_shelves`, `compare_periods`, `store_summary`, `refusal_missing_data`) | 15 / 15 (100.0%) | 15 / 15 (100.0%) | **30 / 30 (100.0%)** |
| Numeric grounding check (`verifyReplyNumbersGrounded`) | 15 / 15 (100.0%) | 15 / 15 (100.0%) | **30 / 30 (100.0%)** |
| Exact target metric present in reply | 12 / 12 (100.0%) | 12 / 12 (100.0%) | **24 / 24 (100.0%)** |
| Missing-data refusal without invented numbers | 3 / 3 (100.0%) | 3 / 3 (100.0%) | **6 / 6 (100.0%)** |
| Cross-tenant leakage (`user-other-tenant`) | 0 leaks | 0 leaks | **0 leaks** |

## Failure & Guardrail Verification

- **Hallucinated number injection test:** Passing `"There are 999 items on the shelf."` when the tool returned `[8, 15]` is rejected by `verifyReplyNumbersGrounded` (`grounded: false`, `ungroundedNumbers: [999]`).
- **Missing store / shelf refusal:** Queries asking about unrecorded branches (`Chattogram` / `চট্টগ্রাম`) or unrecorded aisles (`Pharmacy` / `ফার্মেসি`) or empty accounts return `refusal_missing_data` with zero numbers in the response.
