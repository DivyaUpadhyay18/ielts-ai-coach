"""
Diagnostic Test Framework service.

Deterministic (NO AI) assessment of a user's current IELTS level across the
six skill domains: reading, listening, writing, speaking, vocabulary, grammar.

Responsibilities:
  - manage the attempt lifecycle (start / resume / answer / complete)
  - randomize questions per attempt (question randomization)
  - save progress per answer (progress saving + resume support)
  - track per-section and total time (time tracking)
  - compute per-section accuracy and map to IELTS band scores (0.5 steps)
  - generate a report with strengths, weaknesses, and estimated level

All formulas are documented inline. The band estimate feeds directly into the
study-plan generator downstream.
"""
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.models.diagnostic import (
    DIAGNOSTIC_SECTIONS,
    SECTION_ORDER,
)
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.study_plan_repo import StudyPlanRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants (deterministic — no AI)
# ---------------------------------------------------------------------------
# IELTS bands are in 0.5 steps.
BAND_STEP = 0.5

# Number of questions shown per section (randomized from the bank).
QUESTIONS_PER_SECTION = 5

# Accuracy thresholds used to derive band scores (0-100 → band).
# At 0% accuracy → ~3.0; at 100% → ~9.0.
BAND_FLOOR = 3.0
BAND_CEIL = 9.0

# Writing & Speaking are graded on a rubric (0-9 scale) rather than right/wrong.
# We default to a neutral band if the user provides no self-assessment.
WRITING_DEFAULT_BAND = 5.5
SPEAKING_DEFAULT_BAND = 5.5

# Mapping of the six sections to their IELTS "marking criteria" style labels.
SKILL_LABELS = {
    "reading": "Reading",
    "listening": "Listening",
    "writing": "Writing",
    "speaking": "Speaking",
    "vocabulary": "Lexical Resource",
    "grammar": "Grammatical Range",
}


class DiagnosticService:
    """Business logic for the Diagnostic Test Framework."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = DiagnosticRepository(db)
        self.study_plan_repo = StudyPlanRepository(db)

    # ------------------------------------------------------------------
    # Attempt lifecycle
    # ------------------------------------------------------------------
    def start_attempt(self, user_id: str) -> Dict[str, Any]:
        """
        Start a new diagnostic attempt.

        If there is an existing in-progress attempt, it is resumed instead of
        creating a duplicate (resume support).
        """
        existing = self.repo.get_active_attempt(user_id)
        if existing:
            logger.info("resuming diagnostic attempt user=%s attempt=%s", user_id, existing["id"])
            return self._attempt_payload(existing)

        attempt = self.repo.create_attempt(user_id, {})
        logger.info("new diagnostic attempt user=%s attempt=%s", user_id, attempt["id"])
        return self._attempt_payload(attempt)

    def resume_attempt(self, attempt_id: str, user_id: str) -> Dict[str, Any]:
        """Resume a specific attempt and return its state + answered ids."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        answered = self.repo.get_answered_question_ids(attempt_id, user_id)
        return {
            "attempt": self._attempt_payload(attempt),
            "answered_question_ids": answered,
        }

    def get_questions(self, section: str) -> Dict[str, Any]:
        """
        Return a randomized set of questions for a section.

        Question randomization is deterministic-friendly: we shuffle the
        active bank and take QUESTIONS_PER_SECTION items. The `answer` field
        is stripped so the client cannot see the correct answer.
        """
        if section not in DIAGNOSTIC_SECTIONS:
            raise ValidationError(f"Unknown section: {section}")

        bank = self.repo.get_questions(section)
        if not bank:
            return {"section": section, "questions": []}

        random.shuffle(bank)
        selected = bank[:QUESTIONS_PER_SECTION]

        questions = []
        for q in selected:
            questions.append({
                "id": q["id"],
                "section": q["section"],
                "prompt": q["prompt"],
                "options": q.get("options"),
                "difficulty": int(q.get("difficulty") or 3),
                "weight": float(q.get("weight") or 1.0),
                "time_limit_seconds": int(q.get("time_limit_seconds") or 60),
                "skill_tag": q.get("skill_tag"),
            })
        return {"section": section, "questions": questions}

    # ------------------------------------------------------------------
    # Answer + progress saving
    # ------------------------------------------------------------------
    def submit_answer(
        self,
        attempt_id: str,
        user_id: str,
        section: str,
        question_id: str,
        answer: Any,
        time_taken_seconds: int,
    ) -> Dict[str, Any]:
        """Grade and persist a single answer, then update attempt progress."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        if attempt.get("status") != "in_progress":
            raise ValidationError("Attempt is not in progress")

        question = self.repo.get_question(question_id)
        if not question:
            raise NotFoundError("Question not found")

        # Grade deterministic objective sections (right/wrong).
        is_correct = None
        score = None
        if section in ("reading", "listening", "vocabulary", "grammar"):
            is_correct = self._check_answer(question.get("answer"), answer)
            score = float(question.get("weight") or 1.0) if is_correct else 0.0
            question_time = int(question.get("time_limit_seconds") or 60)
            time_taken = min(int(time_taken_seconds or 0), question_time)
        else:
            # Writing & Speaking: rubric-based, client provides a self-score.
            time_taken = int(time_taken_seconds or 0)

        response = self.repo.save_response(
            user_id,
            attempt_id,
            {
                "section": section,
                "question_id": question_id,
                "answer_json": {"value": answer},
                "is_correct": is_correct,
                "score": score,
                "time_taken_seconds": time_taken,
            },
        )

        self._touch_attempt(attempt_id, user_id, time_taken)
        return {
            "question_id": question_id,
            "is_correct": is_correct,
            "score": score,
            "section": section,
        }

    # ------------------------------------------------------------------
    # Section completion
    # ------------------------------------------------------------------
    def complete_section(
        self,
        attempt_id: str,
        user_id: str,
        section: str,
        time_taken_seconds: int,
    ) -> Dict[str, Any]:
        """Mark a section as completed and advance current_section."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        if attempt.get("status") != "in_progress":
            raise ValidationError("Attempt is not in progress")

        completed = list(attempt.get("sections_completed") or [])
        if section not in completed:
            completed.append(section)

        # Advance to next uncompleted section (ordered flow).
        next_section = self._next_section(completed)
        current = next_section or section

        data = {
            "sections_completed": completed,
            "current_section": current,
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.update_attempt(attempt_id, user_id, data)
        return self._attempt_payload(
            self.repo.get_attempt(attempt_id, user_id)
        )

    # ------------------------------------------------------------------
    # Finish + report
    # ------------------------------------------------------------------
    def complete_attempt(self, attempt_id: str, user_id: str) -> Dict[str, Any]:
        """Finalize the attempt and compute the diagnostic report."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        if attempt.get("status") == "completed":
            # Already completed — return existing report.
            return self.get_report(attempt_id, user_id)

        responses = self.repo.list_responses(attempt_id, user_id)

        # Compute per-section accuracy and band.
        skill_scores, accuracies = self._compute_section_scores(attempt, responses)
        overall_band = self._compute_overall_band(list(skill_scores.values()))

        strengths, weaknesses = self._derive_insights(skill_scores, accuracies)

        data = {
            "status": "completed",
            "overall_band": overall_band,
            "skill_scores": skill_scores,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.update_attempt(attempt_id, user_id, data)

        logger.info(
            "diagnostic completed user=%s attempt=%s overall=%.1f",
            user_id, attempt_id, overall_band,
        )
        return self.get_report(attempt_id, user_id)

    def get_report(self, attempt_id: str, user_id: str) -> Dict[str, Any]:
        """Return the full diagnostic report for an attempt."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        skill_scores = attempt.get("skill_scores") or {}
        accuracies = self._accuracy_from_scores(skill_scores)
        strengths, weaknesses = self._derive_insights(skill_scores, accuracies)
        
        # Compute enhanced report fields
        overall_band = float(attempt.get("overall_band") or 0.0)
        recommended_focus_areas = self._compute_focus_areas(skill_scores, weaknesses)
        suggested_weekly_hours = self._compute_suggested_hours(overall_band, skill_scores)
        suggested_exam_timeline_weeks = self._compute_exam_timeline(overall_band, skill_scores)
        roadmap_preview = self._compute_roadmap_preview(user_id, overall_band, skill_scores)

        return {
            "attempt_id": attempt_id,
            "user_id": user_id,
            "overall_band": overall_band,
            "target_note": "Current estimated IELTS level based on your diagnostic.",
            "skill_scores": [
                {
                    "section": section,
                    "band": float(skill_scores.get(section, 0.0)),
                    "accuracy": round(accuracies.get(section, 0.0), 1),
                }
                for section in SECTION_ORDER
                if section in skill_scores
            ],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "total_time_seconds": int(attempt.get("total_seconds_spent") or 0),
            "completed_at": attempt.get("completed_at"),
            "recommended_focus_areas": recommended_focus_areas,
            "suggested_weekly_hours": suggested_weekly_hours,
            "suggested_exam_timeline_weeks": suggested_exam_timeline_weeks,
            "roadmap_preview": roadmap_preview,
        }

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_answer(correct: Any, answer: Any) -> bool:
        """Compare a user answer to the stored correct answer (case-insensitive)."""
        if correct is None:
            return False
        if isinstance(correct, str) and isinstance(answer, str):
            return correct.strip().lower() == answer.strip().lower()
        return correct == answer

    def _compute_section_scores(
        self, attempt: Dict[str, Any], responses: List[Dict[str, Any]]
    ) -> tuple:
        """
        Compute per-section band scores.

        Objective sections (reading/listening/vocabulary/grammar):
          accuracy = (# correct / # answered) * 100
          band     = BAND_FLOOR + (accuracy / 100) * (BAND_CEIL - BAND_FLOOR)
                      rounded to nearest 0.5

        Subjective sections (writing/speaking):
          Use the average of per-response rubric scores (0-9) if provided,
          else the default band.
        """
        objective = ("reading", "listening", "vocabulary", "grammar")
        subjective = ("writing", "speaking")

        skill_scores: Dict[str, float] = {}
        accuracies: Dict[str, float] = {}

        for section in SECTION_ORDER:
            section_responses = [
                r for r in responses if r.get("section") == section
            ]
            if section in objective:
                if not section_responses:
                    continue
                correct = sum(1 for r in section_responses if r.get("is_correct"))
                accuracy = (correct / len(section_responses)) * 100.0
                band = self._accuracy_to_band(accuracy)
                skill_scores[section] = band
                accuracies[section] = accuracy
            elif section in subjective:
                rubric_scores = []
                for r in section_responses:
                    val = (r.get("answer_json") or {}).get("value")
                    if isinstance(val, (int, float)):
                        rubric_scores.append(float(val))
                if rubric_scores:
                    avg = sum(rubric_scores) / len(rubric_scores)
                    band = self._round_band(avg)
                else:
                    band = None
                if band is None:
                    band = WRITING_DEFAULT_BAND if section == "writing" else SPEAKING_DEFAULT_BAND
                skill_scores[section] = band
                accuracies[section] = 0.0  # not accuracy-based

        return skill_scores, accuracies

    def _accuracy_to_band(self, accuracy: float) -> float:
        """Map an accuracy percentage (0-100) to an IELTS band (0.5 steps)."""
        ratio = max(0.0, min(accuracy / 100.0, 1.0))
        band = BAND_FLOOR + ratio * (BAND_CEIL - BAND_FLOOR)
        return self._round_band(band)

    @staticmethod
    def _round_band(value: float) -> float:
        """Round a band to the nearest 0.5 and clamp to [0, 9]."""
        value = max(0.0, min(9.0, value))
        return round(value * 2) / 2

    def _compute_overall_band(self, bands: List[float]) -> float:
        """Average the section bands and round to nearest 0.5 (IELTS rule)."""
        if not bands:
            return 0.0
        avg = sum(bands) / len(bands)
        return self._round_band(avg)

    @staticmethod
    def _derive_insights(
        skill_scores: Dict[str, float], accuracies: Dict[str, float]
    ) -> tuple:
        """Derive strengths/weaknesses from per-section bands."""
        if not skill_scores:
            return [], []
        sorted_sections = sorted(skill_scores.items(), key=lambda kv: kv[1], reverse=True)

        strengths = []
        weaknesses = []
        for i, (section, band) in enumerate(sorted_sections):
            label = SKILL_LABELS.get(section, section.title())
            if i < 2 and band >= 5.0:
                strengths.append(f"{label} ({band})")
            if i >= len(sorted_sections) - 1 and band < 6.0:
                weaknesses.append(f"{label} ({band})")
        return strengths, weaknesses

    @staticmethod
    def _accuracy_from_scores(skill_scores: Dict[str, float]) -> Dict[str, float]:
        """Infer accuracy from stored band scores (for report consistency)."""
        accuracies = {}
        for section, band in skill_scores.items():
            if section in ("writing", "speaking"):
                accuracies[section] = 0.0
            else:
                ratio = max(0.0, min((band - BAND_FLOOR) / (BAND_CEIL - BAND_FLOOR), 1.0))
                accuracies[section] = ratio * 100.0
        return accuracies

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _next_section(self, completed: List[str]) -> Optional[str]:
        """Return the first section not yet completed, in the canonical order."""
        for section in SECTION_ORDER:
            if section not in completed:
                return section
        return None

    def _touch_attempt(self, attempt_id: str, user_id: str, seconds: int) -> None:
        """Update time tracking and last-activity on the attempt."""
        attempt = self.repo.get_attempt(attempt_id, user_id)
        total = int(attempt.get("total_seconds_spent") or 0) + seconds
        section_seconds = dict(attempt.get("section_seconds") or {})
        section = attempt.get("current_section")
        if section:
            section_seconds[section] = int(section_seconds.get(section, 0)) + seconds

        self.repo.update_attempt(
            attempt_id,
            user_id,
            {
                "total_seconds_spent": total,
                "section_seconds": section_seconds,
                "last_activity_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    def _attempt_payload(attempt: Dict[str, Any]) -> Dict[str, Any]:
        """Project a DB row into the API response shape."""
        return {
            "id": attempt.get("id"),
            "user_id": attempt.get("user_id"),
            "status": attempt.get("status"),
            "current_section": attempt.get("current_section"),
            "sections_completed": attempt.get("sections_completed") or [],
            "total_seconds_spent": int(attempt.get("total_seconds_spent") or 0),
            "section_seconds": attempt.get("section_seconds") or {},
            "last_activity_at": attempt.get("last_activity_at"),
            "started_at": attempt.get("started_at"),
            "completed_at": attempt.get("completed_at"),
            "overall_band": attempt.get("overall_band"),
            "skill_scores": attempt.get("skill_scores"),
            "created_at": attempt.get("created_at"),
        }

    def _compute_focus_areas(
        self, skill_scores: Dict[str, float], weaknesses: List[str]
    ) -> List[str]:
        """
        Recommend focus areas based on weakest skills and gaps.
        """
        focus_areas = []
        weak_sections = []
        
        for section, band in skill_scores.items():
            if band < 6.5:
                weak_sections.append((section, band))
        
        weak_sections.sort(key=lambda x: x[1])
        
        for section, band in weak_sections:
            gap = max(0.0, 7.0 - band)
            label = SKILL_LABELS.get(section, section.title())
            
            if gap >= 2.0:
                focus_areas.append(f"Master {label} fundamentals (band gap: {gap:.1f})")
            elif gap >= 1.0:
                focus_areas.append(f"Strengthen {label} advanced techniques (gap: {gap:.1f})")
            else:
                focus_areas.append(f"Refine {label} precision (gap: {gap:.1f})")
        
        technique_map = {
            "reading": "Practice skimming, scanning, and time management",
            "listening": "Improve note-taking and prediction skills",
            "writing": "Work on essay structure and task achievement",
            "speaking": "Practice fluency, pronunciation, and coherence",
            "vocabulary": "Expand academic word range and collocations",
            "grammar": "Focus on complex sentence structures and error reduction",
        }
        
        for section, _ in weak_sections[:3]:
            if section in technique_map and technique_map[section] not in focus_areas:
                focus_areas.append(technique_map[section])
        
        return focus_areas[:5] if focus_areas else ["Maintain current skills across all areas"]

    def _compute_suggested_hours(self, overall_band: float, skill_scores: Dict[str, float]) -> int:
        """Compute suggested weekly study hours based on current level and gaps."""
        if overall_band < 5.0:
            base = 5
        elif overall_band < 6.0:
            base = 8
        elif overall_band < 7.0:
            base = 10
        else:
            base = 12
        
        gap_hours = sum(2 for band in skill_scores.values() if band < 6.0)
        total = base + gap_hours
        return max(5, min(20, total))

    def _compute_exam_timeline(self, overall_band: float, skill_scores: Dict[str, float]) -> int:
        """Compute suggested exam timeline in weeks based on current level."""
        if overall_band < 5.0:
            base_weeks = 18
        elif overall_band < 6.0:
            base_weeks = 14
        elif overall_band < 7.0:
            base_weeks = 10
        else:
            base_weeks = 6
        
        weak_skills = sum(1 for band in skill_scores.values() if band < 5.5)
        adjustment = weak_skills * 2
        return max(4, base_weeks + adjustment)

    def _compute_roadmap_preview(
        self, user_id: str, overall_band: float, skill_scores: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Fetch or generate a roadmap preview for the user."""
        try:
            study_plan = self.study_plan_repo.get_active(user_id)
            if study_plan:
                return {
                    "has_plan": True,
                    "plan_id": study_plan.get("id"),
                    "title": study_plan.get("title", "Study Plan"),
                    "total_weeks": study_plan.get("total_weeks", 0),
                    "target_band": study_plan.get("target_band", overall_band + 1.0),
                    "status": study_plan.get("status", "active"),
                }
        except Exception:
            pass
        
        weak_skills = sorted(skill_scores.items(), key=lambda x: x[1])[:3]
        focus_skills = [SKILL_LABELS.get(s, s.title()) for s, _ in weak_skills]
        
        return {
            "has_plan": False,
            "preview": True,
            "current_band": overall_band,
            "suggested_target": min(9.0, overall_band + 1.0),
            "focus_skills": focus_skills,
            "estimated_weeks": self._compute_exam_timeline(overall_band, skill_scores),
            "message": "Generate a study plan to see your personalized roadmap",
        }


# Singleton bound to the shared DB session.
from app.db.session import db_session

diagnostic_service = DiagnosticService(db_session)
