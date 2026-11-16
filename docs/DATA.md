# Data card

Status: draft. Filled in during S1. Nothing below is final until each dataset's
licence and access method are verified and dated here.

## Rules

- No images, labels or archives are committed. Everything is downloaded by script
  (`training/data/` is gitignored).
- Splits are made by store or by source, never by random image, so photos of the same
  shelf or the same store cannot appear on both sides of a split.
- A near-duplicate check (perceptual hash) runs across splits before training; its
  report is committed in `docs/reports/`.
- Test images are used once, for the final report.

## Candidate datasets (to verify in S1-01)

| Dataset | Why | Licence | Access | Verified |
| --- | --- | --- | --- | --- |
| SKU-110K | Dense retail shelves, ~11.7k images, ~147 boxes per image | to check | Kaggle mirror or original repo | no |
| A grocery shelf set (e.g. Grocery Products / GroceryStore-style) | Closer to supermarket shelves in South Asia | to check | to check | no |

## Splits

To be defined in S1-03.

## Known gaps

To be filled in S1 and S3 (lighting, shelf types, regions not represented).
