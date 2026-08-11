"""
Writing Workspace service.

Provides the business logic for the IELTS Writing Workspace:
  - Fetch writing prompts by task type (Task 1 / Task 2)
  - Start a draft submission (with prompt snapshot)
  - Auto-save essay text + live word count + time spent
  - Submit for evaluation (locks the submission, returns pre-submission summary)
  - Resume a draft
  - List past submissions

All operations are deterministic and owner-scoped. No AI scoring.
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.repositories.writing_diagnostic_repo import WritingDiagnosticRepository

logger = logging.getLogger(__name__)

# Default word counts and time limits (fallback if prompt is missing).
DEFAULT_TASK_1_WORDS = 150
DEFAULT_TASK_2_WORDS = 250
DEFAULT_TASK_1_TIME = 1200  # 20 minutes
DEFAULT_TASK_2_TIME = 2400  # 40 minutes

TASK_LABELS = {
    "task_1": "Academic Task 1",
    "task_2": "Task 2 Essay",
}


class WritingWorkspaceService:
    """Business logic for the Writing Workspace."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingWorkspaceRepository(db)
        self.prompt_repo = WritingDiagnosticRepository(db)

    # ------------------------------------------------------------------
    # Question bank
    # ------------------------------------------------------------------
    def get_prompts(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Return all active writing prompts, optionally filtered by task type."""
        if task_type and task_type not in ("task_1", "task_2"):
            raise ValidationError(f"Unknown task type: {task_type}")

        prompts = self.prompt_repo.get_prompts(task_type)
        bank = []
        for p in sorted(prompts, key=lambda x: int(x.get("difficulty") or 3)):
            bank.append({
                "id": p["id"],
                "task_type": p.get("task_type") or "task_2",
                "title": p["title"],
                "prompt_text": p["prompt_text"],
                "word_limit": int(p.get("word_limit") or (
                    DEFAULT_TASK_1_WORDS if p.get("task_type") == "task_1" else DEFAULT_TASK_2_WORDS
                )),
                "time_limit_seconds": int(p.get("time_limit_seconds") or (
                    DEFAULT_TASK_1_TIME if p.get("task_type") == "task_1" else DEFAULT_TASK_2_TIME
                )),
                "difficulty": int(p.get("difficulty") or 3),
                "topics": p.get("topics") or [],
            })
        task = task_type or "all"
        return {"task_type": task, "prompts": bank, "total": len(bank)}

    # ------------------------------------------------------------------
    # Draft + submission lifecycle
    # ------------------------------------------------------------------
    def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """Fetch a single active prompt by id."""
        prompt = self.prompt_repo.get_prompt(prompt_id)
        if not prompt:
            raise NotFoundError("Writing prompt not found")
        return {
            "id": prompt["id"],
            "task_type": prompt.get("task_type") or "task_2",
            "title": prompt["title"],
            "prompt_text": prompt["prompt_text"],
            "word_limit": int(prompt.get("word_limit") or DEFAULT_TASK_2_WORDS),
            "time_limit_seconds": int(
                prompt.get("time_limit_seconds") or DEFAULT_TASK_2_TIME
            ),
            "difficulty": int(prompt.get("difficulty") or 3),
            "topics": prompt.get("topics") or [],
        }

    def start_submission(self, user_id: str, prompt_id: str) -> Dict[str, Any]:
        """
        Start a new writing submission for a prompt.

        Reuses the latest draft if one exists for this prompt (resume support).
        """
        prompt = self.get_prompt(prompt_id)

        # Check for an existing draft for this prompt (resume).
        existing_drafts = self.repo.list_drafts(user_id)
        for draft in existing_drafts:
            if draft.get("prompt_id") == prompt_id:
                logger.info(
                    "writing workspace resume user=%s submission=%s prompt=%s",
                    user_id, draft["id"], prompt_id,
                )
                return self._submission_payload(draft, prompt)

        # Create a new draft.
        submission = self.repo.create_submission(user_id, {
            "prompt_id": prompt["id"],
            "task_type": prompt["task_type"],
            "title": prompt["title"],
            "prompt_text": prompt["prompt_text"],
            "word_limit": prompt["word_limit"],
            "time_limit_seconds": prompt["time_limit_seconds"],
            "essay_text": "",
            "word_count": 0,
            "time_seconds_spent": 0,
            "status": "draft",
            "submission_summary": {},
        })
        logger.info(
            "writing workspace started user=%s submission=%s prompt=%s",
            user_id, submission["id"], prompt_id,
        )
        return self._submission_payload(submission, prompt)

    def auto_save(
        self,
        user_id: str,
        submission_id: str,
        essay_text: str,
        time_seconds_spent: int,
    ) -> Dict[str, Any]:
        """Auto-save the essay body and update word count + time."""
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") == "submitted":
            raise ValidationError("Submission already locked — cannot edit")

        word_count = self._count_words(essay_text)
        prompt = self._build_prompt_snapshot(submission)

        updated = self.repo.update_submission(submission_id, user_id, {
            "essay_text": essay_text,
            "word_count": word_count,
            "time_seconds_spent": max(0, int(time_seconds_spent or 0)),
            "updated_at": datetime.utcnow().isoformat(),
        })
        return self._submission_payload(updated, prompt)

    def submit(
        self,
        user_id: str,
        submission_id: str,
        time_seconds_spent: int,
    ) -> Dict[str, Any]:
        """
        Submit the essay for evaluation.

        Locks the submission (is_locked=True, status='submitted') and
        stores a pre-submission summary capturing word count, time spent,
        and any warnings.
        """
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") == "submitted":
            raise ValidationError("Submission already locked")

        word_count = int(submission.get("word_count") or 0)
        word_limit = int(submission.get("word_limit") or DEFAULT_TASK_2_WORDS)
        time_limit = int(
            submission.get("time_limit_seconds") or DEFAULT_TASK_2_TIME
        )
        time_spent = max(0, int(time_seconds_spent or 0))

        # Build pre-submission summary with warnings.
        warnings: List[str] = []
        if word_count < word_limit:
            warnings.append(
                f"Word count ({word_count}) is below the recommended "
                f"minimum of {word_limit}."
            )
        if time_spent > time_limit:
            warnings.append(
                f"Time spent ({time_spent}s) exceeds the limit ({time_limit}s)."
            )
        if not submission.get("essay_text", "").strip():
            warnings.append("Your essay is empty.")

        summary = {
            "word_count": word_count,
            "word_limit": word_limit,
            "time_seconds_spent": time_spent,
            "time_limit_seconds": time_limit,
            "meets_word_requirement": word_count >= word_limit,
            "within_time_limit": time_spent <= time_limit,
            "warnings": warnings,
            "submitted_at": datetime.utcnow().isoformat(),
        }

        updated = self.repo.update_submission(submission_id, user_id, {
            "status": "submitted",
            "is_locked": True,
            "time_seconds_spent": time_spent,
            "submission_summary": summary,
            "submitted_at": datetime.utcnow().isoformat(),
        })

        # Ensure submission_summary is present in the response even if the
        # DB row does not return it (defensive for mock/test scenarios).
        if not updated.get("submission_summary"):
            updated["submission_summary"] = summary

        prompt = self._build_prompt_snapshot(submission)
        logger.info(
            "writing workspace submitted user=%s submission=%s words=%d",
            user_id, submission_id, word_count,
        )
        return self._submission_payload(updated, prompt)

    def get_submission(self, user_id: str, submission_id: str) -> Dict[str, Any]:
        """Fetch a full submission (owner-scoped)."""
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")

        prompt = None
        if submission.get("prompt_id"):
            prompt = self.prompt_repo.get_prompt(submission["prompt_id"])
        return self._submission_payload(submission, prompt)

    def list_submissions(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """List all submissions for a user (most recent first)."""
        rows = self.repo.list_submissions(user_id, limit)
        results = []
        for r in rows:
            prompt = None
            if r.get("prompt_id"):
                prompt = self.prompt_repo.get_prompt(r["prompt_id"])
            results.append(self._submission_payload(r, prompt))
        return {"results": results, "total": len(results)}

    # ------------------------------------------------------------------
    # Payload + helpers
    # ------------------------------------------------------------------
    def _submission_payload(
        self,
        submission: Dict[str, Any],
        prompt: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Project a DB row into the API response shape."""
        p = prompt or {}
        return {
            "id": submission.get("id"),
            "user_id": submission.get("user_id"),
            "prompt_id": submission.get("prompt_id"),
            "task_type": submission.get("task_type") or "task_2",
            "title": submission.get("title") or (p.get("title") or ""),
            "prompt_text": submission.get("prompt_text") or p.get("prompt_text"),
            "word_limit": int(
                submission.get("word_limit") or p.get("word_limit")
                or DEFAULT_TASK_2_WORDS
            ),
            "time_limit_seconds": int(
                submission.get("time_limit_seconds") or p.get("time_limit_seconds")
                or DEFAULT_TASK_2_TIME
            ),
            "essay_text": submission.get("essay_text") or "",
            "word_count": int(submission.get("word_count") or 0),
            "time_seconds_spent": int(
                submission.get("time_seconds_spent") or 0
            ),
            "status": submission.get("status") or "draft",
            "is_locked": bool(submission.get("is_locked") or False),
            "submission_summary": submission.get("submission_summary") or {},
            "created_at": submission.get("created_at"),
            "updated_at": submission.get("updated_at"),
            "submitted_at": submission.get("submitted_at"),
        }

    def _build_prompt_snapshot(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """Reconstruct prompt snapshot from a submission row."""
        return {
            "id": submission.get("prompt_id"),
            "task_type": submission.get("task_type") or "task_2",
            "title": submission.get("title"),
            "prompt_text": submission.get("prompt_text"),
            "word_limit": submission.get("word_limit") or DEFAULT_TASK_2_WORDS,
            "time_limit_seconds": submission.get("time_limit_seconds") or DEFAULT_TASK_2_TIME,
        }

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in an essay (whitespace-separated tokens)."""
        if not text:
            return 0
        return len(re.findall(r"\S+", text.strip()))
