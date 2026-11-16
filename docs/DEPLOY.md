# Deployment & Operations Guide

How to deploy and run each part of **ShelfSense** using free-forever tiers only.

## 1. Web App on Vercel (`apps/web/`)

1. Complete the account steps in [docs/OWNER_TODO.md](OWNER_TODO.md) so `private/.env.local` has your Clerk, Neon (`DATABASE_URL`), Cloudinary, and Google AI Studio keys.
2. Push each secret from `private/.env.local` to Vercel Production without printing it:
   ```powershell
   vercel link --yes
   # Push each environment variable to production
   Get-Content private/.env.local | Where-Object { $_ -match '^[A-Z0-9_]+=.+$' } | ForEach-Object {
     $parts = $_ -split '=', 2
     $parts[1] | vercel env add $parts[0] production
   }
   ```
3. Provision the Neon Postgres tables (`stores`, `aisles`, `shelves`, `scans`) using the SQL DDL in `apps/web/src/lib/schema.ts`.
4. Deploy once per finished web slice (respecting Vercel Hobby's daily deployment limit):
   ```powershell
   vercel --prod
   ```

## 2. Python Package, CLI & Batch FastAPI Service (`python/`)

Interactive detection runs in the browser via `onnxruntime-web`, so no cloud Python server is required (see `docs/DECISIONS.md`, ADR-003 and ADR-008). For local batch processing:

### Install with `uv` (foreground only)

```powershell
uv sync --directory python --extra dev
```

### Run the CLI

```powershell
uv run --directory python shelfsense count path/to/shelf.jpg --threshold 15 --json
```

### Run the FastAPI Batch Server Locally or via Docker

```powershell
uv run --directory python uvicorn shelfsense.api:app --host 127.0.0.1 --port 8000
```

Or build the container image from `python/`:

```powershell
docker build -t shelfsense-batch ./python
docker run --rm -p 8000:8000 shelfsense-batch
```

## 3. Kaggle GPU Training & ONNX Export (`training/`)

1. Ensure `~/.kaggle/access_token` or `~/.kaggle/kaggle.json` is in place and phone verification is enabled on Kaggle (`docs/OWNER_TODO.md` item 2).
2. Download datasets into `training/data/` (gitignored):
   ```powershell
   uv run --directory training python -m shelfsense_training.download --dataset all
   ```
3. Stage and push the YOLOX Kaggle GPU kernel:
   ```powershell
   kaggle kernels push -p training/runs/baseline
   kaggle kernels status <owner>/shelfsense-yolox-train
   ```
4. Upload the exported int8 ONNX weights to a GitHub Release (`gh release create v0.1.0 ...`) and record its SHA-256 checksum (`shelfsense_training.kaggle_job.sha256_file`).
