# Deployment & Operations Guide

How to deploy and run each part of **ShelfSense** using free-forever tiers only.

## 1. Web App on Vercel (`apps/web/`)

As of 2026-11-20 the Vercel team is blocked for exceeding the Hobby plan's fair-use limits: the
production alias answers `402 Payment Required` (`DEPLOYMENT_DISABLED`) and new deployments are
refused. Owner steps are item 4 in [docs/OWNER_TODO.md](OWNER_TODO.md). Everything below is correct
for the first push after the block is lifted.

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
4. The Vercel project's **Root Directory** is `apps/web` (ADR-012). Every push to `main` therefore
   builds the app directory on its own; `vercel.json` has no key for this setting, so a project
   rebuilt from scratch needs it set the same way:
   ```
   printf '%s' '{"rootDirectory":"apps/web"}' | vercel api \
     "/v9/projects/<project-id>?teamId=<team-id>" -X PATCH --input -
   ```
   A manual deploy from the same directory is:
   ```
   cd apps/web
   vercel deploy --prod --yes
   ```
   Batch web changes into one push per slice: Hobby counts deployments per day.

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
3. Push the FCOS Kaggle GPU kernel (it clones this repository, so push the code first):
   ```powershell
   kaggle kernels push -p training/runs/baseline
   kaggle kernels status ibrahimhossainsumon/shelfsense-fcos-training
   ```
4. Upload the exported int8 ONNX weights to a GitHub Release (`gh release create v0.1.0 ...`) and record its SHA-256 checksum (`shelfsense_training.kaggle_job.sha256_file`).
