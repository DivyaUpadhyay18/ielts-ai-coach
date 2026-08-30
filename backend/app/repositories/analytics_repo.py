"""
Repository for the Analytics domain.

Backs the analytics_events (append-only event ledger), resource_analytics
(per-resource aggregate counters), user_analytics (per-user aggregate
counters), resource_likes, resource_ratings, and user_resource_completions
tables. Provides event ingestion, resource interaction tracking, and
dashboard aggregation (views, completions, bookmarks, likes, ratings,
study time, completion %, success rate, drop-off rate).
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundError
from app.db.session import DatabaseSession
from app.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository):
    """Data access for the analytics tables."""

    table_name = "analytics_events"
    user_id_column = "user_id"
    _ownable = False

    def __init__(self, db: DatabaseSession) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------
    def track_event(
        self,
        user_id: str,
        event: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Append a single analytics event to the ledger."""
        payload = {
            "user_id": user_id,
            "event": event,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "properties": properties or {},
            "session_id": session_id,
        }
        if timestamp:
            payload["timestamp"] = timestamp.isoformat()

        query = self.db.table("analytics_events").insert(payload)
        result = self.db.execute(query, "track analytics event")
        if not result.data:
            raise NotFoundError("Failed to track analytics event")
        return result.data[0]

    def track_events_batch(
        self,
        user_id: str,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Append multiple analytics events in a single batch."""
        payloads = []
        for ev in events:
            payload = {
                "user_id": user_id,
                "event": ev.get("event", ""),
                "entity_type": ev.get("entity_type"),
                "entity_id": ev.get("entity_id"),
                "properties": ev.get("properties") or {},
                "session_id": ev.get("session_id"),
            }
            ts = ev.get("timestamp")
            if ts:
                payload["timestamp"] = ts.isoformat() if isinstance(ts, datetime) else str(ts)
            payloads.append(payload)

        if not payloads:
            return []

        query = self.db.table("analytics_events").insert(payloads)
        result = self.db.execute(query, "track analytics events batch")
        return result.data or []

    # ------------------------------------------------------------------
    # Resource interaction tracking
    # ------------------------------------------------------------------
    def record_view(self, user_id: str, resource_id: str) -> Dict[str, Any]:
        """Record a resource view (event + aggregate counters)."""
        event = self.track_event(
            user_id=user_id,
            event="resource_viewed",
            entity_type="resource",
            entity_id=resource_id,
            properties={"source": "catalog"},
        )
        self._increment_resource_counter(resource_id, "view_count", 1)
        self._increment_user_counter(user_id, "total_views", 1)
        self._touch_user_activity(user_id)
        return event

    def record_completion(self, user_id: str, resource_id: str) -> Dict[str, Any]:
        """Record a resource completion (event + aggregate counters)."""
        # Idempotent: only count once per (user, resource).
        existing = (
            self.db.table("user_resource_completions")
            .select("id")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        existing_result = self.db.execute(existing, "check existing completion")
        if existing_result.data:
            return existing_result.data[0]

        insert = (
            self.db.table("user_resource_completions")
            .insert({"user_id": user_id, "resource_id": resource_id})
        )
        insert_result = self.db.execute(insert, "record resource completion")
        if not insert_result.data:
            raise NotFoundError("Failed to record resource completion")

        event = self.track_event(
            user_id=user_id,
            event="resource_completed",
            entity_type="resource",
            entity_id=resource_id,
            properties={"completion_source": "manual"},
        )
        self._increment_resource_counter(resource_id, "completion_count", 1)
        self._increment_user_counter(user_id, "total_completions", 1)
        self._touch_user_activity(user_id)
        return insert_result.data[0]

    def record_bookmark(self, user_id: str, resource_id: str) -> Dict[str, Any]:
        """Record a resource bookmark (event + aggregate counters)."""
        event = self.track_event(
            user_id=user_id,
            event="resource_bookmarked",
            entity_type="resource",
            entity_id=resource_id,
            properties={"source": "catalog"},
        )
        self._increment_resource_counter(resource_id, "bookmark_count", 1)
        self._increment_user_counter(user_id, "total_bookmarks", 1)
        self._touch_user_activity(user_id)
        return event

    def remove_bookmark(self, user_id: str, resource_id: str) -> None:
        """Remove a resource bookmark (event + decrement counters)."""
        self.track_event(
            user_id=user_id,
            event="resource_unbookmarked",
            entity_type="resource",
            entity_id=resource_id,
            properties={"source": "catalog"},
        )
        self._increment_resource_counter(resource_id, "bookmark_count", -1)
        self._increment_user_counter(user_id, "total_bookmarks", -1)

    def toggle_like(self, user_id: str, resource_id: str) -> Dict[str, Any]:
        """Toggle a like on a resource. Returns the like row or None if unliked."""
        existing = (
            self.db.table("resource_likes")
            .select("id")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        existing_result = self.db.execute(existing, "check existing like")
        if existing_result.data:
            # Unlike
            delete = (
                self.db.table("resource_likes")
                .delete()
                .eq("user_id", user_id)
                .eq("resource_id", resource_id)
            )
            self.db.execute(delete, "remove resource like")
            self.track_event(
                user_id=user_id,
                event="resource_unliked",
                entity_type="resource",
                entity_id=resource_id,
            )
            self._increment_resource_counter(resource_id, "like_count", -1)
            self._increment_user_counter(user_id, "total_likes", -1)
            return {"liked": False, "resource_id": resource_id}

        # Like
        insert = (
            self.db.table("resource_likes")
            .insert({"user_id": user_id, "resource_id": resource_id})
        )
        insert_result = self.db.execute(insert, "record resource like")
        if not insert_result.data:
            raise NotFoundError("Failed to record resource like")

        self.track_event(
            user_id=user_id,
            event="resource_liked",
            entity_type="resource",
            entity_id=resource_id,
        )
        self._increment_resource_counter(resource_id, "like_count", 1)
        self._increment_user_counter(user_id, "total_likes", 1)
        self._touch_user_activity(user_id)
        return {"liked": True, "resource_id": resource_id, **insert_result.data[0]}

    def rate_resource(self, user_id: str, resource_id: str, rating: int) -> Dict[str, Any]:
        """Rate a resource (1-5). Upserts on (user_id, resource_id)."""
        # Validate rating range
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        # Check existing rating
        existing = (
            self.db.table("resource_ratings")
            .select("*")
            .eq("user_id", user_id)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        existing_result = self.db.execute(existing, "check existing rating")

        if existing_result.data:
            old_rating = int(existing_result.data[0].get("rating") or 0)
            # Update rating
            update = (
                self.db.table("resource_ratings")
                .update({"rating": rating, "updated_at": datetime.now(timezone.utc).isoformat()})
                .eq("user_id", user_id)
                .eq("resource_id", resource_id)
            )
            update_result = self.db.execute(update, "update resource rating")
            row = update_result.data[0] if update_result.data else existing_result.data[0]
            # Adjust aggregate: subtract old, add new
            self._adjust_rating_aggregate(resource_id, old_rating, rating)
        else:
            insert = (
                self.db.table("resource_ratings")
                .insert({"user_id": user_id, "resource_id": resource_id, "rating": rating})
            )
            insert_result = self.db.execute(insert, "record resource rating")
            if not insert_result.data:
                raise NotFoundError("Failed to record resource rating")
            row = insert_result.data[0]
            self._increment_resource_counter(resource_id, "rating_sum", rating)
            self._increment_resource_counter(resource_id, "rating_count", 1)
            self._increment_user_counter(user_id, "total_ratings", 1)
            self._recompute_avg_rating(resource_id)

        self.track_event(
            user_id=user_id,
            event="resource_rated",
            entity_type="resource",
            entity_id=resource_id,
            properties={"rating": rating},
        )
        self._touch_user_activity(user_id)
        return row

    def record_study_session(
        self,
        user_id: str,
        minutes: int,
        skill: Optional[str] = None,
        source_type: str = "task",
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a study session (event + aggregate counters)."""
        event = self.track_event(
            user_id=user_id,
            event="study_session_logged",
            entity_type="task" if source_type == "task" else "mission",
            entity_id=source_id,
            properties={
                "minutes": minutes,
                "skill": skill,
                "source_type": source_type,
            },
        )
        self._increment_user_counter(user_id, "total_study_minutes", minutes)
        self._increment_user_counter(user_id, "total_sessions", 1)
        if source_type in ("task", "mission"):
            self._increment_user_counter(user_id, "total_tasks_completed", 1)
        self._touch_user_activity(user_id)
        return event

    # ------------------------------------------------------------------
    # Internal counter helpers
    # ------------------------------------------------------------------
    def _increment_resource_counter(self, resource_id: str, column: str, delta: int) -> None:
        """Increment a counter on the resource_analytics row (upsert)."""
        # Fetch current row
        query = (
            self.db.table("resource_analytics")
            .select(column)
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch resource analytics counter")
        current = int(result.data[0].get(column) or 0) if result.data else 0
        new_value = max(current + delta, 0)

        upsert = (
            self.db.table("resource_analytics")
            .upsert(
                {
                    "resource_id": resource_id,
                    column: new_value,
                },
                on_conflict="resource_id",
            )
        )
        try:
            self.db.execute(upsert, "increment resource analytics counter")
        except Exception:
            # Table may not exist yet — silently ignore for resilience
            pass

    def _increment_user_counter(self, user_id: str, column: str, delta: int) -> None:
        """Increment a counter on the user_analytics row (upsert)."""
        query = (
            self.db.table("user_analytics")
            .select(column)
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch user analytics counter")
        current = int(result.data[0].get(column) or 0) if result.data else 0
        new_value = max(current + delta, 0)

        upsert = (
            self.db.table("user_analytics")
            .upsert(
                {
                    "user_id": user_id,
                    column: new_value,
                },
                on_conflict="user_id",
            )
        )
        try:
            self.db.execute(upsert, "increment user analytics counter")
        except Exception:
            pass

    def _adjust_rating_aggregate(self, resource_id: str, old_rating: int, new_rating: int) -> None:
        """Adjust rating_sum when a rating changes."""
        query = (
            self.db.table("resource_analytics")
            .select("rating_sum, rating_count")
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch rating aggregate")
        if result.data:
            current_sum = float(result.data[0].get("rating_sum") or 0)
            new_sum = max(current_sum - old_rating + new_rating, 0)
            update = (
                self.db.table("resource_analytics")
                .update({"rating_sum": new_sum})
                .eq("resource_id", resource_id)
            )
            try:
                self.db.execute(update, "adjust rating aggregate")
            except Exception:
                pass
        self._recompute_avg_rating(resource_id)

    def _recompute_avg_rating(self, resource_id: str) -> None:
        """Recompute avg_rating from rating_sum / rating_count."""
        query = (
            self.db.table("resource_analytics")
            .select("rating_sum, rating_count")
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch rating for avg")
        if result.data:
            rating_sum = float(result.data[0].get("rating_sum") or 0)
            rating_count = int(result.data[0].get("rating_count") or 0)
            avg = round(rating_sum / rating_count, 2) if rating_count > 0 else 0
            update = (
                self.db.table("resource_analytics")
                .update({"avg_rating": avg})
                .eq("resource_id", resource_id)
            )
            try:
                self.db.execute(update, "recompute avg rating")
            except Exception:
                pass

    def _touch_user_activity(self, user_id: str) -> None:
        """Update last_active_at on the user_analytics row."""
        upsert = (
            self.db.table("user_analytics")
            .upsert(
                {
                    "user_id": user_id,
                    "last_active_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id",
            )
        )
        try:
            self.db.execute(upsert, "touch user activity")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Reads (used by API + dashboard)
    # ------------------------------------------------------------------
    def get_resource_analytics(self, resource_id: str) -> Dict[str, Any]:
        """Fetch aggregate analytics for a single resource."""
        query = (
            self.db.table("resource_analytics")
            .select("*")
            .eq("resource_id", resource_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch resource analytics")
        if not result.data:
            return {
                "resource_id": resource_id,
                "view_count": 0,
                "bookmark_count": 0,
                "like_count": 0,
                "rating_sum": 0,
                "rating_count": 0,
                "completion_count": 0,
                "avg_rating": 0,
            }
        return result.data[0]

    def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """Fetch aggregate analytics for a single user."""
        query = (
            self.db.table("user_analytics")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
        )
        result = self.db.execute(query, "fetch user analytics")
        if not result.data:
            return {
                "user_id": user_id,
                "total_views": 0,
                "total_completions": 0,
                "total_bookmarks": 0,
                "total_likes": 0,
                "total_ratings": 0,
                "total_study_minutes": 0,
                "total_tasks_completed": 0,
                "total_sessions": 0,
                "last_active_at": None,
            }
        return result.data[0]

    def get_user_events(
        self,
        user_id: str,
        limit: int = 50,
        event: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent analytics events for a user."""
        query = (
            self.db.table("analytics_events")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
        )
        if event:
            query = query.eq("event", event)
        if entity_type:
            query = query.eq("entity_type", entity_type)
        result = self.db.execute(query, "fetch user analytics events")
        return result.data or []

    def get_user_events_range(
        self,
        user_id: str,
        start: date,
        end: date,
    ) -> List[Dict[str, Any]]:
        """Fetch analytics events within a date range for a user."""
        query = (
            self.db.table("analytics_events")
            .select("*")
            .eq("user_id", user_id)
            .gte("timestamp", f"{start.isoformat()}T00:00:00")
            .lte("timestamp", f"{end.isoformat()}T23:59:59")
            .order("timestamp")
        )
        result = self.db.execute(query, "fetch user analytics events range")
        return result.data or []

    def get_user_liked_ids(self, user_id: str) -> List[str]:
        """Get resource IDs the user has liked."""
        query = (
            self.db.table("resource_likes")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "fetch user liked resource IDs")
        return [r.get("resource_id") for r in (result.data or []) if r.get("resource_id")]

    def get_user_rated_ids(self, user_id: str) -> List[str]:
        """Get resource IDs the user has rated."""
        query = (
            self.db.table("resource_ratings")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "fetch user rated resource IDs")
        return [r.get("resource_id") for r in (result.data or []) if r.get("resource_id")]

    def get_user_completed_ids(self, user_id: str) -> List[str]:
        """Get resource IDs the user has completed."""
        query = (
            self.db.table("user_resource_completions")
            .select("resource_id")
            .eq("user_id", user_id)
        )
        result = self.db.execute(query, "fetch user completed resource IDs")
        return [r.get("resource_id") for r in (result.data or []) if r.get("resource_id")]

    # ------------------------------------------------------------------
    # Dashboard aggregation
    # ------------------------------------------------------------------
    def get_dashboard(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Build the full analytics dashboard payload for a user.

        Includes summary metrics (views, completions, bookmarks, likes,
        ratings, study time, completion %, success rate, drop-off rate),
        daily trends, skill breakdown, top resources, and recent events.
        """
        today = date.today()
        start = today - timedelta(days=days - 1)

        # 1. User aggregate counters
        user_stats = self.get_user_analytics(user_id)

        # 2. Events in range for trends
        events = self.get_user_events_range(user_id, start, today)

        # 3. Build daily trend series
        trend_map: Dict[str, Dict[str, int]] = {}
        for i in range(days):
            d = start + timedelta(days=i)
            trend_map[d.isoformat()] = {
                "date": d.isoformat(),
                "label": d.strftime("%d %b"),
                "views": 0,
                "completions": 0,
                "bookmarks": 0,
                "likes": 0,
                "ratings": 0,
                "study_minutes": 0,
            }

        for ev in events:
            ts = ev.get("timestamp")
            if not ts:
                continue
            try:
                day = str(ts)[:10]
            except (ValueError, TypeError):
                continue
            if day not in trend_map:
                continue
            event_name = ev.get("event", "")
            props = ev.get("properties") or {}
            if event_name == "resource_viewed":
                trend_map[day]["views"] += 1
            elif event_name == "resource_completed":
                trend_map[day]["completions"] += 1
            elif event_name == "resource_bookmarked":
                trend_map[day]["bookmarks"] += 1
            elif event_name == "resource_liked":
                trend_map[day]["likes"] += 1
            elif event_name == "resource_rated":
                trend_map[day]["ratings"] += 1
            elif event_name == "study_session_logged":
                trend_map[day]["study_minutes"] += int(props.get("minutes") or 0)

        trends = list(trend_map.values())

        # 4. Skill breakdown from study sessions + resource events
        skill_map: Dict[str, Dict[str, int]] = {}
        for ev in events:
            event_name = ev.get("event", "")
            props = ev.get("properties") or {}
            skill = props.get("skill") or "general"
            entry = skill_map.setdefault(skill, {
                "skill": skill,
                "views": 0,
                "completions": 0,
                "bookmarks": 0,
                "likes": 0,
                "ratings": 0,
                "study_minutes": 0,
            })
            if event_name == "resource_viewed":
                entry["views"] += 1
            elif event_name == "resource_completed":
                entry["completions"] += 1
            elif event_name == "resource_bookmarked":
                entry["bookmarks"] += 1
            elif event_name == "resource_liked":
                entry["likes"] += 1
            elif event_name == "resource_rated":
                entry["ratings"] += 1
            elif event_name == "study_session_logged":
                entry["study_minutes"] += int(props.get("minutes") or 0)

        skill_breakdown = list(skill_map.values())
        skill_breakdown.sort(key=lambda x: x["study_minutes"], reverse=True)

        # 5. Top resources from resource_analytics (join with resources table)
        top_resources = self._get_top_resources(user_id, limit=10)

        # 6. Recent events
        recent_events = self.get_user_events(user_id, limit=20)

        # 7. Summary metrics
        total_views = int(user_stats.get("total_views") or 0)
        total_completions = int(user_stats.get("total_completions") or 0)
        total_bookmarks = int(user_stats.get("total_bookmarks") or 0)
        total_likes = int(user_stats.get("total_likes") or 0)
        total_ratings = int(user_stats.get("total_ratings") or 0)
        total_study_minutes = int(user_stats.get("total_study_minutes") or 0)
        total_tasks_completed = int(user_stats.get("total_tasks_completed") or 0)
        total_sessions = int(user_stats.get("total_sessions") or 0)

        # Completion rate: completions / views (as %)
        completion_rate = round((total_completions / total_views) * 100, 1) if total_views > 0 else 0.0

        # Success rate: tasks completed / sessions (as %)
        success_rate = round((total_tasks_completed / total_sessions) * 100, 1) if total_sessions > 0 else 0.0

        # Drop-off rate: 100 - completion rate
        drop_off_rate = round(100.0 - completion_rate, 1) if total_views > 0 else 0.0

        # Active days: distinct days with events in range
        active_days = len({str(ev.get("timestamp"))[:10] for ev in events if ev.get("timestamp")})

        # Avg study time per session
        avg_study_time = round(total_study_minutes / total_sessions, 1) if total_sessions > 0 else 0.0

        summary = {
            "total_views": total_views,
            "total_completions": total_completions,
            "total_bookmarks": total_bookmarks,
            "total_likes": total_likes,
            "total_ratings": total_ratings,
            "total_study_minutes": total_study_minutes,
            "total_tasks_completed": total_tasks_completed,
            "total_sessions": total_sessions,
            "avg_study_time_per_session": avg_study_time,
            "completion_rate": completion_rate,
            "success_rate": success_rate,
            "drop_off_rate": drop_off_rate,
            "active_days": active_days,
            "last_active_at": user_stats.get("last_active_at"),
        }

        return {
            "summary": summary,
            "trends": trends,
            "skill_breakdown": skill_breakdown,
            "top_resources": top_resources,
            "recent_events": recent_events,
        }

    def _get_top_resources(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch top resources by views/completions for the user's dashboard."""
        # Get resource analytics rows joined with resource details
        query = (
            self.db.table("resource_analytics")
            .select("resource_id, view_count, bookmark_count, like_count, completion_count, avg_rating, rating_count, resources(*)")
            .order("view_count", desc=True)
            .limit(limit)
        )
        try:
            result = self.db.execute(query, "fetch top resources")
        except Exception:
            return []

        items = []
        for row in result.data or []:
            resource = row.get("resources") or {}
            if not resource:
                continue
            views = int(row.get("view_count") or 0)
            completions = int(row.get("completion_count") or 0)
            items.append({
                "resource_id": row.get("resource_id", ""),
                "title": resource.get("title", ""),
                "type": resource.get("type", ""),
                "skill": resource.get("skill", ""),
                "views": views,
                "bookmarks": int(row.get("bookmark_count") or 0),
                "likes": int(row.get("like_count") or 0),
                "completions": completions,
                "avg_rating": float(row.get("avg_rating") or 0),
                "rating_count": int(row.get("rating_count") or 0),
                "completion_rate": round((completions / views) * 100, 1) if views > 0 else 0.0,
            })
        return items