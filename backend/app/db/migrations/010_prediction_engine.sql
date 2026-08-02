-- Migration 010: Prediction Engine
-- Stores historical prediction snapshots for audit and trend analysis.
-- All predictions are deterministic (no AI).

CREATE TABLE IF NOT EXISTS prediction_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    run_date        DATE NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Core estimates
    preparation_percentage  REAL NOT NULL,
    estimated_band          REAL NOT NULL,
    study_consistency       REAL NOT NULL,
    completion_rate         REAL NOT NULL,
    risk_level              TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    readiness_score         REAL NOT NULL,

    -- Supporting context
    current_band            REAL,
    target_band             REAL,
    days_remaining          INTEGER NOT NULL,
    intensity               TEXT NOT NULL,

    -- Raw metrics (JSONB for flexibility)
    metrics_json            JSONB NOT NULL DEFAULT '{}',

    -- Human-readable formula documentation
    formulas_json           JSONB NOT NULL DEFAULT '{}',

    -- Recommendations
    recommendations         TEXT[],

    -- Indexes
    UNIQUE (user_id, run_date),
    INDEX idx_prediction_user_date ON prediction_history (user_id, run_date DESC),
    INDEX idx_prediction_user_generated ON prediction_history (user_id, generated_at DESC)
);

-- Track when predictions were last computed per user (for caching).
CREATE TABLE IF NOT EXISTS prediction_cache (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_run_date   DATE NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    readiness_score REAL NOT NULL,
    risk_level      TEXT NOT NULL,
    estimated_band  REAL NOT NULL
);
