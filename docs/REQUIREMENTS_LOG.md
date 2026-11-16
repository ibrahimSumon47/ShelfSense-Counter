# Requirements log

Non-sensitive summary of what the owner asked for. Full answers are kept privately.

## 2026-11-16 Initial brief

- Product: retail shelf inventory counter. Shelf photo in; detected products, count,
  gaps and low-stock alerts out. Bilingual chat (English, Bangla) answers questions
  about stored scans.
- Audience: owner's resume, portfolio and Upwork profile. Must be honestly measured and
  read as human work.
- Architecture: Python training on Kaggle GPU; in-browser ONNX inference; Next.js on
  Vercel; Clerk; Neon Postgres; Cloudinary thumbnails; free LLM API with tool calling;
  next-intl for en/bn; Python package, CLI and FastAPI app.
- Phases S0 to S8 as listed in `docs/features.json`.

## 2026-11-16 Intake answers

- Shelf domain: grocery and supermarket shelves.
- UI mood: clean operations dashboard, dark blue-grey, light theme available.
- Structure: Store → Aisle → Shelf.
- Language: English default with a Bangla toggle; both must read naturally.
- Roles: owner, and staff who can scan but cannot change thresholds.
- Accounts: GitHub CLI logged in; Vercel, Neon, Cloudinary and a Google AI Studio key
  exist. Clerk and Kaggle still to be created (see `docs/OWNER_TODO.md`).
- Constraints restated: free-forever services only; no secrets, datasets or weights on
  GitHub; owner's identity only, no co-authors, `main` only.
- Nothing added or removed from the brief.
