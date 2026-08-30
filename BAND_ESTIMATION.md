# Band Estimation Engine

## Overview

The Band Estimation Engine is a **deterministic (NO AI)** system that maps a user's
six skill-wise band scores (Reading, Listening, Writing, Speaking, Vocabulary, Grammar)
to an estimated overall IELTS band score, per-skill bands, a confidence score,
weakest/strongest skill identification, and human-readable explanations for every
score assigned.

Results are **stored** in the `band_estimations` table (one snapshot per user per day,
upsert semantics) so users can track their estimated bands over time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          API Layer                                   │
│  POST /api/v1/band-estimation    — estimate overall band from scores │
│  GET  /api/v1/band-estimation/latest — fetch most recent estimation   │
│  GET  /api/v1/band-estimation/history — paginated estimation history  │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                       Service Layer                                  │
│  BandEstimationService                                                │
│   - estimate()          — runs the full algorithm & stores result     │
│   - get_latest()        — fetches most recent snapshot              │
│   - get_history()       — paginated list of snapshots               │
│   - _round_to_band()    — round to nearest 0.5 (IELTS step)         │
│   - _compute_overall_band() — mean of 4 official skills → 0.5 step   │
│   - _compute_confidence()    — dispersion + completeness → 0-100    │
│   - _compute_weakest_skills() / _compute_strongest_skills()         │
│   - _explain_skill()   — deterministic per-skill explanation        │
│   - _build_formulas()  — human-readable formula docs                 │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                     Repository Layer                                 │
│  BandEstimationRepository                                            │
│   - save_result()   — upsert (UPSERT on user_id, run_date)           │
│   - get_latest()    — most recent snapshot for a user               │
│   - list_results()  — paginated list                                 │
│   - count_results() — total count                                    │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────────┐
│                       Database                                       │
│  band_estimations table (PostgreSQL / Supabase)                     │
│  with Row Level Security (owner-scoped)                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Input

A POST body containing six skill-wise band scores, each in the range **0.0 – 9.0**.
Inputs are rounded to the nearest **0.5** (IELTS band step) by the Pydantic validator.

| Field          | Type  | Range  | Description                                  |
|----------------|-------|--------|----------------------------------------------|
| `reading`      | float | 0–9    | Reading comprehension score                  |
| `listening`    | float | 0–9    | Listening comprehension score                |
| `writing`      | float | 0–9    | Writing task performance score               |
| `speaking`     | float | 0–9    | Speaking fluency score                       |
| `vocabulary`   | float | 0–9    | Vocabulary breadth score                     |
| `grammar`      | float | 0–9    | Grammar accuracy score                       |

### Example Request

```json
POST /api/v1/band-estimation
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "reading": 7.3,
  "listening": 7.7,
  "writing": 6.2,
  "speaking": 5.8,
  "vocabulary": 8.1,
  "grammar": 4.9
}
```

> After input validation, the scores above are rounded to: 7.5, 7.5, 6.0, 6.0, 8.0, 5.0.

## Algorithm

All computations are **pure functions** with no randomness and no AI. Every result is
fully reproducible and reversible from the stored `raw_input`.

### 1. Skill-wise Bands

Each input score is rounded to the nearest 0.5 (IELTS band convention).

```
band = round(raw_input * 2) / 2
```

Vocabulary and Grammar are **supporting inputs**: they influence per-skill explanations
but do **not** enter the overall band calculation (only the 4 official skills do).

### 2. Estimated Overall Band

The overall band is the arithmetic mean of the **four official IELTS skills**
(Reading, Listening, Writing, Speaking), rounded to the nearest 0.5, clamped to [0, 9].

```
overall = round( (reading + listening + writing + speaking) / 4 / 0.5 ) * 0.5
overall = clamp(overall, 0.0, 9.0)
```

**Example:** `(7.5 + 7.5 + 6.0 + 6.0) / 4 = 6.75 → round to 7.0`

### 3. Confidence Score (0–100)

Confidence reflects how reliable the estimate is. It is penalised by **score dispersion**
(bands spread far apart are less predictable) and reduced when **official skills are
missing** (provided as 0.0).

```
dispersion        = max(official_bands) - min(official_bands)
dispersion_steps  = round(dispersion / 0.5)
dispersion_penalty = dispersion_steps * 3.0          # 3 points per 0.5-band of spread

provided          = count of official skills with raw_input > 0
completeness      = provided / 4
completeness_bonus = completeness * 1.0 * 100        # full marks when all 4 provided

confidence = clamp(completeness_bonus - dispersion_penalty, 0, 100)
```

| Confidence Label | Threshold   |
|------------------|-------------|
| `very_high`      | >= 90       |
| `high`           | >= 75       |
| `medium`         | >= 50       |
| `low`            | < 50        |

**Example (perfect consistency):** all four skills = 7.0 → dispersion = 0,
completeness = 100% → confidence = **100.0 (very_high)**.

**Example (1 band dispersion):** bands 6.0, 7.0, 7.0, 7.0 → dispersion = 1.0,
steps = 2, penalty = 6 → confidence = **94.0 (very_high)**.

### 4. Weakest & Strongest Skills

Skills are sorted by their band score and the top 3 are returned.

```
weakest  = sort_all_skills_by_band_ascending()[:3]
strongest = sort_all_skills_by_band_descending()[:3]
```

Ties are broken alphabetically by skill name for deterministic output.

### 5. Explanations

Each skill receives a deterministic explanation that references the raw input, the
rounded band, and a proficiency-level descriptor:

| Band Range | Level     | Description                                         |
|------------|-----------|-----------------------------------------------------|
| 8.0–9.0    | expert    | consistently accurate with sophisticated control    |
| 7.0–7.5    | proficient| mostly accurate with some complexity                |
| 6.0–6.5    | competent | adequate control with occasional errors            |
| 5.0–5.5    | modest    | limited control with frequent errors               |
| < 5.0      | elementary| significant difficulty with basic communication    |

If a skill is not provided (raw input = 0.0), the explanation states that the score
defaults to 0.0.

## Output Schema

```typescript
interface BandEstimationResponse {
  user_id: string;
  generated_at: string;     // ISO-8601 UTC (timezone-aware)
  run_date: string;          // YYYY-MM-DD
  overall_band: number;      // 0.0–9.0, 0.5 steps
  confidence_score: number;  // 0–100
  confidence_label: "low" | "medium" | "high" | "very_high";
  skill_bands: Record<string, number>;       // { reading: 7.5, ... }
  weakest_skills: string[];                   // ascending
  strongest_skills: string[];                 // descending
  explanations: Record<string, string>;       // per-skill rationale
  formulas: Record<string, string>;           // human-readable formula docs
  raw_input: Record<string, number>;          // audit snapshot
}
```

### Example Response

```json
{
  "user_id": "uuid",
  "generated_at": "2026-08-06T14:32:10.123456+00:00",
  "run_date": "2026-08-06",
  "overall_band": 7.0,
  "confidence_score": 94.0,
  "confidence_label": "very_high",
  "skill_bands": {
    "reading": 7.5, "listening": 7.5, "writing": 6.0,
    "speaking": 6.0, "vocabulary": 8.0, "grammar": 5.0
  },
  "weakest_skills": ["grammar", "writing", "speaking"],
  "strongest_skills": ["vocabulary", "reading", "listening"],
  "explanations": {
    "reading": "Reading: Band 7.5 (raw input: 7.3). Assessment: proficient — mostly accurate with some complexity.",
    "grammar": "Grammar: Band 5.0 (raw input: 4.9). Assessment: modest — limited control with frequent errors."
  },
  "formulas": { ... },
  "raw_input": { "reading": 7.5, "listening": 7.5, ... }
}
```

## API Endpoints

### `POST /api/v1/band-estimation`

Estimate your overall IELTS band from six skill-wise scores.

**Request Body:** `BandEstimationInput` (see Input above)

**Response:** `BandEstimationResponse`

**Behaviour:**
- Runs the deterministic algorithm.
- Stores the result (upsert by `user_id` + `run_date`).
- Returns the full estimation payload.

### `GET /api/v1/band-estimation/latest`

Returns the most recent stored estimation for the authenticated user.

**Response:** `BandEstimationResponse` (or 404 if none exists).

### `GET /api/v1/band-estimation/history`

Returns a paginated list of stored estimations (most recent first).

**Query Parameters:**
- `limit` (default 20, 1–100): page size.
- `offset` (default 0): pagination offset.

**Response:**
```json
{
  "items": [ { ...BandEstimationHistoryItem } ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

## Database Schema

```sql
CREATE TABLE band_estimations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  run_date        DATE NOT NULL DEFAULT CURRENT_DATE,
  overall_band    NUMERIC(3,1) NOT NULL,          -- 0.0–9.0 in 0.5 steps
  confidence_score NUMERIC(5,2) NOT NULL,        -- 0–100
  confidence_label TEXT NOT NULL DEFAULT 'medium'
                    CHECK (confidence_label IN ('low','medium','high','very_high')),
  skill_bands     JSONB NOT NULL DEFAULT '{}',
  weakest_skills  JSONB NOT NULL DEFAULT '[]',
  strongest_skills JSONB NOT NULL DEFAULT '[]',
  explanations    JSONB NOT NULL DEFAULT '{}',
  formulas_json   JSONB NOT NULL DEFAULT '{}',
  raw_input       JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, run_date)
);
```

- **Row Level Security** is enabled; users can only read/insert/update/delete their
  own estimations (`auth.uid() = user_id`).
- **One estimation per user per day** — re-running on the same day overwrites the
  previous snapshot via `UPSERT (user_id, run_date)`.
- Indexes on `user_id` and `(user_id, run_date DESC)` for fast lookups.

## Configuration

All tunable constants live at the top of
`backend/app/services/band_estimation_service.py`:

| Constant                         | Default | Description                                  |
|----------------------------------|---------|----------------------------------------------|
| `BAND_STEP`                      | 0.5     | IELTS band increment                         |
| `CONFIDENCE_HIGH`                | 90.0    | very_high threshold                          |
| `CONFIDENCE_MEDIUM`              | 75.0    | high threshold                               |
| `CONFIDENCE_LOW`                 | 50.0    | medium threshold                             |
| `DISPERSION_PENALTY_PER_STEP`    | 3.0     | Confidence lost per 0.5-band of dispersion   |
| `COMPLETENESS_WEIGHT`            | 1.0     | Base completeness multiplier (x100 bonus)    |

## Verification

Run the verification script:

```bash
python backend/verify_band_estimation.py
```

This runs 23 checks covering:
- Skill constants (`OVERALL_SKILLS` = 4, `ALL_SKILLS` = 6)
- Input validation & rounding (Pydantic `field_validator`)
- Overall band computation (mean of 4 official skills to 0.5 step)
- Confidence score computation (perfect, 1-band dispersion, 3-skills-with-zero)
- Weakest / strongest skill ordering (asc / desc, tie-break by name)
- End-to-end estimation with storage-safe path (db=None)
- Formula documentation and explanation generation

All checks pass: **ALL TESTS PASSED**.

## Frontend

The UI is available at `/estimation` (linked from the sidebar under "Band Estimation"):

- **Input form** — six number inputs (0–9) for each skill, default 6.0.
- **Results card** — overall band, confidence score + progress bar, skill-wise bands
  with weakest/strongest badges.
- **Explanations card** — per-skill rationale ("why this score was assigned").
- **Formula reference** — transparent display of every formula used.
- **History view** — paginated table of past estimations.

Frontend service (`bandEstimationService` in `src/services/api.ts`):
- `estimate(data)`       -> `POST /band-estimation`
- `getLatest()`          -> `GET /band-estimation/latest`
- `getHistory({limit, offset})` -> `GET /band-estimation/history`
