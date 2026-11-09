# Deploying UniCompass (Vercel + Render)

```
Browser ──HTTPS──▶ Vercel (Next.js frontend + /api/backend proxy)
                        │  server-to-server, BACKEND_URL
                        ▼
                   Render: unicompass-api (FastAPI + background workers)
                        ├──▶ Render Postgres 16 (pgvector)
                        └──▶ Render Key Value (Redis)
```

The browser only ever talks to the Vercel domain. The Next.js server holds the login cookie and forwards
requests to the API, so **no CORS setup is needed**.

Rough cost: API on Render Starter ≈ $7/mo, Postgres Basic-256mb ≈ $6/mo, Redis free, Vercel Hobby free.

## 0. Before you start

1. **Commit and push your work.** Deployment builds from GitHub, and your branch has many uncommitted changes
   (`git status`). Merge or choose the branch you want to deploy.
2. Have these ready: a Groq API key, your SMTP details (the ones in `backend/.env`), and your own email for `ADMIN_EMAILS`.

## 1. Backend on Render

1. Render dashboard → **New → Blueprint** → connect the GitHub repo → pick the branch. Render reads `render.yaml`
   and proposes: `unicompass-api`, `unicompass-redis`, `unicompass-db`.
2. Fill in the prompted secrets (the ones marked `sync: false`):

   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key |
   | `ADMIN_EMAILS` | your email |
   | `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_STARTTLS` | copy from `backend/.env` |

   Leave the optional job-source keys empty if you don't use them.
3. Click **Apply**. The first build takes several minutes (it installs the embedding runtime).
   Migrations run automatically on start and create the `vector` extension.
4. When it's live, open `https://<your-api>.onrender.com/health` → `{"status":"healthy"}`.
   Copy that base URL for step 2.

Notes:
- Render's free web plan sleeps after 15 minutes, which would stop the background feed refresh, so the Blueprint uses Starter.
- Your `.env` shows SMTP port `588` (usual ports are 587/465). Confirm it with your provider; a wrong port means no OTP emails.
- If sign-up should work before email is configured, set `REQUIRE_EMAIL_VERIFICATION=false` on the API.

## 2. Frontend on Vercel

1. Vercel → **Add New → Project** → import the same repo.
2. **Root Directory: `frontend`** (important). Framework is auto-detected as Next.js.
3. Environment variable: `BACKEND_URL` = the Render API URL, e.g. `https://unicompass-api.onrender.com`
   (no trailing slash).
4. Deploy.

## 3. Verify

1. Open the Vercel URL → register → receive the OTP email → sign in.
2. Upload a resume on **Profile**. Open **Feed** and search; ask the assistant for an ATS check.
3. If something fails, check **Render → unicompass-api → Logs** and **Vercel → Deployment → Functions logs**.

Feed data appears after the first worker cycle (a few minutes after the API starts).

## Known limits on this setup

- **Resume size:** Vercel functions accept request bodies up to ~4.5 MB, so larger PDFs fail even though the API allows 5 MB.
- **Long streams:** the assistant and live-notification streams run through a Vercel function. Very long replies can hit the
  function time limit; notifications reconnect automatically.
- **Cold start:** the first request after a redeploy can be slow while the embedding model loads.
- **Spoofable IP for rate limits:** `--forwarded-allow-ips='*'` trusts the forwarded client IP; acceptable for a project, tighten for production.

## Updating

Push to the deployed branch: Render and Vercel both redeploy automatically. Database migrations run on API start.

## Alternative: everything on one machine

`docker compose --profile app up --build` runs Postgres, Redis, the API and a worker (set `SECRET_KEY` first).
Run the frontend with `cd frontend && npm run build && BACKEND_URL=http://localhost:8000 npm start`.
