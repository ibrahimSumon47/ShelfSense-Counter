# Production checks: flows, accessibility and Lighthouse

Everything in this report was run against the deployed site, not a local build:
https://shelfsense-counter.vercel.app (Vercel deployment `shelfsense-counter-iwmsov0ds`,
the build that also carries the icon added below). The exception is marked where it applies: the
analysed-photo scan and the pre-load message check exercise code that is not in that deployment
yet, so they ran against `next start` of the same commit on `http://localhost:3100`. Every entry in
`axe-production.json` records the URL it was scanned on.

Run on 2026-11-20 with Node 24.22.1, Playwright 1.65.1 (bundled Chromium), axe-core 4.14.0 and
Lighthouse 13.6.0. The raw artifacts are committed next to this file:
`axe-production.json`, `lighthouse-mobile.json`, `lighthouse-desktop.json`,
`lighthouse-summary.json`.

## Commands

```
pnpm exec playwright test                    # 8 flows + 5 accessibility checks (8 states)
node scripts/lighthouse-report.mjs           # mobile and desktop, writes the three JSON files
```

Both default to the production URL; `SHELFSENSE_URL=http://localhost:3000` points them at a local
build, which is how the fixes below were checked before deploying.

## Flows (8, all passing)

| Flow | What it asserts |
| --- | --- |
| Loads with the trained detector available | H1 renders, the upload input is enabled, the "Detector not published in this build" state is absent |
| Counts the products in a shelf photo | A committed CC0 shelf photo yields >100 products, the gaps KPI fills, the overlay draws >50 boxes, and the runtime line says `on WASM` |
| Does not invent a shelf where there is none | A dashboard screenshot (no shelf) yields fewer than 100 detections |
| Saves a scan to history and exports it as CSV | Store/aisle/shelf are stored with the measured count in the table, and the export downloads `shelfsense-scans.csv` |
| Switches language without losing the page | The toggle flips the section headings, the upload input stays enabled, and switching back restores English |
| Only the owner can edit the low-stock threshold | The threshold input is enabled for the owner, disabled for staff, enabled again for the owner |
| Chat refuses to invent numbers when nothing is stored | A question with no stored scans is answered with `refusal_missing_data` |
| Explains a photo chosen before the detector has loaded | With `/models/manifest.json` held, a file is dispatched into the still-disabled input; the page answers with a readable alert instead of doing nothing, the KPIs stay empty, and releasing the manifest enables the input again |

The three upload flows each transfer the 32.8 MB model over the network, so the suite takes about
two minutes against production. It is a manual check, not a CI job: CI already scores a 20-image
regression bundle on the released file, which is the check that belongs on every push.

## Accessibility (axe-core, zero violations)

Scanned after the fixes with the WCAG A/AA and best-practice rule sets, in both themes and both
languages, because the Bangla copy and the light palette are the two states most likely to break
contrast or labels. Each of those four states is scanned twice: once on the page as a visitor first
sees it, and once after a real photo has been through the detector.

| State | Rules passed | Violations |
| --- | --- | --- |
| dark, English | 32 | 0 |
| light, English | 32 | 0 |
| dark, Bangla | 32 | 0 |
| light, Bangla | 32 | 0 |
| dark, English, photo analysed | 39 | 0 |
| light, English, photo analysed | 39 | 0 |
| dark, Bangla, photo analysed | 39 | 0 |
| light, Bangla, photo analysed | 39 | 0 |

### What the analysed state adds

The empty page has no detection surface at all, so the first four rows say nothing about the parts a
visitor actually uses. The analysed check uploads the committed CC0 shelf photo once, waits for the
measured count (**294 products** on this browser's WASM run), saves one scan at the default
threshold and a second at threshold 500, then scans the same page in all four theme and language
states. That single page carries every surface the result state renders:

- the box overlay (`svg[role="img"]` with its accessibility label) over the photo preview;
- both KPI cards with real numbers in them, and the runtime line beside them;
- the history table with two saved rows and both stock badges - `Stock Normal` for the default
  threshold and `Low Stock Alert` for the row above the limit.

Those states were scanned on the local production build noted at the top, because they need the
message fix below, which is not deployed yet. The rules went from 32 to 39 per state: the table,
the badges and the overlay expose checks the empty page cannot run.

### What the first run found, and what changed

The first run against production failed with two serious rules. Both were real defects, not
tool noise, and both are fixed in `apps/web`:

1. **`label-content-name-mismatch` on the three toggle buttons.** The role, theme and language
   buttons carried `aria-label` values ("Toggle language", "Switch user role", "Toggle color
   theme") that replaced the visible text, so a voice-control user saying what they can read
   ("বাংলা") could not activate the button. The action words now sit in a `.sr-only` span in front
   of the visible label, which makes the accessible name "Toggle language: বাংলা" - the visible
   text is part of the name, and the purpose is still announced.
2. **`color-contrast` on the primary buttons in the light theme.** White text on `#0284c7` is
   4.09:1, under the 4.5:1 minimum for normal text, which hit the language toggle and the chat
   send button. The light-theme accent is now `#0369a1` (5.9:1 on white, 5.9:1 for the hover
   state `#075985` used later), so the same two buttons pass.

## Lighthouse (production)

| Form factor | Performance | Accessibility | Best practices | SEO | FCP | LCP | TBT | CLS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mobile (412x823, 4x CPU, 1.6 Mbps) | 99 | 100 | 100 | 100 | 869 ms | 869 ms | 118 ms | 0 |
| Desktop (1350x940, no throttling) | 100 | 100 | 100 | 100 | 289 ms | 289 ms | 0 ms | 0 |

Best practices first came back at 96 on both profiles because the page logged a console error:
`/favicon.ico` returned 404. The app now ships `apps/web/src/app/icon.svg`, Next serves it with a
`<link rel="icon">` tag, and the audit is clean.

The page is a static prerender of 112 kB of JavaScript. The 32.8 MB model is only fetched after a
visitor chooses a photo, so it does not enter the load path Lighthouse measures; that is why the
scores are high while the first detection still takes a few seconds.

## A race the flows caught

Against production the two upload flows timed out while the same flows passed locally. The cause
was not the deploy: `MODEL_AVAILABLE` is false until `/models/manifest.json` resolves, the upload
input is disabled until then, and a file that arrived before that moment was ignored without any
error, because the change handler returned early. The tests wait for the input to become enabled -
the app's own ready signal - and for the blob preview that proves the handler ran.

The silent path is now closed as well. If a photo does reach the page before the manifest resolves
(the input is disabled, so this takes a drop, an extension or automation), the handler shows a
readable alert - "The detector is still loading in this browser, so this photo was not analysed.
Wait a moment, then choose the photo again." - in both languages, and clears the field so the same
file can be chosen again. With no detector published at all it shows the existing `Detector not
published in this build` explanation instead. The `Explains a photo chosen before the detector has
loaded` flow holds the manifest request and dispatches exactly that change event to prove it.

## Not covered here

- The live-LLM chat evaluation cannot be re-run on this PC: `private/.env.local` is missing and the
  key cannot be read back from Vercel. Owner steps are item 2b in `docs/OWNER_TODO.md`; the
  `S5-03` figures come from the run made while the key was still available.
- No load or concurrency testing. The detector runs in the visitor's browser, so server load is
  limited to serving static files.
