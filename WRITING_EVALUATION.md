# IELTS Writing Evaluation Engine

## Overview

The Writing Evaluation Engine automatically assesses a submitted **Writing Workspace**
essay (Task 1 or Task 2) against the **four official IELTS Writing marking criteria**
and returns an **estimated** overall band, per-criterion bands, a confidence score,
strengths, weaknesses, specific quoted errors, and actionable improvement suggestions.

**Important disclaimer:** every evaluation is an **AI estimate**, not an official
IELTS score. The engine always sets `is_estimate = true` and the UI shows
_"this is NOT an official IELTS score."_ Only a certified IELTS examiner can issue an
official Writing band.

## Criteria (Task-aware)

The four criteria are assessed for both task types. The first criterion is the only
one that differs by task type:

| Criterion key                  | Task 1 label         | Task 2 label     |
|--------------------------------|----------------------|------------------|
| `task_response`                | Task Achievement     | Task Response    |
| `coherence_cohesion`           | Coherence and Cohesion | Coherence and Cohesion |
| `lexical_resource`             | Lexical Resource     | Lexical Resource |
| `grammatical_range_accuracy`   | Grammatical Range and Accuracy | Grammatical Range and Accuracy |

- **Task 1 (Academic report / letter)** — Task Achievement assesses coverage of all
  parts of the data/instructions and selection of key features.
- **Task 2 (Essay)** — Task Response assesses whether the position is clear, all parts
  of the prompt are addressed, and ideas are extended and supported.

## Architecture

```
  Frontend (Next.js)
    writing/page.tsx           — workspace + evaluation result modal
    services/api.ts            — writingEvaluationService → /api/v1/writing-evaluations
    types/writing-workspace.ts — WritingEvaluation types
        │
        ▼  (only the API; NO API keys / prompts reach the client)
  Backend (FastAPI)
    api/v1/writing_evaluation.py          — POST/GET evaluation endpoints
    services/writing_evaluation_engine.py — engine: orchestration + storage
    services/ai_service.py                — ALL AI calls (OpenAI), prompt + fallback
    ai/prompts.py                         — examiner system prompt (backend-only)
    repositories/writing_workspace_repo.py — DB access (create/get/update/list)
        │
        ▼
  Supabase / PostgreSQL
    writing_evaluations (034_writing_evaluations.sql)
```

Key points:

- **All AI calls happen on the backend** via `AIService.analyze_writing()`.
  The OpenAI API key is read from the `OPENAI_API_KEY` environment variable and never
  leaves the server. The examiner prompt lives in `app/ai/prompts.py` — it is **not**
  exposed to the frontend.
- When no API key is set, or the OpenAI call fails, `AIService` returns a
  **deterministic structural fallback** so the pipeline always works
  (`source = "deterministic_fallback"`).
- Each submitted essay owns an immutable evaluation record. The complete evaluation is
  stored in the `writing_evaluations` table and mirrored onto the submission's
  `ai_evaluation` JSONB for read-side convenience.

## Scoring Algorithm (documented)

### 1. Criterion bands

For each of the four criteria, the model returns a band in **0.0–9.0 in 0.5 steps**,
plus a strength, a weakness, specific errors (quoted verbatim from the essay), and
improvement suggestions. Every band is normalized/clamped with `_round_band()`:

```
round_to_half(v) = clamp( round( clamp(v, 0, 9) * 2 ) / 2, 0, 9 )
```

### 2. Overall band — NOT a blind average

The overall band is the **mean of the four criterion bands, rounded to the nearest
0.5** (the standard IELTS rounding rule). It is deliberately **not** a plain average
left unrounded:

```
overall_band = round_to_half( (c1 + c2 + c3 + c4) / 4 )
```

Example: `(6.0 + 6.0 + 6.0 + 6.5) / 4 = 6.125  →  overall = 6.0` (rounded to 0.5).

Implemented in `ai_service._compute_overall_band()` and mirrored/validated in the
engine. The same formula applies to Task 1 and Task 2.

### 3. Confidence score

A 0.00–1.00 signal reflecting how reliable the estimate is:

```
base = 0.7
length_bonus      = min(0.15, word_count / 1000)       # more words = more signal
spread            = max(bands) - min(bands)            # criterion disagreement
spread_penalty    = min(0.10, spread * 0.05)
consistency_bonus = max(0.0, 0.05 - spread_penalty)    # narrow spread → higher confidence
confidence = clamp( round(base + length_bonus + consistency_bonus - spread_penalty, 1), 0, 1 )
```

Implemented in `ai_service._compute_confidence()`.

## Data Model (SQL — migration 034)

`writing_evaluations` stores: `overall_band`, `confidence`, `criteria_bands`
(JSONB `{criterion: band}`), `criteria_detail` (JSONB full per-criterion detail),
flattened `strengths` / `weaknesses` / `errors` / `suggestions` (JSONB arrays),
`word_count`, `is_estimate` (always `true`), `source`, and lifecycle `status`
(`pending` → `evaluated`). Evaluations are immutable — RLS is enabled and only
SELECT/INSERT policies exist, each scoped to `auth.uid() = user_id`.

## API Reference

Base path: `/api/v1/writing-evaluations` (all endpoints require authentication)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{submission_id}` | `POST` | Run the AI evaluation on a submitted essay (`?task_type=task_1\|task_2`). |
| `/{submission_id}` | `GET`  | Fetch the stored evaluation for a submission. |
| `` (root)          | `GET`  | List the current user's evaluations (`?limit=20`). |

Response shape (`WritingEvaluation`):

```json
{
  "task_type": "task_2",
  "criteria": {
    "task_response": { "band": 7.0, "label": "Task Response",
                       "strength": "…", "weakness": "…",
                       "errors": ["…"], "suggestions": ["…"] },
    "coherence_cohesion": { … },
    "lexical_resource": { … },
    "grammatical_range_accuracy": { … }
  },
  "overall_band": 7.0,
  "confidence": 0.82,
  "is_estimate": true,
  "is_official": false,
  "word_count": 250,
  "source": "ai",
  "strengths": [ … ],
  "weaknesses": [ … ],
  "errors": [ … ],
  "suggestions": [ … ],
  "evaluation_status": "evaluated",
  "evaluated_at": "…"
}
```

## Security

- API keys and the examiner prompt are **backend-only**; the frontend only calls the
  HTTP endpoints and receives the already-shaped JSON.
- All operations are owner-scoped (queries filter by `user_id` derived from the JWT).
- Evaluations are immutable; users can only read/insert their own records.

## Verification

- `backend/tests/test_writing_evaluation_engine.py` — 29 deterministic tests covering
  band rounding, overall-band formula (proving it is **not** a plain average),
  confidence, engine business logic, owner-scoping, pending-record creation, AI flow,
  and immutability. AI calls are mocked — no live API calls.
- Full backend suite: `python -m pytest -q` passes.
- Frontend: `npx tsc --noEmit` passes clean.