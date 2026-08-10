"""
Repository for the AI Mentor Memory system.

Stores long-term learner insights that allow the mentor to provide
increasingly personalized coaching across sessions. All operations are
owner-scoped to prevent cross-user access (IDOR).
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository

# ---------------------------------------------------------------------------
# Memory types and their defaults
# ---------------------------------------------------------------------------
MEMORY_TYPES = {
    "recurring_mistake": {"category_required": True, "subcategory_required": True},
    "faq": {"category_required": True, "subcategory_optional": True},
    "weak_grammar": {"category_required": False, "subcategory_required": True},
    "weak_vocabulary": {"category_required": False, "subcategory_required": True},
    "learning_preference": {"category_required": False, "subcategory_required": False},
    "motivation_style": {"category_required": False, "subcategory_required": False},
    "conversation_insight": {"category_required": False, "subcategory_required": False},
}

# Confidence decay: each access reduces confidence by this factor.
CONFIDENCE_DECAY = 0.95

# Minimum confidence for a memory to be surfaced in recommendations.
MIN_CONFIDENCE = 0.3

# Default TTL for time-sensitive memories (in days). None = permanent.
DEFAULT_TTL_DAYS = None


class MentorMemoryRepository(BaseRepository):
    """Data access for the mentor_memory + mentor_memory_events tables."""

    table_name = "mentor_memory"
    user_id_column = "user_id"

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ─── Memory CRUD ────────────────────────────────────────────────

    def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
        context: Optional[Dict[str, Any]] = None,
        ttl_days: Optional[int] = DEFAULT_TTL_DAYS,
    ) -> Dict[str, Any]:
        """
        Create or update a mentor memory entry.

        If a memory with the same (user_id, memory_type, category, subcategory, content)
        already exists, it is updated (weight incremented, confidence reinforced).

        Otherwise a new entry is created.
        """
        if memory_type not in MEMORY_TYPES:
            raise ValidationError(f"Invalid memory_type: {memory_type}")

        # Validate required fields.
        type_spec = MEMORY_TYPES[memory_type]
        if type_spec.get("category_required") and not category:
            raise ValidationError(f"category is required for memory_type '{memory_type}'")
        if type_spec.get("subcategory_required") and not subcategory:
            raise ValidationError(f"subcategory is required for memory_type '{memory_type}'")

        now = datetime.utcnow()

        # Check for existing memory (consolidation).
        existing = self._find_existing(
            user_id, memory_type, category, subcategory, content
        )

        expires_at = None
        if ttl_days is not None:
            expires_at = now + timedelta(days=ttl_days)

        if existing:
            # Reinforce: increment weight, boost confidence.
            new_weight = int(existing.get("weight", 1)) + 1
            new_confidence = min(
                1.0,
                float(existing.get("confidence", 0.5)) + (0.1 * (1.0 - float(existing.get("confidence", 0.5)))),
            )
            if expires_at:
                new_confidence = min(new_confidence, 0.9)  # don't max out on reinforcement

            update = (
                self.db.table("mentor_memory")
                .update({
                    "weight": new_weight,
                    "confidence": round(new_confidence, 2),
                    "structured_data": structured_data or {},
                    "context": {**(existing.get("context") or {}), **(context or {})},
                    "last_accessed_at": now.isoformat(),
                    "accessed_count": int(existing.get("accessed_count", 0)) + 1,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "is_active": True,
                })
                .eq("id", existing["id"])
                .eq("user_id", user_id)
            )
            result = self.db.execute(update, "update existing mentor memory")
            if result.data:
                return result.data[0]
            return existing

        # New memory.
        payload = {
            "user_id": user_id,
            "memory_type": memory_type,
            "category": category,
            "subcategory": subcategory,
            "content": content,
            "structured_data": structured_data or {},
            "confidence": round(float(confidence), 2),
            "weight": 1,
            "context": context or {},
            "last_accessed_at": now.isoformat(),
            "accessed_count": 0,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "is_active": True,
        }
        query = self.db.table("mentor_memory").insert(payload)
        result = self.db.execute(query, "create mentor memory")
        if not result.data:
            raise NotFoundError("Failed to create mentor memory")
        return result.data[0]

    def get_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> List[Dict[str, Any]]:
        """
        Fetch memories, optionally filtered by type/category.
        Only returns active memories with confidence >= min_confidence
        that haven't expired.
        """
        query = (
            self.db.table("mentor_memory")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .gte("confidence", min_confidence)
            .or_("expires_at.is.null,expires_at.gt." + datetime.utcnow().isoformat())
            .order("weight", desc=True)
            .order("last_accessed_at", desc=True)
            .limit(limit)
        )
        if memory_type:
            query = query.eq("memory_type", memory_type)
        if category:
            query = query.eq("category", category)

        result = self.db.execute(query, "fetch mentor memories")
        return result.data or []

    def get_memory(self, user_id: str, memory_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single memory owner-scoped."""
        query = (
            self.db.table("mentor_memory")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", memory_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch single mentor memory")
        if not result.data:
            return None
        return result.data[0]

    def update_memory(
        self, user_id: str, memory_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a memory owner-scoped."""
        allowed_fields = {
            "content", "category", "subcategory", "structured_data",
            "confidence", "is_active", "expires_at",
        }
        payload = {k: v for k, v in data.items() if k in allowed_fields}
        if not payload:
            raise ValidationError("No valid fields to update")

        query = (
            self.db.table("mentor_memory")
            .update(payload)
            .eq("id", memory_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "update mentor memory")
        if not result.data:
            raise NotFoundError("Mentor memory not found")
        return result.data[0]

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        """Soft-delete a memory (set is_active = False)."""
        query = (
            self.db.table("mentor_memory")
            .update({"is_active": False})
            .eq("id", memory_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "soft-delete mentor memory")
        if not result.data:
            raise NotFoundError("Mentor memory not found")

    def increment_access(self, user_id: str, memory_id: str) -> None:
        """Track that a memory was accessed (for decay/scoring)."""
        query = (
            self.db.table("mentor_memory")
            .update({
                "accessed_count": "accessed_count + 1",
                "last_accessed_at": datetime.utcnow().isoformat(),
                "confidence": "GREATEST(confidence * :decay, :min)",
            })
            .eq("id", memory_id)
            .eq("user_id", user_id)
        )
        # Use raw SQL for the confidence decay computation.
        raw_query = (
            self.db.table("mentor_memory")
            .update({
                "accessed_count": "accessed_count + 1",
                "last_accessed_at": datetime.utcnow().isoformat(),
                "confidence": f"GREATEST(confidence * {CONFIDENCE_DECAY}, {MIN_CONFIDENCE})",
            })
            .eq("id", memory_id)
            .eq("user_id", user_id)
        )
        try:
            self.db.execute(raw_query, "increment memory access")
        except Exception:
            pass

    def _find_existing(
        self,
        user_id: str,
        memory_type: str,
        category: Optional[str],
        subcategory: Optional[str],
        content: str,
    ) -> Optional[Dict[str, Any]]:
        """Find an existing memory to consolidate (same type + category + subcategory + similar content)."""
        query = (
            self.db.table("mentor_memory")
            .select("*")
            .eq("user_id", user_id)
            .eq("memory_type", memory_type)
            .is_("is_active", True)
            .limit(50)
        )
        if category:
            query = query.eq("category", category)
        else:
            query = query.is_("category", None)
        if subcategory:
            query = query.eq("subcategory", subcategory)
        else:
            query = query.is_("subcategory", None)

        # Also check content similarity (case-insensitive exact match first).
        result = self.db.execute(query, "find existing memory for consolidation")
        for row in result.data or []:
            if (row.get("content") or "").strip().lower() == content.strip().lower():
                return row
        return None

    # ─── Events (audit log) ─────────────────────────────────────────

    def log_event(
        self,
        user_id: str,
        event_type: str,
        payload: Dict[str, Any],
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log a raw event to mentor_memory_events for the extraction pipeline."""
        insert_payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "event_type": event_type,
            "payload": payload,
            "processed": False,
        }
        query = self.db.table("mentor_memory_events").insert(insert_payload)
        result = self.db.execute(query, "log mentor memory event")
        if not result.data:
            raise NotFoundError("Failed to log mentor memory event")
        return result.data[0]

    def list_events(
        self, user_id: str, limit: int = 50, processed: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """List raw memory events for a user."""
        query = (
            self.db.table("mentor_memory_events")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if processed is not None:
            query = query.eq("processed", processed)
        result = self.db.execute(query, "list mentor memory events")
        return result.data or []

    # ─── Bulk operations ────────────────────────────────────────────

    def get_all_memories_by_type(
        self, user_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch all memories grouped by type.
        Used by the AI recommendations service to improve coaching.
        """
        memories = self.get_memories(user_id, limit=200)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for m in memories:
            mt = m.get("memory_type", "unknown")
            grouped.setdefault(mt, []).append(m)
        return grouped

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Build a consolidated memory profile for the user.
        This is what the AI mentor / recommendations service consumes to
        personalize coaching.
        """
        memories = self.get_all_memories_by_type(user_id)

        recurring_mistakes = memories.get("recurring_mistake", [])
        faqs = memories.get("faq", [])
        weak_grammar = memories.get("weak_grammar", [])
        weak_vocab = memories.get("weak_vocabulary", [])
        learning_prefs = memories.get("learning_preference", [])
        motivation_styles = memories.get("motivation_style", [])
        insights = memories.get("conversation_insight", [])

        # Extract skill focus from weak grammar/vocab.
        weak_skills: List[str] = []
        for m in weak_grammar + weak_vocab:
            cat = m.get("category")
            if cat and cat not in weak_skills:
                weak_skills.append(cat)

        # Extract preference text.
        preferences = [m.get("content", "") for m in learning_prefs if m.get("content")]
        motivation = motivations = [m.get("content", "") for m in motivation_styles if m.get("content")]

        return {
            "total_memories": sum(len(v) for v in memories.values()),
            "recurring_mistakes": [self._serialize(m) for m in recurring_mistakes],
            "faqs": [self._serialize(m) for m in faqs],
            "weak_grammar": [self._serialize(m) for m in weak_grammar],
            "weak_vocabulary": [self._serialize(m) for m in weak_vocab],
            "learning_preferences": [self._serialize(m) for m in learning_prefs],
            "motivation_styles": [self._serialize(m) for m in motivation_styles],
            "conversation_insights": [self._serialize(m) for m in insights],
            "weak_skills": weak_skills,
            "preference_texts": preferences,
            "motivation_texts": motivations,
        }

    def _serialize(self, m: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize a memory row for JSON output."""
        return {
            "id": m.get("id"),
            "memory_type": m.get("memory_type"),
            "category": m.get("category"),
            "subcategory": m.get("subcategory"),
            "content": m.get("content"),
            "structured_data": m.get("structured_data") or {},
            "confidence": float(m.get("confidence") or 0.5),
            "weight": int(m.get("weight") or 1),
            "context": m.get("context") or {},
            "last_accessed_at": m.get("last_accessed_at"),
            "accessed_count": int(m.get("accessed_count") or 0),
            "expires_at": m.get("expires_at"),
            "is_active": m.get("is_active", True),
            "created_at": m.get("created_at"),
            "updated_at": m.get("updated_at"),
        }
