# Handoff

Last updated: 2026-11-16, end of S0.

## Next step

**S1-01 Dataset survey.** Use `[MODEL: Claude Opus 5.5, HIGH]`.

1. Verify licence and access for SKU-110K (original repo terms and the Kaggle mirror)
   and one grocery shelf dataset; record findings with dates in `docs/DATA.md` and an
   ADR in `docs/DECISIONS.md`.
2. Decide the split unit for each set (store, source or capture session).
3. Then S1-02: `training/` uv project and download script using the kaggle CLI.
   Needs the Kaggle token (OWNER_TODO item 2). If it is still missing, write the
   script and its tests first and run the download once the token exists.

## Session notes

- Hooks are active only when `git config core.hooksPath` prints `.githooks`.
- gitleaks was installed with winget; a new terminal may be needed for it to be on PATH.
