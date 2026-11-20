# Owner to-do

Steps only the owner can do (sign-ups, phone checks, web consoles). Each item says
exactly where to click. When done, tell the assistant "<item> done" and it will verify
from the command line.

Never paste keys into chat or into any committed file. Keys go only into
`private/.env.local` (already created, gitignored, with empty slots).

---

## 1. Clerk account and app (needed for S4-02)

Status: **done** (verified 2026-11-17: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` present in `private/.env.local`).

---

## 2. Kaggle account, phone verification and API token (needed for S1-02 and S2-02)

Status: **done** (verified 2026-11-17 via `kaggle datasets list -s sku110k` and `kaggle config view`, username `ibrahimhossainsumon`).

### If the weekly Kaggle GPU quota is exhausted

All training logic lives in `training/train.py`, driven by `training/configs/fcos-dense-v3.json`,
and the Kaggle notebook only clones this repository and calls it. If Kaggle reports that your
weekly GPU quota is gone, wait for the quota to reset; there is no Colab fallback notebook in the
repository because it duplicated the same pipeline and drifted out of date.

---

## 2b. Google AI Studio key on this machine (needed to re-run the chat checks, 2026-11-19)

Status: **blocked**. `private/.env.local` does not exist on this machine, and Vercel will not
return a secret's value: `vercel env pull` writes `[SENSITIVE]` placeholders for all six
production secrets, including `GOOGLE_GENERATIVE_AI_API_KEY`. The value exists in the Vercel
project, so nothing needs creating — it only has to be copied to disk once.

1. Open https://aistudio.google.com/apikey in a browser where you are signed in.
2. Find the existing key for this project, click **Show key**, copy it.
3. In a terminal on this PC, run (do not paste the key into chat):
   ```
   mkdir -p private
   printf 'GOOGLE_GENERATIVE_AI_API_KEY=%s\n' 'PASTE_KEY_HERE' > private/.env.local
   ```
4. Tell the assistant it is done; it will verify with
   `node --experimental-strip-types scripts/eval-chat-live.mts`.

Until then the 2026-11-17 chat numbers in `docs/reports/chat-eval-s5.md` stand as the only
measurement, and they are not re-verified in the 2026-11-19 slices.

---

## 3. Keys for services you already have (needed for S4 and S5)

Status: **done in Vercel, missing on this PC** (verified 2026-11-19: all four keys are present in the Vercel project; `private/.env.local` itself is absent, see item 2b. `vercel whoami` and `neonctl me` are authenticated).

---

## 4. Vercel blocked the team for fair use (2026-11-20, the site is down)

Status: **blocked, owner only**. https://shelfsense-counter.vercel.app answers `402 Payment Required`
with `X-Vercel-Error: DEPLOYMENT_DISABLED`, and `vercel deploy --prod --yes` from `apps/web` prints:

```
x Your Team exceeded our fair use limits and has been blocked.
  Check the billing or feature requirement reported above with a team owner. Retry after that requirement is resolved.
```

The deployment itself is READY and still has the production alias; Vercel is refusing to serve it,
and it will refuse new deployments too. Nothing in the repository causes or clears this. The Root
Directory has already been fixed to `apps/web`, so pushes are configured correctly and will deploy
once the block is gone.

1. Open https://vercel.com/ibrahimsumon47s-projects in a browser where you are signed in.
2. Click the team **ibrahimsumon47's projects**, then **Settings**, then **Billing**. Read the notice
   at the top of that page: it names the limit that was exceeded and whether an upgrade or a support
   reply clears it.
3. Open the **Usage** tab and note this month's **Fast Data Transfer** and **Deployments** figures.
   Each production check uploads the 32.8 MB detector, which is what most of the transfer is.
4. If the notice asks for a support reply, open https://vercel.com/help, choose the project
   `shelfsense-counter` and ask for the block to be reviewed and lifted. Say what the site is and
   that it is a personal portfolio project on the Hobby plan.
5. If the notice instead offers an upgrade, decide whether to stay on Hobby. Under `Free forever
   only` in `AGENTS.md` an upgrade that needs a card is not acceptable, so a support reply is the
   only option that keeps this project within the rules.
6. When the notice is gone, tell the assistant "Vercel block done". It verifies with
   `curl -sI https://shelfsense-counter.vercel.app` (expect `200`), then pushes a commit and checks
   that the git-triggered deployment reaches READY on its own.

Do not delete the project or its deployments to clear the block: the block is on the team, not on a
deployment, and deleting removes the D1 database, the R2 bucket and the production secrets with it.
