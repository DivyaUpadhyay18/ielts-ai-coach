"""
Speaking Practice Mode Engine.

Provides focused practice sessions for individual Speaking skills:

  Modes:
    - quick_practice      → random question, any part
    - part_1_practice     → Part 1 questions (Introduction & Interview)
    - part_2_practice     → Part 2 cue cards (Individual Long Turn)
    - part_3_practice     → Part 3 discussion questions
    - vocabulary_practice → vocabulary-focused prompts
    - fluency_practice    → fluency-focused prompts
    - random_question     → random across all modes
    - weak_area_practice  → targets the user's weakest criterion

Each session:
  1. Generates/selects a suitable question from the speaking_prompts bank.
  2. Stores the session (user records the response externally).
  3. Evaluates the response (AI evaluation + error analysis).
  4. Provides feedback and a next recommendation.
  5. Awards XP.
  6. Integrates with the Mission Engine (schedulable mission) and
     Adaptive Scheduler (next exercise recommendation).

Design:
  - ``start_session()`` selects a prompt and creates a practice session.
  - ``save_response()`` stores the transcript + duration.
  - ``evaluate_session()`` runs AI evaluation + error analysis.
  - ``get_session()`` / ``list_sessions()`` retrieve results.
  - Recommendations use the AI service's error analysis to suggest the next
    exercise type, integrated with the Resource Engine and Adaptive Scheduler.
  - All operations are owner-scoped.
  - Previous sessions are never overwritten.
"""
import logging
from datetime import date
from typing import Any, Dict, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.speaking_test_repo import SpeakingTestRepository
from app.repositories.streak_repo import StreakRepository
from app.services.ai_service import AIService
from app.services.speaking_mission_service import SpeakingMissionService

logger = logging.getLogger(__name__)

# XP awarded for completing a practice session.
PRACTICE_SESSION_XP = 20

# XP threshold for meaningful improvement (band delta).
IMPROVEMENT_XP = 30

# Practice mode → part mapping.
_MODE_TO_PART = {
    "quick_practice": None,
    "part_1_practice": "part_1",
    "part_2_practice": "part_2",
    "part_3_practice": "part_3",
    "vocabulary_practice": None,
    "fluency_practice": None,
    "random_question": None,
    "weak_area_practice": None,
}


class SpeakingPracticeModeEngine:
    """
    Engine for the Speaking Practice Mode lifecycle.

    All operations are owner-scoped.  Sessions are immutable after
    evaluation — the user's original recording is never overwritten.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = SpeakingTestRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)
        self.ai_service: AIService = AIService()
        self.mission_service = SpeakingMissionService(db)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def start_session(
        self,
        user_id: str,
        practice_mode: str,
        target_band: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Start a speaking practice session.

        Selects a suitable question from the speaking_prompts bank based on
        the practice mode, creates a practice session, and returns the
        prompt + timer settings.
        """
        if practice_mode not in _MODE_TO_PART:
            raise ValidationError(f"Invalid practice mode: {practice_mode}")

        part = _MODE_TO_PART.get(practice_mode)
        prompt = self._select_prompt(practice_mode, part, user_id)

        payloads = {
            "user_id": user_id,
            "practice_mode": practice_mode,
            "prompt_id": prompt.get("id") if prompt else None,
            "part": prompt.get("part", "part_1") if prompt else "part_1",
            "title": prompt.get("title", "") if prompt else "",
            "prompt_text": prompt.get("prompt_text", "") if prompt else "",
            "prep_time_seconds": prompt.get("prep_time_seconds", 0) if prompt else 0,
            "speak_time_seconds": prompt.get("speak_time_seconds", 60) if prompt else 60,
            "status": "in_progress",
        }

        query = self.db.table("speaking_practice_sessions").insert(payloads)
        result = self.db.execute(query, "create speaking practice session")
        if not result.data:
            raise NotFoundError("Failed to create speaking practice session")

        session = result.data[0]
        logger.info(
            "speaking practice session started user=%s mode=%s session=%s",
            user_id, practice_mode, session.get("id"),
        )
        return self._to_session_response(session)

    def save_response(
        self,
        user_id: str,
        session_id: str,
        transcript: str,
        duration_seconds: int = 0,
        audio_url: str = "",
    ) -> Dict[str, Any]:
        """Save the user's recorded response (transcript + duration)."""
        session = self._get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Practice session not found")
        if session.get("status") != "in_progress":
            raise ValidationError("Only in-progress sessions can be updated")

        data = {
            "transcript": transcript,
            "duration_seconds": int(duration_seconds),
            "audio_url": audio_url,
        }
        query = (
            self.db.table("speaking_practice_sessions")
            .update(data)
            .eq("id", session_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "save speaking practice response")
        if not result.data:
            raise NotFoundError("Failed to save practice response")

        return self._to_session_response(result.data[0])

    async def evaluate_session(
        self,
        user_id: str,
        session_id: str,
        target_band: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a practice session's transcript.

        Runs AI evaluation + error analysis, computes bands, awards XP,
        and generates a next-exercise recommendation.
        """
        session = self._get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Practice session not found")
        if session.get("status") != "in_progress":
            raise ValidationError("Only in-progress sessions can be evaluated")

        transcript = session.get("transcript") or ""
        if not transcript.strip():
            raise ValidationError(
                "No transcript available. Save a response first."
            )

        part = session.get("part", "part_1")

        # Run AI evaluation.
        ai_eval = await self.ai_service.analyze_speaking(transcript)
        ai_errors = await self.ai_service.analyze_speaking_errors(
            transcript=transcript, part=part, topic=session.get("title", "")
        )

        issues = ai_errors.get("issues", [])
        error_count = len(issues)
        filler_count = self._count_fillers_in_issues(issues)

        # Compute next recommendation.
        next_rec = self._generate_next_recommendation(
            ai_eval, ai_errors, session.get("practice_mode", "quick_practice")
        )

        # Award XP.
        xp_earned = PRACTICE_SESSION_XP
        xp_reason = "Practice session completed"

        # Update session.
        update_data = {
            "overall_band": ai_eval.get("overall_band", 6.0),
            "fluency_coherence_band": ai_eval.get("fluency_coherence_band", 6.0),
            "lexical_resource_band": ai_eval.get("lexical_resource_band", 6.0),
            "grammatical_range_band": ai_eval.get("grammatical_range_band", 6.0),
            "pronunciation_band": ai_eval.get("pronunciation_band", 6.0),
            "error_count": error_count,
            "filler_words_count": filler_count,
            "feedback": ai_eval.get("feedback", ""),
            "next_recommendation": next_rec,
            "status": "evaluated",
            "completed_at": session.get("updated_at") or session.get("created_at"),
        }
        query = (
            self.db.table("speaking_practice_sessions")
            .update(update_data)
            .eq("id", session_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "evaluate speaking practice session")
        if not result.data:
            raise NotFoundError("Failed to update practice session")

        session = result.data[0]

        # Log to history.
        self._log_history(
            user_id, session_id, session.get("practice_mode", "quick_practice"),
            session.get("part", "part_1"),
            float(session.get("overall_band", 0) or 0),
            error_count, filler_count, xp_earned, xp_reason,
        )

        # Award XP via progress tracking.
        self._award_xp(user_id, session_id, xp_earned, xp_reason)

        # If a target band was provided and we exceeded it, award bonus XP.
        if target_band is not None:
            current = float(session.get("overall_band", 0) or 0)
            if current >= target_band:
                bonus = IMPROVEMENT_XP
                self._award_xp(user_id, session_id, bonus, "Met target band")
                update_data = {"xp_bonus": bonus}
                self.db.execute(
                    self.db.table("speaking_practice_sessions")
                    .update(update_data)
                    .eq("id", session_id)
                    .eq("user_id", user_id),
                    "award bonus XP to speaking session",
                )
                xp_earned += bonus

        logger.info(
            "speaking practice evaluated user=%s session=%s band=%.1f xp=%d",
            user_id, session_id,
            float(session.get("overall_band", 0) or 0), xp_earned,
        )

        # Sync downstream systems: mission progress, XP, streak, prediction,
        # readiness score, weak-skill detection, and adaptive scheduling.
        try:
            self.mission_service.sync_after_evaluation(
                user_id,
                {
                    **ai_eval,
                    "id": session_id,
                    "overall_band": session.get("overall_band", 6.0),
                    "error_count": error_count,
                    "filler_words": filler_count,
                    "duration_seconds": session.get("duration_seconds", 0),
                    "part": session.get("part", "part_1"),
                    "title": session.get("title", ""),
                },
                context={
                    "evaluation_id": session_id,
                    "session_id": session_id,
                    "practice_mode": session.get("practice_mode", "quick_practice"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking practice mission sync skipped user=%s session=%s: %s",
                user_id, session_id, exc,
            )

        return {
            "session": self._to_session_response(session),
            "evaluation": ai_eval,
            "error_analysis": ai_errors,
            "comparison": self._comparison_within_session(session, ai_eval),
            "xp_earned": xp_earned,
            "xp_reason": xp_reason,
            "next_recommendation": next_rec,
        }

    def get_session(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """Fetch a practice session (owner-scoped)."""
        session = self._get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Practice session not found")
        return self._to_session_response(session)

    def list_sessions(
        self, user_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """List the user's practice sessions (most recent first)."""
        if self.db is None:
            return {"results": [], "total": 0}
        try:
            query = (
                self.db.table("speaking_practice_sessions")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            result = self.db.execute(query, "list speaking practice sessions")
            rows = result.data or []
        except Exception:
            return {"results": [], "total": 0}
        return {
            "results": [self._to_session_response(r) for r in rows],
            "total": len(rows),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _select_prompt(
        self, practice_mode: str, part: Optional[str], user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Select a suitable prompt based on the practice mode."""
        import random

        if practice_mode == "random_question" or practice_mode == "quick_practice":
            prompts = self.repo.get_prompts()
            if prompts:
                return random.choice(prompts)
            return None

        if part:
            prompts = self.repo.get_prompts(part=part)
            if prompts:
                return random.choice(prompts)

        if practice_mode == "vocabulary_practice":
            # Prefer part_3 (discussion) prompts for vocabulary practice.
            prompts = self.repo.get_prompts(part="part_3") or self.repo.get_prompts(part="part_1")
            if prompts:
                return random.choice(prompts)

        if practice_mode == "fluency_practice":
            prompts = self.repo.get_prompts()
            if prompts:
                return random.choice(prompts)

        if practice_mode == "weak_area_practice":
            # Select based on the user's weakest criterion from recent sessions.
            weakest = self._find_weakest_criterion(user_id)
            if weakest == "pronunciation":
                prompts = self.repo.get_prompts(part="part_1")
            elif weakest == "grammatical_range":
                prompts = self.repo.get_prompts(part="part_3")
            elif weakest == "lexical_resource":
                prompts = self.repo.get_prompts(part="part_3") or self.repo.get_prompts(part="part_2")
            else:
                prompts = self.repo.get_prompts(part="part_1")
            if prompts:
                return random.choice(prompts)

        # Fallback: any prompt.
        prompts = self.repo.get_prompts()
        if prompts:
            return random.choice(prompts)
        return None

    def _find_weakest_criterion(self, user_id: str) -> Optional[str]:
        """Find the user's weakest speaking criterion from recent sessions."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_practice_sessions")
                .select("fluency_coherence_band, lexical_resource_band, grammatical_range_band, pronunciation_band")
                .eq("user_id", user_id)
                .eq("status", "evaluated")
                .order("created_at", desc=True)
                .limit(10)
            )
            result = self.db.execute(query, "find weakest criterion")
            rows = result.data or []
        except Exception:
            return None

        if not rows:
            return None

        sums = {"fluency_coherence": 0.0, "lexical_resource": 0.0,
                "grammatical_range": 0.0, "pronunciation": 0.0}
        col_map = {
            "fluency_coherence": "fluency_coherence_band",
            "lexical_resource": "lexical_resource_band",
            "grammatical_range": "grammatical_range_band",
            "pronunciation": "pronunciation_band",
        }
        counts = {k: 0 for k in sums}
        for row in rows:
            for k in sums:
                col = col_map[k]
                val = row.get(col)
                if val is not None:
                    sums[k] += float(val)
                    counts[k] += 1

        averages = {k: (sums[k] / counts[k]) if counts[k] > 0 else 9.0 for k in sums}
        weakest = min(averages, key=averages.get)
        return weakest if averages[weakest] < 8.0 else None

    def _count_fillers_in_issues(self, issues: list) -> int:
        """Count filler-related issues for the filler_words_count field."""
        return sum(1 for i in issues if i.get("issue_type") == "Filler Words")

    def _generate_next_recommendation(
        self,
        ai_eval: Dict[str, Any],
        ai_errors: Dict[str, Any],
        practice_mode: str,
    ) -> str:
        """Generate a next-exercise recommendation from the evaluation data."""
        bands = {
            "fluency_coherence": ai_eval.get("fluency_coherence_band", 0),
            "lexical_resource": ai_eval.get("lexical_resource_band", 0),
            "grammatical_range": ai_eval.get("grammatical_range_band", 0),
            "pronunciation": ai_eval.get("pronunciation_band", 0),
        }
        weakest = min(bands, key=bands.get) if bands else "fluency_coherence"

        mode_recommendations = {
            "fluency_coherence": "Practice fluency drills — record 1-minute timed responses to random Part 1 questions, counting and reducing filler words.",
            "lexical_resource": "Practice vocabulary expansion — write 10 synonyms for common IELTS topics, then use each in a sentence.",
            "grammatical_range": "Practice complex structures — record yourself using 3-4 different sentence types (conditional, relative clause, passive) per response.",
            "pronunciation": "Practice minimal pairs — use think/sink, ship/sheep drills, and record yourself comparing with native models.",
        }

        rec = mode_recommendations.get(weakest, "Practice your weakest area with targeted exercises.")

        # Add filler-specific advice.
        if ai_errors.get("issues"):
            filler_issues = [i for i in ai_errors["issues"] if i.get("issue_type") == "Filler Words"]
            if filler_issues:
                rec += " Focus on pausing instead of saying 'um' or 'uh' — practice with a timer."

        return rec

    def _comparison_within_session(
        self,
        session: Dict[str, Any],
        ai_eval: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Provide a brief self-comparison summary within the session context."""
        feedback = ai_eval.get("feedback", "")
        return {
            "current_band": ai_eval.get("overall_band", 0),
            "criteria": {
                "fluency_coherence": ai_eval.get("fluency_coherence_band", 0),
                "lexical_resource": ai_eval.get("lexical_resource_band", 0),
                "grammatical_range": ai_eval.get("grammatical_range_band", 0),
                "pronunciation": ai_eval.get("pronunciation_band", 0),
            },
            "feedback_summary": feedback[:300] if feedback else "",
        }

    def _get_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a speaking_practice_sessions row (owner-scoped)."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_practice_sessions")
                .select("*")
                .eq("id", session_id)
                .eq("user_id", user_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch speaking practice session")
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _log_history(
        self,
        user_id: str,
        session_id: str,
        practice_mode: str,
        part: str,
        overall_band: float,
        error_count: int,
        filler_count: int,
        xp_earned: int,
        xp_reason: str,
    ) -> None:
        """Log a session to the speaking_practice_history table."""
        if self.db is None:
            return
        try:
            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "practice_mode": practice_mode,
                "part": part,
                "overall_band": overall_band,
                "total_errors": error_count,
                "total_fillers": filler_count,
                "xp_earned": xp_earned,
                "xp_reason": xp_reason,
            }
            query = self.db.table("speaking_practice_history").insert(payload)
            self.db.execute(query, "log speaking practice history")
        except Exception as exc:
            logger.warning("failed to log speaking practice history: %s", exc)

    def _award_xp(
        self,
        user_id: str,
        session_id: str,
        xp: int,
        reason: str,
    ) -> None:
        """Award XP via the progress-tracking ledger."""
        try:
            self.progress_repo.log_session(
                user_id,
                {
                    "activity_date": date.today().isoformat(),
                    "skill": "speaking",
                    "session_type": "practice",
                    "minutes": 0,
                    "xp_earned": xp,
                    "source_type": "speaking_practice",
                    "source_id": session_id,
                    "meta": {"title": "Speaking Practice", "reason": reason},
                },
            )
            try:
                self.streak_repo.process_activity(user_id, day=date.today())
            except Exception:
                pass
        except Exception as exc:
            logger.warning("failed to award speaking XP user=%s: %s", user_id, exc)

    @staticmethod
    def _to_session_response(session: Dict[str, Any]) -> Dict[str, Any]:
        """Project a stored session row into the API response shape."""
        return {
            "id": session.get("id"),
            "user_id": session.get("user_id"),
            "practice_mode": session.get("practice_mode"),
            "prompt_id": session.get("prompt_id"),
            "part": session.get("part", "part_1"),
            "title": session.get("title", ""),
            "prompt_text": session.get("prompt_text", ""),
            "prep_time_seconds": session.get("prep_time_seconds", 0),
            "speak_time_seconds": session.get("speak_time_seconds", 60),
            "audio_url": session.get("audio_url", ""),
            "duration_seconds": session.get("duration_seconds", 0),
            "transcript": session.get("transcript", ""),
            "overall_band": session.get("overall_band"),
            "fluency_coherence_band": session.get("fluency_coherence_band"),
            "lexical_resource_band": session.get("lexical_resource_band"),
            "grammatical_range_band": session.get("grammatical_range_band"),
            "pronunciation_band": session.get("pronunciation_band"),
            "error_count": session.get("error_count", 0),
            "filler_words_count": session.get("filler_words_count", 0),
            "feedback": session.get("feedback"),
            "next_recommendation": session.get("next_recommendation"),
            "status": session.get("status", "in_progress"),
            "mission_id": session.get("mission_id"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "completed_at": session.get("completed_at"),
        }
