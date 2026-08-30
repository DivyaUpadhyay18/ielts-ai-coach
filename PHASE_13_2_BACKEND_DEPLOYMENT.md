# Phase 13.2 — Backend Deployment

## Date
2026-08-28

## 1. Hosting Platform Selected
**Render** (free tier), via the committed blueprint [`render.yaml`](render.yaml).

## 2. Why It Was Selected
- **Free tier for web services** — Railway no longer offers a free plan (trial only); a free beta needs a genuinely free long-running service.
- **Native Python runtime** — the repo has no Dockerfile; Render runs `pip install -r requirements.txt` directly. No new containerization layer was added.
- **Declarative `render.yaml`** with native `healthCheckPath` and monorepo `rootDir: backend` support — minimal config, no code changes.
- The app requires a **long-running single process** (in-process TTL cache + asyncio background loop); Render web services are exactly that.

## 3. Deployment Configuration
Created (config only — nothing was pushed or deployed yet):
- **`render.yaml`** (repo root): web service `ielts-ai-coach-api`, `runtime: python`, `rootDir: backend`, `plan: free`, Python 3.11.9.
  - `buildCommand: pip install -r requirements.txt`
  - `healthCheckPath: /api/health`
  - All secrets use `sync: false` → set manually in the dashboard; **no secret values are in the repo**.
- **`backend/DEPLOYMENT.md`**: full deployment guide (env vars, commands, migrations, rollback).
- **`.gitignore` hygiene fix (Phase 13.1 item #5):** added the exception `!backend/.env.example` so the placeholder-only template is now trackable. Verified: `backend/.env.example` now appears in `git status`; real `backend/.env` and `frontend/.env.local` remain ignored; no new env file got tracked.

## 4. Environment Variables Required (names only — never values)
| Variable | Required |
|---|---|
| `SUPABASE_URL` | ✅ |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ (server-only) |
| `ADMIN_EMAILS` | ✅ |
| `CORS_ORIGINS` | ✅ (exact future frontend origin; **not hard-coded anywhere**) |
| `OPENAI_API_KEY` | recommended (mock fallback without it) |
| `ENVIRONMENT` | auto (`production` via render.yaml) |
| `ENABLE_RESOURCE_HEALTH_BACKGROUND_CHECKS` | auto (`true` via render.yaml) |
| `DATABASE_URL`, `RESOURCE_HEALTH_CHECK_*`, `MAX_AI_REQUESTS_PER_MINUTE_PER_USER`, `DAILY_TOKEN_LIMIT_PER_USER`, `AI_COST_PER_1K_*` | optional (defaults) |

## 5. Start Command
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```
Uses the existing entry point (`app.main:app`); `$PORT` is supplied by Render.

## 6. Health Check
`GET /api/health` → `{"status":"healthy","service":"IELTS AI Coach"}` (verified locally; configured as Render's `healthCheckPath`).

## 7. Worker Configuration
**Exactly 1 worker** — hardcoded in the start command. Verified locally: `--workers 1` starts a single Uvicorn worker. Rationale preserved: the 30 s TTL cache is in-process and the asyncio resource-health loop starts on startup; multiple workers would duplicate background checks and diverge the cache.

## 8. CORS Configuration
Fully driven by `CORS_ORIGINS` (no hard-coded production URL). Verified both directions locally with a live server:
- Preflight (`OPTIONS`) from **allowlisted** origin → `200`, `Access-Control-Allow-Origin` echoed, `authorization,content-type` allowed.
- Preflight from **non-allowlisted** origin → **rejected (400)** — correct deny behavior.

## 9. Database Migration Status
**NOT run against production** (per instruction). Migrations 001–010 remain raw SQL with no runner. Step-by-step manual instructions are in `backend/DEPLOYMENT.md` §3 (Supabase SQL editor, in order, verifying after each). Production DB changes are deliberate, human-executed actions.

## 10. Deployment URL
**PENDING** — the service does not exist yet. Creating it requires a Render account and real secret values, which only you can provide (see §14 / next steps).

## 11. Tests Performed (all local, all passing)
| Check | Result |
|---|---|
| Full backend test suite (`pytest`) | ✅ **171 passed**, 16 subtests |
| Production dependency install check | ✅ All 8 pinned deps import at exact versions (`fastapi 0.115.5`, `uvicorn 0.32.0`, `pydantic 2.9.2`, `pydantic-settings 2.6.1`, `supabase 2.9.1`, `python-dotenv 1.0.1`, `python-multipart 0.0.17`, `httpx 0.27.2`) |
| App import / startup check with production start command | ✅ `Uvicorn running on http://0.0.0.0:8123`, single worker |
| Health endpoint test | ✅ Exact expected JSON payload |
| Frontend↔backend API compatibility | ✅ Every frontend call path has a matching backend route: `/feedback` (GET/POST/{id}), `/ratings` (GET/POST), `/analytics/events` (GET/POST), `/admin/feedback` (GET + PATCH `{id}`), `/admin/ratings`, `/admin/users` (+ PATCH `{id}/deactivate`), all other `/admin/*` (dashboard, analytics, ai-usage, system-health, resources) |
| `.gitignore` fix validation | ✅ template visible; real env files still ignored |
| CORS allow + deny | ✅ (see §8) |

## 12. API Verification Results (local live server)
| Probe | Result |
|---|---|
| `GET /api/health` | ✅ 200, correct payload |
| `GET /api/admin/dashboard` (no auth) | ✅ **401** — admin gate active |
| `POST /api/assess` (no auth) | ✅ **401** — auth enforced before body validation |
| `OPTIONS /api/feedback` (allowed origin) | ✅ 200 + correct CORS headers |
| `OPTIONS` (disallowed origin) | ✅ rejected |

**Live-deployment verification is pending** — it becomes possible only after you complete the dashboard steps below. The post-deploy checklist (Supabase connectivity, monitoring events, AI usage tracking, AI integration, live CORS) is pre-written in `backend/DEPLOYMENT.md` §5 and will be executed against the deployed URL as soon as it exists.

## 13. Remaining Issues
| # | Severity | Item |
|---|---|---|
| 1 | Pending | Actual Render deployment + live verification (blocked on account/credentials — see §14) |
| 2 | LOW | Render free tier spins the service down after ~15 min idle → cold-start latency on first request. Acceptable for free beta; upgrade later if needed |
| 3 | LOW | Local JSONL monitoring logs are wiped on redeploy (ephemeral FS) — durable sink is Supabase `monitoring_events` |
| 4 | INFO | Changes (render.yaml, .gitignore, backend/.env.example, DEPLOYMENT.md) are **uncommitted** — they must be committed & pushed to GitHub before Render can read the blueprint |

## 14. Rollback Instructions
- **Render dashboard → service → Deploys → Rollback** to the previous successful deploy (every deploy image is retained).
- **Code rollback:** revert the offending commit and push; Render auto-redeploys.
- **Database rollback:** migrations are never auto-run; a bad migration must be reverted manually in the Supabase SQL editor.

---

## ⛔ STOP — Action Required From You (manual dashboard step)

Per your instruction, I've stopped here. I cannot create accounts or hold real credentials. To complete the backend deployment, you need to:

1. **Commit & push** the prepared files to GitHub:
   `render.yaml`, `.gitignore`, `backend/.env.example`, `backend/DEPLOYMENT.md` (and this report).
2. **Sign in to Render** (render.com) with GitHub, click **New + → Blueprint**, select this repository — Render will read `render.yaml` and offer to create **`ielts-ai-coach-api`**.
3. When prompted for the `sync: false` variables, enter the **real values** (from your Supabase dashboard / OpenAI account — never commit them):
   - `SUPABASE_URL` — your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY` — service-role key (server-only)
   - `ADMIN_EMAILS` — the beta admin email(s)
   - `CORS_ORIGINS` — the future frontend origin (e.g. `https://<your-app>.vercel.app` — placeholder is fine for now; update it in Phase 13.3)
   - `OPENAI_API_KEY` — optional but recommended for real evaluations
4. Click **Apply/Deploy** and wait for the build + health check to pass.
5. **Send me the deployed service URL** (e.g. `https://ielts-ai-coach-api.onrender.com`) — then I will run the full live verification suite (health, auth gates, Supabase/DB connectivity, CORS, error handling, monitoring & AI-usage event writes) against the real backend.

I did not invent any credentials or configuration values, did not deploy the frontend, and did not proceed to Phase 13.3.


