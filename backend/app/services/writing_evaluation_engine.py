"""
IELTS Writing Evaluation Engine.

Manages evaluation records attached to submitted Writing Workspace essays.

Design:
  - When an essay is submitted, the Writing Workspace service creates a
    *pending* evaluation record in the ``writing_evaluations`` table (one
    evaluation slot per submitted essay).
  - ``evaluate_submission()`` is an async method that runs the AI evaluation
    via :class:`AIService`, fills in the four official IELTS criterion band
    descriptors, computes the overall band (weighted mean rounded to 0.5),
    computes a confidence score, and stores the result.
  - All AI calls stay on the backend — API keys and prompts never leave
    the server.
  - Every evaluation carries ``is_estimate = True`` to clearly signal that
    the band is an AI-generated estimate, not an official IELTS score.
  - When no OpenAI API key is configured, the AIService falls back to a
    deterministic structural assessment so the pipeline is always functional.

Scoring algorithm (documented):
  Overall Band = round_to_half(mean of the 4 criterion bands))
  The four criteria are:
    Task 1 → Task Achievement, Coherence & Cohesion, Lexical Resource,
             Grammatical Range & Accuracy
    Task 2 → Task Response,    Coherence & Cohesion, Lexical Resource,
             Grammatical Range & Accuracy
  Each criterion band is in 0.0–9.0 in 0.5 increments.
"""
import logging
from typing import Any, Dict, List

from app.core.exceptions import NotFoundError, ValidationError
from app.core.exceptions import DatabaseError
from app.db.session import DatabaseSession
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.ai_service import (
    AIService,
    _compute_confidence,
    _compute_overall_band,
    _round_band,
)

logger = logging.getLogger(__name__)

# Criterion keys used by the AI evaluation — stable contract.
CRITERIA_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)

TASK_1_LABEL = "Task Achievement"
TASK_2_LABEL = "Task Response"


class WritingEvaluationEngine:
    """
    Engine for managing and running AI Writing evaluations.

    All operations are owner-scoped.  AI evaluation is performed via the
    backend-only :class:`AIService` — API keys and prompts never reach the
    frontend.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingWorkspaceRepository(db)
        self.ai_service: AIService = AIService()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    async def evaluate_submission(
        self,
        user_id: str,
        submission_id: str,
        task_type: str = "task_2",
    ) -> Dict[str, Any]:
        """
        Run the full AI evaluation on a submitted essay and store the result.

        Steps:
          1. Fetch (and validate) the submission — must be 'submitted'.
          2. If a pending evaluation already exists, reuse it; otherwise
             create one.
          3. Call the AI service to produce the 4-criteria band assessment,
             overall band, confidence, strengths, weaknesses, errors, and
             improvement suggestions.
          4. Store the complete evaluation in ``writing_evaluations``.
          5. Update the submission's ``ai_evaluation`` JSONB column.
          6. Return the evaluation response.

        Raises:
          NotFoundError: if the submission doesn't exist.
          ValidationError: if the submission isn't in 'submitted' state.
        """
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") != "submitted":
            raise ValidationError(
                "Only submitted essays can be evaluated. Submit the essay first."
            )

        essay_text = submission.get("essay_text") or ""
        prompt_text = submission.get("prompt_text") or ""
        task_type = submission.get("task_type") or task_type

        # Run the AI evaluation (backend-only).
        ai_result = await self.ai_service.analyze_writing(
            essay_text=essay_text,
            task_type=task_type,
            prompt_text=prompt_text,
        )

        # Run the detailed per-issue error analysis (backend-only). Never
        # fatal: if it fails we store an empty list rather than failing the
        # whole evaluation.
        error_analysis: List[Dict[str, Any]] = []
        try:
            error_result = await self.ai_service.analyze_writing_errors(
                essay_text=essay_text,
                task_type=task_type,
                prompt_text=prompt_text,
            )
            error_analysis = (error_result or {}).get("error_analysis") or []
        except Exception as e:  # noqa: BLE001 - best-effort error analysis
            logger.warning("writing error analysis failed user=%s: %s", user_id, e)

        # Ensure a pending record exists (for essays submitted before the
        # evaluation infrastructure existed).
        evaluation = self.repo.get_evaluation(submission_id, user_id)
        if not evaluation:
            evaluation = self.repo.create_evaluation(
                user_id=user_id,
                submission_id=submission_id,
                task_type=task_type,
                word_count=int(submission.get("word_count") or 0),
            )

        # Store the complete AI evaluation.
        stored = self._store_ai_evaluation(
            evaluation_id=evaluation["id"],
            user_id=user_id,
            submission_id=submission_id,
            task_type=task_type,
            ai_result=ai_result,
            error_analysis=error_analysis,
        )

        # Update the submission with the AI evaluation result.
        self.repo.update_submission(submission_id, user_id, {
            "ai_evaluation": stored,
        })

        logger.info(
            "writing AI evaluation stored user=%s submission=%s band=%s conf=%s",
            user_id, submission_id, stored.get("overall_band"),
            stored.get("confidence"),
        )
        return self._to_response(stored)

    def get_evaluation(
        self, user_id: str, submission_id: str
    ) -> Dict[str, Any]:
        """Fetch the evaluation for a submission (owner-scoped)."""
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")

        evaluation = self.repo.get_evaluation(submission_id, user_id)
        if not evaluation:
            raise NotFoundError("No evaluation found for this submission")
        return self._to_response(evaluation)

    def get_user_evaluations(
        self, user_id: str, limit: int = 20
    ) -> Dict[str, Any]:
        """List the current user's evaluation records (most recent first)."""
        rows = self.repo.list_evaluations(user_id, limit)
        results = [
            {
                "submission_id": r.get("submission_id"),
                "overall_band": r.get("overall_band"),
                "confidence": r.get("confidence"),
                "word_count": int(r.get("word_count") or 0),
                "task_type": r.get("task_type") or "task_2",
                "evaluation_status": r.get("status") or "pending",
                "created_at": r.get("created_at") or r.get("evaluated_at"),
            }
            for r in rows
        ]
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------
    def _store_ai_evaluation(
        self,
        evaluation_id: str,
        user_id: str,
        submission_id: str,
        task_type: str,
        ai_result: Dict[str, Any],
        error_analysis: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an evaluation record with the AI-computed scores.

        Called after the AI service returns the 4-criteria assessment, plus
        the optional per-issue error analysis. Flips the record status from
        'pending' to 'evaluated'.
        """
        criteria = ai_result.get("criteria", {}) or {}

        # Extract bands for the overall-band formula.
        bands_in = {
            k: float(v.get("band", 0.0)) if isinstance(v, dict) else float(v)
            for k, v in criteria.items()
        }
        overall_band = ai_result.get(
            "overall_band", _compute_overall_band(bands_in, task_type)
        )
        confidence = ai_result.get(
            "confidence",
            _compute_confidence(bands_in, int(ai_result.get("word_count") or 0)),
        )

        # Build the full criteria detail for storage.
        criteria_detail = {}
        for key, label in [
            ("task_response", TASK_2_LABEL if task_type == "task_2" else TASK_1_LABEL),
            ("coherence_cohesion", "Coherence and Cohesion"),
            ("lexical_resource", "Lexical Resource"),
            ("grammatical_range_accuracy", "Grammatical Range and Accuracy"),
        ]:
            c = criteria.get(key, {})
            if isinstance(c, dict):
                criteria_detail[key] = {
                    "band": _round_band(float(c.get("band", 0.0))),
                    "label": c.get("label", label),
                    "strength": c.get("strength", ""),
                    "weakness": c.get("weakness", ""),
                    "errors": c.get("errors", []),
                    "suggestions": c.get("suggestions", []),
                }
            else:
                criteria_detail[key] = {"band": 0.0, "label": label}

        payload = {
            "status": "evaluated",
            "overall_band": float(overall_band),
            "confidence": float(confidence),
            "criteria_bands": {
                k: v.get("band") if isinstance(v, dict) else float(v)
                for k, v in criteria_detail.items()
            },
            "criteria_detail": criteria_detail,
            "strengths": self._collect_field(criteria, "strength"),
            "weaknesses": self._collect_field(criteria, "weakness"),
            "errors": self._collect_list_field(criteria, "errors"),
            "suggestions": self._collect_list_field(criteria, "suggestions"),
            "error_analysis": list(error_analysis or []),
            "word_count": int(ai_result.get("word_count") or 0),
            "is_estimate": True,
            "source": ai_result.get("source", "ai"),
            "evaluated_at": ai_result.get("evaluated_at"),
        }

        return self.repo.update_evaluation(evaluation_id, user_id, payload)

    @staticmethod
    def _collect_field(criteria: Dict[str, Any], field: str) -> List[str]:
        """Collect a text field from all criteria into a flat list."""
        return [
            c[field]
            for c in criteria.values()
            if isinstance(c, dict) and c.get(field)
        ]

    @staticmethod
    def _collect_list_field(criteria: Dict[str, Any], field: str) -> List[str]:
        """Collect a list field from all criteria into a flat list."""
        result = []
        for c in criteria.values():
            if isinstance(c, dict):
                result.extend(c.get(field, []) or [])
        return result

    # ------------------------------------------------------------------
    # Response projection
    # ------------------------------------------------------------------
    @staticmethod
    def _to_response(evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Project a stored evaluation row into the API response shape.

        Pending records carry ``criteria_bands``/``criteria_detail`` JSONB and
        no overall band yet.  Evaluated records carry the full AI assessment.
        ``is_estimate`` is always True to signal the band is an AI estimate.
        """
        criteria_detail = evaluation.get("criteria_detail") or {}

        # Build the criteria dict for the response from detail or bands.
        criteria_resp = {}
        for key in CRITERIA_KEYS:
            detail = criteria_detail.get(key, {})
            if isinstance(detail, dict) and detail:
                criteria_resp[key] = {
                    "band": detail.get("band", 0.0),
                    "label": detail.get("label", key),
                    "strength": detail.get("strength", ""),
                    "weakness": detail.get("weakness", ""),
                    "errors": detail.get("errors", []),
                    "suggestions": detail.get("suggestions", []),
                }
            else:
                # Pending record — populate from bands only.
                bands = evaluation.get("criteria_bands") or {}
                criteria_resp[key] = {
                    "band": bands.get(key, 0.0) if isinstance(bands, dict) else 0.0,
                    "label": key,
                    "strength": "",
                    "weakness": "",
                    "errors": [],
                    "suggestions": [],
                }

        result = {
            "task_type": evaluation.get("task_type") or "task_2",
            "criteria": criteria_resp,
            "criteria_bands": evaluation.get("criteria_bands") or {},
            "criteria_detail": criteria_detail,
            "overall_band": evaluation.get("overall_band"),
            "confidence": evaluation.get("confidence"),
            "is_estimate": bool(evaluation.get("is_estimate", True)),
            "word_count": int(evaluation.get("word_count") or 0),
            "source": evaluation.get("source") or "pending",
            "strengths": evaluation.get("strengths") or [],
            "weaknesses": evaluation.get("weaknesses") or [],
            "errors": evaluation.get("errors") or [],
            "suggestions": evaluation.get("suggestions") or [],
            "error_analysis": evaluation.get("error_analysis") or [],
            "evaluated_at": evaluation.get("evaluated_at"),
            "evaluation_status": evaluation.get("status") or "pending",
            "is_official": False,
        }
        # Strip None values from optional fields.
        result["overall_band"] = evaluation.get("overall_band")  # may be None
        result["confidence"] = evaluation.get("confidence")  # may be None
        result["evaluated_at"] = evaluation.get("evaluated_at")  # may be None
        return result
