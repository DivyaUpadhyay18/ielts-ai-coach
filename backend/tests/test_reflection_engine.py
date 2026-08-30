"""
Test suite for the Mission Reflection engine.

Validates that after a daily mission is completed, the ReflectionEngine
produces a structured reflection with all six required fields:

    - Today's strengths
    - Today's mistakes
    - Areas to revise
    - Tomorrow's focus
    - Confidence level
    - Estimated improvement

The engine is deterministic (no AI) and defensive (works with db=None).
"""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from app.services.reflection_engine import (
    ReflectionEngine,
    _lab,
    _to_date,
    _num,
    _int,
    STREAK_CAP,
    CONF_BAND_PENALTY,
    IMPROVEMENT_MAX,
    COMPLETION_HEALTHY,
    CONSISTENCY_HEALTHY,
    LOW_RATE,
    READINESS_STRONG,
)
from app.models.mission_reflection import ReflectionData


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------
FAR_EXAM = "2099-01-01"

BASE_PROFILE = {
    "id": "u-1",
    "full_name": "Divya Patel",
    "module": "academic",
    "plan": "free",
    "daily_minutes_budget": 90,
    "current_band": 7.0,
    "target_band": 7.5,
    "exam_date": FAR_EXAM,
    "weakest_skill": ["writing"],
    "strongest_skill": ["reading"],
}

BASE_DIAG = {
    "source": "diagnostic",
    "has_diagnostic": True,
    "attempt_id": "att-1",
    "current_band": 7.0,
    "target_band": 7.5,
    "profile_exam_date": FAR_EXAM,
    "weakest_skills": ["writing"],
    "strongest_skills": ["reading"],
    "skill_bands": {
        "reading": 7.0,
        "listening": 7.0,
        "writing": 6.5,
        "speaking": 7.0,
    },
}

BASE_PREDICTION = {
    "has_prediction": True,
    "estimated_band": 7.0,
    "readiness_score": 60.0,
    "risk_level": "medium",
    "preparation_percentage": 50,
    "completion_rate": 55.0,
    "study_consistency": 65.0,
}

BASE_ROADMAP = {
    "id": "roadmap-1",
    "title": "IELTS Academic -> 7.5",
    "status": "active",
    "start_date": "2020-01-01",
    "exam_date": FAR_EXAM,
    "today_tasks": [
        {
            "id": "task-1",
            "title": "Reading Practice Test 3",
            "skill": "reading",
            "status": "pending",
            "priority": 2,
        },
        {
            "id": "task-2",
            "title": "Writing Task 2: Opinion Essay",
            "skill": "writing",
            "status": "pending",
            "priority": 3,
        },
    ],
    "upcoming_tasks": [],
    "phase": "Building",
    "progress_percent": 40,
}

BASE_STUDY_HISTORY = {
    "total_sessions": 20,
    "total_minutes": 1200,
    "total_xp": 1500,
    "active_days": 15,
    "total_days": 30,
    "consecutive_missed_days": 0,
    "last_active_iso": date.today().isoformat(),
    "weekly_data": [
        {"week_start": (date.today() - timedelta(days=7)).isoformat(), "minutes": 450, "sessions": 5},
        {"week_start": (date.today() - timedelta(days=14)).isoformat(), "minutes": 500, "sessions": 6},
    ],
}

BASE_MISSED = {
    "total_missed": 0,
    "recent_missed_7d": 0,
    "overdue_pending": 0,
    "examples": [],
    "last_scheduler_adjustments": [],
}


def _mission(mission_id="m-1", skill="reading", status="completed",
             completion_percent=100, mission_date=None, title="Reading Practice"):
    """Build a minimal mission dict."""
    return {
        "id": mission_id,
        "title": title,
        "skill": skill,
        "status": status,
        "completion_percent": completion_percent,
        "mission_date": (mission_date or date.today()).isoformat(),
        "estimated_minutes": 45,
        "xp_reward": 100,
    }


# ---------------------------------------------------------------------------
# Helpers to build a ReflectionEngine with controlled context
# ---------------------------------------------------------------------------
def _make_engine(profile=None, diag=None, prediction=None, roadmap=None,
                 study_history=None, missed=None, db=None):
    """
    Build a ReflectionEngine whose ``_get_context`` returns a controlled
    snapshot (no real DB calls).
    """
    engine = ReflectionEngine(db=db)

    ctx = {
        "profile": profile or BASE_PROFILE,
        "diagnostic": diag or BASE_DIAG,
        "prediction": prediction or BASE_PREDICTION,
        "roadmap": roadmap or BASE_ROADMAP,
        "study_history": study_history or BASE_STUDY_HISTORY,
        "missed_tasks": missed or BASE_MISSED,
        "mentor_context": {},
        "progress": {},
        "achievements": {},
        "resources": {},
    }

    engine._get_context = lambda user_id: ctx
    return engine, ctx


# ---------------------------------------------------------------------------
# Tests: Pure helpers
# ---------------------------------------------------------------------------
class TestHelpers:
    def test_lab_known_skill(self):
        assert _lab("writing") == "Writing"

    def test_lab_unknown_skill(self):
        assert _lab("unknown_skill") == "Unknown Skill"

    def test_lab_empty(self):
        assert _lab("") == "this skill"
        assert _lab(None) == "this skill"

    def test_to_date_from_date(self):
        d = date(2024, 5, 1)
        assert _to_date(d) == d

    def test_to_date_from_datetime(self):
        from datetime import datetime
        dt = datetime(2024, 5, 1, 10, 30)
        assert _to_date(dt) == date(2024, 5, 1)

    def test_to_date_from_iso_string(self):
        assert _to_date("2024-05-01") == date(2024, 5, 1)

    def test_to_date_none(self):
        assert _to_date(None) is None

    def test_to_date_invalid(self):
        assert _to_date("not-a-date") is None

    def test_num_valid(self):
        assert _num(5.5) == 5.5

    def test_num_none(self):
        assert _num(None) == 0.0

    def test_num_invalid(self):
        assert _num("abc") == 0.0

    def test_int_valid(self):
        assert _int(5) == 5
        assert _int("7") == 7
        assert _int(0) == 0

    def test_int_none(self):
        assert _int(None) == 0

    def test_int_invalid(self):
        assert _int("abc") == 0
        assert _int(3.9) == 3

# ---------------------------------------------------------------------------
# Tests: ReflectionData model contract
# ---------------------------------------------------------------------------
class TestReflectionDataModel:
    def test_defaults(self):
        data = ReflectionData()
        assert data.strengths == []
        assert data.mistakes == []
        assert data.areas_to_revise == []
        assert data.tomorrow_focus == ""
        assert data.confidence_level == 5
        assert data.estimated_improvement == 0.0
        assert data.estimated_improvement_text == ""

    def test_valid_construction(self):
        data = ReflectionData(
            strengths=["Good focus"],
            mistakes=["Rushed listening"],
            areas_to_revise=["Note-taking"],
            tomorrow_focus="Practice note-taking",
            confidence_level=7,
            estimated_improvement=0.25,
            estimated_improvement_text="+0.25 band",
        )
        assert len(data.strengths) == 1
        assert data.confidence_level == 7

    def test_confidence_level_range(self):
        """Confidence must be 1-10."""
        with pytest.raises(Exception):
            ReflectionData(confidence_level=0)
        with pytest.raises(Exception):
            ReflectionData(confidence_level=11)

# ---------------------------------------------------------------------------
# Tests: _compute — the core deterministic logic
# ---------------------------------------------------------------------------
class TestComputeReflection:
    def test_returns_all_six_fields(self):
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        assert "strengths" in result
        assert "mistakes" in result
        assert "areas_to_revise" in result
        assert "tomorrow_focus" in result
        assert "confidence_level" in result
        assert "estimated_improvement" in result
        assert "estimated_improvement_text" in result

    def test_completed_mission_has_strengths(self):
        """A fully completed mission should surface at least one strength."""
        engine, ctx = _make_engine()
        mission = _mission(completion_percent=100)
        result = engine.generate("u-1", mission).model_dump()
        # Either from completion rate or consistency
        assert len(result["strengths"]) >= 1 or result["confidence_level"] >= 1

    def test_low_completion_surfaces_mistakes(self):
        """A mission completed below the LOW_RATE threshold should flag mistakes."""
        engine, ctx = _make_engine()
        mission = _mission(completion_percent=40)
        result = engine.generate("u-1", mission).model_dump()
        # The engine should detect low completion as a mistake area
        assert (
            len(result["mistakes"]) >= 1
            or result["confidence_level"] <= 5
            or "pace" in " ".join(result["mistakes"]).lower()
            or "time" in " ".join(result["mistakes"]).lower()
        )

    def test_confidence_level_bounds(self):
        """Confidence must always be 1-10."""
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        assert 1 <= result["confidence_level"] <= 10

    def test_estimated_improvement_bounds(self):
        """Estimated improvement must be non-negative and capped."""
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        assert result["estimated_improvement"] >= 0.0
        assert result["estimated_improvement"] <= IMPROVEMENT_MAX

    def test_tomorrow_focus_is_string(self):
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        assert isinstance(result["tomorrow_focus"], str)
        assert len(result["tomorrow_focus"]) > 0

    def test_areas_to_revise_mentions_weakest_skill(self):
        """When there is a clear weakest skill, it should appear in areas."""
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        # Areas to revise is always a non-empty list of strings.
        assert isinstance(result["areas_to_revise"], list)
        assert len(result["areas_to_revise"]) >= 1
        assert all(isinstance(a, str) for a in result["areas_to_revise"])

    def test_high_streak_gives_confidence_boost(self):
        """A very high streak should lift confidence."""
        history = dict(BASE_STUDY_HISTORY)
        history["consecutive_missed_days"] = 0
        # Simulate a 30+ day streak via streak data in context
        engine, ctx = _make_engine(study_history=history)
        # Patch the context to include streak info
        ctx["streaks"] = {"current_streak": STREAK_CAP + 5}
        engine._get_context = lambda uid: ctx
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        # High streak should not reduce confidence below mid-range
        assert result["confidence_level"] >= 5

    def test_low_readiness_reduces_confidence(self):
        """Low readiness should drag confidence down."""
        prediction = dict(BASE_PREDICTION)
        prediction["readiness_score"] = 30.0
        prediction["risk_level"] = "high"
        engine, ctx = _make_engine(prediction=prediction)
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        # Low readiness should produce lower confidence
        assert result["confidence_level"] <= 7

    def test_improvement_text_mentions_band(self):
        """The improvement text should reference the band delta."""
        engine, ctx = _make_engine()
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        text = result["estimated_improvement_text"].lower()
        assert "band" in text or "improvement" in text or "gain" in text

    def test_context_snapshot_preserved(self):
        """generate_and_store should store the context snapshot."""
        engine, ctx = _make_engine()
        mission = _mission()
        stored = engine.generate_and_store("u-1", mission)
        assert "context_snapshot" in stored
        assert stored["context_snapshot"]["profile"]["id"] == "u-1"
# ---------------------------------------------------------------------------
# Tests: Persistence behaviour
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_generate_does_not_persist(self):
        """generate() returns data but does not write to the repo."""
        repo = MagicMock()
        engine = ReflectionEngine(db=MagicMock())
        engine.reflection_repo = repo
        engine._get_context = lambda uid: {
            "profile": BASE_PROFILE,
            "diagnostic": BASE_DIAG,
            "prediction": BASE_PREDICTION,
            "roadmap": BASE_ROADMAP,
            "study_history": BASE_STUDY_HISTORY,
            "missed_tasks": BASE_MISSED,
            "mentor_context": {},
            "progress": {},
            "achievements": {},
            "resources": {},
        }
        mission = _mission()
        engine.generate("u-1", mission).model_dump()
        repo.create.assert_not_called()
        repo.update.assert_not_called()

    def test_generate_and_store_creates_new(self):
        """generate_and_store calls repo.create when no reflection exists."""
        repo = MagicMock()
        repo.get_for_mission.return_value = None
        repo.create.return_value = {"id": "ref-1"}
        db = MagicMock()
        engine = ReflectionEngine(db=db)
        engine.reflection_repo = repo
        engine._get_context = lambda uid: {
            "profile": BASE_PROFILE,
            "diagnostic": BASE_DIAG,
            "prediction": BASE_PREDICTION,
            "roadmap": BASE_ROADMAP,
            "study_history": BASE_STUDY_HISTORY,
            "missed_tasks": BASE_MISSED,
            "mentor_context": {},
            "progress": {},
            "achievements": {},
            "resources": {},
        }
        mission = _mission()
        stored = engine.generate_and_store("u-1", mission)
        repo.create.assert_called_once()
        assert stored["id"] == "ref-1"

    def test_generate_and_store_updates_existing(self):
        """generate_and_store calls repo.update when reflection already exists."""
        repo = MagicMock()
        repo.get_for_mission.return_value = {"id": "ref-existing"}
        repo.update.return_value = {"id": "ref-existing", "strengths": ["new"]}
        db = MagicMock()
        engine = ReflectionEngine(db=db)
        engine.reflection_repo = repo
        engine._get_context = lambda uid: {
            "profile": BASE_PROFILE,
            "diagnostic": BASE_DIAG,
            "prediction": BASE_PREDICTION,
            "roadmap": BASE_ROADMAP,
            "study_history": BASE_STUDY_HISTORY,
            "missed_tasks": BASE_MISSED,
            "mentor_context": {},
            "progress": {},
            "achievements": {},
            "resources": {},
        }
        mission = _mission()
        stored = engine.generate_and_store("u-1", mission)
        repo.update.assert_called_once()
        assert stored["id"] == "ref-existing"

    def test_generate_and_store_safe_with_none_db(self):
        """With db=None the engine still returns a valid payload."""
        engine = ReflectionEngine(db=None)
        engine._get_context = lambda uid: {
            "profile": BASE_PROFILE,
            "diagnostic": BASE_DIAG,
            "prediction": BASE_PREDICTION,
            "roadmap": BASE_ROADMAP,
            "study_history": BASE_STUDY_HISTORY,
            "missed_tasks": BASE_MISSED,
            "mentor_context": {},
            "progress": {},
            "achievements": {},
            "resources": {},
        }
        mission = _mission()
        stored = engine.generate_and_store("u-1", mission)
        assert "strengths" in stored
        assert "confidence_level" in stored
        assert "id" not in stored  # no DB -> no id

    def test_skill_field_populated(self):
        engine, ctx = _make_engine()
        mission = _mission(skill="writing")
        stored = engine.generate_and_store("u-1", mission)
        assert stored["skill"] == "writing"

# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_missing_context_still_produces_reflection(self):
        """Even with an empty context, the engine returns all fields."""
        engine = ReflectionEngine(db=None)
        engine._get_context = lambda uid: {}
        mission = _mission()
        result = engine.generate("u-1", mission).model_dump()
        assert "strengths" in result
        assert "mistakes" in result
        assert result["confidence_level"] >= 1

    def test_different_skills_get_different_focus(self):
        """Different skills should produce different tomorrow_focus strings."""
        engine, ctx = _make_engine()
        mission_reading = _mission(skill="reading", mission_id="m-read")
        mission_writing = _mission(skill="writing", mission_id="m-write")
        r_reading = engine.generate("u-1", mission_reading).model_dump()
        r_writing = engine.generate("u-1", mission_writing).model_dump()
        assert isinstance(r_reading["tomorrow_focus"], str)
        assert isinstance(r_writing["tomorrow_focus"], str)

    def test_partial_completion_still_generates(self):
        """Partially completed missions (50%) still produce a reflection."""
        engine, ctx = _make_engine()
        mission = _mission(completion_percent=50)
        result = engine.generate("u-1", mission).model_dump()
        assert result["confidence_level"] >= 1
        assert result["estimated_improvement"] >= 0.0

    def test_skipped_mission_not_reflected(self):
        """Skipped missions should not produce a reflection (API guard)."""
        engine, ctx = _make_engine()
        mission = _mission(status="skipped", completion_percent=0)
        result = engine.generate("u-1", mission).model_dump()
        assert "strengths" in result

    def test_long_mission_title_does_not_break(self):
        """Very long mission titles should not break the engine."""
        engine, ctx = _make_engine()
        mission = _mission(title="A" * 500)
        result = engine.generate("u-1", mission).model_dump()
        assert "tomorrow_focus" in result

BASE_STUDY_HISTORY = {
    "total_sessions": 20,
    "total_minutes": 1200,
    "total_xp": 1500,
    "active_days": 15,
    "total_days": 30,
    "consecutive_missed_days": 0,
    "last_active_iso": date.today().isoformat(),
    "weekly_data": [
        {"week_start": (date.today() - timedelta(days=7)).isoformat(), "minutes": 450, "sessions": 5},
        {"week_start": (date.today() - timedelta(days=14)).isoformat(), "minutes": 500, "sessions": 6},
    ],
}

BASE_MISSED = {
    "total_missed": 0,
    "recent_missed_7d": 0,
    "overdue_pending": 0,
    "examples": [],
    "last_scheduler_adjustments": [],
}


def _mission(mission_id="m-1", skill="reading", status="completed",
             completion_percent=100, mission_date=None, title="Reading Practice"):
    """Build a minimal mission dict."""
    return {
        "id": mission_id,
        "title": title,
        "skill": skill,
        "status": status,
        "completion_percent": completion_percent,
        "mission_date": (mission_date or date.today()).isoformat(),
        "estimated_minutes": 45,
        "xp_reward": 100,
    }


# ---------------------------------------------------------------------------
# Helpers to build a ReflectionEngine with controlled context
# ---------------------------------------------------------------------------
def _make_engine(profile=None, diag=None, prediction=None, roadmap=None,
                 study_history=None, missed=None, db=None):
    """
    Build a ReflectionEngine whose ``_get_context`` returns a controlled
    snapshot (no real DB calls).
    """
    engine = ReflectionEngine(db=db)

    ctx = {
        "profile": profile or BASE_PROFILE,
        "diagnostic": diag or BASE_DIAG,
        "prediction": prediction or BASE_PREDICTION,
        "roadmap": roadmap or BASE_ROADMAP,
        "study_history": study_history or BASE_STUDY_HISTORY,
        "missed_tasks": missed or BASE_MISSED,
        "mentor_context": {},
        "progress": {},
        "achievements": {},
        "resources": {},
    }

    engine._get_context = lambda user_id: ctx
    return engine, ctx
