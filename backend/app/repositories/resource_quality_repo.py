"""
Repository for the Resource Quality Scoring domain.

Backs the resource_feedback (user feedback), resource_quality_scores
(per-resource computed scores), and resource_moderation_log (admin audit
trail) tables. Provides feedback submission, moderation, and quality score
computation.

Scoring formulas:
  - Quality Score (0-100): weighted avg of ratings, adjusted for broken links,
    corrections, verified status
  - Popularity Score (0-100): normalized views, bookmarks, likes
  - Completion Score (0-100): completion rate normalized
  - Recommendation Score (0-100): combined weighted mix of quality, popularity,
    completion, minus broken link penalty
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class ResourceQualityRepository(BaseRepository):
    """Data access for the resource quality scoring tables."""

    table_name = "resource_feedback"
    user_id_column = "user_id"
    _ownable = True

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Feedback submission
    # ------------------------------------------------------------------
    def submit_feedback(
        self,
        user_id: str,
        resource_id: str,
        feedback_type: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        suggested_url: Optional[str] = None,
        suggested_title: Optional[str] = None,
        field_name: Optional[str] = None,
        suggested_value: Optional[str] = None,
        reason: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Submit new resource feedback."""
        payload: Dict[str, Any] = {
            "user_id": user_id,
            "resource_id": resource_id,
            "feedback_type": feedback_type,
            "status": "pending",
        }

        # Only include fields relevant to the feedback type
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if suggested_url is not None:
            payload["suggested_url"] = suggested_url
        if suggested_title is not None:
            payload["suggested_title"] = suggested_title
        if field_name is not None:
            payload["field_name"] = field_name
        if suggested_value is not None:
            payload["suggested_value"] = suggested_value
        if reason is not None:
            payload["reason"] = reason
        if rating is not None:
            payload["rating"] = rating

        query = self.db.table("resource_feedback").insert(payload)
        result = self.db.execute(query, "submit resource feedback")
        if not result.data:
            raise NotFoundError("Failed to submit resource feedback")
        return result.data[0]

    def get_feedback(self, feedback_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a single feedback entry by ID. If user_id is provided, restrict to own."""
        query = (
            self.db.table("resource_feedback")
            .select("*")
            .eq("id", feedback_id)
            .limit(1)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        result = self.db.execute(query, "fetch resource feedback")
        return result.data[0] if result.data else None

    def list_user_feedback(
        self,
        user_id: str,
        resource_id: Optional[str] = None,
        feedback_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List feedback submitted by a user."""
        query = (
            self.db.table("resource_feedback")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if resource_id:
            query = query.eq("resource_id", resource_id)
        if feedback_type:
            query = query.eq("feedback_type", feedback_type)
        if status:
            query = query.eq("status", status)
        result = self.db.execute(query, "list user feedback")
        return result.data or []

    def list_resource_feedback(
        self,
        resource_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List all feedback for a resource (admin view)."""
        query = (
            self.db.table("resource_feedback")
            .select("*")
            .eq("resource_id", resource_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.eq("status", status)
        result = self.db.execute(query, "list resource feedback")
        return result.data or []

    def delete_feedback(self, feedback_id: str, user_id: str) -> bool:
        """Delete (withdraw) feedback. Only the owner can delete."""
        query = (
            self.db.table("resource_feedback")
            .delete()
            .eq("id", feedback_id)
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "delete resource feedback")
        return len(result.data or []) > 0

    # ------------------------------------------------------------------
    # Moderation
    # ------------------------------------------------------------------
    def moderate_feedback(
        self,
        feedback_id: str,
        admin_id: str,
        action: str,
        admin_notes: Optional[str] = None,
        new_priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform a moderation action on feedback. Returns the updated feedback."""
        # Fetch current feedback
        current = self.get_feedback(feedback_id)
        if not current:
            raise NotFoundError(f"Feedback {feedback_id} not found")

        old_status = current.get("status", "pending")

        # Map action to new status
        status_map = {
            "approved": "approved",
            "rejected": "rejected",
            "resolved": "resolved",
            "dismissed": "dismissed",
            "escalated": "pending",  # Escalated stays pending but flagged
            "commented": old_status,  # Comment doesn't change status
        }
        new_status = status_map.get(action, old_status)

        update_payload: Dict[str, Any] = {
            "status": new_status,
            "moderated_by": admin_id,
            "moderated_at": datetime.now(timezone.utc).isoformat(),
        }
        if admin_notes is not None:
            update_payload["admin_notes"] = admin_notes
        if new_priority is not None:
            update_payload["priority"] = new_priority
        if action == "resolved":
            update_payload["resolved_at"] = datetime.now(timezone.utc).isoformat()

        update = (
            self.db.table("resource_feedback")
            .update(update_payload)
            .eq("id", feedback_id)
        )
        result = self.db.execute(update, "moderate resource feedback")
        if not result.data:
            raise NotFoundError(f"Failed to update feedback {feedback_id}")

        # Log the moderation action
        log_payload = {
            "feedback_id": feedback_id,
            "admin_id": admin_id,
            "action": action,
            "old_status": old_status,
            "new_status": new_status,
            "notes": admin_notes,
        }
        log_query = self.db.table("resource_moderation_log").insert(log_payload)
        try:
            self.db.execute(log_query, "log moderation action")
        except Exception:
            pass  # Don't fail moderation if logging fails

        return result.data[0]

    def get_moderation_queue(
        self,
        status: Optional[str] = None,
        feedback_type: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get the moderation queue with summary stats."""
        query = (
            self.db.table("resource_feedback")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.eq("status", status)
        if feedback_type:
            query = query.eq("feedback_type", feedback_type)
        if priority:
            query = query.eq("priority", priority)
        result = self.db.execute(query, "fetch moderation queue")
        items = result.data or []

        # Get summary stats
        all_query = self.db.table("resource_feedback").select("status, priority, feedback_type")
        all_result = self.db.execute(all_query, "fetch feedback stats")
        all_items = all_result.data or []

        pending_count = sum(1 for i in all_items if i.get("status") == "pending")
        high_priority_count = sum(
            1 for i in all_items
            if i.get("status") == "pending" and i.get("priority") in ("high", "urgent")
        )
        broken_link_count = sum(
            1 for i in all_items
            if i.get("feedback_type") == "broken_link" and i.get("status") == "pending"
        )
        correction_count = sum(
            1 for i in all_items
            if i.get("feedback_type") == "correction" and i.get("status") == "pending"
        )
        suggestion_count = sum(
            1 for i in all_items
            if i.get("feedback_type") == "better_resource" and i.get("status") == "pending"
        )

        return {
            "items": items,
            "total": len(all_items),
            "pending_count": pending_count,
            "high_priority_count": high_priority_count,
            "broken_link_count": broken_link_count,
            "correction_count": correction_count,
            "suggestion_count": suggestion_count,
        }

    def get_moderation_log(self, feedback_id: str) -> List[Dict[str, Any]]:
        """Get the moderation log for a feedback entry."""
        query = (
            self.db.table("resource_moderation_log")
            .select("*")
            .eq("feedback_id", feedback_id)
            .order("created_at", desc=True)
        )
        result = self.db.execute(query, "fetch moderation log")
        return result.data or []

    # ------------------------------------------------------------------
    # Quality score computation
    # ------------------------------------------------------------------
    def compute_quality_scores(self, resource_id: str) -> Dict[str, Any]:
        """
        Compute all quality scores for a resource.

        Quality Score (0-100):
          - Base: avg_rating * 20 (convert 0-5 to 0-100)
          - Verified bonus: +5
          - Official bonus: +5
          - Broken link penalty: -10 per pending/approved broken link (max -30)
          - Low rating penalty: -5 if avg_rating < 2.5

        Popularity Score (0-100):
          - Normalized: (views * 1 + bookmarks * 3 + likes * 2) / max_possible * 100
          - Capped at 100

        Completion Score (0-100):
          - (completions / views) * 100 if views > 0, else 0

        Recommendation Score (0-100):
          - Weighted: quality * 0.4 + popularity * 0.25 + completion * 0.25 + rating_factor * 0.1
          - Broken link penalty: -15 if any pending broken links
        """
        # 1. Fetch resource details
        resource_query = (
            self.db.table("resources")
            .select("id, title, type, skill, verified, official, rating")
            .eq("id", resource_id)
            .limit(1)
        )
        resource_result = self.db.execute(resource_query, "fetch resource for scoring")
        resource = resource_result.data[0] if resource_result.data else None
        if not resource:
            raise NotFoundError(f"Resource {resource_id} not found")

        # 2. Fetch resource analytics
        analytics_query = (
            self.db.table("resource_analytics")
            .select("*")
            .eq("resource_id", resource_id)
            .limit(1)
        )
        analytics_result = self.db.execute(analytics_query, "fetch resource analytics for scoring")
        analytics = analytics_result.data[0] if analytics_result.data else {}

        view_count = int(analytics.get("view_count") or 0)
        bookmark_count = int(analytics.get("bookmark_count") or 0)
        like_count = int(analytics.get("like_count") or 0)
        completion_count = int(analytics.get("completion_count") or 0)
        rating_sum = float(analytics.get("rating_sum") or 0)
        rating_count = int(analytics.get("rating_count") or 0)
        avg_rating = float(analytics.get("avg_rating") or 0)

        # 3. Fetch feedback counts
        feedback_query = (
            self.db.table("resource_feedback")
            .select("feedback_type, status")
            .eq("resource_id", resource_id)
        )
        feedback_result = self.db.execute(feedback_query, "fetch feedback for scoring")
        feedback_items = feedback_result.data or []

        broken_link_count = sum(
            1 for f in feedback_items
            if f.get("feedback_type") == "broken_link"
            and f.get("status") in ("pending", "approved")
        )
        correction_count = sum(
            1 for f in feedback_items
            if f.get("feedback_type") == "correction"
            and f.get("status") in ("pending", "approved")
        )
        suggestion_count = sum(
            1 for f in feedback_items
            if f.get("feedback_type") == "better_resource"
            and f.get("status") in ("pending", "approved")
        )

        # 4. Compute Quality Score
        quality_score = avg_rating * 20  # 0-5 → 0-100

        if resource.get("verified"):
            quality_score += 5
        if resource.get("official"):
            quality_score += 5

        # Broken link penalty (max -30)
        broken_link_penalty = min(broken_link_count * 10, 30)
        quality_score -= broken_link_penalty

        # Low rating penalty
        if avg_rating > 0 and avg_rating < 2.5:
            quality_score -= 5

        quality_score = max(0, min(100, quality_score))

        # 5. Compute Popularity Score
        # Weight: views=1, bookmarks=3, likes=2
        # Normalize against a soft cap (e.g., 100 views = max)
        popularity_raw = (view_count * 1) + (bookmark_count * 3) + (like_count * 2)
        popularity_cap = 200  # Soft cap for normalization
        popularity_score = min((popularity_raw / popularity_cap) * 100, 100) if popularity_cap > 0 else 0
        popularity_score = round(popularity_score, 2)

        # 6. Compute Completion Score
        if view_count > 0:
            completion_score = (completion_count / view_count) * 100
        else:
            completion_score = 0.0
        completion_score = round(min(completion_score, 100), 2)

        # 7. Compute Recommendation Score
        # Weighted: quality 40%, popularity 25%, completion 25%, rating 10%
        rating_factor = (avg_rating / 5) * 100 if avg_rating > 0 else 0
        recommendation_score = (
            (quality_score * 0.40)
            + (popularity_score * 0.25)
            + (completion_score * 0.25)
            + (rating_factor * 0.10)
        )

        # Broken link penalty for recommendation
        if broken_link_count > 0:
            recommendation_score -= 15

        recommendation_score = max(0, min(100, round(recommendation_score, 2)))

        # 8. Upsert scores
        scores_payload = {
            "resource_id": resource_id,
            "quality_score": quality_score,
            "popularity_score": popularity_score,
            "completion_score": completion_score,
            "recommendation_score": recommendation_score,
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "view_count": view_count,
            "bookmark_count": bookmark_count,
            "like_count": like_count,
            "completion_count": completion_count,
            "broken_link_count": broken_link_count,
            "correction_count": correction_count,
            "suggestion_count": suggestion_count,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

        upsert = (
            self.db.table("resource_quality_scores")
            .upsert(scores_payload, on_conflict="resource_id")
        )
        try:
            self.db.execute(upsert, "upsert quality scores")
        except Exception:
            pass  # Table may not exist yet

        # 9. Return with breakdown
        return {
            **scores_payload,
            "components": {
                "avg_rating": avg_rating,
                "verified": resource.get("verified", False),
                "official": resource.get("official", False),
                "broken_link_penalty": broken_link_penalty,
                "low_rating_penalty": 5 if (avg_rating > 0 and avg_rating < 2.5) else 0,
            },
            "weights": {
                "quality": 0.40,
                "popularity": 0.25,
                "completion": 0.25,
                "rating": 0.10,
            },
        }

    def get_quality_scores(self, resource_id: str) -> Dict[str, Any]:
        """Get stored quality scores for a resource (computes if missing)."""
        query = (
            self.db.table("resource_quality_scores")
            .select("*")
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch quality scores")
        if not result.data:
            # Compute on demand
            return self.compute_quality_scores(resource_id)
        return result.data[0]

    def get_score_breakdown(self, resource_id: str) -> Dict[str, Any]:
        """Get a detailed score breakdown for transparency."""
        return self.compute_quality_scores(resource_id)

    def get_leaderboard(
        self,
        sort_by: str = "recommendation_score",
        limit: int = 20,
        skill: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get the quality leaderboard (top resources by score)."""
        valid_sorts = ("recommendation_score", "quality_score", "popularity_score", "completion_score")
        if sort_by not in valid_sorts:
            sort_by = "recommendation_score"

        query = (
            self.db.table("resource_quality_scores")
            .select(f"*, resources(id, title, type, skill)")
            .order(sort_by, desc=True)
            .limit(limit)
        )
        try:
            result = self.db.execute(query, "fetch quality leaderboard")
        except Exception:
            return []

        items = []
        for row in result.data or []:
            resource = row.get("resources") or {}
            if not resource:
                continue
            if skill and resource.get("skill") != skill:
                continue
            items.append({
                "resource_id": row.get("resource_id", ""),
                "title": resource.get("title", ""),
                "type": resource.get("type", ""),
                "skill": resource.get("skill", ""),
                "quality_score": float(row.get("quality_score") or 0),
                "popularity_score": float(row.get("popularity_score") or 0),
                "completion_score": float(row.get("completion_score") or 0),
                "recommendation_score": float(row.get("recommendation_score") or 0),
                "avg_rating": float(row.get("avg_rating") or 0),
                "rating_count": int(row.get("rating_count") or 0),
                "view_count": int(row.get("view_count") or 0),
                "like_count": int(row.get("like_count") or 0),
                "completion_count": int(row.get("completion_count") or 0),
            })
        return items

    def recompute_all_scores(self, limit: int = 100) -> Dict[str, Any]:
        """Recompute quality scores for all resources with analytics. Batch operation."""
        query = (
            self.db.table("resource_analytics")
            .select("resource_id")
            .limit(limit)
        )
        result = self.db.execute(query, "fetch resources for recompute")
        resource_ids = [r.get("resource_id") for r in (result.data or []) if r.get("resource_id")]

        computed = 0
        errors = 0
        for rid in resource_ids:
            try:
                self.compute_quality_scores(rid)
                computed += 1
            except Exception:
                errors += 1

        return {
            "total": len(resource_ids),
            "computed": computed,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def get_quality_stats(self) -> Dict[str, Any]:
        """Get system-wide quality statistics."""
        # Feedback stats
        feedback_query = self.db.table("resource_feedback").select("status, feedback_type")
        feedback_result = self.db.execute(feedback_query, "fetch feedback stats")
        feedback_items = feedback_result.data or []

        total_feedback = len(feedback_items)
        pending = sum(1 for f in feedback_items if f.get("status") == "pending")
        approved = sum(1 for f in feedback_items if f.get("status") == "approved")
        rejected = sum(1 for f in feedback_items if f.get("status") == "rejected")
        resolved = sum(1 for f in feedback_items if f.get("status") == "resolved")
        dismissed = sum(1 for f in feedback_items if f.get("status") == "dismissed")

        broken_links = sum(1 for f in feedback_items if f.get("feedback_type") == "broken_link")
        corrections = sum(1 for f in feedback_items if f.get("feedback_type") == "correction")
        suggestions = sum(1 for f in feedback_items if f.get("feedback_type") == "better_resource")
        ratings = sum(1 for f in feedback_items if f.get("feedback_type") == "rating")

        # Score stats
        scores_query = self.db.table("resource_quality_scores").select(
            "quality_score, popularity_score, completion_score, recommendation_score"
        )
        scores_result = self.db.execute(scores_query, "fetch score stats")
        scores = scores_result.data or []

        total_scored = len(scores)
        avg_quality = sum(float(s.get("quality_score") or 0) for s in scores) / total_scored if total_scored > 0 else 0
        avg_popularity = sum(float(s.get("popularity_score") or 0) for s in scores) / total_scored if total_scored > 0 else 0
        avg_completion = sum(float(s.get("completion_score") or 0) for s in scores) / total_scored if total_scored > 0 else 0
        avg_recommendation = sum(float(s.get("recommendation_score") or 0) for s in scores) / total_scored if total_scored > 0 else 0

        return {
            "total_feedback": total_feedback,
            "pending_feedback": pending,
            "approved_feedback": approved,
            "rejected_feedback": rejected,
            "resolved_feedback": resolved,
            "dismissed_feedback": dismissed,
            "broken_link_reports": broken_links,
            "correction_suggestions": corrections,
            "better_resource_suggestions": suggestions,
            "rating_feedback": ratings,
            "total_resources_scored": total_scored,
            "avg_quality_score": round(avg_quality, 2),
            "avg_popularity_score": round(avg_popularity, 2),
            "avg_completion_score": round(avg_completion, 2),
            "avg_recommendation_score": round(avg_recommendation, 2),
        }