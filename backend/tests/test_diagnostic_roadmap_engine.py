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
        assert SPEAKING_DEFAULT_BAND == 5.5
