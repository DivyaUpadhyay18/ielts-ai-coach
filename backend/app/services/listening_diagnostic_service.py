"""
Listening Diagnostic Module service.

Deterministic (NO AI) assessment of IELTS Listening using authentic audio
sections and five official question types:
  - Multiple Choice
  - Map
  - Form Completion
  - Sentence Completion
  - Matching

Responsibilities:
  - fetch tracks + their questions (question bank)
  - grade answers against stored correct answers (type-aware)
  - compute and STORE per-attempt results:
      * accuracy (overall + per question type)
      * time (total + per question type average)
      * weak question types (accuracy below threshold)
      * difficulty level (Easy / Moderate / Hard)
      * estimated IELTS listening band
  - generate a report and persist it in `listening_diagnostic_results`

The module reuses `diagnostic_attempts` for the lifecycle/resume semantics
and records per-question responses in `diagnostic_responses` to keep one
source of truth for progress.
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.models.listening_diagnostic import (
    LISTENING_QUESTION_TYPES,
)
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.listening_diagnostic_repo import ListeningDiagnosticRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants (deterministic — no AI)
# ---------------------------------------------------------------------------
# IELTS bands are in 0.5 steps.
BAND_STEP = 0.5

# Listening band floor/ceiling derived from accuracy (%).
BAND_FLOOR = 3.0
BAND_CEIL = 9.0

# A question type is considered "weak" when its accuracy is below this %.
WEAK_TYPE_THRESHOLD = 60.0

# A question type is considered "strong" when its accuracy is at/above this %.
STRONG_TYPE_THRESHOLD = 80.0

# Difficulty level thresholds based on average track/question difficulty (1-5).
DIFFICULTY_EASY_MAX = 2.5
DIFFICULTY_MODERATE_MAX = 3.5

# Human-readable labels for each listening question type.
TYPE_LABELS = {
    "multiple_choice": "Multiple Choice",
    "map": "Map",
    "form_completion": "Form Completion",
    "sentence_completion": "Sentence Completion",
    "matching": "Matching",
}


class ListeningDiagnosticService:
    """Business logic for the Listening Diagnostic Module."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = ListeningDiagnosticRepository(db)
        # Reuse the generic diagnostic repo for attempts/responses lifecycle.
        self.diag_repo = DiagnosticRepository(db)

    # ------------------------------------------------------------------
    # Question bank
    # ------------------------------------------------------------------
    def get_bank(self) -> Dict[str, Any]:
        """
        Return all active listening tracks with their questions.

        Tracks are ordered by difficulty; the correct answer is stripped
        from the questions so the client cannot see it in advance.
        """
        tracks = self.repo.get_tracks()
        questions = self.repo.get_listening_questions()

        # Group questions by track.
        by_track: Dict[str, List[Dict[str, Any]]] = {}
        for q in questions:
            tid = q.get("track_id")
            if not tid:
                continue
            by_track.setdefault(tid, []).append(q)

        bank_tracks = []
        bank_questions = []
        for t in sorted(tracks, key=lambda x: int(x.get("difficulty") or 3)):
            bank_tracks.append({
                "id": t["id"],
                "title": t["title"],
                "description": t.get("description"),
                "audio_url": t["audio_url"],
                "section_number": int(t.get("section_number") or 1),
                "difficulty": int(t.get("difficulty") or 3),
                "topics": t.get("topics") or [],
                "transcript": t.get("transcript"),
            })
            for q in by_track.get(t["id"], []):
                bank_questions.append({
                    "id": q["id"],
                    "track_id": q["track_id"],
                    "question_type": q.get("question_type") or "multiple_choice",
                    "prompt": q["prompt"],
                    "options": q.get("options"),
                    "difficulty": int(q.get("difficulty") or 3),
                    "time_limit_seconds": int(q.get("time_limit_seconds") or 90),
                    "skill_tag": q.get("skill_tag"),
                })

        return {
            "tracks": bank_tracks,
            "questions": bank_questions,
            "total": len(bank_questions),
        }

    # ------------------------------------------------------------------
    # Answer submission + grading
    # ------------------------------------------------------------------
    def submit_answer(
        self,
        user_id: str,
        attempt_id: str,
        question_id: str,
        answer: Any,
        time_taken_seconds: int,
    ) -> Dict[str, Any]:
        """Grade and persist a single listening answer."""
        attempt = self.diag_repo.get_attempt(attempt_id, user_id)
        if attempt.get("status") != "in_progress":
            raise ValidationError("Attempt is not in progress")

        question = self.repo.get_listening_question(question_id)
        if not question:
            raise NotFoundError("Listening question not found")

        correct = question.get("answer")
        is_correct = self._check_answer(question.get("question_type"), correct, answer)
        time_taken = min(int(time_taken_seconds or 0), int(question.get("time_limit_seconds") or 90))

        # Persist response in the shared responses table (resume source of truth).
        self.diag_repo.save_response(
            user_id,
            attempt_id,
            {
                "section": "listening",
                "question_id": question_id,
                "answer_json": {"value": answer, "question_type": question.get("question_type")},
                "is_correct": is_correct,
                "score": float(question.get("weight") or 1.0) if is_correct else 0.0,
                "time_taken_seconds": time_taken,
            },
        )

        self._touch_attempt(attempt_id, user_id, time_taken)

        return {
            "question_id": question_id,
            "is_correct": is_correct,
            "correct_answer": correct,
            "question_type": question.get("question_type"),
            "time_taken_seconds": time_taken,
        }

    # ------------------------------------------------------------------
    # Complete + report (auto-calculated metrics + storage)
    # ------------------------------------------------------------------
    def complete_listening(
        self, user_id: str, attempt_id: str
    ) -> Dict[str, Any]:
        """Finalize a listening attempt, compute metrics, and store results."""
        attempt = self.diag_repo.get_attempt(attempt_id, user_id)

        # Build a map of question_id -> question for grading metadata.
        questions = self.repo.get_listening_questions()
        question_map = {q["id"]: q for q in questions}

        responses = [
            r for r in self.diag_repo.list_responses(attempt_id, user_id)
            if r.get("section") == "listening"
        ]

        # Only count responses that map to known listening questions.
        graded = [
            r for r in responses
            if r.get("question_id") in question_map
        ]

        total = len(graded)
        correct = sum(1 for r in graded if r.get("is_correct"))
        accuracy = (correct / total * 100.0) if total else 0.0

        total_time = int(attempt.get("total_seconds_spent") or 0)

        # Per-type breakdown.
        type_breakdown = self._compute_type_breakdown(graded, question_map)
        type_accuracy = {t: b["accuracy"] for t, b in type_breakdown.items()}
        type_time = {t: round(b["avg_time_seconds"], 1) for t, b in type_breakdown.items()}

        weak_types = sorted(
            [t for t, b in type_breakdown.items() if b["accuracy"] < WEAK_TYPE_THRESHOLD],
            key=lambda t: type_accuracy[t],
        )
        strong_types = sorted(
            [t for t, b in type_breakdown.items() if b["accuracy"] >= STRONG_TYPE_THRESHOLD],
            key=lambda t: type_accuracy[t],
            reverse=True,
        )

        # Difficulty level = average of the questions the user actually answered.
        difficulty_level = self._difficulty_level(graded, question_map)

        listening_band = self._accuracy_to_band(accuracy)

        # Detail snapshot for future review.
        detail = []
        for r in graded:
            q = question_map[r["question_id"]]
            detail.append({
                "question_id": r["question_id"],
                "question_type": q.get("question_type"),
                "user_answer": (r.get("answer_json") or {}).get("value"),
                "correct_answer": q.get("answer"),
                "is_correct": r.get("is_correct"),
                "time_taken_seconds": int(r.get("time_taken_seconds") or 0),
                "difficulty": int(q.get("difficulty") or 3),
            })

        # Persist the listening result.
        self.repo.save_result(user_id, {
            "attempt_id": attempt_id,
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": round(accuracy, 1),
            "total_time_seconds": total_time,
            "listening_band": listening_band,
            "difficulty_level": difficulty_level,
            "type_accuracy": type_accuracy,
            "type_time": type_time,
            "weak_types": weak_types,
            "strong_types": strong_types,
            "detail": detail,
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Mark listening as completed on the shared attempt.
        completed = list(attempt.get("sections_completed") or [])
        if "listening" not in completed:
            completed.append("listening")
        self.diag_repo.update_attempt(attempt_id, user_id, {
            "sections_completed": completed,
            "last_activity_at": datetime.utcnow().isoformat(),
        })

        logger.info(
            "listening diagnostic done user=%s attempt=%s acc=%.1f band=%.1f",
            user_id, attempt_id, accuracy, listening_band,
        )
        return self.build_report(user_id, attempt_id, graded, question_map)

    def build_report(
        self,
        user_id: str,
        attempt_id: str,
        responses: Optional[List[Dict[str, Any]]] = None,
        question_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build (and return) the listening diagnostic report."""
        stored = self.repo.get_result(attempt_id, user_id)
        if not stored:
            raise NotFoundError("Listening result not found")

        breakdown = self._report_breakdown(stored)
        completed_at = stored.get("completed_at") or stored.get("created_at")

        return {
            "attempt_id": attempt_id,
            "user_id": user_id,
            "total_questions": int(stored.get("total_questions") or 0),
            "correct_answers": int(stored.get("correct_answers") or 0),
            "accuracy": float(stored.get("accuracy") or 0.0),
            "total_time_seconds": int(stored.get("total_time_seconds") or 0),
            "listening_band": float(stored.get("listening_band") or 0.0),
            "difficulty_level": stored.get("difficulty_level") or "Easy",
            "type_breakdown": breakdown,
            "weak_types": stored.get("weak_types") or [],
            "strong_types": stored.get("strong_types") or [],
            "completed_at": completed_at,
        }

    def list_results(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """Return a user's stored listening diagnostic results."""
        rows = self.repo.list_results(user_id, limit)
        results = []
        for r in rows:
            results.append({
                "attempt_id": r.get("attempt_id"),
                "total_questions": int(r.get("total_questions") or 0),
                "correct_answers": int(r.get("correct_answers") or 0),
                "accuracy": float(r.get("accuracy") or 0.0),
                "listening_band": float(r.get("listening_band") or 0.0),
                "difficulty_level": r.get("difficulty_level"),
                "weak_types": r.get("weak_types") or [],
                "strong_types": r.get("strong_types") or [],
                "total_time_seconds": int(r.get("total_time_seconds") or 0),
                "completed_at": r.get("completed_at"),
            })
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_answer(question_type: Optional[str], correct: Any, answer: Any) -> bool:
        """Type-aware answer comparison (case-insensitive, whitespace-normalized)."""
        if correct is None:
            return False

        def norm(v: Any) -> str:
            if v is None:
                return ""
            return re.sub(r"\s+", " ", str(v).strip()).lower()

        c = norm(correct)
        a = norm(answer)
        if not c and not a:
            return True
        if not c or not a:
            return False

        # Objective exact-match types (MCQ, map, matching).
        if question_type in ("multiple_choice", "map", "matching"):
            return c == a

        # Completion types: tolerant substring match.
        # Accept if the answer is contained in the correct answer or vice-versa,
        # but avoid trivial single-char matches.
        if len(a) >= 2 and (a in c or c in a):
            return True

        return c == a

    @staticmethod
    def _compute_type_breakdown(
        responses: List[Dict[str, Any]],
        question_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Compute per-question-type accuracy and average time."""
        by_type: Dict[str, Dict[str, Any]] = {}
        for r in responses:
            q = question_map.get(r.get("question_id") or "")
            qtype = (q or {}).get("question_type") or "multiple_choice"
            entry = by_type.setdefault(qtype, {"total": 0, "correct": 0, "time": 0.0})
            entry["total"] += 1
            if r.get("is_correct"):
                entry["correct"] += 1
            entry["time"] += float(r.get("time_taken_seconds") or 0)

        result = {}
        for qtype, entry in by_type.items():
            accuracy = (entry["correct"] / entry["total"] * 100.0) if entry["total"] else 0.0
            result[qtype] = {
                "question_type": qtype,
                "total": entry["total"],
                "correct": entry["correct"],
                "accuracy": round(accuracy, 1),
                "avg_time_seconds": round(entry["time"] / entry["total"], 1) if entry["total"] else 0.0,
            }
        return result

    @staticmethod
    def _difficulty_level(
        responses: List[Dict[str, Any]],
        question_map: Dict[str, Dict[str, Any]],
    ) -> str:
        """Derive Easy/Moderate/Hard from the average question difficulty."""
        if not responses:
            return "Easy"
        difficulties = []
        for r in responses:
            q = question_map.get(r.get("question_id") or "")
            if q:
                difficulties.append(int(q.get("difficulty") or 3))
        if not difficulties:
            return "Easy"
        avg = sum(difficulties) / len(difficulties)
        if avg <= DIFFICULTY_EASY_MAX:
            return "Easy"
        if avg <= DIFFICULTY_MODERATE_MAX:
            return "Moderate"
        return "Hard"

    def _accuracy_to_band(self, accuracy: float) -> float:
        """Map accuracy % to IELTS listening band (0.5 steps)."""
        ratio = max(0.0, min(accuracy / 100.0, 1.0))
        band = BAND_FLOOR + ratio * (BAND_CEIL - BAND_FLOOR)
        return self._round_band(band)

    @staticmethod
    def _round_band(value: float) -> float:
        """Round to nearest 0.5 and clamp to [0, 9]."""
        value = max(0.0, min(9.0, value))
        return round(value * 2) / 2

    @staticmethod
    def _report_breakdown(stored: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform stored type_accuracy/type_time into a report breakdown."""
        type_accuracy = stored.get("type_accuracy") or {}
        type_time = stored.get("type_time") or {}
        breakdown = []
        for qtype, acc in type_accuracy.items():
            breakdown.append({
                "question_type": qtype,
                "total": 0,
                "correct": 0,
                "accuracy": float(acc),
                "avg_time_seconds": float(type_time.get(qtype, 0.0) or 0.0),
            })
        return breakdown

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------
    def _touch_attempt(self, attempt_id: str, user_id: str, seconds: int) -> None:
        """Update time tracking on the shared attempt."""
        attempt = self.diag_repo.get_attempt(attempt_id, user_id)
        total = int(attempt.get("total_seconds_spent") or 0) + seconds
        section_seconds = dict(attempt.get("section_seconds") or {})
        section_seconds["listening"] = int(section_seconds.get("listening", 0)) + seconds
        self.diag_repo.update_attempt(attempt_id, user_id, {
            "total_seconds_spent": total,
            "section_seconds": section_seconds,
            "last_activity_at": datetime.utcnow().isoformat(),
        })


# Singleton bound to the shared DB session.
from app.db.session import db_session

listening_diagnostic_service = ListeningDiagnosticService(db_session)
