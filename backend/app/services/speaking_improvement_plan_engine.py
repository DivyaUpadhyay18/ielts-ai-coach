"""
Speaking Improvement Plan Engine.

Generates a personalized "Improve My Speaking Band" plan after a student's
Speaking response is evaluated and error-analysed.  The plan bridges the gap
between the student's current estimated band and their target band, using
the student's ACTUAL evaluation data — never generic advice.

Design:
  - ``generate_plan()`` uses the AI service (backend-only) to produce a
    structured plan, with a deterministic fallback.
  - The plan is stored in ``speaking_improvement_plans`` and returned to the client.
  - Recommendations integrate with:
    • Adaptive Scheduler — suggested missions can be scheduled.
    • Resource Engine — resource titles/URLs can be resolved to real resources.
    • Mission Engine — suggested_mission provides a schedulable mission template.
    • AI Mentor — plan content can feed the mentor's coaching context.
"""
import logging
from typing import Any, Dict, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.services.ai_service import (
    AIService,
    _rank_speaking_weaknesses,
    _normalize_speaking_improvement_plan,
)
from app.services.speaking_error_analysis_engine import SpeakingErrorAnalysisEngine

logger = logging.getLogger(__name__)


class SpeakingImprovementPlanEngine:
    """
    Engine for generating and storing "Improve My Speaking Band" plans.

    All operations are owner-scoped.  AI calls stay on the backend.
    The user's original transcript and evaluation are never modified.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.ai_service: AIService = AIService()
        self._error_engine = SpeakingErrorAnalysisEngine(db)

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------
    async def generate_plan(
        self,
        user_id: str,
        response_id: str,
        target_band: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized speaking improvement plan.

        Steps:
          1. Fetch the speaking response (must exist + be owned by user).
          2. Determine target band: explicit arg, user profile, or
             current_band + 1.0 default.
          3. Call the AI service for a structured plan (with deterministic fallback).
          4. Store the plan in ``speaking_improvement_plans``.
          5. Return the plan response.

        The user's original transcript and evaluation are never modified.
        """
        response = self._error_engine._get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking response not found")

        # Fetch the existing error analysis if available.
        analysis = self._get_analysis_for_response(user_id, response_id)

        # Build the evaluation context from the analysis + response.
        evaluation = self._build_evaluation_context(response, analysis)
        if not evaluation.get("overall_band"):
            raise ValidationError(
                "No evaluation data found. Run the Speaking evaluation first."
            )

        current_band = float(evaluation["overall_band"])
        resolved_target = await self._resolve_target_band(
            user_id, current_band, target_band
        )

        ai_result = await self.ai_service.generate_speaking_improvement_plan(
            evaluation=evaluation,
            target_band=resolved_target,
        )

        normalised = _normalize_speaking_improvement_plan(ai_result)

        plan = self._store_plan(
            user_id=user_id,
            response_id=response_id,
            evaluation=evaluation,
            plan=normalised,
        )

        logger.info(
            "speaking improvement plan generated user=%s response=%s current=%.1f target=%.1f",
            user_id, response_id, current_band, resolved_target,
        )
        return self._to_response(plan)

    def get_plan(self, user_id: str, response_id: str) -> Dict[str, Any]:
        """Fetch the most recent improvement plan for a response (owner-scoped)."""
        query = (
            self.db.table("speaking_improvement_plans")
            .select("*")
            .eq("response_id", response_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking improvement plan")
        if not result.data:
            raise NotFoundError(
                "No speaking improvement plan found for this response"
            )
        return self._to_response(result.data[0])

    def list_plans(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """List the user's speaking improvement plans (most recent first)."""
        query = (
            self.db.table("speaking_improvement_plans")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking improvement plans")
        rows = result.data or []
        results = [self._to_response(r) for r in rows]
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_analysis_for_response(self, user_id: str, response_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the most recent error analysis for a response."""
        query = (
            self.db.table("speaking_error_analysis")
            .select("*")
            .eq("response_id", response_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking error analysis")
        return result.data[0] if result.data else None

    def _build_evaluation_context(
        self, response: Dict[str, Any], analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build the evaluation dict for the AI service from analysis + response."""
        if analysis:
            return {
                "overall_band": analysis.get("overall_band"),
                "criteria_bands": {
                    "fluency_coherence": analysis.get("fluency_coherence_band"),
                    "lexical_resource": analysis.get("lexical_resource_band"),
                    "grammatical_range": analysis.get("grammatical_range_band"),
                    "pronunciation": analysis.get("pronunciation_band"),
                },
                "part": analysis.get("part", response.get("part", "part_1")),
                "topic": analysis.get("topic") or response.get("title", ""),
                "transcript": analysis.get("transcript", response.get("transcript", "")),
                "issues_summary": (
                    "; ".join(
                        f"{i.get('issue_type', '')}: {i.get('explanation', '')[:80]}"
                        for i in (analysis.get("issues") or [])
                    )[:300]
                ),
            }
        # Fallback: use response-level data
        return {
            "overall_band": response.get("overall_band") or response.get("band"),
            "criteria_bands": response.get("criteria_bands", {}),
            "part": response.get("part", "part_1"),
            "topic": response.get("title", ""),
            "transcript": response.get("transcript", ""),
            "issues_summary": "",
        }

    def _store_plan(
        self,
        user_id: str,
        response_id: str,
        evaluation: Dict[str, Any],
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a speaking-improvement-plan record and return the stored row."""
        payload = {
            "user_id": user_id,
            "response_id": response_id,
            "current_band": plan["current_band"],
            "target_band": plan["target_band"],
            "band_gap": plan["band_gap"],
            "strongest_criterion": plan.get("strongest_criterion", ""),
            "weakest_criterion": plan.get("weakest_criterion", ""),
            "criterion_priorities": plan.get("criterion_priorities", {}),
            "current_level_description": plan.get("current_level_description", ""),
            "target_level_description": plan.get("target_level_description", ""),
            "specific_changes": plan.get("specific_changes", []),
            "practice_exercises": plan.get("practice_exercises", []),
            "practice_topics": plan.get("practice_topics", []),
            "recommended_resources": plan.get("recommended_resources", []),
            "suggested_daily_minutes": plan.get("suggested_daily_minutes", 15),
            "next_speaking_task": plan.get("next_speaking_task", ""),
            "suggested_mission": plan.get("suggested_mission", {}),
            "plan_json": plan,
            "is_estimate": True,
            "source": plan.get("source", "ai"),
        }
        query = self.db.table("speaking_improvement_plans").insert(payload)
        result = self.db.execute(query, "insert speaking improvement plan")
        if not result.data:
            raise NotFoundError("Failed to store speaking improvement plan")
        return result.data[0]

    @staticmethod
    def _to_response(plan: Dict[str, Any]) -> Dict[str, Any]:
        """Project a stored plan row into the API response shape."""
        import json as _json

        def _coerce_json(field, default):
            val = plan.get(field, default)
            if isinstance(val, str):
                try:
                    return _json.loads(val)
                except (ValueError, TypeError):
                    return default
            return val if val is not None else default

        return {
            "id": plan.get("id"),
            "response_id": plan.get("response_id"),
            "current_band": float(plan.get("current_band", 0.0)),
            "target_band": float(plan.get("target_band", 0.0)),
            "band_gap": float(plan.get("band_gap", 0.0)),
            "strongest_criterion": plan.get("strongest_criterion", ""),
            "weakest_criterion": plan.get("weakest_criterion", ""),
            "criterion_priorities": _coerce_json("criterion_priorities", {}),
            "current_level_description": plan.get("current_level_description") or "",
            "target_level_description": plan.get("target_level_description") or "",
            "specific_changes": _coerce_json("specific_changes", []),
            "practice_exercises": _coerce_json("practice_exercises", []),
            "practice_topics": _coerce_json("practice_topics", []),
            "recommended_resources": _coerce_json("recommended_resources", []),
            "suggested_daily_minutes": plan.get("suggested_daily_minutes", 15),
            "next_speaking_task": plan.get("next_speaking_task") or "",
            "suggested_mission": _coerce_json("suggested_mission", {}),
            "is_estimate": bool(plan.get("is_estimate", True)),
            "source": plan.get("source", "ai"),
            "created_at": plan.get("created_at"),
        }

    async def _resolve_target_band(
        self, user_id: str, current_band: float, explicit: Optional[float]
    ) -> float:
        """Resolve the target band from explicit arg, profile, or default.

        Priority:
          1. Explicit target_band query param.
          2. User profile's target_band field (if set and >= current).
          3. current_band + 1.0 (default gap).
        """
        if explicit is not None:
            return round(float(explicit) * 2) / 2
        try:
            from app.services.diagnostic_roadmap_service import (
                diagnostic_roadmap_service,
            )
            profile = diagnostic_roadmap_service.resolve_profile(user_id)
            profile_target = profile.get("profile_target_band")
            if profile_target is not None and float(profile_target) >= current_band:
                return round(float(profile_target) * 2) / 2
        except Exception:
            pass
        return round(min(9.0, (current_band + 1.0)) * 2) / 2
