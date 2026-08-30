# Backend Deployment Guide (Render)

This guide deploys the existing FastAPI backend as a long-running production
service. The frontend is deployed in a separate, later phase.

## 1. Platform & Configuration

- **Platform:** Render (free tier) — native Python runtime, no Docker needed.
- **Blueprint:** [`render.yaml`](../render.yaml) at the repository root defines
  the `ielts-ai-coach-api` web service with `rootDir: backend`.
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- **Health-check path:** `/api/health`
- **Runtime:** Python 3.11.9 (set via `PYTHON_VERSION`).

### Worker requirement (IMPORTANT)
The application stores state **in process** (30 s admin-dashboard TTL cache)
and starts an **asyncio background loop** for resource-health checks on
startup. Therefore the service must run with **exactly 1 worker**. Running
multiple workers would cause duplicate background checks and divergent
cached data. Horizontal scaling is out of scope until the cache and the
loop are externalized.

## 2. Environment Variables (names only — never commit values)

Set these in the Render dashboard (*Environment* tab) or via `render secrets`.

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Server-only Supabase key — NEVER expose client-side |
| `ADMIN_EMAILS` | ✅ | Comma-separated admin allowlist |
| `CORS_ORIGINS` | ✅ | Exact deployed frontend origin (no wildcard, no trailing slash) |
| `OPENAI_API_KEY` | recommended | Real AI evaluations; omit ⇒ deterministic mock fallback |
| `ENVIRONMENT` | auto | Set to `production` by `render.yaml` |
| `ENABLE_RESOURCE_HEALTH_BACKGROUND_CHECKS` | auto | `true` (keeps the existing background loop) |
| `DATABASE_URL` | optional | Defined in config but unused by runtime code |
| `RESOURCE_HEALTH_CHECK_INTERVAL_MINUTES` | optional | Default 30 |
| `RESOURCE_HEALTH_CHECK_TIMEOUT_SECONDS` | optional | Default 10 |
| `RESOURCE_HEALTH_CHECK_BATCH_SIZE` | optional | Default 50 |
| `MAX_AI_REQUESTS_PER_MINUTE_PER_USER` | optional | Default 60 |
| `DAILY_TOKEN_LIMIT_PER_USER` | optional | Default 100000 |
| `AI_COST_PER_1K_PROMPT` / `AI_COST_PER_1K_COMPLETION` | optional | Cost tracking |

The committed template is [`backend/.env.example`](.env.example) — placeholder
values only.

## 3. Database Migrations — MANUAL, DO NOT AUTO-RUN

Migrations are raw SQL files with **no migration runner**. They must be
applied deliberately, in order, by a human:

1. Open the Supabase dashboard → *SQL Editor*.
2. Run each file from `backend/app/db/migrations/` in numeric order
   (`001` → `010`), one at a time, verifying success after each.
3. Optional (once, after data exists): validate the `NOT VALID` foreign keys
   added by `008` with `ALTER TABLE ... VALIDATE CONSTRAINT ...;`.
4. Verify afterwards: create a test user, submit feedback, and confirm rows
   appear in the relevant tables.

Never run these automatically as part of deploy. If a migration fails,
stop and investigate before re-running.

## 4. Deploy Steps (requires a Render account — manual)

1. Commit and push this repository to GitHub (the connected remote).
2. Render dashboard → **New + → Blueprint** → select the repo → Render reads
   `render.yaml` and creates `ielts-ai-coach-api`.
3. When prompted, fill in the `sync: false` environment variables (Section 2).
4. Deploy. Render builds, starts the service, and polls `/api/health`.
5. Verify: `GET https://<service-url>/api/health` returns
   `{"status": "healthy", "service": "IELTS AI Coach"}`.

## 5. Post-Deploy Verification Checklist

- `/api/health` → 200
- `GET /api/admin/dashboard` without auth → **401** (admin gate active)
- `POST /api/feedback` without auth → 422/401 (validation/auth active)
- CORS: preflight `OPTIONS` from the deployed frontend origin succeeds;
  requests from unknown origins are rejected by the browser
- Monitoring events written to `monitoring_events` on induced errors
- AI usage rows written to `ai_usage` on `/api/assess` calls

## 6. Rollback

- **Render dashboard → deploys → "Rollback"** to the previous successful
  deploy (blueprint services keep every deploy image).
- To roll back application code, revert the offending commit and push;
  Render auto-deploys the branch.
- **Database rollbacks are manual:** migrations are not auto-run, so a bad
  migration must be reverted by hand in the Supabase SQL editor. This is why
  migrations are deliberately kept out of the deploy pipeline.

## 7. Free-Tier Notes

- Free web services **spin down after ~15 minutes of inactivity**; the first
  request afterwards incurs a cold-start delay. Acceptable for a free beta;
  upgrade to a paid plan if latency matters.
- Service restarts wipe the local `backend/app/logs/*.jsonl` files — durable
  monitoring lives in the Supabase `monitoring_events` / `ai_usage` tables.
