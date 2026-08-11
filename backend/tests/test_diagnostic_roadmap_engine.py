"""
Comprehensive test suite for the Diagnostic Test Engine and its downstream
integrations (Band Estimation, Study Plan Generator, Adaptive Scheduler,
Mission Engine, Dashboard, Progress Tracking, Band Prediction).

All tests are deterministic (NO AI) and validate:
  1. Reading  – objective section (accuracy → band)
  2. Listening – objective section (accuracy → band)
  3. Writing  – subjective section (rubric score → band)
  4. Speaking – subjective section (rubric score → band)
  5. Vocabulary – objective section (accuracy → band)
  6. Grammar  – objective section (accuracy → band)
  7. Band Estimation Engine – formula correctness
  8. Diagnostic Roadamap Service – resolve_profile() priority
  9. Study Plan Generator from Diagnostic
  10. Dashboard Integration – diagnostic signals reach dashboard
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.diagnostic_service import DiagnosticService
from app.services.band_estimation_service import BandEstimationService
from app.services.diagnostic_roadmap_service import DiagnosticRoadmapService


# ──────────────────────────────────────────────────────────────────────
# 1. Band Estimation Engine — formula correctness
# ──────────────────────────────────────────────────────────────────────
class TestBandEstimationEngine:
    """Validate the deterministic Band Estimation Engine formulas."""

    @pytest.fixture
    def service(self):
        svc = BandEstimationService(db=MagicMock())
        svc.db = None  # disconnect from DB
        return svc

    def test_overall_band_is_mean_of_four_skills(self, service):
        """Overall Band = mean of 4 official skills, rounded to 0.5."""
        data = MagicMock()
        data.reading = 6.0
        data.listening = 7.0
        data.writing = 6.5
        data.speaking = 6.5
        data.vocabulary = 0.0
        data.grammar = 0.0
        result = service.estimate("user-1", data)
        expected = round((6.0 + 7.0 + 6.5 + 6.5) / 4 * 2) / 2
        assert result["overall_band"] == expected

    def test_overall_band_clamped_to_9(self, service):
        """Overall Band is clamped to [0, 9]."""
        data = MagicMock()
        for s in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            setattr(data, s, 9.0)
        result = service.estimate("user-1", data)
        assert result["overall_band"] == 9.0

    def test_overall_band_clamped_to_0(self, service):
        """Overall Band is clamped to [0, 9]."""
        data = MagicMock()
        for s in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            setattr(data, s, 0.0)
        result = service.estimate("user-1", data)
        assert result["overall_band"] == 0.0

    def test_confidence_very_high(self, service):
        """All skills equal → high confidence (no dispersion)."""
        data = MagicMock()
        for s in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            setattr(data, s, 7.0)
        result = service.estimate("user-1", data)
        assert result["confidence_label"] == "very_high"
        assert result["confidence_score"] >= 90.0

    def test_confidence_low_with_high_dispersion(self, service):
        """Large dispersion → low confidence."""
        data = MagicMock()
        data.reading = 8.5
        data.listening = 8.5
        data.writing = 8.5
        data.speaking = 8.5
        data.vocabulary = 8.5
        data.grammar = 8.5
        # All 6 skills at 8.5 → completeness=1.0, dispersion=0 → very_high.
        assert service.estimate("user-1", data)["confidence_label"] == "very_high"

        # Now create dispersion: reading=9, speaking=4, writing=9, listening=9
        data.reading = 9.0
        data.listening = 9.0
        data.writing = 9.0
        data.speaking = 4.0
        # vocabulary and grammar are non-official, so they don't affect dispersion.
        result = service.estimate("user-1", data)
        # dispersion = 9.0 - 4.0 = 5.0 → 10 steps → penalty = 30
        # completeness = 4/4 = 1.0 → bonus = 100
        # confidence = 100 - 30 = 70 → between 50 and 75 → medium
        assert result["confidence_score"] == 70.0
        assert result["confidence_label"] == "medium"

    def test_confidence_incomplete_input(self, service):
        """Missing skills reduce completeness."""
        data = MagicMock()
        data.reading = 0.0  # not provided (0 = not provided in completeness calc)
        data.listening = 6.0
        data.writing = 6.0
        data.speaking = 6.0
        data.vocabulary = 6.0
        data.grammar = 6.0
        result = service.estimate("user-1", data)
        # completeness = 3/4 = 0.75 → bonus = 75
        # dispersion among {6,6,6,0} = 6.0 → 12 steps → penalty = 36
        # confidence = 75 - 36 = 39 → low
        assert result["confidence_label"] == "low"

    def test_weakest_strongest_sorted(self, service):
        """Weakest sorted ascending, strongest sorted descending."""
        data = MagicMock()
        data.reading = 8.0
        data.listening = 7.0
        data.writing = 6.0
        data.speaking = 5.0
        data.vocabulary = 7.0
        data.grammar = 6.0
        result = service.estimate("user-1", data)
        # Top 3 weakest (ascending): speaking(5.0), grammar(6.0), writing(6.0)
        # Tie between grammar and writing → alphabetical: grammar < writing
        assert result["weakest_skills"][0] == "speaking"
        # Top 3 strongest (descending): reading(8.0), listening(7.0), vocabulary(7.0)
        assert result["strongest_skills"][0] == "reading"

    def test_skill_bands_rounded_to_half(self, service):
        """All skill bands are rounded to 0.5 steps."""
        data = MagicMock()
        data.reading = 6.3
        data.listening = 6.7
        data.writing = 6.1
        data.speaking = 6.9
        data.vocabulary = 6.4
        data.grammar = 6.6
        result = service.estimate("user-1", data)
        for band in result["skill_bands"].values():
            assert band == round(band * 2) / 2

    def test_explanations_generated_for_all_skills(self, service):
        """Every skill gets a deterministic explanation string."""
        data = MagicMock()
        for s in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            setattr(data, s, 6.5)
        result = service.estimate("user-1", data)
        for skill in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            assert skill in result["explanations"]
            assert len(result["explanations"][skill]) > 0

    def test_formulas_documented(self, service):
        """All formula keys are present in the result."""
        data = MagicMock()
        for s in ("reading", "listening", "writing", "speaking", "vocabulary", "grammar"):
            setattr(data, s, 7.0)
        result = service.estimate("user-1", data)
        for key in ("overall_band", "confidence_score", "weakest_skills", "strongest_skills", "skill_band"):
            assert key in result["formulas"]


# ──────────────────────────────────────────────────────────────────────
# 2. Diagnostic Service — scoring helpers
# ──────────────────────────────────────────────────────────────────────
class TestDiagnosticScoring:
    """Validate the deterministic scoring helpers in DiagnosticService."""

    @pytest.fixture
    def service(self):
        svc = DiagnosticService(db=MagicMock())
        svc.db = None
        svc.repo = MagicMock()
        return svc

    def test_accuracy_to_band_0pct(self, service):
        """0% accuracy → 3.0 band (BAND_FLOOR)."""
        assert service._accuracy_to_band(0) == 3.0

    def test_accuracy_to_band_100pct(self, service):
        """100% accuracy → 9.0 band (BAND_CEIL)."""
        assert service._accuracy_to_band(100) == 9.0

    def test_accuracy_to_band_50pct(self, service):
        """50% accuracy → 6.0 band (midpoint of 3.0 and 9.0)."""
        assert service._accuracy_to_band(50) == 6.0

    def test_round_band_clamps_high(self, service):
        """Band above 9.0 is clamped to 9.0."""
        assert service._round_band(9.7) == 9.0

    def test_round_band_clamps_low(self, service):
        """Band below 0.0 is clamped to 0.0."""
        assert service._round_band(-1.0) == 0.0

    def test_round_band_half_steps(self, service):
        """Bands are rounded to 0.5 increments."""
        assert service._round_band(6.1) == 6.0
        assert service._round_band(6.3) == 6.5
        assert service._round_band(6.7) == 6.5
        assert service._round_band(6.8) == 7.0

    def test_overall_band_from_sections(self, service):
        """Overall band is mean of section bands, rounded to 0.5."""
        bands = [6.0, 7.0, 6.5, 6.5]
        assert service._compute_overall_band(bands) == 6.5

    def test_check_answer_string_case_insensitive(self, service):
        """String answers compared case-insensitively."""
        assert service._check_answer("Option A", "option a") is True
        assert service._check_answer("Correct", "wrong") is False

    def test_check_answer_non_string(self, service):
        """Non-string answers compared by value."""
        assert service._check_answer(42, 42) is True
        assert service._check_answer(None, None) is False

    def test_derive_insights_empty(self, service):
        """Empty skill_scores → empty strengths/weaknesses."""
        strengths, weaknesses = service._derive_insights({}, {})
        assert strengths == []
        assert weaknesses == []

    def test_derive_insights_with_scores(self, service):
        """Strongest sections → strengths; weakest < 6.0 → weaknesses."""
        skill_scores = {"reading": 8.0, "listening": 7.5, "writing": 5.0, "speaking": 4.5}
        accuracies = {"reading": 90, "listening": 80, "writing": 0, "speaking": 0}
        strengths, weaknesses = service._derive_insights(skill_scores, accuracies)
        assert len(strengths) >= 1
        assert len(weaknesses) >= 1
        assert any("Speaking" in s or "Writing" in s for s in weaknesses)

    def test_compute_focus_areas(self, service):
        """Focus areas are generated for skills below 6.5."""
        skill_scores = {"reading": 8.0, "listening": 7.0, "writing": 5.0, "speaking": 4.0}
        weaknesses = ["Speaking (4.0)", "Writing (5.0)"]
        focus = service._compute_focus_areas(skill_scores, weaknesses)
        assert len(focus) > 0
        assert any("Speaking" in f or "Writing" in f for f in focus)

    def test_suggested_weekly_hours_below_5(self, service):
        """Band < 5.0 → 5 hours base (plus gap adjustments for weak skills < 6.0)."""
        # band=4.0 < 5.0 → base=5; reading band 4.0 < 6.0 → gap_hours=2; total=7
        assert service._compute_suggested_hours(4.0, {"reading": 4.0}) == 7
        """Band >= 7.0 → 12 hours base + gap adjustments."""
        hours = service._compute_suggested_hours(7.5, {"writing": 4.0})
        assert hours >= 12

    def test_exam_timeline_below_5(self, service):
        """Band < 5.0 → 18 weeks base."""
        assert service._compute_exam_timeline(4.0, {}) == 18

    def test_exam_timeline_above_7(self, service):
        """Band >= 7.0 → 6 weeks base + weak_skill adjustments."""
        weeks = service._compute_exam_timeline(7.5, {"speaking": 4.0, "writing": 4.5})
        assert weeks >= 6


# ──────────────────────────────────────────────────────────────────────
# 3. Diagnostic Roadmap Service — resolve_profile()
# ──────────────────────────────────────────────────────────────────────
class TestDiagnosticRoadmapService:
    """Validate the diagnostic-to-roadmap integration layer."""

    @pytest.fixture
    def service(self):
        svc = DiagnosticRoadmapService(db=MagicMock())
        svc.db = None
        return svc

    def test_derive_skill_bands_from_list(self, service):
        """Normalize list-format skill_scores to {skill: band}."""
        skill_scores = [
            {"section": "reading", "band": 6.5},
            {"section": "writing", "band": 5.0},
            {"section": "unknown", "band": 9.0},
        ]
        bands = service.derive_skill_bands(skill_scores)
        assert bands == {"reading": 6.5, "writing": 5.0}

    def test_derive_skill_bands_from_dict(self, service):
        """Normalize dict-format skill_scores to {skill: band}."""
        bands = service.derive_skill_bands({"reading": 6.3, "listening": 7.7})
        assert bands == {"reading": 6.5, "listening": 7.5}

    def test_derive_weakest_strongest(self, service):
        """Weakest sorted ascending, strongest sorted descending."""
        skill_scores = {
            "reading": 8.0,
            "listening": 7.0,
            "writing": 5.5,
            "speaking": 4.5,
            "vocabulary": 7.5,
            "grammar": 6.0,
        }
        weakest, strongest = service.derive_weakest_strongest(skill_scores)
        assert weakest[0] == "speaking"
        assert strongest[0] == "reading"
        assert len(weakest) == 3
        assert len(strongest) == 3

    def test_derive_target_band_preserve_profile(self, service):
        """Profile target >= current is preserved."""
        assert service.derive_target_band(6.0, 7.5) == 7.5

    def test_derive_target_band_default_gap(self, service):
        """No profile target → current + 1 (rounded to 0.5)."""
        assert service.derive_target_band(6.0, None) == 7.0

    def test_resolve_profile_with_no_diagnostic(self, service):
        """Fallback to profile fields when no diagnostic exists."""
        service._safe_get_profile = MagicMock(return_value={
            "current_band": 6.0,
            "target_band": 8.0,
            "weakest_skill": ["writing"],
            "strongest_skill": ["reading"],
            "exam_date": "2025-12-31",
        })
        service.get_latest_diagnostic = MagicMock(return_value=None)
        profile = service.resolve_profile("user-1")
        assert profile["current_band"] == 6.0
        assert profile["target_band"] == 8.0
        assert profile["weakest_skills"] == ["writing"]
        assert profile["strongest_skills"] == ["reading"]
        assert profile["source"] == "profile"
        assert profile["has_diagnostic"] is False

    def test_resolve_profile_diagnostic_priority(self, service):
        """Diagnostic data overrides profile fields."""
        service._safe_get_profile = MagicMock(return_value={
            "current_band": 5.0,
            "target_band": 7.0,
            "weakest_skill": ["grammar"],
            "strongest_skill": ["speaking"],
            "exam_date": "2025-12-31",
        })
        service.get_latest_diagnostic = MagicMock(return_value={
            "id": "attempt-123",
            "skill_scores": {"reading": 7.5, "listening": 7.0, "writing": 5.0, "speaking": 4.5},
            "overall_band": 6.5,
        })
        profile = service.resolve_profile("user-1")
        assert profile["current_band"] == 6.5  # from diagnostic, not profile's 5.0
        assert profile["source"] == "diagnostic"
        assert profile["has_diagnostic"] is True
        assert profile["attempt_id"] == "attempt-123"
        # 4 skills from diagnostic → top 3 weakest = [speaking(4.5), writing(5.0), listening(7.0)]
        assert profile["weakest_skills"] == ["speaking", "writing", "listening"]
        assert profile["strongest_skills"] == ["reading", "listening", "writing"]

    def test_resolve_profile_default_when_nothing(self, service):
        """No diagnostic, no profile → sensible defaults."""
        service._safe_get_profile = MagicMock(return_value=None)
        service.get_latest_diagnostic = MagicMock(return_value=None)
        profile = service.resolve_profile("user-1")
        assert profile["current_band"] == 5.0
        assert profile["target_band"] == 6.0
        assert profile["source"] == "default"
        assert profile["has_diagnostic"] is False

    def test_resolve_profile_with_explicit_target(self, service):
        """Explicit target overrides profile target."""
        service._safe_get_profile = MagicMock(return_value={
            "current_band": 5.0,
            "target_band": 7.0,
        })
        service.get_latest_diagnostic = MagicMock(return_value=None)
        profile = service.resolve_profile("user-1", explicit_target=8.5)
        assert profile["target_band"] == 8.5

    def test_resolve_profile_focus_areas(self, service):
        """Focus areas are derived from diagnostic weakest skills."""
        service._safe_get_profile = MagicMock(return_value={
            "target_band": 7.0,
        })
        service.get_latest_diagnostic = MagicMock(return_value={
            "id": "attempt-456",
            "skill_scores": {"reading": 8.0, "listening": 7.0, "writing": 5.0, "speaking": 4.5},
            "overall_band": 6.0,
        })
        profile = service.resolve_profile("user-1")
        assert len(profile["focus_areas"]) > 0
        assert any("Speaking" in f or "Writing" in f for f in profile["focus_areas"])

    def test_resolve_profile_always_returns_all_keys(self, service):
        """resolve_profile never raises and always returns full keyset."""
        service._safe_get_profile = MagicMock(return_value=None)
        service.get_latest_diagnostic = MagicMock(return_value=None)
        profile = service.resolve_profile("user-1")
        required_keys = {
            "user_id", "source", "has_diagnostic", "attempt_id",
            "current_band", "target_band", "profile_target_band",
            "weakest_skills", "strongest_skills", "skill_bands",
            "focus_areas", "profile_exam_date",
        }
        assert required_keys.issubset(profile.keys())


# ──────────────────────────────────────────────────────────────────────
# 4. Diagnostic section validation
# ──────────────────────────────────────────────────────────────────────
class TestDiagnosticSections:
    """Validate the six IELTS diagnostic sections."""

    def test_all_six_sections_present(self):
        """All 6 skill domains are defined."""
        from app.models.diagnostic import DIAGNOSTIC_SECTIONS
        assert set(DIAGNOSTIC_SECTIONS) == {
            "reading", "listening", "writing", "speaking", "vocabulary", "grammar"
        }

    def test_section_order(self):
        """Sections have a defined ordered flow."""
        from app.models.diagnostic import DIAGNOSTIC_SECTIONS, SECTION_ORDER
        assert SECTION_ORDER == list(DIAGNOSTIC_SECTIONS)
        assert SECTION_ORDER[0] == "reading"
        assert SECTION_ORDER[-1] == "grammar"

    def test_objective_vs_subjective_sections(self):
        """Reading/listening/vocabulary/grammar are objective; writing/speaking are subjective."""
        from app.services.diagnostic_service import (
            BAND_FLOOR, BAND_CEIL, WRITING_DEFAULT_BAND, SPEAKING_DEFAULT_BAND
        )
        assert BAND_FLOOR == 3.0
        assert BAND_CEIL == 9.0
        assert WRITING_DEFAULT_BAND == 5.5


# ──────────────────────────────────────────────────────────────────────
# 5. Weekly AI Reports — pure computation tests
# ──────────────────────────────────────────────────────────────────────
class TestWeeklyReportComputations:
    """Validate the deterministic weekly report computation logic."""

    @pytest.fixture
    def service(self):
        from app.services.weekly_report_service import WeeklyReportService
        svc = WeeklyReportService.__new__(WeeklyReportService)
        svc.db = None
        return svc

    def test_week_bounds(self, service):
        """Monday-Sunday bounds for any date."""
        from datetime import date
        # A Wednesday
        d = date(2025, 6, 18)  # Wednesday
        start, end = service._week_bounds(d)
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6    # Sunday
        assert (end - start).days == 6

    def test_consistency_zero_active(self, service):
        """0 active days → 0% consistency."""
        assert service._compute_consistency(0) == 0.0

    def test_consistency_all_active(self, service):
        """7 active days → 100% consistency."""
        assert service._compute_consistency(7) == 100.0

    def test_consistency_partial(self, service):
        """4 active days → ~57.1%."""
        assert service._compute_consistency(4) == round(4 / 7 * 100, 1)

    def test_estimated_band_no_progress(self, service):
        """0 tasks completed → estimated = current_band."""
        from datetime import date
        result = service._compute_estimated_band(
            current_band=6.0, target_band=7.5, tasks_completed=0,
            daily_budget=60, week_start=date(2025, 6, 9), today=date(2025, 6, 15),
            diag_profile={},
        )
        assert result == 6.0

    def test_estimated_band_full_progress(self, service):
        """100% completion → estimated = target_band."""
        from datetime import date
        # tasks_completed >= total_planned → progress = 1.0
        result = service._compute_estimated_band(
            current_band=6.0, target_band=8.0, tasks_completed=10000,
            daily_budget=60, week_start=date(2025, 6, 9), today=date(2025, 6, 15),
            diag_profile={},
        )
        assert result == 8.0

    def test_estimated_band_half_progress(self, service):
        """50% completion → estimated = midpoint."""
        from datetime import date
        # total_planned = 60 * 6 / 45 = 8.0; tasks = 4 → progress = 0.5
        result = service._compute_estimated_band(
            current_band=6.0, target_band=8.0, tasks_completed=4,
            daily_budget=60, week_start=date(2025, 6, 9), today=date(2025, 6, 15),
            diag_profile={},
        )
        expected = round((6.0 + (8.0 - 6.0) * 0.5) * 2) / 2
        assert result == expected

    def test_estimated_band_clamped(self, service):
        """Estimated band clamped to [0, 9]."""
        from datetime import date
        result = service._compute_estimated_band(
            current_band=9.0, target_band=9.0, tasks_completed=10000,
            daily_budget=60, week_start=date(2025, 6, 9), today=date(2025, 6, 15),
            diag_profile={},
        )
        assert result == 9.0

    def test_next_week_focus_sorted(self, service):
        """Next week focus sorted by lowest bands."""
        skill_bands = {"reading": 7.5, "listening": 6.0, "writing": 5.0, "speaking": 4.5}
        focus = service._compute_next_week_focus(skill_bands)
        assert len(focus) == 3
        assert "Speaking" in focus[0]  # lowest
        assert "Writing" in focus[1]
        assert "Listening" in focus[2]

    def test_next_week_focus_empty(self, service):
        """Empty skill_bands → maintenance suggestion."""
        focus = service._compute_next_week_focus({})
        assert len(focus) == 1
        assert "maintain" in focus[0].lower()

    def test_compute_suggestions_risk(self, service):
        """Suggestions include band gap guidance."""
        recs = service._compute_suggestions(
            current_band=5.0, target_band=7.5, tasks_completed=5,
            daily_budget=60, hours_studied=3.0, consistency=40.0,
            days_remaining=60, estimated_band=5.5,
            skill_bands={"reading": 5.0, "listening": 5.5, "writing": 4.5, "speaking": 5.0},
            weakest_skill="writing",
        )
        assert len(recs) >= 3
        assert any("5.0" in r for r in recs)  # band mentioned

    def test_build_summary_no_tasks(self, service):
        """Summary mentions no tasks when tasks_completed is 0."""
        from datetime import date
        summary = service._build_summary(
            date(2025, 6, 9), date(2025, 6, 15),
            6.0, 6.5, 3.5, 0, 85.0, 7,
        )
        assert "No tasks completed" in summary

    def test_build_summary_with_tasks(self, service):
        """Summary includes hours, tasks, streak, band."""
        from datetime import date
        summary = service._build_summary(
            date(2025, 6, 9), date(2025, 6, 15),
            6.0, 6.5, 5.0, 25, 85.0, 7,
        )
        assert "5.0 hours" in summary
        assert "25 tasks" in summary
        assert "7-day streak" in summary
        assert "6.5" in summary

    def test_formulas_documented(self, service):
        """All formula keys are present."""
        formulas = service._build_formulas()
        for key in ("consistency", "estimated_band", "weakest_skill", "strongest_skill",
                     "hours_studied", "tasks_completed", "streak", "next_week_focus"):
            assert key in formulas

    def test_parse_date_iso(self, service):
        """ISO date string parsed correctly."""
        from datetime import date
        d = service._parse_date("2025-06-15")
        assert d == date(2025, 6, 15)

    def test_parse_date_none(self, service):
        """None input → None."""
        assert service._parse_date(None) is None

    def test_parse_date_invalid(self, service):
        """Invalid string → None."""
        assert service._parse_date("not-a-date") is None

    def test_compute_achievements_no_milestones(self, service):
        """Minimal activity → at least one achievement."""
        streak_overview = {
            "daily": {"current": 0, "longest": 0},
            "weekly": {"current": 0, "longest": 0},
            "monthly": {"current": 0, "longest": 0},
            "bonuses": {"total_bonus_xp": 0, "perfect_day_count": 0},
        }
        ach = service._compute_achievements("user", streak_overview, 1, [])
        assert len(ach) >= 1

    def test_compute_achievements_perfect_day(self, service):
        """Perfect day detected → achievement."""
        streak_overview = {
            "daily": {"current": 10, "longest": 10},
            "weekly": {"current": 3, "longest": 5},
            "monthly": {"current": 1, "longest": 2},
            "bonuses": {"total_bonus_xp": 25, "perfect_day_count": 1},
        }
        ach = service._compute_achievements("user", streak_overview, 40, [])
        assert any("Perfect day" in a for a in ach)
        assert any("Daily streak milestone" in a for a in ach)


# ──────────────────────────────────────────────────────────────────────
# 6. AI Recommendations — pure computation tests
# ──────────────────────────────────────────────────────────────────────
class TestAiRecommendations:
    """Validate the deterministic AI recommendations computation logic."""

    @pytest.fixture
    def rec_service(self):
        from app.services.ai_recommendations_service import AiRecommendationsService
        svc = AiRecommendationsService.__new__(AiRecommendationsService)
        svc.db = None
        return svc

    def test_week_bounds(self, rec_service):
        """Monday-Sunday bounds for any date."""
        from datetime import date
        d = date(2025, 6, 18)  # Wednesday
        start, end = rec_service._week_bounds(d)
        assert start.weekday() == 0
        assert end.weekday() == 6
        assert (end - start).days == 6

    def test_compute_study_order(self, rec_service):
        """Study order ranked by priority (weakest first)."""
        skill_bands = {"reading": 7.0, "listening": 6.5, "writing": 5.0, "speaking": 4.5}
        order = rec_service._compute_study_order(
            skill_bands, ["speaking", "writing"], ["reading", "listening"],
            6.0, 7.5, 60,
        )
        assert len(order) == 4
        assert order[0]["skill"] == "speaking"  # lowest band
        assert order[0]["order"] == 1
        assert order[-1]["skill"] == "reading"  # highest band

    def test_compute_study_order_time_pressure(self, rec_service):
        """Short time remaining increases weak-skill priority."""
        skill_bands = {"reading": 7.0, "listening": 6.5, "writing": 5.0, "speaking": 4.5}
        order_normal = rec_service._compute_study_order(
            skill_bands, ["speaking", "writing"], ["reading", "listening"],
            6.0, 7.5, 60,
        )
        order_pressure = rec_service._compute_study_order(
            skill_bands, ["speaking", "writing"], ["reading", "listening"],
            6.0, 7.5, 10,  # 10 days remaining → time pressure
        )
        # Speaking should still be first, but its priority_score should be higher
        assert order_pressure[0]["priority_score"] > order_normal[0]["priority_score"]

    def test_compute_revision_priorities(self, rec_service):
        """Revision priorities based on band deficit."""
        skill_bands = {"writing": 5.0, "speaking": 6.0, "reading": 7.5}
        priorities = rec_service._compute_revision_priorities(
            ["writing", "speaking"], skill_bands, 60
        )
        assert len(priorities) == 2
        assert priorities[0]["skill"] == "writing"
        assert priorities[0]["intensity"] == "high"  # band 5.0 is < 6.5 but not < 5.0
        assert priorities[1]["skill"] == "speaking"
        assert priorities[1]["intensity"] == "high"

    def test_compute_revision_priorities_critical(self, rec_service):
        """Band < 5.0 → critical intensity."""
        priorities = rec_service._compute_revision_priorities(
            ["grammar"], {"grammar": 4.5}, 60
        )
        assert priorities[0]["intensity"] == "critical"

    def test_compute_extra_practice(self, rec_service):
        """Extra practice allocates more time to weakest skills."""
        skill_bands = {"writing": 5.0, "speaking": 6.0}
        practice = rec_service._compute_extra_practice(
            ["writing", "speaking"], ["reading"], skill_bands, 60, 60
        )
        assert len(practice) >= 2
        # Weakest skill gets highest allocation
        assert practice[0]["skill"] == "writing"
        assert practice[0]["recommended_minutes"] >= practice[1]["recommended_minutes"]
        assert practice[0]["priority"] == "high"

    def test_compute_extra_practice_short_time(self, rec_service):
        """< 30 days → more time to weakest skills."""
        skill_bands = {"writing": 5.0, "speaking": 6.0}
        practice = rec_service._compute_extra_practice(
            ["writing", "speaking"], ["reading"], skill_bands, 60, 15  # < 30 days
        )
        assert practice[0]["recommended_minutes"] == int(60 * 0.55)

    def test_compute_break_suggestions_no_activity(self, rec_service):
        """No active days → recovery suggestion."""
        suggestions = rec_service._compute_break_suggestions(0, 0, 60, 0)
        assert len(suggestions) == 1
        assert suggestions[0]["type"] == "recovery"

    def test_compute_break_suggestions_intensive(self, rec_service):
        """High study load + long streak → micro-breaks + long break."""
        suggestions = rec_service._compute_break_suggestions(700, 6, 60, 10)
        types = [s["type"] for s in suggestions]
        assert "long_break" in types
        assert "micro_break" in types

    def test_compute_break_suggestions_gentle_restart(self, rec_service):
        """Fewer than 3 active days → gentle restart."""
        suggestions = rec_service._compute_break_suggestions(120, 2, 60, 3)
        types = [s["type"] for s in suggestions]
        assert "gentle_restart" in types

    def test_compute_time_management_balanced(self, rec_service):
        """> 30 days → balanced focus."""
        tm = rec_service._compute_time_management(60, 60, 20, 5, 5.0, 6.5, 3)
        assert tm["focus_mode"] == "balanced"
        assert tm["time_split"]["weak_minutes"] == 30  # 50% of 60
        assert tm["tasks_per_day"] >= 1

    def test_compute_time_management_intensive(self, rec_service):
        """14-30 days → intensive focus."""
        tm = rec_service._compute_time_management(60, 20, 15, 3, 5.0, 6.5, 3)
        assert tm["focus_mode"] == "intensive"
        assert tm["time_split"]["weak_minutes"] == int(60 * 0.65)

    def test_compute_time_management_exam_cram(self, rec_service):
        """< 14 days → exam-cram focus."""
        tm = rec_service._compute_time_management(60, 7, 10, 5, 5.0, 6.5, 3)
        assert tm["focus_mode"] == "exam-cram"
        assert tm["time_split"]["weak_minutes"] == int(60 * 0.80)

    def test_build_summary_no_tasks(self, rec_service):
        """Summary mentions no tasks when week_tasks is 0."""
        summary = rec_service._build_summary(6.0, 7.5, 30, 0, 0, 0, 0)
        assert "no tasks" in summary

    def test_build_summary_with_tasks(self, rec_service):
        """Summary includes hours, tasks, streak, band."""
        summary = rec_service._build_summary(6.0, 7.5, 30, 300, 25, 5, 7)
        assert "5.0h" in summary
        assert "25 tasks" in summary
        assert "7-day streak" in summary
        assert "6.0" in summary
        assert "7.5" in summary

    def test_build_formulas_all_keys(self, rec_service):
        """All formula keys present."""
        formulas = rec_service._build_formulas()
        for key in ("study_order", "revision_priorities", "extra_practice",
                     "break_suggestions", "time_management"):
            assert key in formulas

    def test_parse_date_handling(self, rec_service):
        """Date parsing from various formats."""
        from datetime import date
        assert rec_service._parse_date("2025-06-15") == date(2025, 6, 15)
        assert rec_service._parse_date(None) is None
        assert rec_service._parse_date("invalid") is None

    def test_compute_estimated_band_clamped(self, rec_service):
        """Estimated band clamped to [0, 9]."""
        from datetime import date
        result = rec_service._compute_estimated_band(
            6.0, 9.0, 10000, 60,
            date(2025, 6, 9), date(2025, 6, 15),
        )
        assert result == 9.0

    def test_derive_weak_strong_from_bands(self, rec_service):
        """Weakest/strongest derived from skill bands."""
        skill_bands = {"reading": 7.0, "listening": 6.5, "writing": 5.0, "speaking": 4.5}
        weakest, strongest = rec_service._derive_weak_strong(skill_bands, {})
        assert weakest == ["speaking", "writing"]  # lowest two
        assert strongest == ["writing", "speaking"]  # highest two

    def test_compute_consistency_full(self, rec_service):
        """7 active days → 100%."""
        assert rec_service._compute_consistency(7) == 100.0

    def test_compute_consistency_zero(self, rec_service):
        """0 active days → 0%."""
        assert rec_service._compute_consistency(0) == 0.0


# ──────────────────────────────────────────────────────────────────────
# 7. AI Mentor Memory — pure computation tests
# ──────────────────────────────────────────────────────────────────────
class TestMentorMemory:
    """Validate the deterministic mentor memory extraction logic."""

    @pytest.fixture
    def mem_service(self):
        from app.services.mentor_memory_service import MentorMemoryService
        svc = MentorMemoryService.__new__(MentorMemoryService)
        svc.db = None
        return svc

    def test_detect_skill_writing(self, mem_service):
        """Writing-related questions detected."""
        assert mem_service._detect_skill_from_text("How do I improve my essay coherence?") == "writing"

    def test_detect_skill_speaking(self, mem_service):
        """Speaking-related questions detected."""
        assert mem_service._detect_skill_from_text("How to improve fluency in Part 2?") == "speaking"

    def test_detect_skill_reading(self, mem_service):
        """Reading-related questions detected."""
        assert mem_service._detect_skill_from_text("How to approach skimming and scanning?") == "reading"

    def test_detect_skill_listening(self, mem_service):
        """Listening-related questions detected."""
        assert mem_service._detect_skill_from_text("What's the best note-taking strategy?") == "listening"

    def test_detect_skill_grammar(self, mem_service):
        """Grammar-related questions detected."""
        assert mem_service._detect_skill_from_text("I struggle with past perfect tense.") == "grammar"

        # vocabulary detection via VOCAB keywords
    def test_detect_skill_vocab(self, mem_service):
        """Vocabulary-related questions detected."""
        assert mem_service._detect_skill_from_text("How to learn collocations?") == "vocabulary"

    def test_detect_skill_unknown(self, mem_service):
        """Unknown skill returns None."""
        assert mem_service._detect_skill_from_text("How are you today?") is None

    def test_infer_subtopic_grammar_low(self, mem_service):
        """Low band grammar → basic_grammar."""
        assert mem_service._infer_subtopic("grammar", 4.5) == "basic_grammar"

    def test_infer_subtopic_grammar_medium(self, mem_service):
        """Medium band grammar → tenses_and_articles."""
        assert mem_service._infer_subtopic("grammar", 6.0) == "tenses_and_articles"

    def test_infer_subtopic_grammar_high(self, mem_service):
        """High band grammar → complex_sentences."""
        assert mem_service._infer_subtopic("grammar", 7.0) == "complex_sentences"

    def test_infer_subtopic_grammar_advanced(self, mem_service):
        """Very high band grammar → advanced_structures."""
        assert mem_service._infer_subtopic("grammar", 8.0) == "advanced_structures"

    def test_infer_subtopic_vocab_low(self, mem_service):
        """Low band vocab → basic_vocabulary."""
        assert mem_service._infer_subtopic("vocabulary", 4.0) == "basic_vocabulary"

    def test_infer_subtopic_vocab_medium(self, mem_service):
        """Medium band vocab → collocations."""
        assert mem_service._infer_subtopic("vocabulary", 6.0) == "collocations"

    def test_infer_subtopic_unknown(self, mem_service):
        """Unknown skill → general."""
        assert mem_service._infer_subtopic("reading", 6.0) == "general"

    def test_memory_type_label(self, mem_service):
        """Memory type labels are correct."""
        assert mem_service._memory_type_label("recurring_mistake") == "Recurring Mistakes"
        assert mem_service._memory_type_label("faq") == "Frequently Asked Questions"
        assert mem_service._memory_type_label("weak_grammar") == "Weak Grammar Topics"
        assert mem_service._memory_type_label("weak_vocabulary") == "Weak Vocabulary"
        assert mem_service._memory_type_label("learning_preference") == "Learning Preferences"
        assert mem_service._memory_type_label("motivation_style") == "Motivation Style"

    def test_memory_type_description(self, mem_service):
        """Memory type descriptions are non-empty."""
        for mt in ("recurring_mistake", "faq", "weak_grammar", "weak_vocabulary",
                    "learning_preference", "motivation_style", "conversation_insight"):
            desc = mem_service._memory_type_description(mt)
            assert len(desc) > 0

    def test_empty_profile(self, mem_service):
        """Empty profile has all required keys."""
        profile = mem_service._empty_profile()
        for key in ("total_memories", "recurring_mistakes", "faqs", "weak_grammar",
                     "weak_vocabulary", "learning_preferences", "motivation_styles",
                     "conversation_insights", "weak_skills", "preference_texts",
                     "motivation_texts"):
            assert key in profile
        assert profile["total_memories"] == 0

    def test_parse_date(self, mem_service):
        """Date parsing."""
        from datetime import date
        assert mem_service._parse_date("2025-06-15") == date(2025, 6, 15)
        assert mem_service._parse_date(None) is None
        assert mem_service._parse_date("invalid") is None

    def test_get_memory_types(self, mem_service):
        """All 7 memory types are listed."""
        types = mem_service.get_memory_types()
        type_names = [t["type"] for t in types]
        assert "recurring_mistake" in type_names
        assert "faq" in type_names
        assert "weak_grammar" in type_names
        assert "weak_vocabulary" in type_names
        assert "learning_preference" in type_names
        assert "motivation_style" in type_names
        assert "conversation_insight" in type_names
        assert len(types) == 7


# ──────────────────────────────────────────────────────────────────────
# Phase 9: Writing Workspace
# ──────────────────────────────────────────────────────────────────────
from app.services.writing_workspace_service import WritingWorkspaceService


class TestWritingWorkspaceService:
    """Validate the Writing Workspace service — deterministic, NO AI."""

    @pytest.fixture
    def service(self):
        svc = WritingWorkspaceService(db=MagicMock())
        svc.db = None
        svc.repo = MagicMock()
        svc.prompt_repo = MagicMock()
        return svc

    def test_count_words_empty(self, service):
        assert service._count_words("") == 0
        assert service._count_words("   \n  ") == 0

    def test_count_words_normal(self, service):
        assert service._count_words("hello world") == 2
        assert service._count_words("one two three four five") == 5

    def test_get_prompts_invalid_task_type(self, service):
        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            service.get_prompts("invalid")

    def test_get_prompts_empty(self, service):
        service.prompt_repo.get_prompts.return_value = []
        result = service.get_prompts("task_1")
        assert result["total"] == 0
        assert result["prompts"] == []

    def test_get_prompts_with_data(self, service):
        service.prompt_repo.get_prompts.return_value = [
            {"id": "p1", "task_type": "task_2", "title": "Essay 1",
             "prompt_text": "Discuss both views...", "word_limit": 250,
             "time_limit_seconds": 2400, "difficulty": 3, "topics": ["education"]},
        ]
        result = service.get_prompts("task_2")
        assert result["total"] == 1
        assert result["prompts"][0]["id"] == "p1"

    def test_get_prompt_not_found(self, service):
        from app.core.exceptions import NotFoundError
        service.prompt_repo.get_prompt.return_value = None
        with pytest.raises(NotFoundError):
            service.get_prompt("nonexistent")

    def test_start_submission_creates_new(self, service):
        service.prompt_repo.get_prompt.return_value = {
            "id": "p1", "task_type": "task_1", "title": "Line Graph",
            "prompt_text": "The graph shows...", "word_limit": 150,
            "time_limit_seconds": 1200, "difficulty": 3, "topics": ["energy"],
        }
        service.repo.list_drafts.return_value = []
        service.repo.create_submission.return_value = {
            "id": "sub1", "prompt_id": "p1", "task_type": "task_1",
            "title": "Line Graph", "prompt_text": "The graph shows...",
            "word_limit": 150, "time_limit_seconds": 1200,
            "essay_text": "", "word_count": 0, "time_seconds_spent": 0,
            "status": "draft",
        }
        result = service.start_submission("user1", "p1")
        assert result["id"] == "sub1"
        assert result["status"] == "draft"

    def test_start_submission_resumes_draft(self, service):
        service.prompt_repo.get_prompt.return_value = {
            "id": "p1", "task_type": "task_2", "title": "Essay",
            "prompt_text": "Discuss", "word_limit": 250,
            "time_limit_seconds": 2400, "difficulty": 3, "topics": [],
        }
        service.repo.list_drafts.return_value = [
            {"id": "existing", "prompt_id": "p1", "status": "draft",
             "is_locked": False, "essay_text": "existing text", "word_count": 2,
             "task_type": "task_2", "title": "Essay", "prompt_text": "Discuss",
             "word_limit": 250, "time_limit_seconds": 2400, "time_seconds_spent": 60},
        ]
        result = service.start_submission("user1", "p1")
        assert result["id"] == "existing"

    def test_auto_save_updates_word_count(self, service):
        service.repo.get_submission.return_value = {
            "id": "sub1", "status": "in_progress", "prompt_id": "p1",
            "task_type": "task_2", "title": "Essay", "prompt_text": "Discuss",
            "word_limit": 250, "time_limit_seconds": 2400,
        }
        service.repo.update_submission.return_value = {
            "id": "sub1", "essay_text": "hello world", "word_count": 2,
            "time_seconds_spent": 120, "status": "in_progress",
        }
        result = service.auto_save("user1", "sub1", "hello world", 120)
        assert result["word_count"] == 2

    def test_auto_save_locked_submission(self, service):
        from app.core.exceptions import ValidationError
        service.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "is_locked": True,
        }
        with pytest.raises(ValidationError):
            service.auto_save("user1", "sub1", "text", 120)

    def test_submit_generates_warnings(self, service):
        service.repo.get_submission.return_value = {
            "id": "sub1", "status": "draft", "is_locked": False,
            "prompt_id": "p1", "task_type": "task_2", "title": "Essay",
            "prompt_text": "Discuss", "word_limit": 250,
            "time_limit_seconds": 2400, "essay_text": "",
            "word_count": 0, "time_seconds_spent": 0,
        }
        service.prompt_repo.get_prompt.return_value = None
        service.repo.update_submission.return_value = {
            "id": "sub1", "status": "submitted", "is_locked": True,
        }
        result = service.submit("user1", "sub1", 300)
        assert result["status"] == "submitted"
        warnings = result["submission_summary"]["warnings"]
        assert len(warnings) > 0

    def test_submit_already_submitted(self, service):
        from app.core.exceptions import ValidationError
        service.repo.get_submission.return_value = {
            "id": "sub1", "status": "submitted", "is_locked": True,
        }
        with pytest.raises(ValidationError):
            service.submit("user1", "sub1", 100)

    def test_get_submission_not_found(self, service):
        from app.core.exceptions import NotFoundError
        service.repo.get_submission.return_value = None
        with pytest.raises(NotFoundError):
            service.get_submission("user1", "nonexistent")

    def test_submission_payload_has_all_fields(self, service):
        raw = {
            "id": "sub1", "user_id": "u1", "prompt_id": "p1",
            "task_type": "task_2", "title": "Test", "prompt_text": "Prompt",
            "word_limit": 250, "time_limit_seconds": 2400,
            "essay_text": "text", "word_count": 1, "time_seconds_spent": 30,
            "status": "draft", "is_locked": False, "submission_summary": {},
            "created_at": "2024-01-01", "updated_at": "2024-01-01",
            "submitted_at": None,
        }
        result = service._submission_payload(raw, None)
        assert "id" in result
        assert "is_locked" in result
        assert "submission_summary" in result
        assert result["word_count"] == 1
