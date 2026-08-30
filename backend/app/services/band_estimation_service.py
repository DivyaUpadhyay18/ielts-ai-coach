"""
Band Estimation Engine Service.

A deterministic (NO AI) engine that maps a user's skill-wise band scores
to an estimated overall IELTS band.

Algorithm:
  - Estimated Overall Band = mean of the 4 official skills (reading, listening,
    writing, speaking), rounded to the nearest 0.5 per IELTS convention.
  - Skill-wise Band = each input band (rounded to 0.5).
  - Confidence Score = 100 minus dispersion penalty, scaled by completeness.
    Dispersion = max_skill - min_skill (in band steps). Higher dispersion
    lowers confidence because the estimate is less predictable.
    Completeness = fraction of the 4 official skills provided.
  - Weakest/Strongest Skills = sorted ascending/descending by band score.
  - Explanations = deterministic text per skill describing the score.

All scores are rounded to 0.5 steps (IELTS band convention).

See BAND_ESTIMATION.md for full formula documentation.
"""
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.models.band_estimation import (
    OVERALL_SKILLS,
    ALL_SKILLS,
    CONFIDENCE_LABELS,
    BandEstimationInput,
)
from app.repositories.band_estimation_repo import BandEstimationRepository

logger = logging.getLogger(__name__)

# Band step: IELTS bands are in 0.5 increments.
BAND_STEP = 0.5

# Skill display names.
SKILL_DISPLAY: Dict[str, str] = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Vocabulary",
    "grammar": "Grammar",
}

# Confidence thresholds.
CONFIDENCE_HIGH = 90.0
CONFIDENCE_MEDIUM = 75.0
CONFIDENCE_LOW = 50.0

# Dispersion penalty: each 0.5 band of dispersion reduces confidence by this amount.
DISPERSION_PENALTY_PER_STEP = 3.0

# Completeness weight: each provided official skill adds this fraction of 100 points.
# 1.0 means all 4 skills provided = base of 100 before dispersion penalty.
COMPLETENESS_WEIGHT = 1.0


class BandEstimationService:
    """Deterministic band estimation engine — no AI, all formulas documented."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = BandEstimationRepository(db)

    # ─── Public API ────────────────────────────────────────────────────

    def estimate(self, user_id: str, data: BandEstimationInput) -> Dict[str, Any]:
        """
        Compute a band estimation from skill-wise input scores.

        Args:
            user_id: The user ID (for storage).
            data: BandEstimationInput with reading, listening, writing, speaking,
                  vocabulary, and grammar scores (0-9 each, rounded to 0.5).

        Returns:
            A dict matching BandEstimationResponse (stored + returned).
        """
        today = date.today()
        raw_input = {skill: getattr(data, skill) for skill in ALL_SKILLS}

        # ─── 1. Compute skill-wise bands ────────────────────────────────
        # Each input is already rounded to 0.5 by the Pydantic validator.
        skill_bands: Dict[str, float] = {}
        explanations: Dict[str, str] = {}
        for skill in ALL_SKILLS:
            band = float(getattr(data, skill))
            band = self._round_to_band(band)
            skill_bands[skill] = band
            explanations[skill] = self._explain_skill(skill, band, raw_input)

        # ─── 2. Compute overall band ────────────────────────────────────
        overall_band = self._compute_overall_band(skill_bands)

        # ─── 3. Compute confidence ──────────────────────────────────────
        confidence_score, confidence_label = self._compute_confidence(skill_bands, raw_input)

        # ─── 4. Identify weakest / strongest skills ─────────────────────
        weakest_skills = self._compute_weakest_skills(skill_bands)
        strongest_skills = self._compute_strongest_skills(skill_bands)

        # ─── 5. Build formula documentation ───────────────────────────
        formulas = self._build_formulas()

        # ─── 6. Assemble response ─────────────────────────────────────
        result = {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_date": today.isoformat(),
            "overall_band": overall_band,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "skill_bands": skill_bands,
            "weakest_skills": weakest_skills,
            "strongest_skills": strongest_skills,
            "explanations": explanations,
            "formulas": formulas,
            "raw_input": raw_input,
        }

        # ─── 7. Store in DB ───────────────────────────────────────────
        self._safe_save_result(user_id, result)

        return result

    def get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the user's most recent band estimation snapshot."""
        return self._safe_get_latest(user_id)

    def get_history(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Return paginated history of band estimations for a user."""
        items = self._safe_list_history(user_id, limit, offset)
        total = self._safe_count_history(user_id)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ─── Algorithm Implementations ────────────────────────────────────

    @staticmethod
    def _round_to_band(value: float) -> float:
        """Round a score to the nearest 0.5 (IELTS band step)."""
        return round(value / BAND_STEP) * BAND_STEP

    @staticmethod
    def _compute_overall_band(skill_bands: Dict[str, float]) -> float:
        """
        Estimated Overall Band = mean of the 4 official IELTS skills,
        rounded to the nearest 0.5, clamped to [0, 9].

        Formula:
          overall = round(0.5 * (reading + listening + writing + speaking) / 2)
          i.e., mean of 4 skills, rounded to nearest 0.5.
        """
        four_skills = OVERALL_SKILLS  # ("reading", "listening", "writing", "speaking")
        values = [skill_bands.get(s, 0.0) for s in four_skills]
        mean = sum(values) / len(values) if values else 0.0
        overall = BandEstimationService._round_to_band(mean)
        overall = max(0.0, min(9.0, overall))
        return overall

    @staticmethod
    def _compute_confidence(
        skill_bands: Dict[str, float], raw_input: Dict[str, float]
    ) -> tuple:
        """
        Confidence Score (0–100).

        Formula:
          dispersion = max(skill_bands) - min(skill_bands)
          dispersion_steps = round(dispersion / BAND_STEP)
          dispersion_penalty = dispersion_steps * DISPERSION_PENALTY_PER_STEP

          completeness = number of official skills provided / 4
          completeness_bonus = completeness * COMPLETENESS_WEIGHT * 100

          confidence = completeness_bonus - dispersion_penalty
          confidence = clamp(confidence, 0, 100)

        Confidence Label:
          very_high: >= 90
          high:     >= 75
          medium:   >= 50
          low:      < 50
        """
        four_skills = OVERALL_SKILLS
        official_bands = [skill_bands.get(s, 0.0) for s in four_skills]

        if not official_bands:
            return 0.0, "low"

        max_band = max(official_bands)
        min_band = min(official_bands)
        dispersion = max_band - min_band
        dispersion_steps = round(dispersion / BAND_STEP)
        dispersion_penalty = dispersion_steps * DISPERSION_PENALTY_PER_STEP

        # Completeness: count how many official skills have a non-zero input
        provided = sum(1 for s in four_skills if raw_input.get(s, 0.0) > 0)
        completeness = provided / len(four_skills)
        completeness_bonus = completeness * COMPLETENESS_WEIGHT * 100

        confidence = completeness_bonus - dispersion_penalty
        confidence = max(0.0, min(100.0, confidence))

        if confidence >= CONFIDENCE_HIGH:
            label = "very_high"
        elif confidence >= CONFIDENCE_MEDIUM:
            label = "high"
        elif confidence >= CONFIDENCE_LOW:
            label = "medium"
        else:
            label = "low"

        return round(confidence, 2), label

    @staticmethod
    def _compute_weakest_skills(skill_bands: Dict[str, float]) -> List[str]:
        """Weakest skills sorted ascending by band, then by skill name."""
        sorted_skills = sorted(skill_bands.keys(), key=lambda s: (skill_bands[s], s))
        return sorted_skills[:3]

    @staticmethod
    def _compute_strongest_skills(skill_bands: Dict[str, float]) -> List[str]:
        """Strongest skills sorted descending by band, then by skill name."""
        sorted_skills = sorted(skill_bands.keys(), key=lambda s: (-skill_bands[s], s))
        return sorted_skills[:3]

    @staticmethod
    def _explain_skill(
        skill: str, band: float, raw_input: Dict[str, float]
    ) -> str:
        """Generate a deterministic explanation for a skill's band score."""
        display = SKILL_DISPLAY.get(skill, skill.capitalize())
        raw = raw_input.get(skill, 0.0)

        if raw == 0.0:
            return f"No input provided for {display}. Score defaults to 0.0."

        if band >= 8.0:
            level = "expert"
            desc = "consistently accurate with sophisticated control"
        elif band >= 7.0:
            level = "proficient"
            desc = "mostly accurate with some complexity"
        elif band >= 6.0:
            level = "competent"
            desc = "adequate control with occasional errors"
        elif band >= 5.0:
            level = "modest"
            desc = "limited control with frequent errors"
        else:
            level = "elementary"
            desc = "significant difficulty with basic communication"

        return (
            f"{display}: Band {band:.1f} (raw input: {raw:.1f}). "
            f"Assessment: {level} — {desc}."
        )

    @staticmethod
    def _build_formulas() -> Dict[str, str]:
        """Return human-readable documentation of every formula used."""
        return {
            "overall_band": (
                "overall = mean of 4 official skill bands (reading, listening, writing, speaking), "
                "rounded to nearest 0.5, clamped to [0, 9]."
            ),
            "confidence_score": (
                "confidence = (completeness_bonus - dispersion_penalty), where "
                "completeness_bonus = (provided_skills / 4) * 100, "
                "dispersion_penalty = round((max_band - min_band) / 0.5) * 3. "
                "Clamped to 0-100. Label: very_high >= 90, high >= 75, medium >= 50, low < 50."
            ),
            "weakest_skills": "Skill bands sorted ascending (lowest first), top 3.",
            "strongest_skills": "Skill bands sorted descending (highest first), top 3.",
            "skill_band": "Each input score rounded to nearest 0.5 (IELTS band step).",
        }

    # ─── Safe DB wrappers ────────────────────────────────────────────

    def _safe_save_result(self, user_id: str, data: Dict[str, Any]) -> None:
        """Safely store the estimation result in the database."""
        if self.db is None:
            return
        try:
            self.repo.save_result(user_id, data)
        except Exception as exc:
            logger.warning("Failed to save band estimation: %s", exc)

    def _safe_get_latest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Safely fetch the latest estimation."""
        if self.db is None:
            return None
        try:
            return self.repo.get_latest(user_id)
        except Exception as exc:
            logger.warning("Failed to fetch latest band estimation: %s", exc)
            return None

    def _safe_list_history(self, user_id: str, limit: int, offset: int) -> List[Dict[str, Any]]:
        """Safely list estimation history."""
        if self.db is None:
            return []
        try:
            return self.repo.list_results(user_id, limit=limit, offset=offset)
        except Exception as exc:
            logger.warning("Failed to list band estimation history: %s", exc)
            return []

    def _safe_count_history(self, user_id: str) -> int:
        """Safely count estimation history."""
        if self.db is None:
            return 0
        try:
            return self.repo.count_results(user_id)
        except Exception as exc:
            logger.warning("Failed to count band estimation history: %s", exc)
            return 0


# Singleton bound to the shared DB session.
from app.db.session import db_session

band_estimation_service = BandEstimationService(db_session)