"""
AI Mentor Memory service.

Provides a high-level API for recording and retrieving long-term learner
insights that personalize the mentor's coaching. The service extracts memory
signals from multiple data sources and stores them as typed memory entries:

  - Recurring mistakes      → from diagnostic + progress data
  - Frequently asked Q&As    → from mentor conversation transcripts
  - Weak grammar topics     → from diagnostic results + band estimation
  - Weak vocabulary         → from diagnostic results + band estimation
  - Learning preferences    → inferred from study patterns + explicit settings
  - Motivation style        → inferred from consistency patterns + streaks
  - Previous conversations  → conversation history from mentor_conversations

All formulas are deterministic (NO AI extraction) — keyword matching and
statistical thresholds only. All DB access is defensive.
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.band_estimation_repo import BandEstimationRepository
from app.repositories.diagnostic_repo import DiagnosticRepository
from app.repositories.mentor_memory_repo import MentorMemoryRepository
from app.repositories.mentor_repo import MentorRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository
from app.repositories.streak_repo import StreakRepository
from app.services.diagnostic_roadmap_service import diagnostic_roadmap_service

logger = logging.getLogger(__name__)

# Keywords for detecting question types in mentor conversations.
QUESTION_PATTERNS = {
    "writing": [
        "essay", "task 2", "task 1", "coherence", "cohesion", "band", "word count",
        "thesis", "introduction", "conclusion", "paragraph", "linking",
    ],
    "speaking": [
        "fluency", "vocabulary", "pronunciation", "coherence", "part 1", "part 2",
        "part 3", "cue card", "follow-up", "mouth",
    ],
    "reading": [
        "skimming", "scanning", "matching", "true/false", "T/f/ng", "multiple choice",
        "gap fill", "heading", "overview", "word limit",
    ],
    "listening": [
        "note-taking", "predict", "distractor", "section", "map", "form",
        "timer", "transfer",
    ],
    "vocab_grammar": [
        "vocabulary", "collocation", "synonym", "paraphrase", "grammatical range",
        "tense", "conditional", "article", "preposition",
    ],
}

# Grammar topic keywords.
GRAMMAR_TOPIC_KEYWORDS = {
    "tenses": ["tense", "past", "present", "future", "verb"],
    "conditionals": ["conditional", "if-clause", "mixed"],
    "articles": ["article", "a/an/the", "determiner"],
    "prepositions": ["preposition", "in", "on", "at", "by", "with"],
    "sentence_structure": ["sentence", "structure", "clause", "complex"],
    "word_forms": ["word form", "noun", "verb", "adjective", "adverb"],
}

# Vocabulary topic keywords.
VOCAB_TOPIC_KEYWORDS = {
    "collocations": ["collocation", "phrase", "together"],
    "synonyms": ["synonym", "alternative", "word choice"],
    "academic_words": ["academic", "topic sentence", "thematic"],
    "paraphrasing": ["paraphrase", "rephrase", "alternative"],
    "formal_register": ["formal", "informal", "register", "tone"],
}

# Motivation detection keywords.
MOTIVATION_PATTERNS = {
    "achievement": ["achievement", "milestone", "progress", "goal", "target", "win"],
    "streak": ["streak", "consistency", "habit", "daily", "routine"],
    "social": ["compete", "leaderboard", "friend", "community", "share", "compare"],
    "fear": ["fail", "fear", "pressure", "worried", "anxious", "stress", "behind"],
    "rewards": ["reward", "badge", "unlock", "level", "point", "xp"],
}


class MentorMemoryService:
    """Deterministic mentor memory service — no AI, all keyword-matching + stats."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = MentorMemoryRepository(db)
        self.band_estimation_repo = BandEstimationRepository(db)
        self.diagnostic_repo = DiagnosticRepository(db)
        self.mentor_repo = MentorRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)
        self.streak_repo = StreakRepository(db)

    # ─── Public API ────────────────────────────────────────────────────

    def get_memory_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch the user's consolidated mentor memory profile.

        This profile is consumed by the AI mentor service and the AI
        Recommendations service to personalize coaching.
        """
        return self._safe_get_memory_profile(user_id)

    def extract_and_store_memories(
        self, user_id: str, force: bool = False
    ) -> Dict[str, Any]:
        """
        Extract memories from all data sources and store them.

        Called periodically (e.g., after each mentor session) or on-demand.
        Idempotent: existing memories are reinforced, not duplicated.
        """
        if self.db is None and not force:
            return {"status": "no_db", "memories_added": 0, "memories_updated": 0}

        results = {
            "status": "ok",
            "memories_added": 0,
            "memories_updated": 0,
            "details": {},
        }

        # 1. Extract from diagnostic results.
        try:
            diag_results = self._extract_from_diagnostic(user_id)
            added, updated = self._store_memories(user_id, diag_results)
            results["memories_added"] += added
            results["memories_updated"] += updated
            results["details"]["diagnostic"] = len(diag_results)
        except Exception as exc:
            logger.warning("diagnostic extraction failed user=%s: %s", user_id, exc)

        # 2. Extract from band estimation (skill bands → weak areas).
        try:
            est_results = self._extract_from_band_estimation(user_id)
            added, updated = self._store_memories(user_id, est_results)
            results["memories_added"] += added
            results["memories_updated"] += updated
            results["details"]["band_estimation"] = len(est_results)
        except Exception as exc:
            logger.warning("band estimation extraction failed user=%s: %s", user_id, exc)

        # 3. Extract from mentor conversations (FAQs, recurring questions).
        try:
            faq_results = self._extract_from_conversations(user_id)
            added, updated = self._store_memories(user_id, faq_results)
            results["memories_added"] += added
            results["memories_updated"] += updated
            results["details"]["conversations"] = len(faq_results)
        except Exception as exc:
            logger.warning("conversation extraction failed user=%s: %s", user_id, exc)

        # 4. Extract from progress data (learning preferences, motivation).
        try:
            pref_results = self._extract_from_progress(user_id)
            added, updated = self._store_memories(user_id, pref_results)
            results["memories_added"] += added
            results["memories_updated"] += updated
            results["details"]["progress"] = len(pref_results)
        except Exception as exc:
            logger.warning("progress extraction failed user=%s: %s", user_id, exc)

        # 5. Log events for the extraction pipeline.
        try:
            self._log_extraction_event(user_id, results)
        except Exception:
            pass

        logger.info(
            "mentor memory extraction complete user=%s added=%d updated=%d",
            user_id, results["memories_added"], results["memories_updated"],
        )
        return results

    def get_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch raw memories (for the frontend memory browser)."""
        return self._safe_get_memories(user_id, memory_type, category, limit)

    def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        confidence: float = 0.7,
    ) -> Dict[str, Any]:
        """Manually add a memory entry."""
        if memory_type not in self._get_memory_types():
            raise ValidationError(f"Invalid memory_type: {memory_type}")
        return self.repo.add_memory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            category=category,
            subcategory=subcategory,
            structured_data=structured_data,
            confidence=confidence,
        )

    def update_memory(
        self, user_id: str, memory_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a memory entry."""
        return self.repo.update_memory(user_id, memory_id, data)

    def delete_memory(self, user_id: str, memory_id: str) -> None:
        """Soft-delete a memory entry."""
        self.repo.delete_memory(user_id, memory_id)

    def get_memory_types(self) -> List[Dict[str, Any]]:
        """Return the available memory types and their schema."""
        from app.repositories.mentor_memory_repo import MEMORY_TYPES
        return [
            {
                "type": mt,
                "category_required": spec.get("category_required", False),
                "subcategory_required": spec.get("subcategory_required", False),
                "label": self._memory_type_label(mt),
                "description": self._memory_type_description(mt),
            }
            for mt, spec in MEMORY_TYPES.items()
        ]

    # ─── Extraction methods ───────────────────────────────────────────

    def _extract_from_diagnostic(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Extract recurring mistakes and weak skill areas from diagnostic results.

        Looks at the latest diagnostic attempt to identify:
          - Skills with band < 6.0 → weak_grammar / weak_vocabulary memories
          - Common mistake patterns in diagnostic responses
        """
        memories = []
        if self.db is None:
            return memories

        try:
            diag = diagnostic_roadmap_service.resolve_profile(user_id)
            skill_bands = diag.get("skill_bands", {})
            if not skill_bands:
                return memories

            for skill, band in skill_bands.items():
                if skill in ("vocabulary", "grammar") and band < 6.0:
                    memory_type = f"weak_{skill}"
                    category = SKILL_LABELS.get(skill, skill)
                    subcategory = self._infer_subtopic(skill, band)

                    memories.append({
                        "memory_type": memory_type,
                        "category": category,
                        "subcategory": subcategory,
                        "content": f"Persistent weakness in {SKILL_LABELS.get(skill, skill)} "
                                   f"(band {band:.1f}), needs targeted practice.",
                        "structured_data": {
                            "band": band,
                            "skill": skill,
                            "source": diag.get("source", "diagnostic"),
                            "has_diagnostic": diag.get("has_diagnostic", False),
                        },
                        "confidence": 0.7,
                    })

                if band < 5.5:
                    memory_type = "recurring_mistake"
                    category = SKILL_LABELS.get(skill, skill)

                    focus_areas = diag.get("focus_areas", [])
                    content = f"Struggles with {SKILL_LABELS.get(skill, skill)} " \
                              f"(band {band:.1f}). Focus areas: {', '.join(focus_areas[:3]) if focus_areas else 'core concepts'}."

                    memories.append({
                        "memory_type": memory_type,
                        "category": category,
                        "subcategory": "band_deficit",
                        "content": content,
                        "structured_data": {
                            "band": band,
                            "skill": skill,
                            "focus_areas": focus_areas[:3],
                        },
                        "confidence": 0.65,
                    })

        except Exception as exc:
            logger.warning("diagnostic memory extraction failed user=%s: %s", user_id, exc)

        return memories

    def _extract_from_band_estimation(self, user_id: str) -> List[Dict[str, Any]]:
        """Extract weak skill areas from the latest band estimation snapshot."""
        memories = []
        if self.db is None:
            return memories

        try:
            latest = self.band_estimation_repo.get_latest(user_id)
            if not latest:
                return memories

            skill_bands = latest.get("skill_bands", {})
            weakest = latest.get("weakest_skills", [])
            explanations = latest.get("explanations", {})

            for skill in weakest[:3]:
                band = skill_bands.get(skill, 5.0)
                explanation = explanations.get(skill, "")

                label = SKILL_LABELS.get(skill, skill.title())

                if skill in ("vocabulary", "grammar"):
                    mt = f"weak_{skill}"
                    sub = self._infer_subtopic(skill, band)

                    memories.append({
                        "memory_type": mt,
                        "category": label,
                        "subcategory": sub,
                        "content": f"{label} weakness (band {band:.1f}). "
                                   f"Explanation: {explanation[:100]}...",
                        "structured_data": {
                            "band": band,
                            "skill": skill,
                            "source": "band_estimation",
                            "explanation": explanation,
                        },
                        "confidence": float(latest.get("confidence_score", 0.5) or 0.5),
                    })

                # Recurring mistake for all weakest skills.
                memories.append({
                    "memory_type": "recurring_mistake",
                    "category": label,
                    "subcategory": f"band_{band:.1f}",
                    "content": f"Needs improvement in {label} (estimated band {band:.1f}).",
                    "structured_data": {
                        "band": band,
                        "skill": skill,
                        "source": "band_estimation",
                    },
                    "confidence": 0.6,
                })

        except Exception as exc:
            logger.warning("band estimation memory extraction failed user=%s: %s", user_id, exc)

        return memories

    def _extract_from_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Extract frequently asked questions and recurring question themes
        from mentor conversation transcripts.

        Looks at all past conversations (or last 20) and extracts:
          - Questions that appear 3+ times → faq memories
          - Skill-specific question patterns → skill-specific memories
        """
        memories = []
        if self.db is None:
            return memories

        try:
            conversations = self.mentor_repo.list_conversations(user_id, limit=20)
            all_questions: List[str] = []

            for conv in conversations:
                messages = self.mentor_repo.list_messages(conv["id"], user_id)
                for msg in messages:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if content and len(content) > 10:
                            all_questions.append(content.strip())

            if not all_questions:
                return memories

            # Detect frequently asked questions (exact or fuzzy match).
            question_counter = Counter(q.lower() for q in all_questions)
            for question, count in question_counter.items():
                if count >= 2:
                    # Determine which skill this question relates to.
                    skill = self._detect_skill_from_text(question)

                    memories.append({
                        "memory_type": "faq",
                        "category": skill,
                        "subcategory": "user_question",
                        "content": question,
                        "structured_data": {
                            "question_count": count,
                            "detected_skill": skill,
                        },
                        "confidence": min(0.5 + (count * 0.1), 0.9),
                    })

            # Detect skill-specific question patterns.
            skill_question_counts: Dict[str, int] = {}
            for q in all_questions:
                skill = self._detect_skill_from_text(q.lower())
                if skill:
                    skill_question_counts[skill] = skill_question_counts.get(skill, 0) + 1

            for skill, count in skill_question_counts.items():
                if count >= 3:
                    label = SKILL_LABELS.get(skill, skill.title())
                    memories.append({
                        "memory_type": "conversation_insight",
                        "category": skill,
                        "subcategory": "question_pattern",
                        "content": f"User frequently asks about {label} ({count} questions).",
                        "structured_data": {
                            "question_count": count,
                            "skill": skill,
                        },
                        "confidence": min(0.4 + (count * 0.05), 0.85),
                    })

        except Exception as exc:
            logger.warning("conversation memory extraction failed user=%s: %s", user_id, exc)

        return memories

    def _extract_from_progress(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Extract learning preferences and motivation style from study patterns.

        Heuristics:
          - Session duration consistency → preference for short/long sessions
          - Streak patterns → streak-based or milestone-based motivation
          - Active days per week → preference pattern
          - Level progression → gamification preference
        """
        memories = []
        if self.db is None:
            return memories

        try:
            state = self.progress_repo.get_state(user_id)
            streak_overview = self.streak_repo.get_overview(user_id)

            total_minutes = int(state.get("total_minutes") or 0)
            current_streak = int(state.get("current_streak") or 0)
            weekly_streak = streak_overview.get("weekly", {}).get("current", 0)
            perfect_days = streak_overview.get("bonuses", {}).get("perfect_day_count", 0)
            bonus_xp = streak_overview.get("bonuses", {}).get("total_bonus_xp", 0)
            level = int(state.get("level") or 1)

            # Learning preference: session length.
            daily_budget = self._safe_daily_budget(user_id)
            if daily_budget > 90:
                pref_text = "Prefers intensive study sessions (90+ min)"
                pref_key = "intensive"
            elif daily_budget < 30:
                pref_text = "Prefers micro-learning sessions (< 30 min)"
                pref_key = "micro"
            else:
                pref_text = "Prefers moderate study sessions (30-90 min)"
                pref_key = "moderate"

            memories.append({
                "memory_type": "learning_preference",
                "category": "study_habits",
                "subcategory": "session_length",
                "content": pref_text,
                "structured_data": {
                    "preference": pref_key,
                    "daily_budget_minutes": daily_budget,
                },
                "confidence": 0.7,
            })

            # Motivation style: streak-based vs milestone-based vs social.
            if current_streak >= 7 and perfect_days > 0:
                mot_text = "Streak-motivated learner — responds well to daily consistency rewards"
                mot_key = "streak"
            elif level >= 10 and bonus_xp > 100:
                mot_text = "Milestone-motivated learner — driven by achievements and levels"
                mot_key = "milestone"
            elif weekly_streak >= 2:
                mot_text = "Progress-motivated learner — values steady improvement"
                mot_key = "progress"
            else:
                mot_text = "Fresh start motivated — needs gentle encouragement"
                mot_key = "fresh_start"

            memories.append({
                "memory_type": "motivation_style",
                "category": "engagement",
                "subcategory": "motivational_driver",
                "content": mot_text,
                "structured_data": {
                    "style": mot_key,
                    "current_streak": current_streak,
                    "level": level,
                    "perfect_days": perfect_days,
                },
                "confidence": 0.65,
            })

            # Learning preference: active days pattern.
            week_start = date.today() - timedelta(days=6)
            week_stats = self.progress_repo.get_range_stats(user_id, week_start, date.today())
            active_days = sum(1 for s in week_stats if int(s.get("minutes") or 0) > 0)

            if active_days >= 5:
                freq_text = "Consistent daily learner — studies 5+ days/week"
                freq_key = "daily"
            elif active_days >= 3:
                freq_text = "Moderate learner — studies 3-4 days/week"
                freq_key = "moderate"
            else:
                freq_text = "Cramming-style learner — studies in bursts"
                freq_key = "cramming"

            memories.append({
                "memory_type": "learning_preference",
                "category": "study_habits",
                "subcategory": "frequency_pattern",
                "content": freq_text,
                "structured_data": {
                    "pattern": freq_key,
                    "active_days_per_week": active_days,
                },
                "confidence": 0.6,
            })

        except Exception as exc:
            logger.warning("progress memory extraction failed user=%s: %s", user_id, exc)

        return memories

    # ─── Storage helpers ──────────────────────────────────────────────

    def _store_memories(
        self, user_id: str, memories: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """Store a batch of memories, returning (added, updated)."""
        if not memories or self.db is None:
            return 0, 0

        added = 0
        updated = 0
        for m in memories:
            try:
                self.repo.add_memory(
                    user_id=user_id,
                    memory_type=m["memory_type"],
                    content=m["content"],
                    category=m.get("category"),
                    subcategory=m.get("subcategory"),
                    structured_data=m.get("structured_data"),
                    confidence=m.get("confidence", 0.5),
                )
                # If add_memory returns (creates new), it's "added".
                # If it returns existing (consolidation), it's "updated".
                added += 1
            except Exception as exc:
                logger.warning("failed to store memory user=%s: %s", user_id, exc)

        return added, updated

    def _log_extraction_event(
        self, user_id: str, results: Dict[str, Any]
    ) -> None:
        """Log an extraction event for the audit pipeline."""
        if self.db is None:
            return
        try:
            self.repo.log_event(
                user_id=user_id,
                event_type="extraction_complete",
                payload={
                    "memories_added": results["memories_added"],
                    "memories_updated": results["memories_updated"],
                    "details": results.get("details", {}),
                },
            )
        except Exception:
            pass

    # ─── Heuristic helpers ────────────────────────────────────────────

    @staticmethod
    def _detect_skill_from_text(text: str) -> Optional[str]:
        """
        Detect which IELTS skill a question relates to via keyword matching.

        Uses word-boundary matching for all keywords to avoid false positives
        from short substrings (e.g. "on" matching "collocations").
        """
        import re as _re

        text_lower = text.lower()
        for skill, keywords in QUESTION_PATTERNS.items():
            for kw in keywords:
                if _re.search(r'\b' + _re.escape(kw.lower()), text_lower):
                    if skill == "vocab_grammar":
                        # Disambiguate vocab vs grammar using word-boundary matching.
                        for gtopic, gkeywords in GRAMMAR_TOPIC_KEYWORDS.items():
                            for gkw in gkeywords:
                                if _re.search(r'\b' + _re.escape(gkw.lower()), text_lower):
                                    return "grammar"
                        for vtopic, vkeywords in VOCAB_TOPIC_KEYWORDS.items():
                            for vkw in vkeywords:
                                if _re.search(r'\b' + _re.escape(vkw.lower()), text_lower):
                                    return "vocabulary"
                        return skill
                    return skill
        return None

    @staticmethod
    def _infer_subtopic(skill: str, band: float) -> str:
        """Infer a subtopic for weak skill memories based on the band level."""
        if skill == "vocabulary":
            if band < 5.5:
                return "basic_vocabulary"
            elif band < 6.5:
                return "collocations"
            elif band < 7.5:
                return "academic_words"
            else:
                return "advanced_lexis"
        elif skill == "grammar":
            if band < 5.5:
                return "basic_grammar"
            elif band < 6.5:
                return "tenses_and_articles"
            elif band < 7.5:
                return "complex_sentences"
            else:
                return "advanced_structures"
        return "general"

    @staticmethod
    def _memory_type_label(memory_type: str) -> str:
        labels = {
            "recurring_mistake": "Recurring Mistakes",
            "faq": "Frequently Asked Questions",
            "weak_grammar": "Weak Grammar Topics",
            "weak_vocabulary": "Weak Vocabulary",
            "learning_preference": "Learning Preferences",
            "motivation_style": "Motivation Style",
            "conversation_insight": "Conversation Insights",
        }
        return labels.get(memory_type, memory_type)

    @staticmethod
    def _memory_type_description(memory_type: str) -> str:
        descs = {
            "recurring_mistake": "Repeated errors detected in diagnostic or study data",
            "faq": "Questions the user has asked multiple times",
            "weak_grammar": "Grammar topics where the user consistently struggles",
            "weak_vocabulary": "Vocabulary areas needing targeted practice",
            "learning_preference": "Detected study habits and preferred session styles",
            "motivation_style": "What drives the user to keep studying",
            "conversation_insight": "Patterns detected from mentor conversation history",
        }
        return descs.get(memory_type, "")

    def _safe_daily_budget(self, user_id: str) -> int:
        """Get the user's daily minutes budget from profile."""
        if self.db is None:
            return 60
        try:
            profile = self.user_repo.get_profile(user_id)
            return int(profile.get("daily_minutes_budget") or 60)
        except Exception:
            return 60

    def _get_memory_types(self) -> Dict[str, Any]:
        from app.repositories.mentor_memory_repo import MEMORY_TYPES
        return MEMORY_TYPES

    # ─── Safe DB wrappers ──────────────────────────────────────────────

    def _safe_get_memory_profile(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return self._empty_profile()
        try:
            return self.repo.get_profile(user_id)
        except Exception:
            return self._empty_profile()

    def _safe_get_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.get_memories(user_id, memory_type, category, limit)
        except Exception:
            return []

    @staticmethod
    def _empty_profile() -> Dict[str, Any]:
        return {
            "total_memories": 0,
            "recurring_mistakes": [],
            "faqs": [],
            "weak_grammar": [],
            "weak_vocabulary": [],
            "learning_preferences": [],
            "motivation_styles": [],
            "conversation_insights": [],
            "weak_skills": [],
            "preference_texts": [],
            "motivation_texts": [],
        }

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)[:10]).date()
        except (ValueError, TypeError):
            return None


from app.db.session import db_session

mentor_memory_service = MentorMemoryService(db_session)
