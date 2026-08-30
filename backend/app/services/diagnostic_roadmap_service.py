"""
Diagnostic Roadmap Service.

A deterministic (NO AI) integration layer that resolves a user's **latest
completed diagnostic results** into a learning profile, so downstream engines
(Study Plan Generator, Recommendation Engine, Band Prediction, Dashboard, Adaptive
Scheduler, Mission Engine) can build on **real measured performance** instead of
manual assumptions stored on the user profile.

Resolution priority (highest wins):
  1. Latest completed diagnostic (measured per-skill bands).
  2. User profile fields (current_band / target_band / weakest_skill /
     strongest_skill) as a fallback.
  3. Sensible defaults (only when neither exists).

The service exposes pure, unit-testable helpers for deriving weakest/strongest
skills and target-band suggestions, plus `resolve_profile()` which merges the
diagnostic with profile fallbacks. All DB access is defensive (never raises).
"""

from typing import Any, Dict, List, Optional, Tuple

from app.db.session import DatabaseSession
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.user_repo import UserRepository

# The six IELTS skill domains (canonical order).
ALL_SKILLS = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")

# User-friendly labels.
SKILL_LABELS = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Lexical Resource",
    "grammar": "Grammatical Range",
}

# Number of weakest / strongest skills surfaced to downstream engines.
TOP_N_SKILLS = 3

# Default band target gap when no target is known.
DEFAULT_TARGET_GAP = 1.0


class DiagnosticRoadmapService:
    """Resolves deterministic, diagnostic-first learning profiles."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.diagnostic_repo = DiagnosticRepository(db)
        self.user_repo = UserRepository(db)

    # ------------------------------------------------------------------
    # Pure helpers (unit-testable, no DB)
    # ------------------------------------------------------------------
    @staticmethod
    def derive_skill_bands(skill_scores: Any) -> Dict[str, float]:
        """Normalize skill_scores (dict or list) into {skill: band}."""
        bands: Dict[str, float] = {}
        if isinstance(skill_scores, dict):
            for skill, band in skill_scores.items():
                if skill in ALL_SKILLS and isinstance(band, (int, float)):
                    bands[skill] = round(float(band) * 2) / 2
        elif isinstance(skill_scores, list):
            for item in skill_scores:
                if not isinstance(item, dict):
                    continue
                skill = item.get("section")
                band = item.get("band")
                if skill in ALL_SKILLS and isinstance(band, (int, float)):
                    bands[skill] = round(float(band) * 2) / 2
        return bands

    @classmethod
    def derive_weakest_strongest(
        cls, skill_scores: Any, top_n: int = TOP_N_SKILLS
    ) -> Tuple[List[str], List[str]]:
        """Return (weakest, strongest) skill lists from skill_scores.

        Sorting is deterministic: ascending by band, then alphabetical for ties.
        """
        bands = cls.derive_skill_bands(skill_scores)
        if not bands:
            return [], []
        measured = {skill: bands.get(skill, 0.0) for skill in ALL_SKILLS if skill in bands}
        ordered = sorted(measured.items(), key=lambda kv: (kv[1], kv[0]))
        weakest = [s for s, _ in ordered[:top_n]]
        strongest = [s for s, _ in sorted(ordered, key=lambda kv: (-kv[1], kv[0]))[:top_n]]
        return weakest, strongest

    @staticmethod
    def derive_target_band(
        current_band: float,
        profile_target: Optional[float] = None,
    ) -> float:
        """Suggest a target band: preserve profile target if >= current, else current + 1."""
        if profile_target is not None and isinstance(profile_target, (int, float)):
            target = round(float(profile_target) * 2) / 2
            if target >= current_band:
                return min(9.0, target)
        return min(9.0, round((current_band + DEFAULT_TARGET_GAP) * 2) / 2)

    # ------------------------------------------------------------------
    # DB-backed resolution
    # ------------------------------------------------------------------
    def get_latest_diagnostic(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest completed diagnostic attempt, if any."""
        if self.db is None:
            return None
        try:
            return self.diagnostic_repo.get_latest_completed(user_id)
        except Exception:
            return None

    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_by_id(user_id) or self.user_repo.get(user_id)
        except Exception:
            return None

    def resolve_profile(
        self,
        user_id: str,
        explicit_target: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build the diagnostic-first learning profile for a user.

        Returns a dict consumable by the Study Plan Generator, Recommendation
        Engine, Band Prediction, and Dashboard. Always contains a full set of
        keys (never raises).
        """
        profile = self._safe_get_profile(user_id) or {}
        attempt = self.get_latest_diagnostic(user_id)

        # Normalize stored profile fields (lists may be strings/JSON).
        def _as_list(value: Any) -> List[str]:
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                return []
            out = []
            for v in value:
                norm = (v or "").strip().lower() if isinstance(v, str) else ""
                if norm in ALL_SKILLS and norm not in out:
                    out.append(norm)
            return out

        profile_weak = _as_list(profile.get("weakest_skill"))
        profile_strong = _as_list(profile.get("strongest_skill"))
        profile_current = profile.get("current_band")
        profile_target = profile.get("target_band")
        exam_date = profile.get("exam_date")

        # Diagnostic-derived data (highest priority).
        diagnostic_bands: Dict[str, float] = {}
        diagnostic_overall: Optional[float] = None
        attempt_id: Optional[str] = None
        if attempt:
            attempt_id = attempt.get("id")
            diagnostic_bands = self.derive_skill_bands(attempt.get("skill_scores"))
            raw_overall = attempt.get("overall_band")
            if isinstance(raw_overall, (int, float)):
                diagnostic_overall = round(float(raw_overall) * 2) / 2

        # ── Resolve current band ──
        current_band = None
        if diagnostic_overall is not None:
            current_band = diagnostic_overall
        elif isinstance(profile_current, (int, float)) and profile_current > 0:
            current_band = round(float(profile_current) * 2) / 2
        else:
            current_band = 5.0  # neutral baseline

        # ── Resolve weakest / strongest (diagnostic-first) ──
        diag_weak, diag_strong = self.derive_weakest_strongest(diagnostic_bands)
        weakest = diag_weak if diag_weak else (profile_weak or [])
        strongest = diag_strong if diag_strong else (profile_strong or [])

        # ── Resolve target band ──
        target_band = self.derive_target_band(
            current_band, explicit_target if explicit_target is not None else profile_target
        )

        has_diagnostic = bool(attempt) and bool(diagnostic_bands or diagnostic_overall)
        source = "diagnostic" if has_diagnostic else ("profile" if (profile_weak or profile_strong or profile_current) else "default")

        # Focus areas: the weakest measured skills with human-readable labels.
        focus_areas = [
            f"Prioritize {SKILL_LABELS.get(s, s.title())} (band {bands:.1f})"
            for s, bands in sorted(diagnostic_bands.items(), key=lambda kv: kv[1])[:TOP_N_SKILLS]
        ] if diagnostic_bands else []

        return {
            "user_id": user_id,
            "source": source,
            "has_diagnostic": has_diagnostic,
            "attempt_id": attempt_id,
            "current_band": current_band,
            "target_band": target_band,
            "profile_target_band": profile_target,
            "weakest_skills": weakest,
            "strongest_skills": strongest,
            "skill_bands": diagnostic_bands,
            "focus_areas": focus_areas,
            "profile_exam_date": exam_date,
        }


# Singleton bound to the shared DB session.
from app.db.session import db_session

diagnostic_roadmap_service = DiagnosticRoadmapService(db_session)
