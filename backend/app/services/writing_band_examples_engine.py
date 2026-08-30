"""
Writing Band Examples Engine.

Generates and stores band-level improvement examples for a student's essay.
The examples are tailored to the student's actual evaluation data — not
generic advice.  The AI never overwrites the user's original essay.
"""
import logging
from typing import Any, Dict, List

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.ai_service import AIService, _rank_weaknesses

logger = logging.getLogger(__name__)


class WritingBandExamplesEngine:
    """
    Engine for generating and storing band-level improvement examples.

    All operations are owner-scoped.  AI calls stay on the backend.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingWorkspaceRepository(db)
        self.ai_service: AIService = AIService()

    # ------------------------------------------------------------------
    # Example generation
    # ------------------------------------------------------------------
    async def generate_examples(
        self,
        user_id: str,
        submission_id: str,
        target_band: float,
        generate_sample: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate band-level improvement examples for a submitted + evaluated essay.

        Steps:
          1. Fetch the submission (must be 'submitted').
          2. Fetch the evaluation (must be 'evaluated').
          3. Call the AI service to produce examples (with deterministic fallback).
          4. Store the examples in ``writing_band_examples``.
          5. Return the response.

        The user's original essay is never modified or overwritten.
        """
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") != "submitted":
            raise ValidationError(
                "Only submitted essays can receive improvement examples."
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
        current_band = float(evaluation.get("overall_band") or 0.0)

        # Generate the examples via AI service (backend-only).
        ai_result = await self.ai_service.generate_band_examples(
            essay_text=essay_text,
            evaluation=evaluation,
            target_band=target_band,
            generate_sample=generate_sample,
        )

        criteria_bands = evaluation.get("criteria_bands") or {}
        weaknesses = _rank_weaknesses(criteria_bands)

        # Determine focus areas from error_analysis + weakest criteria.
        error_analysis = evaluation.get("error_analysis") or []
        error_types = sorted({e.get("error_type", "Grammar") for e in error_analysis})
        focus_areas = list(dict.fromkeys(error_types + weaknesses))[:6]

        stored = self._store_examples(
            user_id=user_id,
            submission_id=submission_id,
            evaluation_id=evaluation["id"],
            task_type=submission.get("task_type", "task_2"),
            target_band=float(target_band),
            current_band=current_band,
            focus_areas=focus_areas,
            ai_result=ai_result,
        )

        logger.info(
            "band examples generated user=%s submission=%s target=%.1f sample=%s",
            user_id, submission_id, target_band, generate_sample,
        )
        return self._to_response(stored)

    def get_examples(
        self, user_id: str, evaluation_id: str
    ) -> Dict[str, Any]:
        """Fetch stored band examples for an evaluation (owner-scoped)."""
        query = (
            self.db.table("writing_band_examples")
            .select("*")
            .eq("evaluation_id", evaluation_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch writing band examples")
        if not result.data:
            raise NotFoundError("No band examples found for this evaluation")
        return self._to_response(result.data[0])

    def list_examples(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """List the user's band examples (most recent first)."""
        query = (
            self.db.table("writing_band_examples")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list writing band examples")
        rows = result.data or []
        results = [self._to_response(r) for r in rows]
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------
    def _store_examples(
        self,
        user_id: str,
        submission_id: str,
        evaluation_id: str,
        task_type: str,
        target_band: float,
        current_band: float,
        focus_areas: List[str],
        ai_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a band-example record and return the stored row."""
        payload = {
            "user_id": user_id,
            "submission_id": submission_id,
            "task_type": task_type,
            "target_band": target_band,
            "focus_areas": focus_areas,
            "key_weaknesses": ai_result.get("key_weaknesses", ""),
            "improved_sentences": ai_result.get("improved_sentences", []),
            "vocabulary_alternatives": ai_result.get("vocabulary_alternatives", []),
            "paragraph_structure": ai_result.get("paragraph_structure", ""),
            "example_introduction": ai_result.get("example_introduction", ""),
            "example_body_paragraph": ai_result.get("example_body_paragraph", ""),
            "example_conclusion": ai_result.get("example_conclusion", ""),
            "sample_answer": ai_result.get("sample_answer"),
            "is_sample_answer": ai_result.get("is_sample_answer", False),
            "plan_json": ai_result,
            "is_estimate": True,
            "source": ai_result.get("source", "ai"),
        }
        query = self.db.table("writing_band_examples").insert(payload)
        result = self.db.execute(query, "insert writing band examples")
        if not result.data:
            raise NotFoundError("Failed to store band examples")
        return result.data[0]

    @staticmethod
    def _to_response(row: Dict[str, Any]) -> Dict[str, Any]:
        """Project a stored row into the API response shape."""
        return {
            "id": row.get("id"),
            "evaluation_id": row.get("evaluation_id"),
            "submission_id": row.get("submission_id"),
            "task_type": row.get("task_type", "task_2"),
            "target_band": float(row.get("target_band", 0.0)),
            "current_band": float(row.get("current_band", 0.0)),
            "focus_areas": row.get("focus_areas") or [],
            "key_weaknesses": row.get("key_weaknesses", ""),
            "improved_sentences": row.get("improved_sentences") or [],
            "vocabulary_alternatives": row.get("vocabulary_alternatives") or [],
            "paragraph_structure": row.get("paragraph_structure", ""),
            "example_introduction": row.get("example_introduction", ""),
            "example_body_paragraph": row.get("example_body_paragraph", ""),
            "example_conclusion": row.get("example_conclusion", ""),
            "sample_answer": row.get("sample_answer"),
            "is_sample_answer": bool(row.get("is_sample_answer", False)),
            "is_estimate": bool(row.get("is_estimate", True)),
            "source": row.get("source", "ai"),
            "created_at": row.get("created_at"),
        }
