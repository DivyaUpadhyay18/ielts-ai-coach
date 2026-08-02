# Resource Recommendation Engine — Design Document

**Role:** Senior Database Architect  
**Document:** Resource Engine Architecture  
**Status:** Draft for review & approval  

---

## 0. Executive Summary

The Resource Recommendation Engine is the **content discovery layer** of IELTS AI Coach. It curates a library of **100% free, high-quality IELTS preparation materials** from trusted providers and delivers personalized recommendations to each user based on their skill gaps, current band level, target band, study preferences, and learning history. The engine powers the "Study Resources" page, the "Recommended for You" widget on the dashboard, and the resource-attachment system within the Adaptive Scheduler (each scheduled task can link to a relevant resource).

---

## 1. Resource Taxonomy

### 1.1 Resource Types (10 types)

| Type | Code | Description | Example |
|---|---|---|---|
| YouTube Video | `youtube` | Full lessons, walkthroughs, tips | "IELTS Writing Task 2 — Full Guide" by E2 IELTS |
| Official PDF | `pdf` | Official IELTS practice tests, sample papers | Cambridge IELTS 18 Sample Test |
| Practice Website | `website` | Interactive practice platforms | IELTSOnlineTests.com |
| Vocabulary Sheet | `vocab_sheet` | Thematic word lists, collocations | "Academic Word List — Week 1" |
| Grammar Guide | `grammar_guide` | Grammar rules, exercises, explanations | "Complex Sentences for Band 7+" |
| Listening Exercise | `listening` | Audio + questions for Listening section | British Council Listening Practice |
| Writing Sample | `writing_sample` | Band 9 sample essays with examiner comments | "Task 2 — Opinion Essay Band 9" |
| Speaking Practice | `speaking` | Mock speaking questions + model answers | "Speaking Part 2 — Cue Card Drills" |
| Full Practice Test | `practice_test` | Complete timed mock tests | "Full Academic IELTS Mock Test" |
| Strategy Guide | `strategy` | Tips, time management, exam techniques | "How to Manage Time in Reading" |

### 1.2 Provider Sources (7 official providers — all FREE)

| Provider | Code | Content Focus | Content Volume Target |
|---|---|---|---|
| **British Council** | `british_council` | Official practice tests, listening exercises, webinars | 100+ resources |
| **IDP** | `idp` | Official IELTS materials, computer-delivered test simulations | 80+ resources |
| **IELTS Liz** | `ielts_liz` | Writing samples, topic-specific vocabulary, video lessons | 200+ resources |
| **IELTS Advantage** | `ielts_advantage` | Writing task structures, speaking frameworks, grammar guides | 150+ resources |
| **E2 IELTS** | `e2_ielts` | YouTube video lessons, method frameworks, mock tests | 120+ resources |
| **Cambridge English** | `cambridge` | Official sample papers, vocabulary lists, grammar exercises | 60+ resources |
| **IELTS Online Tests** | `ielts_online` | Free practice tests, daily quizzes, score calculators | 500+ tests |

### 1.3 Skill Tags (Primary & Secondary)

| Primary Skill | Code | Secondary Skills |
|---|---|---|
| Writing Task 1 | `writing_task1` | Data description, process, map, letter (GT) |
| Writing Task 2 | `writing_task2` | Opinion, discussion, problem/solution, advantage/disadvantage |
| Speaking Part 1 | `speaking_part1` | Introduction, familiar topics, fluency |
| Speaking Part 2 | `speaking_part2` | Long turn, cue card, storytelling |
| Speaking Part 3 | `speaking_part3` | Abstract discussion, follow-up questions |
| Listening | `listening` | Section 1–4, multiple choice, map labeling |
| Reading | `reading` | Skimming, scanning, true/false/not given, matching headings |
| Vocabulary | `vocabulary` | Academic word list, topic-specific, collocations, phrasal verbs |
| Grammar | `grammar` | Tenses, complex sentences, articles, punctuation |
| Pronunciation | `pronunciation` | Intonation, word stress, connected speech |
| Exam Strategy | `strategy` | Time management, question analysis, anxiety management |

---

## 2. Database Structure

### 2.1 `resources` — Core Catalog Table

```sql
CREATE TABLE resources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core Metadata
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,              -- 2–3 sentence summary
    provider        TEXT NOT NULL,              -- british_council | idp | ielts_liz | ielts_advantage | e2_ielts | cambridge | ielts_online
    resource_type   TEXT NOT NULL,              -- youtube | pdf | website | vocab_sheet | grammar_guide | listening | writing_sample | speaking | practice_test | strategy
    
    -- Categorization
    primary_skill   TEXT NOT NULL,              -- writing_task1 | writing_task2 | speaking_part1 | … | vocabulary | grammar | strategy
    secondary_skills TEXT[] DEFAULT '{}',       -- Array of secondary skill codes
    tags            TEXT[] DEFAULT '{}',        -- Free-form tags: ["academic", "general", "bar_chart", "opinion_essay"]
    
    -- Difficulty & Band Alignment
    difficulty_level TEXT NOT NULL,             -- beginner | intermediate | advanced | all_levels
    min_band        NUMERIC(2,1) DEFAULT 0.0,  -- 0.0 = no minimum
    max_band        NUMERIC(2,1) DEFAULT 9.0,  -- 9.0 = no maximum
    target_band     NUMERIC(2,1),              -- Specific band this resource helps achieve (NULL = general)
    
    -- Access & Duration
    url             TEXT NOT NULL,              -- Direct link to the resource
    is_free         BOOLEAN DEFAULT TRUE,       -- Always TRUE (this catalog is free-only)
    duration_minutes INT,                      -- Estimated time to consume (NULL = variable)
    is_offline_capable BOOLEAN DEFAULT FALSE,  -- Can be downloaded?
    
    -- Quality & Curation
    curator_rating  NUMERIC(2,1),              -- 1.0–5.0 rating by IELTS experts
    student_rating_avg NUMERIC(2,1) DEFAULT 0.0, -- Aggregated user rating
    student_rating_count INT DEFAULT 0,
    is_featured     BOOLEAN DEFAULT FALSE,      -- Editor's pick
    is_official     BOOLEAN DEFAULT FALSE,      -- From British Council / IDP / Cambridge
    
    -- Embedding (for semantic search)
    embedding       VECTOR(1536),              -- OpenAI text-embedding-ada-002
    
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_provider CHECK (provider IN ('british_council', 'idp', 'ielts_liz', 'ielts_advantage', 'e2_ielts', 'cambridge', 'ielts_online')),
    CONSTRAINT valid_resource_type CHECK (resource_type IN ('youtube', 'pdf', 'website', 'vocab_sheet', 'grammar_guide', 'listening', 'writing_sample', 'speaking', 'practice_test', 'strategy')),
    CONSTRAINT valid_difficulty CHECK (difficulty_level IN ('beginner', 'intermediate', 'advanced', 'all_levels')),
    CONSTRAINT valid_band_range CHECK (min_band >= 0.0 AND max_band <= 9.0 AND min_band <= max_band),
    CONSTRAINT valid_rating CHECK (curator_rating >= 1.0 AND curator_rating <= 5.0)
);

-- Indexes
CREATE INDEX idx_resources_provider ON resources(provider);
CREATE INDEX idx_resources_type ON resources(resource_type);
CREATE INDEX idx_resources_primary_skill ON resources(primary_skill);
CREATE INDEX idx_resources_difficulty ON resources(difficulty_level);
CREATE INDEX idx_resources_band_range ON resources(min_band, max_band);
CREATE INDEX idx_resources_rating ON resources(curator_rating DESC);
CREATE INDEX idx_resources_tags ON resources USING GIN(tags);
CREATE INDEX idx_resources_secondary_skills ON resources USING GIN(secondary_skills);
CREATE INDEX idx_resources_embedding ON resources USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_resources_featured ON resources(is_featured) WHERE is_featured = TRUE;
CREATE INDEX idx_resources_official ON resources(is_official) WHERE is_official = TRUE;
```

### 2.2 `resource_bookmarks` — User Bookmark System

```sql
CREATE TABLE resource_bookmarks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id     UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    
    -- Bookmark metadata
    collection_name TEXT DEFAULT 'default',     -- Custom collections: "favorites", "to-study", "writing", "vocabulary"
    notes           TEXT,                       -- User's personal note about this resource
    priority        INT DEFAULT 0,              -- User's sort order (0 = no priority)
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, resource_id)                -- One bookmark per user per resource
);

CREATE INDEX idx_bookmarks_user ON resource_bookmarks(user_id);
CREATE INDEX idx_bookmarks_collection ON resource_bookmarks(user_id, collection_name);
CREATE INDEX idx_bookmarks_priority ON resource_bookmarks(user_id, priority DESC);
```

### 2.3 `resource_completions` — Completion Tracking

```sql
CREATE TABLE resource_completions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id     UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    
    -- Completion metadata
    status          TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | completed | abandoned
    progress_percent INT DEFAULT 0,                       -- 0–100 (e.g., video watched 70%)
    time_spent_minutes INT,                               -- Actual time spent
    rating          INT,                                   -- 1–5 star rating by user
    review_notes    TEXT,                                  -- User's reflection
    
    -- Linked scheduler task (if completed via a study plan task)
    task_id         UUID REFERENCES tasks(id) ON DELETE SET NULL,
    
    -- Timestamps
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, resource_id)                -- One completion record per user per resource
);

CREATE INDEX idx_completions_user ON resource_completions(user_id);
CREATE INDEX idx_completions_status ON resource_completions(user_id, status);
CREATE INDEX idx_completions_rating ON resource_completions(user_id, rating DESC) WHERE rating IS NOT NULL;
```

### 2.4 `resource_recommendations` — Generated Recommendations

```sql
CREATE TABLE resource_recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id     UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    
    -- Recommendation metadata
    reason          TEXT NOT NULL,              -- Human-readable explanation: "Based on your Writing Task 2 skill gap"
    reason_code     TEXT NOT NULL,              -- Machine-readable: 'skill_gap' | 'band_match' | 'weakest_skill' | 'popular' | 'new' | 'task_related' | 'mock_review'
    score           NUMERIC(5,2) NOT NULL,      -- Relevance score 0.00–100.00 (used for ranking)
    rank            INT,                        -- Position in the user's recommendation list
    is_dismissed    BOOLEAN DEFAULT FALSE,      -- User dismissed this recommendation
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                -- Recommendation expiry (e.g., 7 days)
    
    UNIQUE(user_id, resource_id, reason_code)   -- Avoid duplicate recommendations with same reason
);

CREATE INDEX idx_recommendations_user ON resource_recommendations(user_id, score DESC);
CREATE INDEX idx_recommendations_active ON resource_recommendations(user_id, is_dismissed, expires_at)
    WHERE is_dismissed = FALSE AND expires_at > NOW();
```

### 2.5 `resource_views` — Analytics Events

```sql
CREATE TABLE resource_views (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resource_id     UUID NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    session_id      UUID,                       -- Track user session for grouping
    view_duration_seconds INT,                  -- How long user stayed
    source          TEXT,                        -- 'recommendation' | 'search' | 'bookmark' | 'task_link' | 'browse'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_views_user ON resource_views(user_id, created_at DESC);
CREATE INDEX idx_views_resource ON resource_views(resource_id, created_at DESC);
CREATE INDEX idx_views_source ON resource_views(source);
-- Partition by month for scalability
```

---

## 3. Band-Wise Categorization

### 3.1 Difficulty Levels ↔ Band Mapping

| Difficulty Level | Band Range | Typical User Profile | Content Focus |
|---|---|---|---|
| **Beginner** | 0.0 – 5.0 | First-time test taker, weak fundamentals | Grammar basics, test format, vocabulary building, simple sentence structures |
| **Intermediate** | 5.0 – 6.5 | Some exposure, knows the format, inconsistent scores | Task structure, coherence, common vocabulary, speaking fluency |
| **Advanced** | 6.5 – 8.0 | Strong foundation, polishing for high score | Complex grammar, lexical resource, sophisticated arguments, nuance |
| **All Levels** | 0.0 – 9.0 | Universal content | Strategy guides, exam tips, time management, official practice tests |

### 3.2 Band-Wise Resource Distribution Targets

| Provider | Beginner | Intermediate | Advanced | All Levels |
|---|---|---|---|---|
| British Council | 20% | 35% | 25% | 20% |
| IDP | 15% | 30% | 30% | 25% |
| IELTS Liz | 40% | 35% | 20% | 5% |
| IELTS Advantage | 20% | 30% | 40% | 10% |
| E2 IELTS | 25% | 35% | 30% | 10% |
| Cambridge | 10% | 25% | 25% | 40% |
| IELTS Online Tests | 30% | 30% | 20% | 20% |

### 3.3 Resource Recommendation by Band (Algorithm)

```
PROCEDURE RecommendByBand(user_current_band, user_target_band):
    // Resources are eligible if user's current band falls within the resource's band range
    // AND the resource helps bridge the gap toward the target band
    
    band_gap = user_target_band - user_current_band
    
    IF band_gap >= 2.0:
        // Large gap: prioritize beginner and intermediate resources
        // Focus on foundation skills
        priority_types = ['grammar_guide', 'vocab_sheet', 'strategy', 'writing_sample']
        priority_difficulty = ['beginner', 'intermediate']
        
    ELIF band_gap >= 1.0 AND band_gap < 2.0:
        // Medium gap: mix of intermediate and advanced
        priority_types = ['writing_sample', 'speaking', 'listening', 'youtube', 'practice_test']
        priority_difficulty = ['intermediate', 'advanced']
        
    ELSE:
        // Small gap (< 1.0): advanced and targeted
        priority_types = ['practice_test', 'youtube', 'writing_sample', 'speaking']
        priority_difficulty = ['advanced']
        
    RETURN FilterResources(priority_types, priority_difficulty, user_current_band)
```

---

## 4. Filtering Logic

### 4.1 Filter Dimensions

| Dimension | Values | UI Component |
|---|---|---|
| Skill | All skills from §1.3 | Category buttons |
| Resource Type | All types from §1.1 | Dropdown / chips |
| Provider | All providers from §1.2 | Checkbox group |
| Difficulty | Beginner / Intermediate / Advanced / All Levels | Segmented control |
| Band Range | 0–9 (slider or numeric input) | Range slider |
| Duration | < 5 min / 5–15 min / 15–30 min / 30+ min | Button group |
| Rating | ≥ 3 / ≥ 4 / ≥ 4.5 | Star filter |
| Official Only | Boolean toggle | Toggle switch |
| Bookmarked | Boolean (show only bookmarked) | Toggle switch |

### 4.2 Filter Query Builder

```
PROCEDURE BuildFilterQuery(user, filters):
    query = "SELECT * FROM resources WHERE is_free = TRUE"
    params = []
    
    // 1. Skill filter (primary_skill OR secondary_skills contains)
    IF filters.skills:
        query += " AND (primary_skill = ANY($params) OR secondary_skills && $params)"
        params.append(filters.skills)
    
    // 2. Resource type filter
    IF filters.resource_types:
        query += " AND resource_type = ANY($params)"
        params.append(filters.resource_types)
    
    // 3. Provider filter
    IF filters.providers:
        query += " AND provider = ANY($params)"
        params.append(filters.providers)
    
    // 4. Difficulty filter
    IF filters.difficulties:
        query += " AND difficulty_level = ANY($params)"
        params.append(filters.difficulties)
    
    // 5. Band range filter (user's current band)
    // Show resources where user's band falls within the resource's band range
    query += " AND $user_band BETWEEN min_band AND max_band"
    params.append(user.current_band)
    
    // 6. Duration filter
    IF filters.max_duration:
        query += " AND (duration_minutes IS NULL OR duration_minutes <= $params)"
        params.append(filters.max_duration)
    
    // 7. Rating filter
    IF filters.min_rating:
        query += " AND student_rating_avg >= $params"
        params.append(filters.min_rating)
    
    // 8. Official only
    IF filters.official_only:
        query += " AND is_official = TRUE"
    
    // 9. Search (full-text search on title + description + tags)
    IF filters.search_query:
        query += " AND (title ILIKE $search OR description ILIKE $search OR $search = ANY(tags))"
        params.append(f'%{filters.search_query}%')
    
    // 10. Exclude already completed resources
    query += " AND id NOT IN (SELECT resource_id FROM resource_completions WHERE user_id = $user_id AND status = 'completed')"
    
    // 11. Ordering
    query += " ORDER BY curator_rating DESC, student_rating_count DESC"
    
    // 12. Pagination
    query += " LIMIT $limit OFFSET $offset"
    params.extend([filters.limit, filters.offset])
    
    RETURN ExecuteQuery(query, params)
```

---

## 5. Recommendation Logic

### 5.1 Recommendation Score Calculation

The recommendation engine computes a **composite score** for each (user, resource) pair:

```
SCORE = 0.30 * SkillGapScore + 0.20 * BandMatchScore + 0.15 * PopularityScore
        + 0.10 * DiversityScore + 0.10 * RecencyScore + 0.10 * ProviderScore
        + 0.05 * SchedulerAlignmentScore
```

### 5.2 Score Components

#### 5.2.1 SkillGapScore (Weight: 0.30)

Measures how well the resource addresses the user's weakest skills.

```
PROCEDURE CalculateSkillGapScore(user, resource):
    // Get user's skill gaps from diagnostic + latest assessments
    skill_gaps = GetUserSkillGaps(user)  // Returns {skill: gap_deficit} sorted descending
    
    // Resource's primary skill
    resource_skill = resource.primary_skill
    
    // If resource targets the user's #1 weakness
    IF resource_skill == skill_gaps[0].skill:
        RETURN 100.0
    
    // If resource targets one of top 3 weaknesses
    top_3_skills = [s.skill for s in skill_gaps[:3]]
    IF resource_skill in top_3_skills:
        position = top_3_skills.index(resource_skill)
        RETURN 80.0 - (position * 15)  // 80, 65, 50
    
    // If resource targets a secondary skill that is a weakness
    FOR secondary IN resource.secondary_skills:
        IF secondary in top_3_skills:
            RETURN 40.0
    
    // Default
    RETURN 20.0
```

#### 5.2.2 BandMatchScore (Weight: 0.20)

Measures how well the resource's difficulty aligns with the user's current band.

```
PROCEDURE CalculateBandMatchScore(user, resource):
    user_band = GetCurrentAverageBand(user)
    
    // Resource is designed for exactly this band level
    IF resource.min_band <= user_band AND resource.max_band >= user_band:
        // Perfect match: how centered is the resource?
        mid_band = (resource.min_band + resource.max_band) / 2
        proximity = 1.0 - (ABS(user_band - mid_band) / 4.5)  // 4.5 = max distance (9.0/2)
        RETURN proximity * 100.0
    
    // Resource is slightly above user's level (aspirational)
    IF resource.min_band > user_band AND resource.min_band - user_band <= 0.5:
        RETURN 60.0
    
    // Resource is slightly below (review)
    IF resource.max_band < user_band AND user_band - resource.max_band <= 0.5:
        RETURN 50.0
    
    // Too far above or below
    RETURN 10.0
```

#### 5.2.3 PopularityScore (Weight: 0.15)

Based on how other users have engaged with the resource.

```
PROCEDURE CalculatePopularityScore(resource):
    // Factors: completion rate, average rating, view count, bookmark count
    completions = CountCompletions(resource.id)
    avg_rating = resource.student_rating_avg
    view_count = CountViews(resource.id)
    bookmark_count = CountBookmarks(resource.id)
    
    // Normalize each factor to 0–100
    completion_rate = completions / MAX_EXPECTED_COMPLETIONS * 100
    rating_score = (avg_rating / 5.0) * 100
    view_score = MIN(view_count / 1000, 1.0) * 100  // Cap at 1000 views
    bookmark_score = MIN(bookmark_count / 100, 1.0) * 100  // Cap at 100 bookmarks
    
    score = 0.30 * completion_rate + 0.35 * rating_score + 0.20 * view_score + 0.15 * bookmark_score
    RETURN score
```

#### 5.2.4 DiversityScore (Weight: 0.10)

Ensures the user sees a variety of providers, types, and skills rather than 10 results from the same provider.

```
PROCEDURE CalculateDiversityScore(user, resource, recent_recommendations):
    // Count how many times this provider appears in the last 10 recommendations
    same_provider_count = COUNT(recent_recommendations WHERE provider == resource.provider)
    same_type_count = COUNT(recent_recommendations WHERE resource_type == resource.resource_type)
    
    // Penalize if same provider appears too frequently
    provider_penalty = MAX(0, same_provider_count - 2) * 15  // -15 per extra occurrence
    type_penalty = MAX(0, same_type_count - 3) * 10          // -10 per extra occurrence
    
    score = 100.0 - provider_penalty - type_penalty
    RETURN MAX(score, 0)
```

#### 5.2.5 RecencyScore (Weight: 0.10)

Promotes newly added resources to ensure freshness.

```
PROCEDURE CalculateRecencyScore(resource):
    days_since_added = NOW() - resource.created_at
    
    IF days_since_added <= 7:
        RETURN 100.0  // New this week
    ELIF days_since_added <= 30:
        RETURN 80.0   // New this month
    ELIF days_since_added <= 90:
        RETURN 50.0   // Added this quarter
    ELSE:
        RETURN 20.0   // Older content
```

#### 5.2.6 ProviderScore (Weight: 0.10)

Official sources get a baseline boost.

```
PROCEDURE CalculateProviderScore(resource):
    IF resource.is_official:
        RETURN 100.0  // British Council, IDP, Cambridge
    ELIF resource.provider IN ('ielts_liz', 'ielts_advantage', 'e2_ielts'):
        RETURN 80.0   // Trusted third-party
    ELSE:
        RETURN 50.0   // Community or other
```

#### 5.2.7 SchedulerAlignmentScore (Weight: 0.05)

Links resources to the user's current phase in the Adaptive Scheduler.

```
PROCEDURE CalculateSchedulerAlignmentScore(user, resource):
    current_phase = GetCurrentPhase(user)
    
    phase_skill_map = {
        'foundation': ['grammar_guide', 'vocab_sheet', 'writing_sample'],
        'skill_building': ['writing_sample', 'speaking', 'listening', 'youtube'],
        'advanced': ['youtube', 'writing_sample', 'speaking', 'practice_test'],
        'mock_tests': ['practice_test', 'website', 'strategy'],
        'revision': ['strategy', 'vocab_sheet', 'grammar_guide']
    }
    
    IF resource.resource_type IN phase_skill_map[current_phase]:
        RETURN 100.0
    ELSE:
        RETURN 30.0
```

---

## 6. Automatic Recommendation Algorithm

### 6.1 Trigger Events

Recommendations are regenerated when any of the following occurs:

| Event | Trigger | Action |
|---|---|---|
| **New user signup** | After diagnostic complete | Generate initial 10 recommendations |
| **Assessment completed** | New band score recorded | Re-rank recommendations |
| **Phase transition** | Scheduler moves to next phase | Update phase-aligned recommendations |
| **Daily** | Cron job (midnight) | Refresh 3 stale recommendations |
| **Resource consumed** | Completion recorded | Replace with next best |
| **Manual refresh** | User pulls to refresh | Regenerate all recommendations |

### 6.2 Recommendation Generation Algorithm

```
PROCEDURE GenerateRecommendations(user, count=10):
    // 1. Get all eligible resources (not completed, not dismissed)
    candidates = SELECT * FROM resources
                 WHERE id NOT IN (
                     SELECT resource_id FROM resource_completions
                     WHERE user_id = user.id AND status = 'completed'
                 )
                 AND min_band <= user.current_band
                 AND max_band >= user.current_band
    
    // 2. Calculate composite score for each candidate
    scored_candidates = []
    recent_recommendations = GetRecentRecommendations(user, 10)
    
    FOR resource IN candidates:
        score = (
            0.30 * CalculateSkillGapScore(user, resource) +
            0.20 * CalculateBandMatchScore(user, resource) +
            0.15 * CalculatePopularityScore(resource) +
            0.10 * CalculateDiversityScore(user, resource, recent_recommendations) +
            0.10 * CalculateRecencyScore(resource) +
            0.10 * CalculateProviderScore(resource) +
            0.05 * CalculateSchedulerAlignmentScore(user, resource)
        )
        scored_candidates.append((resource, score))
    
    // 3. Sort by score descending
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    // 4. Ensure diversity in top results
    final_recommendations = []
    used_providers = set()
    used_types = set()
    used_skills = set()
    
    FOR resource, score IN scored_candidates:
        // Top 3: no diversity constraints (best matches)
        IF len(final_recommendations) < 3:
            final_recommendations.append(resource)
            used_providers.add(resource.provider)
            used_types.add(resource.resource_type)
            used_skills.add(resource.primary_skill)
            CONTINUE
        
        // Positions 4–7: enforce provider diversity
        IF len(final_recommendations) < 7:
            IF resource.provider in used_providers AND len(used_providers) < 4:
                CONTINUE  // Skip if we already have 3+ different providers
            IF resource.resource_type in used_types AND len(used_types) < 3:
                CONTINUE  // Skip if we already have 3+ different types
        
        // Positions 8–10: enforce skill diversity
        IF len(final_recommendations) >= 7:
            IF resource.primary_skill in used_skills AND len(used_skills) < 5:
                CONTINUE  // Skip if we already have 5+ different skills
        
        final_recommendations.append(resource)
        used_providers.add(resource.provider)
        used_types.add(resource.resource_type)
        used_skills.add(resource.primary_skill)
        
        IF len(final_recommendations) >= count:
            BREAK
    
    // 5. Persist recommendations
    ClearExistingRecommendations(user.id)
    FOR rank, resource IN enumerate(final_recommendations):
        InsertRecommendation(
            user_id=user.id,
            resource_id=resource.id,
            reason=GenerateReason(user, resource),
            reason_code=GetReasonCode(user, resource),
            score=scored_candidates[rank][1],
            rank=rank,
            expires_at=NOW() + INTERVAL '7 days'
        )
    
    RETURN final_recommendations
```

### 6.3 Reason Generation

```
PROCEDURE GenerateReason(user, resource):
    skill_gaps = GetUserSkillGaps(user)
    current_band = GetCurrentAverageBand(user)
    current_phase = GetCurrentPhase(user)
    
    // Check if resource targets weakest skill
    IF resource.primary_skill == skill_gaps[0].skill:
        RETURN f"Targets your weakest skill ({FormatSkillName(resource.primary_skill)}) — improving this could boost your overall band"
    
    // Check if resource matches current phase
    phase_resource_map = {
        'foundation': 'Great for building your foundation',
        'skill_building': 'Perfect for your current skill-building phase',
        'advanced': 'Helps you master advanced techniques',
        'mock_tests': 'Essential for your mock test phase',
        'revision': 'Ideal for your revision phase'
    }
    IF current_phase in phase_resource_map:
        RETURN phase_resource_map[current_phase]
    
    // Check difficulty alignment
    IF resource.difficulty_level == 'beginner' AND current_band <= 5.0:
        RETURN "Recommended for your current band level"
    ELIF resource.difficulty_level == 'intermediate' AND current_band BETWEEN 5.0 AND 6.5:
        RETURN "Matches your current proficiency level"
    ELIF resource.difficulty_level == 'advanced' AND current_band >= 6.5:
        RETURN "Challenging content to push you to the next band"
    
    // Default reasons
    reasons = [
        "Popular among students preparing for IELTS",
        "Highly rated by our community",
        "Official resource from a trusted provider",
        "Newly added to our library",
        "Complements your current study plan"
    ]
    RETURN SELECT_RANDOM(reasons)
```

---

## 7. Bookmark System

### 7.1 Features

| Feature | Description |
|---|---|
| **Add Bookmark** | Save a resource with optional collection name, notes, and priority |
| **Collections** | User-created folders: "Favorites", "To Study", "Writing", "Vocabulary", "This Week" |
| **Default Collection** | Resources bookmarked without specifying a collection go to "default" |
| **Reorder** | Drag-and-drop reordering within a collection |
| **Notes** | Personal annotation per bookmark (e.g., "Watch this after finishing Task 2 lesson") |
| **Bulk Actions** | Select multiple bookmarks → move to collection, mark as completed, or remove |
| **Export** | Export bookmarks as a JSON/CSV list (links + notes) |
| **Search within Bookmarks** | Full-text search across bookmarked resource titles and user notes |

### 7.2 Bookmark API

```
POST   /api/v1/resources/{id}/bookmark        → Add bookmark (with optional collection + notes)
DELETE /api/v1/resources/{id}/bookmark        → Remove bookmark
GET    /api/v1/bookmarks                      → List all bookmarks (optionally filtered by collection)
PUT    /api/v1/bookmarks/{id}                 → Update collection, notes, priority
POST   /api/v1/bookmarks/reorder              → Bulk reorder
GET    /api/v1/bookmarks/collections          → List all collection names for user
```

---

## 8. Resource Completion Tracking

### 8.1 Completion States

| State | Meaning | Trigger |
|---|---|---|
| `in_progress` | User started but hasn't finished | User clicks "Open Resource" |
| `completed` | User finished the resource | User clicks "Mark Complete" or reaches end of video/article |
| `abandoned` | User started but won't finish | Explicit "Skip" or no activity for 7 days on same resource |

### 8.2 Automatic Progress Detection

```
// For YouTube videos:
//   - Track watch percentage via embedded player API
//   - Auto-mark as "completed" when watch >= 90%

// For PDFs and articles:
//   - Track scroll depth via JavaScript
//   - Auto-mark as "completed" when scroll >= 90% or time_spent >= estimated_duration

// For practice websites:
//   - User explicitly marks as complete
//   - Or auto-complete if user submits answers on the linked site

// For vocabulary sheets and grammar guides:
//   - User marks as complete after studying
//   - Or auto-complete after 15 minutes of page focus
```

### 8.3 Completion Rewards

```
PROCEDURE OnResourceCompleted(user, resource):
    // 1. Update completion record
    UpdateCompletion(user.id, resource.id, 'completed')
    
    // 2. Log study session time
    LogStudySession(user.id, resource.duration_minutes, 'resource', resource.id)
    
    // 3. Update daily activity (for streak)
    UpdateDailyActivity(user.id, resource.duration_minutes)
    
    // 4. If resource is linked to a scheduler task, update task status
    IF resource.task_id:
        MarkTaskCompleted(resource.task_id)
    
    // 5. Increment resource completion count in analytics
    IncrementMetric(user.id, 'resources_completed')
    
    // 6. Check if any achievement is unlocked
    CheckResourceAchievements(user.id)
    
    // 7. Generate next recommendation to replace this one
    GenerateSingleRecommendation(user, exclude=[resource.id])
```

---

## 9. Estimated Study Time Logic

### 9.1 Duration Calculation

```
PROCEDURE EstimateStudyTime(resource):
    IF resource.duration_minutes IS NOT NULL:
        RETURN resource.duration_minutes
    
    // Estimate based on type and content length
    estimation_rules = {
        'youtube':         video_length_in_minutes + 5,       // Watch time + note-taking
        'pdf':             page_count * 2,                     // 2 minutes per page
        'website':         section_count * 5,                  // 5 minutes per section
        'vocab_sheet':     word_count / 10,                    // 10 words per minute
        'grammar_guide':   rule_count * 3,                     // 3 minutes per rule
        'listening':       audio_length_in_minutes + 10,       // Audio + answering questions
        'writing_sample':  estimated_read_time + 5,            // Read + analyze
        'speaking':        prompt_count * 3,                   // 3 minutes per prompt
        'practice_test':   180,                                // Full test = 3 hours
        'strategy':        estimated_read_time + 2             // Read + reflect
    }
    
    RETURN estimation_rules.get(resource.resource_type, 15)  // Default 15 min
```

### 9.2 Duration Display Format

```
PROCEDURE FormatDuration(minutes):
    IF minutes < 60:
        RETURN f"{minutes} min"
    ELSE:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        IF remaining_minutes == 0:
            RETURN f"{hours} hr"
        ELSE:
            RETURN f"{hours} hr {remaining_minutes} min"
```

### 9.3 Duration Filter Groups

| Group | Range | Label |
|---|---|---|
| Quick | 1–5 min | "Quick Read" |
| Short | 5–15 min | "Short Session" |
| Medium | 15–30 min | "Standard Lesson" |
| Long | 30–60 min | "Deep Dive" |
| Extended | 60+ min | "Full Session" |

---

## 10. Content Curation & Ingestion Pipeline

### 10.1 Initial Content Target

| Provider | Minimum Resources | Target Resources |
|---|---|---|
| British Council | 50 | 100+ |
| IDP | 40 | 80+ |
| IELTS Liz | 100 | 200+ |
| IELTS Advantage | 75 | 150+ |
| E2 IELTS | 60 | 120+ |
| Cambridge | 30 | 60+ |
| IELTS Online Tests | 200 | 500+ |
| **Total** | **555** | **1,210+** |

### 10.2 Curation Workflow

```
1. DISCOVERY
   → AI crawler + manual curation by IELTS experts
   → Verify resource is still accessible (link checker)
   → Verify resource is free (no paywall detected)

2. CLASSIFICATION
   → Assign: provider, resource_type, primary_skill, secondary_skills, tags
   → Assign: difficulty_level, min_band, max_band
   → Estimate: duration_minutes
   → Rate: curator_rating (1.0–5.0)

3. INDEXING
   → Generate embedding via OpenAI text-embedding-ada-002
   → Store in resources.embedding
   → Build full-text search index

4. PUBLISHING
   → Set is_featured flag for top 10% of resources
   → Set is_official flag for British Council / IDP / Cambridge
   → Resource becomes available in recommendations
```

### 10.3 Content Refresh Cadence

| Activity | Frequency |
|---|---|
| Link checker (dead link detection) | Daily |
| New resource ingestion | Weekly |
| Rating recalculation | Weekly |
| Embedding regeneration (for updated resources) | Monthly |
| Provider content audit | Quarterly |

---

## 11. Dashboard Integration Points

### 11.1 "Recommended for You" Widget

```
Location: Dashboard page, right sidebar or below "Today's Tasks"
Display: 3–4 resource cards with:
  - Title, provider badge, type icon
  - Reason text (e.g., "Based on your Writing skill gap")
  - Estimated duration
  - "View" and "Bookmark" buttons
  - "Dismiss" (X) button
Source: resource_recommendations table, top 4 by score, not dismissed
```

### 11.2 Task-Attached Resources

```
When the Adaptive Scheduler creates a task (e.g., "Writing Task 2 — Opinion Essay"),
it can optionally attach a recommended resource:
  - task.resource_id = resource.id
  - Displayed in the task card as "Recommended Resource: [Title]"
  - User can open directly from the task
  - Completing the resource auto-updates task progress
```

### 11.3 Post-Assessment Recommendations

```
After a user completes an assessment:
  - If band_score < target on a specific criterion:
    → Show 2–3 resources targeting that criterion
    → "Improve your Coherence & Cohesion with these resources"
  - If band_score improved:
    → Show 1 "next level" resource
    → "Great progress! Ready to challenge yourself?"
```

---

## 12. Edge Cases

| Edge Case | Handling |
|---|---|
| **No resources match filters** | Show "No resources found" with a suggestion to broaden filters; show admin contact for request |
| **User has completed all available resources** | Show "You've completed everything! New resources are added weekly."; notify user when new resources arrive |
| **Resource link is broken** | Auto-detect via daily link checker; hide from recommendations; notify admin; set `is_active = FALSE` |
| **User is on free tier** | All resources are free — no differentiation needed |
| **User has no diagnostic yet** | Show general popular resources (no personalization); prompt to take diagnostic |
| **Bookmark count exceeds 500** | Paginate bookmarks; user can archive old bookmarks |
| **Resource completion leaves no recommendations** | Fall back to "popular this week" resources |
| **Multiple users completing same resource** | PopularityScore naturally increases; no duplicate recommendations per user |
| **User dismisses a recommendation** | Mark `is_dismissed = TRUE`; exclude from future recommendations for 30 days (then re-evaluate) |
| **Resource is seasonal (exam date specific)** | Tag with `exam_season`; filter out if user's exam date is far outside the season |
| **User's band changes significantly** | Recalculate all recommendations immediately (triggered by assessment completion event) |

---

## 13. API Surface

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/resources` | GET | Browse all resources with filters and pagination |
| `/api/v1/resources/search` | GET | Full-text search across resources |
| `/api/v1/resources/{id}` | GET | Get single resource details |
| `/api/v1/resources/{id}/view` | POST | Log a resource view |
| `/api/v1/recommendations` | GET | Get personalized recommendations for current user |
| `/api/v1/recommendations/{id}/dismiss` | POST | Dismiss a recommendation |
| `/api/v1/recommendations/refresh` | POST | Force regenerate recommendations |
| `/api/v1/bookmarks` | GET | List user's bookmarks |
| `/api/v1/bookmarks` | POST | Add bookmark |
| `/api/v1/bookmarks/{id}` | PUT | Update bookmark (collection, notes, priority) |
| `/api/v1/bookmarks/{id}` | DELETE | Remove bookmark |
| `/api/v1/completions` | GET | Get user's completion history |
| `/api/v1/completions` | POST | Mark resource as in_progress/completed/abandoned |
| `/api/v1/resources/stats` | GET | Get user's resource statistics (total completed, hours spent, etc.) |

---

*This document describes the complete Resource Recommendation Engine architecture. It is designed to be a self-contained module that integrates with the existing frontend Resources page, the Adaptive Scheduler, the Dashboard, and the Analytics module.*
