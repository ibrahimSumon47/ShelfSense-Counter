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

### Optional Colab Pro fallback (only if your 30-hour weekly Kaggle GPU quota is exhausted)

All training logic lives in `training/train.py` with configs in `training/configs/baseline.json` and `training/configs/improved.json`. If Kaggle reports that your weekly GPU quota is exhausted:
1. Open Google Colab (https://colab.research.google.com) → **File → Upload notebook** → upload `training/notebooks/colab_train.ipynb`.
2. Select **Runtime → Change runtime type → T4 GPU (or A100)** and run the cells.
3. Download the generated folder `repo/training/outputs/` from the Colab file browser and place its contents (`baseline/metrics.json`, `improved/metrics.json`, `improved/shelfsense-yolox-s-int8.onnx`, `improved/shelfsense-yolox-s-fp32.onnx`) into `E:\AI Engineering Projects\ShelfSense-Counter\training\outputs\` (gitignored).

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
