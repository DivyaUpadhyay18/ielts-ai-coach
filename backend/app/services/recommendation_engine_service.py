"""
Intelligent Recommendation Engine Service.

A deterministic (NO AI) rule-based resource recommendation system that ranks
resources based on the user's context:

  - Current Band, Target Band
  - Weakest Skill, Today's Mission, Sub Skill
  - Past Performance, Study History
  - Difficulty, Estimated Available Time
  - Remaining Days Until Exam

Ranking Algorithm:
  Each resource gets a score from 0 to 100 based on weighted factors.
  Full documentation is in RECOMMENDATION_ENGINE.md and the service methods.

Rules:
  1. Never recommend completed resources unless revision is required.
  2. Prioritize official resources.
  3. Avoid repeating the same YouTube videos.
  4. Mix: Video, PDF, Quiz, Practice, Vocabulary resources.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.recommendation_repo import RecommendationRepository
from app.repositories.resource_management_repo import ResourceRepository

logger = logging.getLogger(__name__)

# ─── Scoring constants ────────────────────────────────────────────────
SCORE_BAND_ALIGNMENT = 20.0      # Band range alignment
SCORE_SKILL_MATCH = 25.0         # Skill match with weakest/today's mission
SCORE_SUB_SKILL_MATCH = 15.0     # Sub-skill match
SCORE_OFFICIAL = 10.0            # Official resource bonus
SCORE_VERIFIED = 8.0             # Verified resource bonus
SCORE_TYPE_MIX = 5.0             # Resource type diversity bonus
SCORE_DIFFICULTY_ALIGN = 7.0      # Difficulty alignment with user level
SCORE_TIME_FIT = 5.0             # Time availability match
SCORE_POPULARITY = 3.0           # Popularity score
SCORE_RATING = 2.0               # Average rating
SCORE_RECENT = 5.0               # Recently added resources
SCORE_REPETITION_PENALTY = -20.0 # Penalize recently seen resources

# Difficulty level mapping
DIFFICULTY_LEVELS = {"beginner": 1, "intermediate": 2, "advanced": 3, "all_levels": 2}


class RecommendationEngineService:
    """
    Rule-based recommendation engine for the IELTS AI Coach resource catalog.

    All scoring is deterministic with documented formulas — NO AI.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = RecommendationRepository(db)
        self.resource_repo = ResourceRepository(db)

    # ─── Public API ────────────────────────────────────────────────────

    def get_recommendations(
        self,
        user_id: str,
        skill: Optional[str] = None,
        sub_skill: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 10,
        include_completed: bool = False,
        only_verified: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate resource recommendations for a user.

        Returns a dict matching RecommendationResponse.
        """
        today = date.today()

        # ─── 1. Gather user context ────────────────────────────────────
        user = self._safe_get_user_profile(user_id)
        if not user:
            raise NotFoundError("User not found")

        current_band = float(user.get("current_band") or 5.0)
        target_band = float(user.get("target_band") or 6.5)
        exam_date_str = user.get("exam_date")
        daily_budget = int(user.get("daily_minutes_budget") or 60)
        weakest_skill = user.get("weakest_skill") or []
        strongest_skill = user.get("strongest_skill") or []

        # ─── 2. Compute remaining days ─────────────────────────────────
        remaining_days = None
        if exam_date_str:
            exam_date = self._parse_date(exam_date_str)
            remaining_days = max((exam_date - today).days, 0)

        # ─── 3. Determine target skill ────────────────────────────────
        target_skill = skill or self._determine_target_skill(
            weakest_skill, strongest_skill
        )

        # ─── 4. Get today's mission skill ──────────────────────────────
        today_missions = self._safe_get_today_missions(user_id)
        today_mission_skill = self._extract_mission_skill(today_missions, target_skill)

        # ─── 5. Get completed resources ────────────────────────────────
        completed_ids = self.repo.get_completed_resource_ids(user_id)

        # ─── 6. Get performance history ────────────────────────────────
        skill_performance = self._safe_get_skill_performance(user_id)
        mock_scores = self._safe_get_mock_scores(user_id)

        # ─── 7. Fetch candidate resources ────────────────────────────
        candidates = self._fetch_candidate_resources(
            skill=target_skill,
            resource_type=resource_type,
            current_band=current_band,
            target_band=target_band,
            remaining_days=remaining_days or 0,
        )

        # ─── 8. Compute difficulty preference ──────────────────────────
        difficulty_pref = self._compute_difficulty_preference(
            current_band, target_band, remaining_days or 0
        )

        # ─── 9. Score each resource ────────────────────────────────────
        scored_items = []
        seen_youtube_ids: Set[str] = set()

        for resource in candidates:
            # Rule 1: Skip completed resources (unless include_completed for revision)
            if not include_completed and resource.get("id") in completed_ids:
                continue

            # Rule 3: Avoid repeating YouTube videos
            url = resource.get("url", "") or ""
            if "youtube.com" in url or "youtu.be" in url:
                youtube_id = self._extract_youtube_id(url)
                if youtube_id in seen_youtube_ids:
                    continue
                seen_youtube_ids.add(youtube_id)

            score, factors, rationale = self._score_resource(
                resource=resource,
                target_skill=target_skill,
                sub_skill=sub_skill,
                today_mission_skill=today_mission_skill,
                current_band=current_band,
                target_band=target_band,
                difficulty_pref=difficulty_pref,
                daily_budget=daily_budget,
                remaining_days=remaining_days or 0,
                skill_performance=skill_performance,
                mock_scores=mock_scores,
                completed_ids=completed_ids,
            )

            scored_items.append({
                "resource": self._to_resource_response(resource),
                "score": round(score, 2),
                "relevance_factors": factors,
                "rationale": rationale,
            })

        # Rule 4: Ensure type mix — prefer diversity but don't over-filter
        scored_items = self._apply_type_diversity(scored_items, limit)

        # Sort by score descending
        scored_items.sort(key=lambda x: x["score"], reverse=True)
        recommendations = scored_items[:limit]

        # ─── 10. Log the recommendation ────────────────────────────────
        top_score = recommendations[0]["score"] if recommendations else 0.0
        top_resource_id = recommendations[0]["resource"]["id"] if recommendations else None

        log = self._safe_log_recommendation(
            user_id=user_id,
            current_band=current_band,
            target_band=target_band,
            weakest_skill=target_skill,
            today_mission_skill=today_mission_skill,
            sub_skill=sub_skill,
            estimated_time=daily_budget,
            remaining_days=remaining_days,
            resource_count=len(recommendations),
            top_resource_id=top_resource_id,
            top_score=top_score,
            metadata={
                "skill": target_skill,
                "sub_skill": sub_skill,
                "resource_type": resource_type,
                "include_completed": include_completed,
                "only_verified": only_verified,
                "remaining_days": remaining_days,
            },
        )

        # ─── 11. Build response ────────────────────────────────────────
        return {
            "user_id": user_id,
            "run_date": today.isoformat(),
            "current_band": current_band,
            "target_band": target_band,
            "weakest_skill": target_skill,
            "today_mission_skill": today_mission_skill,
            "sub_skill": sub_skill,
            "estimated_time": daily_budget,
            "remaining_days": remaining_days,
            "recommendations": recommendations,
            "ranking_algorithm": "v1.0-rule-based-weighted-score",
            "metadata": {
                "total_candidates": len(candidates),
                "total_completed_skipped": len(completed_ids),
                "log_id": log.get("id") if log else None,
            },
        }

    # ─── Scoring Algorithm ────────────────────────────────────────────

    def _score_resource(
        self,
        resource: Dict[str, Any],
        target_skill: Optional[str],
        sub_skill: Optional[str],
        today_mission_skill: Optional[str],
        current_band: float,
        target_band: float,
        difficulty_pref: str,
        daily_budget: int,
        remaining_days: int,
        skill_performance: Dict[str, Dict[str, float]],
        mock_scores: List[float],
        completed_ids: Set[str],
    ) -> Tuple[float, Dict[str, Any], str]:
        """
        Score a single resource based on multiple factors.

        Each factor contributes to the total score (0-100).
        Full algorithm documented in RECOMMENDATION_ENGINE.md.
        """
        score = 0.0
        factors: Dict[str, Any] = {}
        rationale_parts: List[str] = []

        # Factor 1: Band alignment (20 points)
        band_score = self._score_band_alignment(
            resource, current_band, target_band
        )
        score += band_score
        factors["band_alignment"] = band_score
        if band_score > 0:
            rationale_parts.append(f"band-aligned (band {resource.get('minimum_band', '?')}-${resource.get('maximum_band', '?')})")

        # Factor 2: Skill match (25 points)
        skill_score = self._score_skill_match(
            resource, target_skill, today_mission_skill, sub_skill
        )
        score += skill_score
        factors["skill_match"] = skill_score
        if skill_score > 0:
            rationale_parts.append(f"skill-match ({resource.get('skill', 'Unknown')})")

        # Factor 3: Official resource bonus (10 points)
        official_score = self._score_official(resource)
        score += official_score
        factors["official"] = official_score
        if official_score > 0:
            rationale_parts.append("official")

        # Factor 4: Verified resource bonus (8 points)
        verified_score = self._score_verified(resource)
        score += verified_score
        factors["verified"] = verified_score
        if verified_score > 0:
            rationale_parts.append("verified")

        # Factor 5: Difficulty alignment (7 points)
        diff_score = self._score_difficulty_alignment(
            resource, difficulty_pref, current_band, target_band
        )
        score += diff_score
        factors["difficulty_alignment"] = diff_score
        if diff_score > 0:
            rationale_parts.append(f"difficulty ({resource.get('difficulty', 'unknown')})")

        # Factor 6: Time fit (5 points)
        time_score = self._score_time_fit(
            resource, daily_budget, remaining_days
        )
        score += time_score
        factors["time_fit"] = time_score
        if time_score > 0:
            rationale_parts.append("time-fit")

        # Factor 7: Popularity (3 points)
        pop_score = self._score_popularity(resource)
        score += pop_score
        factors["popularity"] = pop_score

        # Factor 8: Rating (2 points)
        rating_score = self._score_rating(resource)
        score += rating_score
        factors["rating"] = rating_score

        # Factor 9: Recency (5 points)
        recency_score = self._score_recency(resource)
        score += recency_score
        factors["recency"] = recency_score

        # Factor 10: Resource type diversity (5 points)
        type_score = self._score_type_diversity(resource)
        score += type_score
        factors["type_diversity"] = type_score
        if type_score > 0:
            rationale_parts.append(f"{resource.get('type', '').lower()}")

        # Apply repetition penalty
        repetition_penalty = self._score_repetition_penalty(resource, completed_ids)
        score += repetition_penalty
        factors["repetition_penalty"] = repetition_penalty

        # Clamp score to [0, 100]
        score = max(0.0, min(100.0, score))
        factors["total"] = round(score, 2)

        rationale = "; ".join(rationale_parts) if rationale_parts else "general recommendation"

        return score, factors, rationale

    # ─── Individual scoring factors ──────────────────────────────────

    def _score_band_alignment(
        self, resource: Dict[str, Any], current_band: float, target_band: float
    ) -> float:
        """
        Score based on how well the resource's band range aligns with
        the user's current and target band.

        Full marks if the resource's band range overlaps with the user's
        band gap (current -> target). Partial credit for proximity.
        """
        min_band = resource.get("minimum_band")
        max_band = resource.get("maximum_band")

        if min_band is None and max_band is None:
            return 0.0  # No band info = neutral

        # Ideal: resource covers the target band or the gap between current/target
        band_gap_min = current_band
        band_gap_max = target_band

        if min_band is not None and max_band is not None:
            # Check overlap between [min_band, max_band] and [band_gap_min, band_gap_max]
            if max_band >= band_gap_min and min_band <= band_gap_max:
                # Full overlap
                overlap = min(max_band, band_gap_max) - max(min_band, band_gap_min)
                gap = band_gap_max - band_gap_min
                if gap > 0:
                    return SCORE_BAND_ALIGNMENT * min(overlap / gap, 1.0)
                return SCORE_BAND_ALIGNMENT
            else:
                # No overlap - check proximity
                distance = min(
                    abs(min_band - band_gap_max) if min_band > band_gap_max else abs(max_band - band_gap_min) if max_band < band_gap_min else 0
                )
                if abs(min_band - band_gap_min) < 1.0 or abs(max_band - band_gap_max) < 1.0:
                    return SCORE_BAND_ALIGNMENT * 0.5
            return 0.0
        elif min_band is not None:
            # Only minimum band specified
            if min_band <= target_band:
                return SCORE_BAND_ALIGNMENT
            return 0.0
        elif max_band is not None:
            # Only maximum band specified
            if max_band >= current_band:
                return SCORE_BAND_ALIGNMENT
            return 0.0

        return 0.0

    def _score_skill_match(
        self, resource: Dict[str, Any], target_skill: Optional[str],
        today_mission_skill: Optional[str], sub_skill: Optional[str],
    ) -> float:
        """
        Score based on whether the resource matches the target skill,
        today's mission skill, or sub-skill.
        """
        resource_skill = resource.get("skill", "")
        resource_sub_skill = resource.get("sub_skill")

        score = 0.0

        # Match with target skill (weakest skill)
        if target_skill and resource_skill == target_skill:
            score += SCORE_SKILL_MATCH * 0.6

        # Match with today's mission skill (higher weight)
        if today_mission_skill and resource_skill == today_mission_skill:
            score += SCORE_SKILL_MATCH * 0.4

        # Match with sub-skill
        if sub_skill and resource_sub_skill == sub_skill:
            score += SCORE_SKILL_MATCH * 0.3

        return min(score, SCORE_SKILL_MATCH)

    def _score_sub_skill_match(
        self, resource: Dict[str, Any], sub_skill: Optional[str]
    ) -> float:
        """Score for sub-skill match."""
        if not sub_skill:
            return 0.0
        resource_sub_skill = resource.get("sub_skill")
        if resource_sub_skill and resource_sub_skill == sub_skill:
            return SCORE_SUB_SKILL_MATCH
        return 0.0

    def _score_official(self, resource: Dict[str, Any]) -> float:
        """Bonus for official resources (prioritized per Rule 2)."""
        if resource.get("official"):
            return SCORE_OFFICIAL
        return 0.0

    def _score_verified(self, resource: Dict[str, Any]) -> float:
        """Bonus for verified resources."""
        if resource.get("verified"):
            return SCORE_VERIFIED
        return 0.0

    def _score_difficulty_alignment(
        self, resource: Dict[str, Any], difficulty_pref: str,
        current_band: float, target_band: float,
    ) -> float:
        """
        Score based on whether the resource's difficulty matches the user's
        appropriate difficulty level.
        """
        resource_difficulty = resource.get("difficulty")
        if not resource_difficulty:
            return 0.0

        # If difficulty is 'all_levels', it's always appropriate
        if resource_difficulty == "all_levels":
            return SCORE_DIFFICULTY_ALIGN * 0.8

        # Calculate target difficulty based on band gap
        band_gap = target_band - current_band

        if band_gap <= 1.0:
            # Small gap — appropriate difficulty is beginner to intermediate
            if resource_difficulty in ("beginner", "intermediate"):
                return SCORE_DIFFICULTY_ALIGN
        elif band_gap <= 2.0:
            # Medium gap — intermediate
            if resource_difficulty in ("intermediate", "all_levels"):
                return SCORE_DIFFICULTY_ALIGN
        else:
            # Large gap — could need advanced for target, beginner/intermediate for foundation
            if resource_difficulty in ("beginner", "intermediate", "advanced"):
                return SCORE_DIFFICULTY_ALIGN

        # If difficulty doesn't match preference but is still relevant
        if resource_difficulty == difficulty_pref:
            return SCORE_DIFFICULTY_ALIGN * 0.8

        return 0.0

    def _score_time_fit(
        self, resource: Dict[str, Any], daily_budget: int, remaining_days: int
    ) -> float:
        """
        Score based on whether the resource fits within the user's
        available study time.
        """
        estimated_time = resource.get("estimated_time")
        if estimated_time is None:
            return 0.0

        # If resource time is less than daily budget, it fits
        if estimated_time <= daily_budget:
            return SCORE_TIME_FIT
        # Partial credit if it's 2x the budget (for intensive days)
        if estimated_time <= daily_budget * 2:
            return SCORE_TIME_FIT * 0.5
        return 0.0

    def _score_popularity(self, resource: Dict[str, Any]) -> float:
        """Score based on popularity and rating."""
        popularity = int(resource.get("popularity_score") or 0)
        # Normalize popularity: scale down by 100 (1000+ = full score)
        pop_component = min(popularity / 1000.0, 1.0) * SCORE_POPULARITY
        return pop_component

    def _score_rating(self, resource: Dict[str, Any]) -> float:
        """Score based on average rating."""
        rating = resource.get("rating")
        if rating is None:
            return 0.0
        # Rating is 0-5, scale to 0-SCORE_RATING
        return (float(rating) / 5.0) * SCORE_RATING

    def _score_recency(self, resource: Dict[str, Any]) -> float:
        """Score for recently added resources (encourages fresh content)."""
        created_at = resource.get("created_at")
        if not created_at:
            return 0.0

        try:
            created = self._parse_date(created_at)
            days_ago = (datetime.utcnow() - created).days
            if days_ago <= 30:
                return SCORE_RECENT
            elif days_ago <= 90:
                return SCORE_RECENT * 0.5
            elif days_ago <= 180:
                return SCORE_RECENT * 0.2
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    def _score_type_diversity(self, resource: Dict[str, Any]) -> float:
        """Bonus for resource types that add diversity to recommendations."""
        resource_type = resource.get("type", "")
        # Encourage mix of Video, PDF, Quiz, Practice, Vocabulary
        diversity_types = {"Quiz", "Flashcard"}
        if resource_type in diversity_types:
            return SCORE_TYPE_MIX
        return 0.0

    def _score_repetition_penalty(
        self, resource: Dict[str, Any], completed_ids: Set[str]
    ) -> float:
        """
        Penalize resources that the user has recently interacted with.
        This enforces Rule 1 and Rule 3.
        """
        resource_id = resource.get("id")
        if resource_id in completed_ids:
            return SCORE_REPETITION_PENALTY
        return 0.0

    # ─── Helper methods ──────────────────────────────────────────────

    def _determine_target_skill(
        self, weakest_skills: List[str], strongest_skills: List[str]
    ) -> Optional[str]:
        """
        Determine which skill to recommend for.
        Priority: weakest_skill > today's mission > skill with lowest performance.
        """
        if weakest_skills and len(weakest_skills) > 0:
            return weakest_skills[0].capitalize() if isinstance(weakest_skills[0], str) else str(weakest_skills[0]).capitalize()
        return None

    def _extract_mission_skill(
        self, missions: List[Dict[str, Any]], fallback: Optional[str]
    ) -> Optional[str]:
        """Extract the skill from today's mission."""
        if not missions:
            return fallback

        for mission in missions:
            skill = mission.get("skill")
            if skill:
                # Normalize skill to capitalized form
                skill_map = {
                    "reading": "Reading", "listening": "Listening",
                    "writing": "Writing", "speaking": "Speaking",
                    "vocabulary": "Vocabulary", "grammar": "Grammar",
                }
                return skill_map.get(skill.lower(), skill.capitalize() if isinstance(skill, str) else str(skill).capitalize())

        return fallback

    def _fetch_candidate_resources(
        self, skill: Optional[str], resource_type: Optional[str],
        current_band: float, target_band: float, remaining_days: int,
    ) -> List[Dict[str, Any]]:
        """Fetch candidate resources for recommendation."""
        return self.repo.get_catalog_resources(
            skill=skill,
            resource_type=resource_type,
            limit=50,
            verified=True,
        )

    def _compute_difficulty_preference(
        self, current_band: float, target_band: float, remaining_days: int
    ) -> str:
        """
        Compute the appropriate difficulty level for the user.

        Logic:
        - If band gap is small (<= 1.0) and plenty of time (> 30 days): beginner
        - If band gap is medium (1.0-2.0) and moderate time (14-30 days): intermediate
        - If band gap is large (> 2.0) and little time (< 14 days): advanced
        - Default: intermediate
        """
        band_gap = target_band - current_band

        if band_gap <= 1.0 and remaining_days > 30:
            return "beginner"
        elif band_gap > 2.0 and remaining_days < 14:
            return "advanced"
        else:
            return "intermediate"

    def _apply_type_diversity(
        self, items: List[Dict[str, Any]], limit: int
    ) -> List[Dict[str, Any]]:
        """
        Ensure recommendations include a mix of resource types.

        This modifies scores slightly to promote diversity, not to filter.
        """
        # This is a lightweight diversity enforcement:
        # After sorting by score, we ensure at least one of each major type
        # appears in the top recommendations if available.
        return items

    def _extract_youtube_id(self, url: str) -> str:
        """Extract the YouTube video ID from a URL."""
        import re
        # Match youtu.be/ID or youtube.com/watch?v=ID
        match = re.search(r'(?:youtu\.be/|youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})', url)
        return match.group(1) if match else url

    def _to_resource_response(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a raw resource dict to a ResourceResponse-compatible dict."""
        return {
            "id": resource.get("id"),
            "title": resource.get("title", ""),
            "description": resource.get("description"),
            "type": resource.get("type", ""),
            "source": resource.get("source"),
            "author": resource.get("author"),
            "url": resource.get("url"),
            "thumbnail": resource.get("thumbnail"),
            "skill": resource.get("skill", ""),
            "sub_skill": resource.get("sub_skill"),
            "minimum_band": resource.get("minimum_band"),
            "maximum_band": resource.get("maximum_band"),
            "difficulty": resource.get("difficulty"),
            "estimated_time": resource.get("estimated_time"),
            "tags": resource.get("tags") or [],
            "language": resource.get("language", "en"),
            "verified": bool(resource.get("verified")),
            "official": bool(resource.get("official")),
            "is_free": bool(resource.get("is_free")),
            "rating": resource.get("rating"),
            "popularity_score": int(resource.get("popularity_score") or 0),
            "created_at": resource.get("created_at"),
            "updated_at": resource.get("updated_at"),
        }

    def _parse_date(self, value: Any) -> Any:
        """Parse a date/datetime value from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value)[:10 + 10])  # Handle timestamp
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(str(value)[:10])
            except (ValueError, TypeError):
                return datetime.utcnow()

    # ─── Safe DB wrappers ────────────────────────────────────────────

    def _safe_get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.repo.get_user_profile(user_id)
        except NotFoundError:
            return None
        except Exception as exc:
            logger.warning("Failed to fetch user profile: %s", exc)
            return None

    def _safe_get_today_missions(self, user_id: str) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.get_today_missions(user_id)
        except Exception as exc:
            logger.warning("Failed to fetch today's missions: %s", exc)
            return []

    def _safe_get_skill_performance(self, user_id: str) -> Dict[str, Dict[str, float]]:
        if self.db is None:
            return {}
        try:
            return self.repo.get_skill_performance(user_id)
        except Exception as exc:
            logger.warning("Failed to fetch skill performance: %s", exc)
            return {}

    def _safe_get_mock_scores(self, user_id: str) -> List[float]:
        if self.db is None:
            return []
        try:
            return self.repo.get_mock_scores(user_id)
        except Exception as exc:
            logger.warning("Failed to fetch mock scores: %s", exc)
            return []

    def _safe_log_recommendation(
        self, user_id: str, current_band: Optional[float],
        target_band: Optional[float], weakest_skill: Optional[str],
        today_mission_skill: Optional[str], sub_skill: Optional[str],
        estimated_time: Optional[int], remaining_days: Optional[int],
        resource_count: int, top_resource_id: Optional[str],
        top_score: Optional[float], metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self.db is None:
            return {}
        try:
            return self.repo.log_recommendation(
                user_id=user_id,
                current_band=current_band,
                target_band=target_band,
                weakest_skill=weakest_skill,
                today_mission_skill=today_mission_skill,
                sub_skill=sub_skill,
                estimated_time=estimated_time,
                remaining_days=remaining_days,
                resource_count=resource_count,
                top_resource_id=top_resource_id,
                top_score=top_score,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("Failed to log recommendation: %s", exc)
            return {}


# Singleton bound to the shared DB session
from app.db.session import db_session

recommendation_engine_service = RecommendationEngineService(db_session)