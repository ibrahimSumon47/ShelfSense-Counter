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

## 3. Keys for services you already have (needed for S4 and S5)

Status: **done** (verified 2026-11-17: `GOOGLE_GENERATIVE_AI_API_KEY`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` present in `private/.env.local`, and `vercel whoami` + `neonctl me` authenticated).
