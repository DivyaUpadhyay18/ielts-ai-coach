# Intelligent Recommendation Engine

## Overview

The Intelligent Recommendation Engine is a **deterministic, rule-based** resource recommendation system (NO AI) for the IELTS AI Coach. It analyzes the user's IELTS profile and study context to recommend the most relevant learning resources from the catalog.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer                                 │
│  GET  /api/v1/recommendations                                    │
│  GET  /api/v1/recommendations/history                            │
│  POST /api/v1/recommendations/track                            │
│  GET  /api/v1/recommendations/stats                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                     Service Layer                               │
│  RecommendationEngineService                                     │
│  - gather_user_context()                                        │
│  - fetch_candidate_resources()                                  │
│  - score_resources()                                            │
│  - apply_filters()                                               │
│  - rank_and_limit()                                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                  Repository Layer                               │
│  RecommendationRepository                                       │
│  ResourceRepository                                             │
│  (User, Task, Progress repos accessed internally)              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   Database                                      │
│  resources, users, tasks, study_sessions,                       │
│  daily_missions, recommendation_logs,                         │
│  recommendation_resource_view, recommendation_cache             │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

The recommendation engine pulls from these data sources:

1. **User Profile** (users table):
   - `current_band` — current IELTS band score
   - `target_band` — target IELTS band score
   - `exam_date` — exam date for remaining days calculation
   - `daily_minutes_budget` — available study time per day
   - `weakest_skill` — skills user is weakest in (array)
   - `strongest_skill` — skills user is strongest in (array)

2. **Today's Missions** (daily_missions table):
   - Skill assigned for today's study session

3. **Past Performance** (study_sessions table):
   - Task completion rates per skill
   - Study minutes per skill
   - XP earned per skill

4. **Completed Resources** (study_sessions table):
   - Resources with `source_type = 'resource'` or `'recommendation'`
   - Used to exclude previously seen resources

5. **Mock Scores** (study_sessions table):
   - Mock test band scores for band alignment scoring

6. **Resource Catalog** (resources table):
   - All available resources with full metadata

## Ranking Algorithm

### Overview

The ranking algorithm assigns each resource a **relevance score** from 0 to 100 based on weighted factors. Resources are then sorted by score descending. The maximum achievable positive score is 90 points, with a -20 repetition penalty for previously completed resources.

### Scoring Factors

| Factor | Max Points | Weight | Description |
|--------|-----------|--------|-------------|
| Band Alignment | 20.0 | 20% | How well the resource's band range matches the user's current→target band gap |
| Skill Match | 25.0 | 25% | Match with weakest skill, today's mission skill, or sub-skill |
| Official Bonus | 10.0 | 10% | Official resources (e.g., Cambridge, British Council) get a bonus |
| Verified Bonus | 8.0 | 8% | Verified resources get a bonus |
| Difficulty Alignment | 7.0 | 7% | Resource difficulty matches user's appropriate level |
| Time Fit | 5.0 | 5% | Resource estimated time fits within daily study budget |
| Popularity | 3.0 | 3% | Normalized popularity score |
| Rating | 2.0 | 2% | Average user rating (0-5 scale) |
| Recency | 5.0 | 5% | Recently added resources get a bonus |
| Type Diversity | 5.0 | 5% | Quiz/Flashcard resources get a bonus for diversity |
| Repetition Penalty | -20.0 | — | Penalize resources user has already seen |

**Total possible positive score: 90 points** (before repetition penalty of -20)

### Detailed Factor Calculations

#### 1. Band Alignment (20 points)

```
band_gap = target_band - current_band
resource_range = [resource.minimum_band, resource.maximum_band]

IF resource_range overlaps with [current_band, target_band]:
    overlap = min(resource.max, target_band) - max(resource.min, current_band)
    score = 20 * (overlap / band_gap)
ELSE IF resource is within 1.0 band of gap:
    score = 20 * 0.5  (partial credit)
ELSE:
    score = 0
```

#### 2. Skill Match (25 points)

```
match_score = 0

IF resource.skill == target_skill (weakest):
    match_score += 25 * 0.6 = 15

IF resource.skill == today_mission_skill:
    match_score += 25 * 0.4 = 10

IF resource.sub_skill == sub_skill:
    match_score += 25 * 0.3 = 7.5

TOTAL = min(match_score, 25)
```

#### 3. Official Bonus (10 points)

```
score = 10 if resource.official == True else 0
```

#### 4. Verified Bonus (8 points)

```
score = 8 if resource.verified == True else 0
```

#### 5. Difficulty Alignment (7 points)

```
band_gap = target_band - current_band

IF band_gap <= 1.0 and remaining_days > 30:
    appropriate = "beginner"
ELIF band_gap > 2.0 and remaining_days < 14:
    appropriate = "advanced"
ELSE:
    appropriate = "intermediate"

score = 7 if resource.difficulty matches OR resource.difficulty == "all_levels"
score = 7 * 0.8 if resource.difficulty == appropriate
score = 0 otherwise
```

#### 6. Time Fit (5 points)

```
estimated_time = resource.estimated_time

IF estimated_time <= daily_budget:
    score = 5
ELIF estimated_time <= daily_budget * 2:
    score = 5 * 0.5 = 2.5
ELSE:
    score = 0
```

#### 7. Popularity (3 points)

```
popularity = resource.popularity_score
score = min(popularity / 1000, 1.0) * 3
```

#### 8. Rating (2 points)

```
score = (resource.rating / 5.0) * 2
```

#### 9. Recency (5 points)

```
days_since_created = (now - resource.created_at).days

IF days_since_created <= 30:
    score = 5
ELIF days_since_created <= 90:
    score = 5 * 0.5 = 2.5
ELIF days_since_created <= 180:
    score = 5 * 0.2 = 1.0
ELSE:
    score = 0
```

#### 10. Type Diversity (5 points)

```
IF resource.type IN ("Quiz", "Flashcard"):
    score = 5  (encourage variety)
ELSE:
    score = 0
```

#### 11. Repetition Penalty (-20 points)

```
IF resource.id IN completed_resource_ids:
    score = -20
ELSE:
    score = 0
```

### Final Score

```
total_score = sum of all factors
total_score = max(0, min(100, total_score))
```

## Rules

### Rule 1: Never recommend completed resources unless revision is required
Resources that the user has previously interacted with (tracked in `study_sessions` with `source_type = 'resource'` or `'recommendation'`) are excluded from recommendations unless `include_completed=True` is explicitly passed. When included, they receive a -20 point repetition penalty.

### Rule 2: Prioritize official resources
Official resources (from Cambridge, British Council, IDP, etc.) receive a +10 point bonus in the scoring algorithm. This ensures they naturally rank higher in recommendations.

### Rule 3: Avoid repeating YouTube videos
When multiple YouTube video resources exist, only the first one is considered. Subsequent YouTube videos are skipped to ensure diversity in video recommendations.

### Rule 4: Mix resource types
The algorithm gives a +5 point bonus to Quiz and Flashcard resources to encourage a diverse mix of:
- Video
- PDF
- Quiz
- Practice
- Vocabulary (Flashcard)

## API Endpoints

### GET /api/v1/recommendations

Get personalized resource recommendations.

**Query Parameters:**
- `skill` (optional): Filter by skill (Reading, Listening, Writing, Speaking, Vocabulary, Grammar)
- `sub_skill` (optional): Filter by sub-skill
- `resource_type` (optional): Filter by type (Video, PDF, Website, Quiz, Flashcard)
- `limit` (default: 10, max: 50): Number of recommendations to return
- `include_completed` (default: false): Include previously completed resources
- `only_verified` (default: true): Only recommend verified resources

**Response:**
```json
{
  "user_id": "uuid",
  "run_date": "2026-08-02",
  "current_band": 6.0,
  "target_band": 7.5,
  "weakest_skill": "Writing",
  "today_mission_skill": "Writing",
  "sub_skill": null,
  "estimated_time": 60,
  "remaining_days": 45,
  "recommendations": [
    {
      "resource": { ... },
      "score": 85.5,
      "relevance_factors": { "band_alignment": 18.0, ... },
      "rationale": "skill-match (Writing); official; verified"
    }
  ],
  "ranking_algorithm": "v1.0-rule-based-weighted-score",
  "metadata": { "total_candidates": 50, "total_completed_skipped": 12, "log_id": "..." }
}
```

### GET /api/v1/recommendations/history

Get the user's recommendation history.

### POST /api/v1/recommendations/track

Track user interaction with a recommended resource.

### GET /api/v1/recommendations/stats

Get statistics about recommendations served.

## Configuration

All scoring constants are defined in `backend/app/services/recommendation_engine_service.py` and can be tuned without algorithm changes:

```python
SCORE_BAND_ALIGNMENT = 20.0
SCORE_SKILL_MATCH = 25.0
SCORE_OFFICIAL = 10.0
SCORE_VERIFIED = 8.0
SCORE_DIFFICULTY_ALIGN = 7.0
SCORE_TIME_FIT = 5.0
SCORE_POPULARITY = 3.0
SCORE_RATING = 2.0
SCORE_RECENT = 5.0
SCORE_TYPE_MIX = 5.0
SCORE_REPETITION_PENALTY = -20.0
```

## Verification

Run the verification script:
```bash
python backend/verify_recommendation_engine.py
```

This runs 50+ checks covering:
- Band alignment scoring
- Skill match scoring
- Official/verified bonuses
- Difficulty alignment
- Time fit
- Repetition penalty
- YouTube deduplication
- Type diversity enforcement
- Rule enforcement (no completed, prioritize official, etc.)