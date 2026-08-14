"""
Writing Improvement Plan Engine.

Generates a personalized "Improve My Band" plan after a student's essay is
evaluated.  The plan bridges the gap between the student's current estimated
band and their target band, using the *actual* evaluation data — not generic
advice.

Design:
  - ``generate_plan()`` uses the AI service (backend-only) to produce a
    structured plan, with a deterministic fallback.
  - The plan is stored in ``writing_improvement_plans`` and returned to the
    client.
  - Recommendations are integrated with the Resource Engine (resolved via
    ``RecommendationEngineService``) and the Adaptive Scheduler (suggested
    missions can be created + scheduled).
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.ai_service import AIService, _rank_weaknesses

logger = logging.getLogger(__name__)


class WritingImprovementPlanEngine:
    """
    Engine for generating and storing "Improve My Band" plans.

    All operations are owner-scoped.  AI calls stay on the backend.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingWorkspaceRepository(db)
        self.ai_service: AIService = AIService()

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------
    async def generate_plan(
        self,
        user_id: str,
        submission_id: str,
        target_band: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized improvement plan for a submitted + evaluated essay.

        Steps:
          1. Fetch the submission (must be 'submitted').
          2. Fetch the stored evaluation (must be 'evaluated').
          3. Determine the target band: explicit arg, user profile, or
             current_band + 1.0 default.
          4. Call the AI service to produce the plan (with deterministic fallback).
          5. Store the plan in ``writing_improvement_plans``.
          6. Return the plan response.

        Raises:
            NotFoundError: if submission or evaluation doesn't exist.
            ValidationError: if submission isn't submitted or evaluation isn't ready.
        """
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") != "submitted":
            raise ValidationError(
                "Only submitted essays can be improved. Submit the essay first."
            )

        evaluation = self.repo.get_evaluation(submission_id, user_id)
        if not evaluation:
            raise NotFoundError(
                "No evaluation found. Run the AI evaluation first."
            )
        if evaluation.get("status") != "evaluated" or not evaluation.get("overall_band"):
            raise ValidationError(
                "Evaluation is still pending. Wait for the evaluation to complete."
            )

        essay_text = submission.get("essay_text") or ""

        # Determine target band.
        current_band = float(evaluation.get("overall_band") or 0.0)
        resolved_target = await self._resolve_target_band(user_id, current_band, target_band)

        # Generate the plan via AI service (backend-only).
        ai_result = await self.ai_service.generate_improvement_plan(
            essay_text=essay_text,
            evaluation=evaluation,
            target_band=resolved_target,
        )

        # Persist the plan.
        plan = self.repo.create_improvement_plan(
            user_id=user_id,
            data={
                "evaluation_id": evaluation["id"],
                "submission_id": submission_id,
                "task_type": submission.get("task_type", "task_2"),
                "current_band": current_band,
                "target_band": resolved_target,
                "band_gap": round(resolved_target - current_band, 1),
                "weaknesses": _rank_weaknesses(evaluation.get("criteria_bands") or {}),
                "current_level_description": ai_result.get("current_level_description", ""),
                "target_level_description": ai_result.get("target_level_description", ""),
                "specific_changes": ai_result.get("specific_changes", []),
                "practice_exercises": ai_result.get("practice_exercises", []),
                "recommended_resources": ai_result.get("recommended_resources", []),
                "suggested_mission": ai_result.get("suggested_mission", {}),
                "plan_json": ai_result,
                "is_estimate": True,
                "source": ai_result.get("source", "ai"),
            },
        )

        logger.info(
            "improvement plan generated user=%s submission=%s current=%.1f target=%.1f",
            user_id, submission_id, current_band, resolved_target,
        )
        return self._to_response(plan)

    def get_plan(
        self, user_id: str, evaluation_id: str
    ) -> Dict[str, Any]:
        """Fetch a stored improvement plan (owner-scoped)."""
        plan = self.repo.get_improvement_plan(evaluation_id, user_id)
        if not plan:
            raise NotFoundError("No improvement plan found for this evaluation")
        return self._to_response(plan)

    def list_plans(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """List the user's improvement plans (most recent first)."""
        rows = self.repo.list_improvement_plans(user_id, limit)
        results = [self._to_response(r) for r in rows]
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _resolve_target_band(
        self, user_id: str, current_band: float, explicit: Optional[float]
    ) -> float:
        """Resolve the target band from explicit arg, profile, or default.

        Priority:
          1. Explicit target_band query param.
          2. User profile's ``target_band`` field (if explicitly set and >= current).
          3. ``current_band + 1.0`` (default gap).
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

    @staticmethod
    def _to_response(plan: Dict[str, Any]) -> Dict[str, Any]:
        """Project a stored plan row into the API response shape."""
        return {
            "id": plan.get("id"),
            "evaluation_id": plan.get("evaluation_id"),
            "submission_id": plan.get("submission_id"),
            "task_type": plan.get("task_type", "task_2"),
            "current_band": float(plan.get("current_band", 0.0)),
            "target_band": float(plan.get("target_band", 0.0)),
            "band_gap": float(plan.get("band_gap", 0.0)),
            "weaknesses": plan.get("weaknesses") or [],
            "current_level_description": plan.get("current_level_description", ""),
            "target_level_description": plan.get("target_level_description", ""),
            "specific_changes": plan.get("specific_changes") or [],
            "practice_exercises": plan.get("practice_exercises") or [],
            "recommended_resources": plan.get("recommended_resources") or [],
            "suggested_mission": plan.get("suggested_mission") or {},
            "is_estimate": bool(plan.get("is_estimate", True)),
            "source": plan.get("source", "ai"),
            "created_at": plan.get("created_at"),
        }
