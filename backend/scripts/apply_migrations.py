#!/usr/bin/env python3
"""
apply_migrations.py — run backend/app/db/migrations/*.sql against the real
Supabase Postgres database, in a dependency-safe order.

SAFETY PROPERTIES
-----------------
- Reads DATABASE_URL from the environment, or from backend/.env (KEY=VALUE).
  The URL is NEVER printed or logged.
- Runs each migration file inside its own transaction (BEGIN ... COMMIT).
- Executes statements one-by-one under SAVEPOINTs so that harmless
  "already exists" duplicates (tables/policies/indexes defined in more than
  one migration) are skipped with a clear log line, while ANY other error
  rolls back the entire file and aborts the whole run immediately.
- No destructive statements are tolerated: any DROP TABLE / TRUNCATE /
  DROP SCHEMA found in a file aborts the run before executing it.
- Prints a clear APPLY / OK / SKIP / FAIL line per file, and a summary.

PREREQUISITES
-------------
    pip install psycopg2-binary

USAGE
-----
    python apply_migrations.py            # DATABASE_URL from env or backend/.env
    python apply_migrations.py --dry-run  # print the plan only, no DB connection
"""
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]          # backend/
MIGRATIONS_DIR = REPO_ROOT / "app" / "db" / "migrations"
ENV_FILE = REPO_ROOT / ".env"

# --------------------------------------------------------------------------
# Execution order.
# Base: numeric filename order, with these deliberate adjustments:
#   1. 012_resources BEFORE 003: both define public.resources with different
#      columns; 012's 32-column version is the superset the newer app code
#      expects. 003's CREATE TABLE then no-ops via IF NOT EXISTS.
#   2. RECONCILE-1 between 012_resources and 003: re-adds the columns that
#      only 003 defines (is_published, view_count, module, provider,
#      duration_minutes) so 003's indexes apply cleanly.
#   3. 017 AFTER 013_recommendation_engine: same table defined twice; 017's
#      version is a strict superset. 017's CREATE TABLE no-ops, its extra
#      index is added, and its duplicate policies are skipped by the
#      savepoint logic.
#   4. 037_speaking_error_analysis AFTER 040: it references
#      speaking_test_responses, which only 040 creates.
#   5. RECONCILE-2 at the end: additive columns from the losing half of the
#      013/015 resource_likes + resource_ratings duplicate definitions.
# --------------------------------------------------------------------------
ORDER = [
    "001_users.sql",
    "002_onboarding.sql",
    "012_resources.sql",
    "RECONCILE:1_resources_003_columns",
    "003_core_domains.sql",
    "004_resource_bookmarks.sql",
    "005_daily_missions.sql",
    "006_progress_tracking.sql",
    "007_streaks.sql",
    "008_study_plan_engine.sql",
    "009_adaptive_scheduler.sql",
    "010_prediction_engine.sql",
    "011_schedule_history.sql",
    "012_resource_notes.sql",
    "013_analytics.sql",
    "013_recommendation_engine.sql",
    "014_learning_session.sql",
    "014_resource_quality.sql",
    "015_admin_resource_dashboard.sql",
    "016_admin_roles.sql",
    "017_recommendation_engine.sql",
    "018_community_resources.sql",
    "019_diagnostic_test.sql",
    "020_reading_diagnostic.sql",
    "021_listening_diagnostic.sql",
    "022_writing_diagnostic.sql",
    "023_speaking_diagnostic.sql",
    "024_vocab_grammar_diagnostic.sql",
    "025_band_estimation.sql",
    "026_ai_mentor.sql",
    "027_mentor_missed_day_mode.sql",
    "028_weekly_reports.sql",
    "029_ai_recommendations.sql",
    "030_motivation_engine.sql",
    "031_mission_reflections.sql",
    "032_mentor_memory.sql",
    "033_writing_workspace.sql",
    "034_writing_evaluations.sql",
    "035_writing_error_analysis.sql",
    "036_writing_band_examples.sql",
    "036_writing_improvement_plans.sql",
    "037_writing_reattempt_mode.sql",
    "040_speaking_test_workspace.sql",
    "037_speaking_error_analysis.sql",
    "038_writing_evaluation_attempt_number.sql",
    "039_writing_coaching_conversations.sql",
    "041_speaking_audio_pipeline.sql",
    "042_speaking_ai_evaluation.sql",
    "043_speaking_improvement_plans.sql",
    "044_speaking_reattempt_mode.sql",
    "045_speaking_practice_mode.sql",
    "046_speaking_coach_conversations.sql",
    "047_speaking_progress_analytics.sql",
    "RECONCILE:2_duplicate_table_columns",
]

# Additive-only reconciliation SQL (ALTER TABLE ADD COLUMN IF NOT EXISTS /
# CREATE INDEX IF NOT EXISTS — never destructive, never modifies data).
RECONCILIATIONS = {
    "1_resources_003_columns": """
-- Reconcile public.resources: 012_resources.sql won the base definition;
-- re-add the columns that only 003_core_domains.sql defines (additive only).
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS module TEXT NOT NULL DEFAULT 'academic';
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS duration_minutes SMALLINT;
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE public.resources ADD COLUMN IF NOT EXISTS view_count BIGINT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_resources_type_skill ON public.resources(type, skill);
CREATE INDEX IF NOT EXISTS idx_resources_published ON public.resources(is_published);
CREATE INDEX IF NOT EXISTS idx_resources_tags ON public.resources USING gin(tags);
""",
    "2_duplicate_table_columns": """
-- Reconcile tables defined in two migrations each (additive only):
-- resource_likes / resource_ratings: 013_analytics.sql won; add the columns
-- that only 015_admin_resource_dashboard.sql defines.
ALTER TABLE public.resource_likes ADD COLUMN IF NOT EXISTS liked_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE public.resource_ratings ADD COLUMN IF NOT EXISTS review TEXT;
ALTER TABLE public.resource_ratings ADD COLUMN IF NOT EXISTS rated_at TIMESTAMPTZ DEFAULT NOW();
-- recommendation_logs: 013_recommendation_engine.sql won; add the column
-- that only 017_recommendation_engine.sql defines.
ALTER TABLE public.recommendation_logs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
""",
}

# SQLSTATE codes meaning "object already exists" — safe to skip when the same
# object is deliberately defined in two migration files.
DUPLICATE_SQLSTATES = {"42P07", "42710", "42701", "42P06", "42712"}
# Unique violations on INSERT statements are treated as "seed row already
# present" and skipped — this makes re-runs of seed-bearing migrations safe.
UNIQUE_VIOLATION = "23505"
DESTRUCTIVE_RE = re.compile(r"\b(DROP\s+TABLE|TRUNCATE|DROP\s+SCHEMA)\b", re.I)


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and "=" in line:
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    print("FATAL: DATABASE_URL not found in environment or backend/.env", flush=True)
    sys.exit(2)


def split_statements(sql: str):
    """Split a SQL file into statements, honouring $$...$$ dollar-quoted
    function bodies, $tag$ variants, single quotes, and comments."""
    statements, buf = [], []
    i, n = 0, len(sql)
    in_single = False
    while i < n:
        ch = sql[i]
        if in_single:
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":   # escaped '' literal
                    buf.append("'")
                    i += 1
                else:
                    in_single = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == "-" and sql[i:i + 2] == "--":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            buf.append(" ")      # comment == whitespace: never buffer comment text
            i = j
            continue
        if ch == "/" and sql[i:i + 2] == "/*":
            j = sql.find("*/", i)
            j = n if j == -1 else j + 2
            i = j
            continue
        if ch == "$":
            m = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if m:
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                end = n if end == -1 else end + len(tag)
                buf.append(sql[i:end])
                i = end
                continue
        if ch == ";":
            statements.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if "".join(buf).strip():
        statements.append("".join(buf))

    def _real_sql(s: str) -> bool:
        # Belt-and-suspenders: drop any chunk that is only comments/whitespace
        # (e.g. a trailing comment block) instead of executing it as an empty query.
        no_block = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        no_line = re.sub(r"--[^\n]*", "", no_block)
        return bool(no_line.strip())

    return [s.strip() for s in statements if _real_sql(s)]


def is_duplicate_error(pg_exc) -> bool:
    code = getattr(pg_exc, "pgcode", None) or getattr(pg_exc, "sqlstate", None) or ""
    return code in DUPLICATE_SQLSTATES


def apply_file(cur, label: str, sql: str) -> bool:
    """Apply one file under savepoints. Returns True on success."""
    if DESTRUCTIVE_RE.search(sql):
        print(f"  ABORT: {label} contains a destructive statement (DROP TABLE/TRUNCATE).")
        return False
    statements = split_statements(sql)
    cur.execute("SAVEPOINT file_sp")
    try:
        for idx, stmt in enumerate(statements, 1):
            short = " ".join(stmt.split())[:90]
            cur.execute("SAVEPOINT stmt_sp")
            try:
                cur.execute(stmt)
                cur.execute("RELEASE SAVEPOINT stmt_sp")
            except Exception as exc:
                code = getattr(exc, "pgcode", None) or getattr(exc, "sqlstate", None) or ""
                if code in DUPLICATE_SQLSTATES:
                    cur.execute("ROLLBACK TO SAVEPOINT stmt_sp")
                    cur.execute("RELEASE SAVEPOINT stmt_sp")
                    print(f"    SKIP  [{label} #{idx}] already exists: {short}")
                elif code == UNIQUE_VIOLATION and stmt.lstrip().upper().startswith("INSERT"):
                    cur.execute("ROLLBACK TO SAVEPOINT stmt_sp")
                    cur.execute("RELEASE SAVEPOINT stmt_sp")
                    print(f"    SKIP  [{label} #{idx}] duplicate seed row: {short}")
                else:
                    print(f"    ERROR [{label} #{idx}] {short}")
                    print(f"    pgcode={getattr(exc, 'pgcode', '?')} message={str(exc).strip()[:500]}")
                    cur.execute("ROLLBACK TO SAVEPOINT stmt_sp")
                    cur.execute("RELEASE SAVEPOINT stmt_sp")
                    raise
        cur.execute("RELEASE SAVEPOINT file_sp")
        return True
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT file_sp")
        cur.execute("RELEASE SAVEPOINT file_sp")
        return False


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    print("=== Migration plan ===")
    for pos, entry in enumerate(ORDER, 1):
        kind = "reconcile" if entry.startswith("RECONCILE:") else "file     "
        print(f"  {pos:>3}. [{kind}] {entry}")
    print(f"Total steps: {len(ORDER)}\n")

    if dry_run:
        print("Dry run — no database connection made.")
        return

    url = load_database_url()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"

    import psycopg2  # pip install psycopg2-binary

    conn = psycopg2.connect(url)
    conn.autocommit = False
    applied = 0

    try:
        with conn.cursor() as cur:
            # Bookkeeping: track applied steps so re-runs skip them.
            cur.execute(
                "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
                "version TEXT PRIMARY KEY, "
                "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            conn.commit()
            cur.execute("SELECT version FROM public.schema_migrations")
            already_applied = {row[0] for row in cur.fetchall()}
            if already_applied:
                print(f"Bookkeeping: {len(already_applied)} step(s) already recorded "
                      f"and will be skipped.\n")

            for entry in ORDER:
                label = entry.split(":", 1)[1] if entry.startswith("RECONCILE:") else entry
                if label in already_applied:
                    print(f"SKIP  {label} (already recorded in schema_migrations)")
                    continue
                if not entry.startswith("RECONCILE:"):
                    path = MIGRATIONS_DIR / entry
                    if not path.exists():
                        print(f"FAIL  {label}: file not found — aborting.")
                        sys.exit(1)
                    sql = path.read_text(encoding="utf-8", errors="replace")
                else:
                    sql = RECONCILIATIONS[label]

                print(f"APPLY {label} ...")
                if apply_file(cur, label, sql):
                    cur.execute(
                        "INSERT INTO public.schema_migrations (version) VALUES (%s) "
                        "ON CONFLICT (version) DO NOTHING",
                        (label,),
                    )
                    conn.commit()
                    applied += 1
                    print(f"  OK    {label}")
                else:
                    conn.rollback()
                    print(f"\nSTOPPED at {label}. Previous files remain committed "
                          f"({applied} applied this run). Fix the error above, then "
                          f"re-run — already-applied steps are recorded in "
                          f"schema_migrations and will be skipped.")
                    sys.exit(1)
    finally:
        conn.close()

    print(f"\n=== DONE: {applied}/{len(ORDER)} steps applied successfully ===")


if __name__ == "__main__":
    main()

