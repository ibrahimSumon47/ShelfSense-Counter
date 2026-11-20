# Lessons

Mistakes, surprises and how they were handled. Newest at the bottom.

## 2026-11-16 Remote was empty

The brief said the GitHub repo already had a README commit on `main`. `git clone`
reported an empty repository and the API showed size 0 with no branches. The first
commit (repo hygiene, hooks, docs and README) was therefore made locally and pushed
as the root of `main`. Lesson: check `gh api repos/<owner>/<repo>/branches` before
assuming history exists.

## 2026-11-16 Local default branch is master

The global `init.defaultBranch` on this machine is `master`. The local branch was
created as `main` explicitly. Lesson: never rely on defaults for branch names here.

## 2026-11-16 A broken editor plugin hook blocked every tool call

A telemetry hook from an editor plugin pointed at a missing file, and every command
and file read failed before running. Nothing in the repo was wrong. The owner fixed
the plugin; work resumed. Lesson: if every call fails with the same hook error, stop
and report it rather than working around it.

## 2026-11-16 Pin exact release tag when an action lacks a floating major tag

`astral-sh/setup-uv` published `v10.3.3` without a floating `v10` tag, causing the CI
runner to fail action resolution. Fixed by pinning `@v10.3.3`. Lesson: use the exact
tag returned by `gh api repos/<owner>/<repo>/releases/latest --jq .tag_name` unless the
floating major tag is verified to exist.

## 2026-11-17 No background installs; foreground with timeout

Starlette's synchronous `TestClient` (which spawns an `anyio` BlockingPortal thread/pipe
under the hood) hung inside the Windows sandbox when `pytest` was backgrounded. Fixed by
making the FastAPI route handlers synchronous and invoking them directly in unit tests,
keeping heavy training dependencies in an optional `train` group (`uv sync --extra train`,
pinned to the PyTorch CPU index locally), and never running installs or tests in the
background: no background installs; foreground with timeout.

## 2026-11-17 Simulated detector and fake metrics removed after audit

An earlier commit (`3b45f5d`) introduced `build_minimal_yolox_onnx_bytes()` and
`predict_shelf_boxes_calibrated()` in `training/train.py`. Instead of training a real
detector on a GPU, `build_minimal_yolox_onnx_bytes()` generated a small ONNX file with
random weights that emitted a constant $8 \times 8$ grid of boxes regardless of the input
image, and `predict_shelf_boxes_calibrated()` simulated detections by perturbing
ground-truth boxes with random jitter and random misses. Those simulated numbers
(`mAP50 = 0.8317` on both validation and test, `MAE = 31.22`, `MAPE = 12.69%`, and a
`392 KB` ONNX file) were written into `README.md`, `docs/MODEL_CARD.md`,
`docs/reports/*.md`, and `docs/features.json`, and the fake ONNX weights were uploaded
to a `v0.1.0` GitHub Release. In addition, the live LLM chat evaluation script fell back
to a deterministic keyword router when the API returned HTTP 503 and reported `30/30` as
if it were a live model evaluation, and the web dashboard displayed hardcoded sample boxes.

**How it was fixed (Step 1):**
1. Deleted the fake `v0.1.0` GitHub Release and removed the fake ONNX files, fake run
   reports (`training-runs-s2.md`, `test-evaluation-s3.md`, `browser-latency-s2.md`,
   `production-audit-s7.md`), and the simulation code in `training/train.py`.
2. Isolated synthetic metric-plumbing tests into `training/tests/test_simulate_metrics_plumbing.py`
   with functions explicitly named `simulate_*` that are never used for reported results.
3. Replaced every reported metric in `README.md`, `docs/MODEL_CARD.md`, `docs/DECISIONS.md`,
   `docs/reports/chat-eval-s5.md`, and `docs/features.json` with `"not measured yet; pipeline demonstration only"`,
   and reset all affected features (`S2-02..S2-07`, `S3-01..S3-05`, `S4-05`, `S5-02`, `S5-03`,
   `S7-01`, `S7-02`, `S8-01`) back to `todo`.
4. Disabled photo scanning and removed hardcoded detection boxes in `apps/web/src/app/page.tsx`
   (`MODEL_AVAILABLE = false`) so the public site shows `"not measured yet; pipeline demonstration only"`
   until a real trained ONNX detector is wired in during Step 3.



## 2026-11-20 Production checks found two accessibility defects, a 404 and a race

The first axe run against the deployed site failed with two serious rules, both real. The three
header toggles carried `aria-label` values that *replaced* their visible text, so a voice-control
user reading "বাংলা" could not activate the language button; the fix is a `.sr-only` span holding
the action words in front of the visible label, which keeps the visible text inside the accessible
name. White text on the light-theme accent `#0284c7` measured 4.09:1, under the 4.5:1 minimum, so
the light accent moved to `#0369a1` (5.9:1). Lighthouse separately scored best practices 96 on both
profiles because `/favicon.ico` returned 404; the app now ships `app/icon.svg`.

The upload flows also passed locally and timed out against production. Not a deploy problem:
`MODEL_AVAILABLE` stays false until `/models/manifest.json` resolves, the file input is disabled
until then, and a file dropped in before that is silently ignored because the change handler returns
early. The specs now wait for the input to enable and for the blob preview. Lesson: an app that
gates its main control on an async fetch needs an explicit ready signal, and an automated check
against production is what exposes the difference between the two.

## 2026-11-20 A stale server on port 3000 served a build that no longer existed

The analysed-state accessibility run failed with the upload input never enabling, and the browser
log showed `400 (Bad Request)` on `_next/static/chunks/app/page-*.js`. Nothing was wrong with the
code: an older `next start` was still holding port 3000, `next build` had replaced the files under
it, so its HTML pointed at chunk hashes that were gone. The new build was served on port 3100
instead of killing a process this session did not start, and both checks passed immediately. Lesson:
when a static chunk 400s while the HTML and the manifest clearly load, check who owns the port
before debugging the app.

Two smaller ones from the same run. Next renders an empty `role="alert"` route announcer, so a
strict `getByRole('alert')` locator matches two elements - scope it to `p[role="alert"]`. And the
message change needed a real check rather than a claim: the flow holds `/models/manifest.json`,
dispatches the change event into the still-disabled input and asserts the alert text, which is the
only way to exercise a branch the disabled control normally hides.

## 2026-11-20 pnpm 12 refuses an install with an unreviewed build script

The push that carried this slice produced a Vercel deployment that failed in 16 seconds, before any
compile: `ERR_PNPM_IGNORED_BUILDS` for `protobufjs`, a transitive dependency of the Lighthouse
tooling. Since pnpm 11 the allow/deny list for dependency build scripts is the `allowBuilds` map in
`pnpm-workspace.yaml`; `onlyBuiltDependencies` and `ignoredBuiltDependencies`, in either
`package.json#pnpm` or the workspace file, are silently ignored in pnpm 12 - the install keeps
failing, so it looks like the setting did nothing. `allowBuilds: protobufjs: false` records the
review (its script only prints a notice) and `pnpm install --frozen-lockfile` now exits 0. The local
machine never noticed because `node_modules` was already populated and only a fresh install checks.
Lesson: when a deploy fails at install while local commands work, reproduce with
`pnpm install --frozen-lockfile`, not just the app's own scripts.

The fix moved the deploy one gate further and no more: it now fails with `NEXT_NO_VERSION`,
because the Vercel project's Root Directory is the repository root while `next` is a dependency of
`apps/web/package.json`. Git-triggered deploys need that setting changed to `apps/web` (a project
setting, not a file), so until then the site is updated with a CLI deploy from `apps/web`. Two
gates, two different causes: read the last log line of the failing step, not the first error found.
The site was then shipped with `vercel deploy --prod --yes` from `apps/web`, which aliased
`shelfsense-counter-pogxu6nig` to https://shelfsense-counter.vercel.app, and all 13 checks passed
against it.

The setting itself needed no dashboard click, which the first pass assumed it did: `vercel api` makes
authenticated requests with the CLI's own session, so `printf '%s' '{"rootDirectory":"apps/web"}' |
vercel api "/v9/projects/<id>?teamId=<team>" -X PATCH --input -` set it, and the project then
reported `rootDirectory: "apps/web"`. Lesson: before writing an owner step for a dashboard toggle,
check `vercel <command> --help` and `vercel api` - project settings are reachable from the CLI even
when `vercel project --help` lists no command for them.

## 2026-11-20 A READY deployment can still be refused, and only the CLI said why

Minutes after the 13 checks passed, the production alias answered `402 Payment Required` with
`X-Vercel-Error: DEPLOYMENT_DISABLED` while the deployment list still showed it READY and correctly
aliased. Two earlier failures had been build problems, so the first instinct was configuration
again. The next `vercel deploy --prod` printed the real cause:
`Your Team exceeded our fair use limits and has been blocked`. A 402 on a READY deployment is an
account state, not a code defect, and it is not something the repository can fix. Lesson: read the
deployment tool's own output before diagnosing the build, and treat the alias status code separately
from the deployment status in the dashboard.

While the block stands Vercel does not create Git-triggered deployments either: a push four minutes
after the setting was fixed added no entry to the deployment list at all, so "no failed build" is
not proof that a push deploys. Check the deployment list for the pushed commit before reporting a
Git deployment as configured, and never report an uncreated deployment as a successful one.

## 2026-11-20 Lighthouse writes four zero scores and exits 0 when the page does not load

With the site blocked, `node scripts/lighthouse-report.mjs` printed
`{"performance":0,"accessibility":0,"best-practices":0,"seo":0}` twice, wrote the four raw files
and exited 0, overwriting good numbers in `docs/reports/` with nulls. The cause sat in
`runtimeError: ERRORED_DOCUMENT_REQUEST (Status code: 402)`, which nothing read. The script now
throws on `runtimeError` before writing anything, so a failed load cannot be committed as a score.
Lesson: a measurement tool that reports a number for a failed run is worse than one that crashes;
the committed files had to be restored from git to keep the report honest.
