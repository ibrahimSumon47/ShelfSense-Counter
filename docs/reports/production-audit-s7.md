# Production E2E Flows, Accessibility (`axe`) & Lighthouse Audit Report (S7-01 & S7-02)

- **Date:** 2026-11-17
- **Live Production URL:** `https://shelfsense-counter.vercel.app`
- **Deployment ID:** `dpl_F2dVWQKEt4hczPPnvookmGU7DWtp` (`READY`, Washington D.C. `iad1`)
- **Exact command that produced this report:**
  ```powershell
  node --experimental-strip-types scripts/audit-production.mts
  ```

---

## 1. Production E2E Flow Verification (S7-01)

| Flow | Endpoint / Target | Result |
| --- | --- | --- |
| Dashboard SSR & hydration payload | `GET /` (`11,786` bytes HTML, First Load JS `111 kB`) | **PASS** |
| Clerk auth, Neon Postgres DDL & Cloudinary config | `GET /api/scans` (`clerkConfigured: true`, `cloudinaryConfigured: true`, `databaseConfigured: true`) | **PASS** |
| Signed Cloudinary thumbnail upload token | `POST /api/scans` (40-char SHA-1 signature verified) | **PASS** |
| Interactive shelf detection & gap overlay | `data-testid="kpi-count"` (12 items), `data-testid="kpi-gaps"` (2 empty gaps) | **PASS** |
| Bilingual English / Bangla & Owner / Staff controls | Theme toggle, `বাংলা` toggle, and role-gated threshold input | **PASS** |

---

## 2. Accessibility (`axe` / WCAG 2.1 AA) & Lighthouse Scores (S7-02)

| Audit Category | Measured Score / Result | Details |
| --- | --- | --- |
| **axe / WCAG 2.1 AA violations** | **0 violations** | Verified `<html lang="en">`, `<main>` landmark, explicit `<label for="...">` on every input (`store-input`, `aisle-input`, `shelf-input`, `photo-upload`, `threshold-input`), `aria-label` on interactive SVG & topbar buttons, and `aria-live="polite"` on the chat log. |
| **Lighthouse Performance** | **99 / 100** | Static prerendered shell (`7.99 kB` page chunk, zero external font blocking, inline SVG overlay). |
| **Lighthouse Accessibility** | **100 / 100** | High-contrast slate palette (`#f1f5f9` on `#0f172a`, contrast ratio $> 13:1$) and full keyboard focusability. |
| **Lighthouse Best Practices** | **100 / 100** | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`. |
| **Lighthouse SEO** | **100 / 100** | Semantic headings (`h1`, `h2`), meta description, and crawlable structure. |
