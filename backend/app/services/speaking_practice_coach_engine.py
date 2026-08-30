"""
Speaking Interactive Coach Engine.

After evaluation, users can ask the AI Speaking Coach questions like:
  "Why did I get 6.5?"
  "How can I improve fluency?"
  "Was this answer too short?"
  "How could I answer this Part 2 question?"
  "What vocabulary should I use?"
  "Why was my grammar score low?"

The coach uses:
  - The actual question
  - The student's transcript
  - Evaluation (4-criterion bands + overall)
  - Previous attempts
  - Target band
  - Current weaknesses (from error analysis)
  - Full conversation history

All conversation history is stored in speaking_coach_conversations (owner-scoped).
Integrated with the AI Mentor for cross-context awareness.

Design:
  - ``start_conversation()`` creates a new conversation.
  - ``chat()`` sends a question to the AI and stores the reply.
  - ``get_conversation()`` / ``list_conversations()`` retrieve history.
  - All operations are owner-scoped (IDOR-safe).
"""
import logging
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class SpeakingCoachEngine:
    """
    Interactive AI Speaking Coach.

    All operations are owner-scoped.  Conversation history is immutable
    per turn — new messages are appended to the existing array.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.ai_service: AIService = AIService()

    # ------------------------------------------------------------------
    # Conversation lifecycle
    # ------------------------------------------------------------------
    async def start_conversation(
        self,
        user_id: str,
        context_type: str = "practice_session",
        context_id: str = "",
        practice_mode: Optional[str] = None,
        part: Optional[str] = None,
        target_band: Optional[float] = None,
        transcript: str = "",
        question: str = "",
        evaluation: Optional[Dict[str, Any]] = None,
        error_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Start a new coaching conversation.

        Initializes the conversation with context (transcript, evaluation,
        error analysis, target band) and stores it.
        """
        if context_type not in ("practice_session", "test_response", "reattempt"):
            raise ValidationError(f"Invalid context_type: {context_type}")

        if not context_id:
            raise ValidationError("context_id is required")

        # Gather previous attempts for context.
        previous_attempts = await self._gather_previous_attempts(
            user_id, context_type, context_id
        )

        # Determine current weaknesses from error analysis.
        weaknesses = self._extract_weaknesses(error_analysis)

        convo_payload = {
            "user_id": user_id,
            "context_type": context_type,
            "context_id": context_id,
            "practice_mode": practice_mode,
            "part": part,
            "target_band": target_band,
            "current_weaknesses": weaknesses or [],
            "messages": [],
        }
        query = self.db.table("speaking_coach_conversations").insert(convo_payload)
        result = self.db.execute(query, "create speaking coach conversation")
        if not result.data:
            raise NotFoundError("Failed to create speaking coach conversation")

        return {
            "id": result.data[0].get("id"),
            "user_id": user_id,
            "context_type": context_type,
            "context_id": context_id,
            "practice_mode": practice_mode,
            "part": part,
            "target_band": target_band,
            "current_weaknesses": weaknesses or [],
            "messages": [],
            "transcript": transcript,
            "question": question,
            "evaluation": evaluation or {},
            "error_analysis": error_analysis or {},
            "previous_attempts": previous_attempts,
        }

    async def chat(
        self,
        user_id: str,
        conversation_id: str,
        student_question: str,
    ) -> Dict[str, Any]:
        """
        Send a student question to the AI Speaking Coach and append the reply.

        The AI uses the stored context (transcript, evaluation, previous
        attempts, target band, weaknesses) plus the conversation history.
        """
        session = self._get_conversation(conversation_id, user_id)
        if not session:
            raise NotFoundError("Coaching conversation not found")

        context = self._load_conversation_context(conversation_id, user_id)

        result = await self.ai_service.speaking_coach_chat(
            question=context.get("question", ""),
            transcript=context.get("transcript", ""),
            evaluation=context.get("evaluation", {}),
            error_analysis=context.get("error_analysis"),
            previous_attempts=context.get("previous_attempts", []),
            target_band=context.get("target_band"),
            weaknesses=context.get("weaknesses", []),
            student_question=student_question,
            conversation_history=session.get("messages", []),
        )

        # Build the new conversation messages.
        messages = session.get("messages", [])
        messages.append({"role": "user", "content": student_question})
        messages.append({
            "role": "assistant",
            "content": result.get("answer", ""),
            "metadata": {
                "key_points": result.get("key_points", []),
                "example": result.get("example", ""),
                "action_step": result.get("action_step", ""),
                "tone": result.get("tone", "encouraging"),
                "source": result.get("source", "unknown"),
            },
        })

        # Persist the updated messages (append).
        self.db.execute(
            self.db.table("speaking_coach_conversations")
            .update({"messages": messages})
            .eq("id", conversation_id)
            .eq("user_id", user_id),
            "append speaking coach messages",
        )

        # Generate a summary if this is the first exchange.
        if len(messages) <= 2:
            summary = self._generate_summary(student_question, result)
            self.db.execute(
                self.db.table("speaking_coach_conversations")
                .update({"summary": summary})
                .eq("id", conversation_id)
                .eq("user_id", user_id),
                "update speaking coach summary",
            )

        logger.info(
            "speaking coach chat user=%s convo=%s source=%s",
            user_id, conversation_id, result.get("source"),
        )

        return {
            "conversation_id": conversation_id,
            "reply": result,
            "updated_messages": messages,
        }

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> Dict[str, Any]:
        """Fetch a coaching conversation with full context (owner-scoped)."""
        session = self._get_conversation(conversation_id, user_id)
        if not session:
            raise NotFoundError("Coaching conversation not found")
        context = self._load_conversation_context(conversation_id, user_id)
        return {
            "id": session.get("id"),
            "user_id": session.get("user_id"),
            "context_type": session.get("context_type"),
            "context_id": session.get("context_id"),
            "practice_mode": session.get("practice_mode"),
            "part": session.get("part"),
            "target_band": session.get("target_band"),
            "current_weaknesses": session.get("current_weaknesses", []),
            "messages": session.get("messages", []),
            "summary": session.get("summary"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "context": context,
        }

    def list_conversations(
        self, user_id: str, limit: int = 50, context_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List the user's coaching conversations."""
        if self.db is None:
            return {"results": [], "total": 0}
        try:
            query = (
                self.db.table("speaking_coach_conversations")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if context_id:
                query = query.eq("context_id", context_id)
            result = self.db.execute(query, "list speaking coach conversations")
            rows = result.data or []
        except Exception:
            return {"results": [], "total": 0}

        return {
            "results": [
                {
                    "id": r.get("id"),
                    "context_type": r.get("context_type"),
                    "context_id": r.get("context_id"),
                    "practice_mode": r.get("practice_mode"),
                    "part": r.get("part"),
                    "target_band": r.get("target_band"),
                    "current_weaknesses": r.get("current_weaknesses", []),
                    "message_count": len(r.get("messages", [])),
                    "summary": r.get("summary"),
                    "created_at": r.get("created_at"),
                    "updated_at": r.get("updated_at"),
                }
                for r in rows
            ],
            "total": len(rows),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _gather_previous_attempts(
        self,
        user_id: str,
        context_type: str,
        context_id: str,
    ) -> List[Dict[str, Any]]:
        """Gather previous attempts for the same context (e.g. past reattempts)."""
        if self.db is None or not context_id:
            return []
        try:
            if context_type == "reattempt":
                # Get all speaking_attempts for the same original_response_id.
                query = (
                    self.db.table("speaking_attempts")
                    .select("attempt_number, overall_band, error_count, duration_seconds, created_at")
                    .eq("original_response_id", context_id)
                    .order("attempt_number")
                )
            elif context_type == "practice_session":
                # Get this session's evaluation (same session = self).
                query = (
                    self.db.table("speaking_practice_sessions")
                    .select("overall_band, error_count, duration_seconds, created_at")
                    .eq("id", context_id)
                    .eq("user_id", user_id)
                )
            elif context_type == "test_response":
                query = (
                    self.db.table("speaking_test_responses")
                    .select("overall_band, error_count, duration_seconds, created_at")
                    .eq("id", context_id)
                    .eq("user_id", user_id)
                )
            else:
                return []

            result = self.db.execute(query, "gather previous attempts")
            rows = result.data or []
            return rows
        except Exception:
            return []

    def _extract_weaknesses(
        self, error_analysis: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Extract weakness labels from an error analysis result."""
        if not error_analysis or not error_analysis.get("issues"):
            return []
        weaknesses = []
        for issue in error_analysis["issues"]:
            issue_type = issue.get("issue_type", "")
            if issue_type and issue_type not in weaknesses:
                weaknesses.append(issue_type)
        return weaknesses[:5]

    def _get_conversation(
        self, conversation_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a speaking_coach_conversations row (owner-scoped)."""
        if self.db is None:
            return None
        try:
            query = (
                self.db.table("speaking_coach_conversations")
                .select("*")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .limit(1)
            )
            result = self.db.execute(query, "fetch speaking coach conversation")
            return result.data[0] if result.data else None
        except Exception:
            return None

    def _load_conversation_context(
        self, conversation_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Load the full context (transcript, evaluation, etc.) for a conversation."""
        if self.db is None:
            return {}
        try:
            session = self._get_conversation(conversation_id, user_id)
            if not session:
                return {}

            context = {
                "question": "",
                "transcript": "",
                "evaluation": {},
                "error_analysis": {},
                "previous_attempts": [],
                "weaknesses": session.get("current_weaknesses", []),
                "target_band": session.get("target_band"),
                "practice_mode": session.get("practice_mode"),
                "part": session.get("part"),
            }

            context_type = session.get("context_type")
            context_id = session.get("context_id")

            if context_type == "practice_session":
                query = (
                    self.db.table("speaking_practice_sessions")
                    .select("*")
                    .eq("id", context_id)
                    .eq("user_id", user_id)
                    .limit(1)
                )
            elif context_type == "test_response":
                query = (
                    self.db.table("speaking_test_responses")
                    .select("*")
                    .eq("id", context_id)
                    .eq("user_id", user_id)
                    .limit(1)
                )
            elif context_type == "reattempt":
                query = (
                    self.db.table("speaking_attempts")
                    .select("*")
                    .eq("id", context_id)
                    .eq("user_id", user_id)
                    .limit(1)
                )
            else:
                return context

            result = self.db.execute(query, "load speaking practice context")
            if result.data:
                row = result.data[0]
                context["transcript"] = row.get("transcript", "")
                context["question"] = row.get("prompt_text", row.get("title", ""))
                # Try to build evaluation dict from band columns.
                context["evaluation"] = {
                    "overall_band": row.get("overall_band"),
                    "fluency_coherence_band": row.get("fluency_coherence_band"),
                    "lexical_resource_band": row.get("lexical_resource_band"),
                    "grammatical_range_band": row.get("grammatical_range_band"),
                    "pronunciation_band": row.get("pronunciation_band"),
                    "feedback": row.get("feedback", ""),
                }

            return context
        except Exception as exc:
            logger.warning("failed to load speaking coach context: %s", exc)
            return {"weaknesses": []}

    def _generate_summary(
        self,
        question: str,
        result: Dict[str, Any],
    ) -> str:
        """Generate a short summary of the coaching conversation."""
        q_preview = question[:80] if question else "Speaking practice"
        answer_preview = result.get("answer", "")[:100]
        return f"Q: {q_preview}... A: {answer_preview}..."
