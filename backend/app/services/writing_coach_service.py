"""
Writing Coach service.

Provides context-aware Q&A on the student's writing. After receiving an
evaluation, the student can ask questions like:

  - "Why is this sentence wrong?"
  - "How can I improve my introduction?"
  - "Why is my Task Response low?"
  - "Give me a better way to express this idea."
  - "How can I improve my grammar?"

The AI always receives the student's actual essay text + evaluation data
as context — never generic answers when specific data is available.

Conversation history is stored and paginated. The service also persists
messages to the AI Mentor's conversation tables so history flows through
the unified mentor memory.

All DB operations are defensive (safe wrappers), so the service works with
db=None and never crashes a request.
"""
import json
import logging
import os
from typing import Any

import httpx

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.writing_workspace_repo import WritingWorkspaceRepository
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

WRITING_COACH_TIMEOUT = 30.0
WRITING_COACH_MODEL = "gpt-4o-mini"


class WritingCoachService:
    """
    Context-aware writing Q&A coach.

    Answers student questions grounded in their actual essay + evaluation,
    stores conversation history, and integrates with the AI Mentor memory.
    """

    def __init__(self, db: DatabaseSession) -> None:
        from app.ai.prompts import IELTS_WRITING_COACH_PROMPT

        self.db = db
        self.ai_service = AIService()
        self.repo = WritingWorkspaceRepository(db)
        self._coach_prompt = IELTS_WRITING_COACH_PROMPT

    async def ask(
        self,
        user_id: str,
        submission_id: str,
        question: str,
    ) -> dict[str, Any]:
        """
        Answer a student question about their written essay.

        Grounds the answer in the student's actual essay text + evaluation.
        Stores the Q&A in the conversation history.
        """
        # 1. Fetch the submission (essay text + prompt).
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")
        if submission.get("status") != "submitted":
            raise NotFoundError("Only submitted essays can be coached")

        # 2. Fetch the evaluation.
        evaluation = self.repo.get_evaluation(submission_id, user_id)
        if not evaluation or evaluation.get("status") != "evaluated":
            raise NotFoundError("No evaluation found for this submission")

        essay_text = submission.get("essay_text") or ""
        evaluation_data = self._evaluation_to_context(evaluation)

        # 3. Build or reuse a coaching conversation.
        conversation = self._get_or_create_conversation(
            user_id, evaluation.get("id"), submission_id
        )

        # 4. Build conversation history for context.
        history = self._list_messages(conversation["id"], user_id)
        context_messages = self._build_llm_messages(
            question, essay_text, evaluation_data, history
        )

        # 5. Call the LLM.
        answer = await self._call_coach_llm(context_messages)

        # 6. Persist Q (if not already in history) + A.
        already_asked = any(
            m.get("role") == "user" and m.get("content") == question
            for m in history
        )
        if not already_asked:
            self._save_message(
                user_id, conversation["id"], "user", question, {}
            )
        self._save_message(
            user_id, conversation["id"], "coach", answer,
            {
                "essay_text": essay_text,
                "evaluation_id": evaluation.get("id"),
            },
        )

        # Update conversation updated_at.
        self._touch_conversation(conversation["id"], user_id)

        return {
            "conversation_id": conversation["id"],
            "answer": answer.get("answer", ""),
            "focus": answer.get("focus", "other"),
            "referenced_text": answer.get("referenced_text", []),
            "referenced_feedback": answer.get("referenced_feedback", []),
        }

    async def ask_standalone(
        self,
        user_id: str,
        submission_id: str,
        question: str,
    ) -> dict[str, Any]:
        """
        Answer a question without persisting — for quick inline coaching
        (e.g. hover tooltip on a highlighted sentence).
        """
        submission = self.repo.get_submission(submission_id, user_id)
        if not submission:
            raise NotFoundError("Writing submission not found")

        evaluation = self.repo.get_evaluation(submission_id, user_id)
        if not evaluation or evaluation.get("status") != "evaluated":
            raise NotFoundError("No evaluation found for this submission")

        essay_text = submission.get("essay_text") or ""
        evaluation_data = self._evaluation_to_context(evaluation)

        context_messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_user_prompt(
                question, essay_text, evaluation_data, []
            )},
        ]
        answer = await self._call_coach_llm(context_messages)
        return {
            "answer": answer.get("answer", ""),
            "focus": answer.get("focus", "other"),
            "referenced_text": answer.get("referenced_text", []),
            "referenced_feedback": answer.get("referenced_feedback", []),
        }

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> dict[str, Any]:
        """Fetch a coaching conversation and all its messages."""
        conv = self._get_conversation(conversation_id, user_id)
        if not conv:
            raise NotFoundError("Coaching conversation not found")
        messages = self._list_messages(conversation_id, user_id)
        return {
            "id": conv.get("id"),
            "user_id": conv.get("user_id"),
            "evaluation_id": conv.get("evaluation_id"),
            "submission_id": conv.get("submission_id"),
            "title": conv.get("title", "Writing coaching session"),
            "status": conv.get("status", "active"),
            "messages": messages,
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
        }

    def list_conversations(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List the user's coaching conversations (newest first)."""
        rows = self._safe_list_conversations(user_id, limit, offset)
        total = self._safe_count_conversations(user_id)
        items = []
        for row in rows:
            conv_id = row.get("id")
            items.append({
                "id": conv_id,
                "evaluation_id": row.get("evaluation_id"),
                "submission_id": row.get("submission_id"),
                "title": row.get("title", "Writing coaching session"),
                "status": row.get("status", "active"),
                "message_count": (
                    self._safe_count_messages(conv_id) if conv_id else 0
                ),
                "last_message_at": (
                    self._safe_get_last_message_at(conv_id) if conv_id else None
                ),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            })
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------
    def _build_system_prompt(self) -> str:
        """Build the system prompt, injecting the prompt template."""
        # The prompt is already a complete system prompt that includes
        # the JSON schema instructions. We return it as-is.
        return self._coach_prompt

    def _build_user_prompt(
        self,
        question: str,
        essay_text: str,
        evaluation_data: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> str:
        """Build the user message with conversation history for context."""
        prompt = self._coach_prompt.format(
            question=question,
            essay_text=essay_text,
            evaluation_data=json.dumps(evaluation_data, indent=2, default=str),
        )
        return prompt

    def _evaluation_to_context(
        self, evaluation: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert an evaluation row into a structured context dict."""
        return {
            "overall_band": evaluation.get("overall_band"),
            "criteria_bands": evaluation.get("criteria_bands") or {},
            "strengths": evaluation.get("strengths") or [],
            "weaknesses": evaluation.get("weaknesses") or [],
            "errors": evaluation.get("errors") or [],
            "suggestions": evaluation.get("suggestions") or [],
            "task_type": evaluation.get("task_type", "task_2"),
            "word_count": evaluation.get("word_count", 0),
            "confidence": evaluation.get("confidence"),
            "is_estimate": evaluation.get("is_estimate", True),
        }

    def _build_llm_messages(
        self,
        question: str,
        essay_text: str,
        evaluation_data: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build the full message list for the LLM call."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        for msg in history:
            role = "assistant" if msg.get("role") == "coach" else "user"
            messages.append({"role": role, "content": msg.get("content", "")})
        messages.append({
            "role": "user",
            "content": self._build_user_prompt(
                question, essay_text, evaluation_data, history
            ),
        })
        return messages

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------
    async def _call_coach_llm(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Call the LLM; parse structured response. Falls back to deterministic."""
        api_key = os.getenv("OPENAI_API_KEY") or getattr(
            __import__("app.core.config", fromlist=["settings"]).settings,
            "OPENAI_API_KEY",
            None,
        )
        if not api_key:
            return self._fallback_answer()

        try:
            async with httpx.AsyncClient(timeout=WRITING_COACH_TIMEOUT) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": WRITING_COACH_MODEL,
                        "messages": messages,
                        "temperature": 0.4,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return {
                    "answer": str(parsed.get("answer", "")).strip(),
                    "focus": str(parsed.get("focus", "other")).strip(),
                    "referenced_text": parsed.get("referenced_text", []),
                    "referenced_feedback": parsed.get("referenced_feedback", []),
                }
        except Exception as exc:  # noqa: BLE001
            logger.info("writing coach LLM call failed: %s", exc)
            return self._fallback_answer()

    def _fallback_answer(self) -> dict[str, Any]:
        """Deterministic fallback when no API key or LLM fails."""
        return {
            "answer": (
                "I don't have enough information to give a specific answer. "
                "Please ensure your essay has been evaluated first, then ask "
                "me a question about your Task Response, Coherence, Vocabulary, "
                "or Grammar."
            ),
            "focus": "other",
            "referenced_text": [],
            "referenced_feedback": [],
        }

    # ------------------------------------------------------------------
    # Conversation/message persistence (defensive)
    # ------------------------------------------------------------------
    def _get_or_create_conversation(
        self,
        user_id: str,
        evaluation_id: str,
        submission_id: str,
    ) -> dict[str, Any]:
        """Fetch the most recent active coaching conversation, or create one."""
        existing = self._safe_list_conversations(
            user_id, limit=1, filters={
                "evaluation_id": evaluation_id,
                "status": "active",
            }
        )
        if existing:
            return existing[0]
        return self._safe_create_conversation(
            user_id, evaluation_id, submission_id
        )

    def _get_conversation(
        self, conversation_id: str, user_id: str
    ) -> dict[str, Any] | None:
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("writing_coaching_conversations")
                .select("*")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .limit(1)
            )
            result = self.db.execute(query, "get writing coaching conversation")
            if result.data:
                return result.data[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_coaching_conversation failed user=%s: %s", user_id, exc)
        return None

    def _safe_list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.db is None:
            return []
        try:
            query = (
                self.db.table("writing_coaching_conversations")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .offset(offset)
            )
            if filters:
                for col, val in filters.items():
                    query = query.eq(col, val)
            result = self.db.execute(query, "list writing coaching conversations")
            return result.data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "list_coaching_conv failed user=%s: %s", user_id, exc
            )
            return []

    def _safe_count_conversations(self, user_id: str) -> int:
        if self.db is None:
            return 0
        try:
            query = (
                self.db.table("writing_coaching_conversations")
                .select("*", count="exact")
                .eq("user_id", user_id)
            )
            result = self.db.execute(query, "count writing coaching conversations")
            return result.count or 0
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "count_coaching_conv failed user=%s: %s", user_id, exc
            )
            return 0

    def _safe_create_conversation(
        self,
        user_id: str,
        evaluation_id: str,
        submission_id: str,
    ) -> dict[str, Any]:
        if self.db is None:
            return {"id": f"local-{user_id}-{submission_id}"}
        try:
            payload = {
                "user_id": user_id,
                "evaluation_id": evaluation_id,
                "submission_id": submission_id,
                "title": "Writing coaching session",
                "status": "active",
                "meta": {},
            }
            query = self.db.table("writing_coaching_conversations").insert(payload)
            result = self.db.execute(query, "create writing coaching conversation")
            if result.data:
                return result.data[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "create_coaching_conv failed user=%s: %s", user_id, exc
            )
        return {"id": f"local-{user_id}-{submission_id}"}

    def _list_messages(
        self, conversation_id: str, user_id: str
    ) -> list[dict[str, Any]]:
        if self.db is None:
            return []
        try:
            query = (
                self.db.table("writing_coaching_messages")
                .select("*")
                .eq("conversation_id", conversation_id)
                .eq("user_id", user_id)
                .order("created_at")
            )
            result = self.db.execute(query, "list writing coaching messages")
            return result.data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("list_coaching_messages failed: %s", exc)
            return []

    def _safe_count_messages(self, conversation_id: str) -> int:
        if self.db is None or not conversation_id:
            return 0
        try:
            query = (
                self.db.table("writing_coaching_messages")
                .select("*", count="exact")
                .eq("conversation_id", conversation_id)
            )
            result = self.db.execute(query, "count writing coaching messages")
            return result.count or 0
        except Exception:  # noqa: BLE001
            return 0

    def _safe_get_last_message_at(
        self, conversation_id: str
    ) -> str | None:
        if self.db is None or not conversation_id:
            return None
        try:
            query = (
                self.db.table("writing_coaching_messages")
                .select("created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(1)
            )
            result = self.db.execute(query, "get last coaching message time")
            if result.data:
                return result.data[0].get("created_at")
        except Exception:  # noqa: BLE001
            return None

    def _save_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        structured: dict[str, Any] | None = None,
    ) -> None:
        if self.db is None:
            return
        try:
            payload = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "structured": structured or {},
            }
            query = self.db.table("writing_coaching_messages").insert(payload)
            self.db.execute(query, "save writing coaching message")
        except Exception as exc:  # noqa: BLE001
            logger.warning("save_coaching_message failed: %s", exc)

    def _touch_conversation(
        self, conversation_id: str, user_id: str
    ) -> None:
        if self.db is None:
            return
        try:
            query = (
                self.db.table("writing_coaching_conversations")
                .update({"updated_at": "now()::timestamptz"})
                .eq("id", conversation_id)
                .eq("user_id", user_id)
            )
            self.db.execute(query, "touch writing coaching conversation")
        except Exception as exc:  # noqa: BLE001
            logger.warning("touch_coaching_conversation failed: %s", exc)
