"""
Speaking Error Analysis Engine.

Generates and stores detailed error analysis for a student's spoken
response in an IELTS Speaking test.

Analysed categories:
  - Grammar errors
  - Repeated vocabulary
  - Weak vocabulary
  - Unnatural expressions
  - Filler words
  - Repetition
  - Incomplete sentences
  - Hesitation indicators
  - Coherence problems
  - Pronunciation (only when supported by audio/transcript evidence)

For every issue the engine reports:
  - original_phrase (verbatim from the transcript)
  - issue_type
  - explanation (What happened?)
  - why_problem (Why is this a problem?)
  - suggested_improvement (How should I improve it?)
  - criterion_affected
  - severity

The analysis never shames the student — it is constructive and specific.
The user's original recording/transcript is never overwritten.
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.services.ai_service import AIService, _normalize_speaking_error_analysis

logger = logging.getLogger(__name__)


class SpeakingErrorAnalysisEngine:
    """
    Engine for generating and storing detailed speaking error analysis.

    All operations are owner-scoped.  AI calls stay on the backend.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.ai_service: AIService = AIService()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------
    async def analyze_transcript(
        self,
        user_id: str,
        response_id: str,
        part: str = "part_1",
        topic: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a detailed speaking error analysis for a recorded response.

        Steps:
          1. Fetch the response (speaking_test_responses row).
          2. Validate it has a transcript.
          3. Call the AI service for error analysis (with deterministic fallback).
          4. Store the analysis in ``speaking_error_analysis``.
          5. Return the response projection.

        The user's original transcript is never modified.
        """
        response = self._get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking response not found")

        transcript = response.get("transcript") or ""
        if not transcript.strip():
            raise ValidationError(
                "No transcript available for analysis. "
                "Please save your response with a transcript first."
            )

        ai_result = await self.ai_service.analyze_speaking_errors(
            transcript=transcript,
            part=part or response.get("part", "part_1"),
            topic=topic or response.get("title", ""),
        )

        normalised = _normalize_speaking_error_analysis(ai_result)

        stored = self._store_analysis(
            user_id=user_id,
            response_id=response_id,
            part=part or response.get("part", "part_1"),
            topic=topic or response.get("title", ""),
            transcript=transcript,
            ai_result=normalised,
        )

        logger.info(
            "speaking error analysis generated user=%s response=%s issues=%d",
            user_id, response_id, len(normalised.get("issues", []))
        )
        return self._to_response(stored)

    def get_analysis(self, user_id: str, response_id: str) -> Dict[str, Any]:
        """Fetch the most recent analysis for a response (owner-scoped)."""
        query = (
            self.db.table("speaking_error_analysis")
            .select("*")
            .eq("response_id", response_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking error analysis")
        if not result.data:
            raise NotFoundError(
                "No speaking error analysis found for this response"
            )
        return self._to_response(result.data[0])

    def list_analyses(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """List the user's speaking error analyses (most recent first)."""
        query = (
            self.db.table("speaking_error_analysis")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        result = self.db.execute(query, "list speaking error analyses")
        rows = result.data or []
        results = [self._to_response(r) for r in rows]
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def _get_response(self, response_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a speaking_test_responses row (owner-scoped)."""
        query = (
            self.db.table("speaking_test_responses")
            .select("*")
            .eq("id", response_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch speaking response")
        return result.data[0] if result.data else None

    def _store_analysis(
        self,
        user_id: str,
        response_id: str,
        part: str,
        topic: str,
        transcript: str,
        ai_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a speaking-error-analysis record and return the stored row."""
        issues = ai_result.get("issues", [])
        severity_counts = {"critical": 0, "major": 0, "minor": 0}
        for issue in issues:
            sev = issue.get("severity", "minor")
            if sev in severity_counts:
                severity_counts[sev] += 1

        payload = {
            "user_id": user_id,
            "response_id": response_id,
            "part": part,
            "transcript": transcript,
            "overall_band": float(ai_result.get("overall_band", 6.0)),
            "fluency_coherence_band": float(ai_result.get("fluency_coherence_band", 6.0)),
            "lexical_resource_band": float(ai_result.get("lexical_resource_band", 6.0)),
            "grammatical_range_band": float(ai_result.get("grammatical_range_band", 6.0)),
            "pronunciation_band": float(ai_result.get("pronunciation_band", 6.0)),
            "issue_count": len(issues),
            "high_severity_count": severity_counts["critical"] + severity_counts["major"],
            "medium_severity_count": 0,
            "low_severity_count": severity_counts["minor"],
            "issues": issues,
            "feedback": ai_result.get("feedback", ""),
            "plan_json": ai_result,
            "is_estimate": True,
            "source": ai_result.get("source", "ai"),
        }
        query = self.db.table("speaking_error_analysis").insert(payload)
        result = self.db.execute(query, "insert speaking error analysis")
        if not result.data:
            raise NotFoundError("Failed to store speaking error analysis")
        return result.data[0]

    @staticmethod
    def _to_response(row: Dict[str, Any]) -> Dict[str, Any]:
        """Project a stored row into the API response shape."""
        issues = row.get("issues") or []
        if isinstance(issues, str):
            import json as _json
            try:
                issues = _json.loads(issues)
            except (ValueError, TypeError):
                issues = []

        return {
            "id": row.get("id"),
            "response_id": row.get("response_id"),
            "part": row.get("part", "part_1"),
            "topic": row.get("topic", ""),
            "issues": issues,
            "overall_band": float(row.get("overall_band", 6.0)),
            "fluency_coherence_band": float(row.get("fluency_coherence_band", 6.0)),
            "lexical_resource_band": float(row.get("lexical_resource_band", 6.0)),
            "grammatical_range_band": float(row.get("grammatical_range_band", 6.0)),
            "pronunciation_band": float(row.get("pronunciation_band", 6.0)),
            "feedback": row.get("feedback") or "",
            "issue_count": row.get("issue_count", len(issues)),
            "high_severity_count": row.get("high_severity_count", 0),
            "medium_severity_count": row.get("medium_severity_count", 0),
            "low_severity_count": row.get("low_severity_count", 0),
            "is_estimate": bool(row.get("is_estimate", True)),
            "source": row.get("source", "ai"),
            "created_at": row.get("created_at"),
        }
