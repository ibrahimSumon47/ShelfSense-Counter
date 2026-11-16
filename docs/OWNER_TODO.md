# Owner to-do

Steps only the owner can do (sign-ups, phone checks, web consoles). Each item says
exactly where to click. When done, tell the assistant "<item> done" and it will verify
from the command line.

Never paste keys into chat or into any committed file. Keys go only into
`private/.env.local` (already created, gitignored, with empty slots).

---

## 1. Clerk account and app (needed for S4-02)

1. Open https://dashboard.clerk.com/sign-up and choose **Continue with GitHub**
   (use the ibrahimSumon47 account) or Google.
2. When asked to create an application, name it **ShelfSense**.
3. Under sign-in options leave **Email** on and turn on **Google**. Click **Create application**.
4. You land on a quick-start page. In the left menu open **Configure → API keys**
   (sometimes shown as **Developers → API keys**).
5. Copy **Publishable key** (starts with `pk_test_`) into `private/.env.local` after
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=`.
6. Copy **Secret key** (starts with `sk_test_`, click the eye icon to reveal) after
   `CLERK_SECRET_KEY=`.
7. Save the file. Do not choose any paid plan; the free plan is the default.

Status: open

---

## 2. Kaggle account, phone verification and API token (needed for S1-02 and S2-02)

1. Open https://www.kaggle.com and click **Register**. Sign up with Google.
2. Phone verification (required for free GPU and internet in notebooks):
   click your **profile picture** (top right) → **Settings** → scroll to
   **Phone verification** → enter your mobile number with country code (+880…) →
   type the SMS code. Virtual numbers are usually refused.
3. API token: on the same **Settings** page scroll to **API**.
   - If you see **Generate New Token**: click it, copy the token, and save it as a
     plain text file at `C:\Users\ibrah\.kaggle\access_token` (no extension, token only).
   - If you see **Create New Token** (legacy): it downloads `kaggle.json`. Move that
     file to `C:\Users\ibrah\.kaggle\kaggle.json`.
4. Create the folder `C:\Users\ibrah\.kaggle` first if it does not exist.
5. Tell the assistant "Kaggle done". It will run `kaggle datasets list -s sku110k`
   to confirm the token works, without printing it.

Status: open

---

## 3. Keys for services you already have (needed for S4 and S5)

Fill these slots in `private/.env.local`:

- `GOOGLE_GENERATIVE_AI_API_KEY=` your Google AI Studio key
  (https://aistudio.google.com/apikey, copy the existing key).
- `CLOUDINARY_CLOUD_NAME=`, `CLOUDINARY_API_KEY=`, `CLOUDINARY_API_SECRET=`
  (https://console.cloudinary.com → **Settings** (gear) → **API Keys**; the cloud name is
  shown at the top of the dashboard).
- Neon and Vercel need no keys pasted: the assistant will use `neonctl` and `vercel`
  after you log in once. If either CLI asks you to log in, run in a terminal:
  `vercel login` and `neonctl auth`, and finish the browser step.

Status: open
