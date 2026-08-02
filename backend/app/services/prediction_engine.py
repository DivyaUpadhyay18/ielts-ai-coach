"""
Prediction Engine service.

Computes deterministic (NO AI) predictions for a user's IELTS exam readiness:

  - Current Preparation %
  - Estimated Band
  - Study Consistency
  - Completion Rate
  - Risk Level
  - Readiness Score

All formulas are documented inline and in PREDICTION_ENGINE.md.
Predictions are stored in the prediction_history table for audit/trend analysis.

Data sources (all from existing repositories):
  - User profile (current_band, target_band, exam_date, daily_minutes_budget)
  - Study plan (active plan, start_date)
  - Tasks (completed, total, skipped, missed days)
  - Progress tracking (study minutes, streak, mock test scores)
"""
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.daily_plan_repo import DailyPlanRepository
from app.repositories.study_plan_repo import StudyPlanRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.repositories.progress_tracking_repo import ProgressTrackingRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants (deterministic thresholds — no AI)
# ---------------------------------------------------------------------------
# Band rounding: IELTS bands are in 0.5 steps.
BAND_STEP = 0.5

# Risk level thresholds (based on completion_rate and days_remaining).
RISK_LOW_COMPLETION = 70.0       # completion_rate >= 70%
RISK_LOW_DAYS = 30               # days_remaining > 30
RISK_MEDIUM_COMPLETION = 40.0    # completion_rate >= 40%
RISK_MEDIUM_DAYS = 14            # days_remaining > 14
RISK_CRITICAL_DAYS = 7           # days_remaining <= 7
RISK_CRITICAL_COMPLETION = 20.0  # completion_rate < 20%

# Readiness score weights (must sum to 1.0).
W_COMPLETION = 0.30
W_CONSISTENCY = 0.25
W_BAND_PROGRESS = 0.20
W_MISSED_DAYS = 0.15
W_STREAK = 0.10

# Mock test blending: 70% mock-based, 30% completion-based.
MOCK_BLEND = 0.70

# Streak factor: cap at 30 days for full score.
STREAK_CAP = 30

# Missed days ratio: cap at 14 days for full penalty.
MISSED_DAYS_CAP = 14

# Study consistency: minimum days since start to compute (avoid 0/0).
MIN_DAYS_FOR_CONSISTENCY = 3


class PredictionEngineService:
    """Deterministic prediction engine — no AI, all formulas documented."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.study_plan_repo = StudyPlanRepository(db)
        self.daily_plan_repo = DailyPlanRepository(db)
        self.task_repo = TaskRepository(db)
        self.progress_repo = ProgressTrackingRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_prediction(self, user_id: str, run_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Compute the full prediction payload for a user.

        Returns a dict matching PredictionResponse.
        """
        today = run_date or date.today()
        user = self._safe_get_profile(user_id)

        if not user:
            raise NotFoundError("User not found")

        exam_raw = user.get("exam_date")
        if not exam_raw:
            raise ValidationError(
                "Set your exam date in onboarding before predictions can be computed."
            )

        exam_date = self._parse_date(exam_raw)
        days_remaining = max((exam_date - today).days, 0)

        # ---- Gather raw data -------------------------------------------
        study_plan = self._safe_get_active_plan(user_id)
        study_plan_id = study_plan.get("id") if study_plan else None
        plan_start = self._parse_date(study_plan.get("start_date")) if study_plan else None

        # Tasks
        all_tasks = self._safe_list_tasks(user_id, study_plan_id)
        completed_tasks = [t for t in all_tasks if t.get("status") == "completed"]
        skipped_tasks = [t for t in all_tasks if t.get("status") == "skipped"]
        total_tasks = len(all_tasks)
        completed_count = len(completed_tasks)
        skipped_count = len(skipped_tasks)

        # Completion rate: completed / (total - skipped)
        schedulable = total_tasks - skipped_count
        completion_rate = (completed_count / schedulable * 100) if schedulable > 0 else 0.0
        completion_rate = min(max(completion_rate, 0.0), 100.0)

        # Study time & streak from progress state
        progress_state = self._safe_get_progress_state(user_id)
        study_minutes = int(progress_state.get("total_minutes") or 0)
        study_hours = round(study_minutes / 60.0, 1)
        daily_streak = int(progress_state.get("current_streak") or 0)
        longest_streak = int(progress_state.get("longest_streak") or 0)

        # Mock test scores
        mock_scores = self._safe_get_mock_scores(user_id)
        mock_test_count = len(mock_scores)
        latest_mock_band = mock_scores[-1] if mock_scores else None
        average_mock_band = (
            round(sum(mock_scores) / len(mock_scores), 1) if mock_scores else None
        )

        # Missed days
        missed_days = self._safe_count_missed_days(user_id, today)

        # Study consistency (uses DB-backed active dates)
        active_days, total_days_since_start, study_consistency = self._compute_consistency_with_db(
            user_id, plan_start, today
        )

        # Days remaining
        # (already computed above)

        # ---- Compute derived metrics -----------------------------------
        # 1. Current Preparation %
        preparation_percentage = round(completion_rate, 1)

        # 2. Estimated Band
        current_band = float(user.get("current_band") or 5.0)
        target_band = float(user.get("target_band") or 7.0)
        estimated_band = self._compute_estimated_band(
            current_band, target_band, completion_rate,
            latest_mock_band, average_mock_band, mock_test_count,
        )

        # 3. Study Consistency (already computed)
        # 4. Completion Rate (already computed)

        # 5. Risk Level
        risk_level = self._compute_risk_level(completion_rate, days_remaining)

        # 6. Readiness Score
        readiness_score = self._compute_readiness_score(
            completion_rate, study_consistency,
            estimated_band, target_band,
            missed_days, daily_streak,
        )

        # Intensity (reuse countdown logic)
        intensity = self._intensity(days_remaining)

        # ---- Build formulas documentation ------------------------------
        formulas = self._build_formulas()

        # ---- Build recommendations -------------------------------------
        recommendations = self._build_recommendations(
            risk_level, completion_rate, days_remaining,
            study_consistency, missed_days, daily_streak,
            estimated_band, target_band,
        )

        # ---- Assemble response -----------------------------------------
        metrics = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_count,
            "skipped_tasks": skipped_count,
            "completion_rate": round(completion_rate, 1),
            "study_minutes": study_minutes,
            "study_hours": study_hours,
            "daily_streak": daily_streak,
            "longest_streak": longest_streak,
            "missed_days": missed_days,
            "active_days": active_days,
            "total_days_since_start": total_days_since_start,
            "study_consistency": round(study_consistency, 1),
            "mock_test_count": mock_test_count,
            "latest_mock_band": latest_mock_band,
            "average_mock_band": average_mock_band,
            "days_remaining": days_remaining,
        }

        result = {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "run_date": today.isoformat(),
            "preparation_percentage": preparation_percentage,
            "estimated_band": estimated_band,
            "study_consistency": round(study_consistency, 1),
            "completion_rate": round(completion_rate, 1),
            "risk_level": risk_level,
            "readiness_score": round(readiness_score, 1),
            "current_band": current_band,
            "target_band": target_band,
            "days_remaining": days_remaining,
            "intensity": intensity,
            "metrics": metrics,
            "formulas": formulas,
            "recommendations": recommendations,
        }

        # ---- Persist to history (if DB available) -------------------
        self._store_history(user_id, today, result)

        return result

    def get_history(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Return paginated prediction history for a user."""
        if self.db is None:
            return {"items": [], "total": 0, "limit": limit, "offset": offset}

        query = (
            self.db.table("prediction_history")
            .select("*")
            .eq("user_id", user_id)
            .order("run_date", desc=True)
            .limit(limit)
            .offset(offset)
        )
        result = self.db.execute(query, "fetch prediction history")
        rows = result.data or []

        # Count total
        count_query = (
            self.db.table("prediction_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
        )
        count_result = self.db.execute(count_query, "count prediction history")
        total = count_result.count or 0

        items = []
        for row in rows:
            items.append({
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "run_date": row.get("run_date"),
                "generated_at": row.get("generated_at"),
                "preparation_percentage": float(row.get("preparation_percentage") or 0),
                "estimated_band": float(row.get("estimated_band") or 0),
                "study_consistency": float(row.get("study_consistency") or 0),
                "completion_rate": float(row.get("completion_rate") or 0),
                "risk_level": row.get("risk_level"),
                "readiness_score": float(row.get("readiness_score") or 0),
                "metrics_json": row.get("metrics_json") or {},
            })

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # ------------------------------------------------------------------
    # Formula implementations
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_estimated_band(
        current_band: float,
        target_band: float,
        completion_rate: float,
        latest_mock_band: Optional[float],
        average_mock_band: Optional[float],
        mock_test_count: int,
    ) -> float:
        """
        Estimate the user's likely band score.

        Formula:
          If mock tests exist:
            mock_based = average_mock_band (or latest if only one)
            completion_based = current_band + (target_band - current_band) * (completion_rate / 100)
            estimated = MOCK_BLEND * mock_based + (1 - MOCK_BLEND) * completion_based
          Else:
            estimated = current_band + (target_band - current_band) * (completion_rate / 100)

          Rounded to nearest 0.5 (IELTS band step).
          Clamped to [0, 9].
        """
        band_gap = target_band - current_band
        completion_based = current_band + band_gap * (completion_rate / 100.0)

        if mock_test_count > 0 and average_mock_band is not None:
            mock_based = average_mock_band
            estimated = MOCK_BLEND * mock_based + (1 - MOCK_BLEND) * completion_based
        else:
            estimated = completion_based

        # Round to nearest 0.5
        estimated = round(estimated / BAND_STEP) * BAND_STEP
        # Clamp to [0, 9]
        estimated = max(0.0, min(9.0, estimated))
        return estimated

    @staticmethod
    def _compute_risk_level(completion_rate: float, days_remaining: int) -> str:
        """
        Determine risk level based on completion rate and time remaining.

        Formula:
          critical: days_remaining <= 7 OR completion_rate < 20%
          high:     completion_rate < 40% OR days_remaining <= 14
          medium:   completion_rate < 70% OR days_remaining <= 30
          low:      completion_rate >= 70% AND days_remaining > 30
        """
        if days_remaining <= RISK_CRITICAL_DAYS or completion_rate < RISK_CRITICAL_COMPLETION:
            return "critical"
        if completion_rate < RISK_MEDIUM_COMPLETION or days_remaining <= RISK_MEDIUM_DAYS:
            return "high"
        if completion_rate < RISK_LOW_COMPLETION or days_remaining <= RISK_LOW_DAYS:
            return "medium"
        return "low"

    @staticmethod
    def _compute_readiness_score(
        completion_rate: float,
        study_consistency: float,
        estimated_band: float,
        target_band: float,
        missed_days: int,
        daily_streak: int,
    ) -> float:
        """
        Compute a composite readiness score (0–100).

        Formula:
          readiness = W_COMPLETION * completion_rate
                    + W_CONSISTENCY * study_consistency
                    + W_BAND_PROGRESS * (estimated_band / target_band) * 100
                    + W_MISSED_DAYS * (1 - missed_days / MISSED_DAYS_CAP) * 100
                    + W_STREAK * min(daily_streak / STREAK_CAP, 1.0) * 100

          Clamped to [0, 100].
        """
        band_progress = 0.0
        if target_band > 0:
            band_progress = min(estimated_band / target_band, 1.0) * 100

        missed_ratio = min(missed_days / MISSED_DAYS_CAP, 1.0) if MISSED_DAYS_CAP > 0 else 0.0
        missed_score = (1.0 - missed_ratio) * 100

        streak_score = min(daily_streak / STREAK_CAP, 1.0) * 100

        score = (
            W_COMPLETION * completion_rate
            + W_CONSISTENCY * study_consistency
            + W_BAND_PROGRESS * band_progress
            + W_MISSED_DAYS * missed_score
            + W_STREAK * streak_score
        )
        return max(0.0, min(100.0, score))

    @staticmethod
    def _compute_consistency(
        user_id: str,
        plan_start: Optional[date],
        today: date,
        active_dates: Optional[set] = None,
    ) -> Tuple[int, int, float]:
        """
        Compute study consistency.

        Formula:
          total_days = (today - plan_start).days  (or days since first activity)
          active_days = count of days with >=1 minute of study activity
          consistency = (active_days / total_days) * 100

          If total_days < MIN_DAYS_FOR_CONSISTENCY, consistency = 100 (too early to judge).
        """
        if active_dates is None:
            active_dates = set()

        if plan_start is not None:
            total_days = max((today - plan_start).days, 0)
        else:
            total_days = 0

        if total_days < MIN_DAYS_FOR_CONSISTENCY:
            return (len(active_dates), total_days, 100.0)

        active_count = len(active_dates)
        consistency = (active_count / total_days) * 100.0
        consistency = min(max(consistency, 0.0), 100.0)
        return (active_count, total_days, consistency)

    @staticmethod
    def _intensity(days_remaining: int) -> str:
        """Map remaining days to a preparation-intensity label."""
        if days_remaining < 14:
            return "final"
        if days_remaining < 30:
            return "intensive"
        if days_remaining < 60:
            return "focused"
        return "normal"

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    @staticmethod
    def _build_recommendations(
        risk_level: str,
        completion_rate: float,
        days_remaining: int,
        study_consistency: float,
        missed_days: int,
        daily_streak: int,
        estimated_band: float,
        target_band: float,
    ) -> List[str]:
        """Generate actionable, deterministic recommendations."""
        recs: List[str] = []

        if risk_level == "critical":
            recs.append("Critical: You are at high risk of not reaching your target band. Increase daily study time immediately.")
        elif risk_level == "high":
            recs.append("High risk: Focus on completing missed tasks and maintaining daily streaks.")
        elif risk_level == "medium":
            recs.append("Medium risk: Stay consistent and prioritize weak-skill tasks.")
        else:
            recs.append("Low risk: Maintain your current pace and focus on mock tests.")

        if completion_rate < 50:
            recs.append("Your task completion rate is below 50%. Prioritize finishing scheduled tasks before starting new ones.")

        if study_consistency < 60:
            recs.append("Your study consistency is low. Try to study at the same time every day to build a habit.")

        if missed_days > 0:
            recs.append(f"You have {missed_days} consecutive missed day(s). Use streak freezes or catch up today.")

        if daily_streak < 7:
            recs.append("Build a daily streak of at least 7 days to establish a consistent routine.")

        if estimated_band < target_band:
            gap = round(target_band - estimated_band, 1)
            recs.append(f"Your estimated band ({estimated_band}) is {gap} below your target ({target_band}). Focus on weak skills.")

        if days_remaining < 30:
            recs.append("Less than 30 days remain. Shift to intensive revision and full mock tests.")

        return recs

    # ------------------------------------------------------------------
    # Formula documentation (for transparency)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_formulas() -> Dict[str, str]:
        """Return human-readable documentation of every formula used."""
        return {
            "preparation_percentage": (
                "completion_rate = (completed_tasks / (total_tasks - skipped_tasks)) * 100. "
                "preparation_percentage = completion_rate (clamped 0–100)."
            ),
            "estimated_band": (
                "If mock tests exist: estimated = 0.7 * avg_mock_band + 0.3 * (current_band + (target_band - current_band) * completion_rate/100). "
                "Else: estimated = current_band + (target_band - current_band) * completion_rate/100. "
                "Rounded to nearest 0.5, clamped to [0, 9]."
            ),
            "study_consistency": (
                "consistency = (active_days / total_days_since_start) * 100. "
                "active_days = days with >=1 minute of study activity. "
                "If total_days < 3, consistency = 100 (too early to judge)."
            ),
            "completion_rate": (
                "completion_rate = (completed_tasks / (total_tasks - skipped_tasks)) * 100. "
                "Clamped to 0–100."
            ),
            "risk_level": (
                "critical: days_remaining <= 7 OR completion_rate < 20%. "
                "high: completion_rate < 40% OR days_remaining <= 14. "
                "medium: completion_rate < 70% OR days_remaining <= 30. "
                "low: completion_rate >= 70% AND days_remaining > 30."
            ),
            "readiness_score": (
                "readiness = 0.30*completion_rate + 0.25*study_consistency + 0.20*(estimated_band/target_band)*100 "
                "+ 0.15*(1 - missed_days/14)*100 + 0.10*min(daily_streak/30, 1)*100. "
                "Clamped to 0–100."
            ),
        }

    # ------------------------------------------------------------------
    # Safe DB wrappers
    # ------------------------------------------------------------------
    def _safe_get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        try:
            return self.user_repo.get_profile(user_id)
        except NotFoundError:
            return None

    def _safe_get_active_plan(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.db is None:
            return None
        return self.study_plan_repo.get_active(user_id)

    def _safe_list_tasks(
        self, user_id: str, study_plan_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        return self.task_repo.list_for_user(
            user_id=user_id, study_plan_id=study_plan_id
        )

    def _safe_get_progress_state(self, user_id: str) -> Dict[str, Any]:
        if self.db is None:
            return {}
        return self.progress_repo.get_state(user_id)

    def _safe_get_mock_scores(self, user_id: str) -> List[float]:
        """
        Extract mock test band scores from the study session ledger.

        Looks for sessions with session_type='mock_test' and extracts the
        band score from the meta field (meta.band_score or meta.score).
        """
        if self.db is None:
            return []

        history = self.progress_repo.get_history(user_id, limit=100)
        scores: List[float] = []
        for session in history:
            if session.get("session_type") != "mock_test":
                continue
            meta = session.get("meta") or {}
            band = meta.get("band_score") or meta.get("score")
            if band is not None:
                try:
                    scores.append(float(band))
                except (ValueError, TypeError):
                    continue
        return scores

    def _safe_count_missed_days(self, user_id: str, today: date) -> int:
        if self.db is None:
            return 0
        return self.task_repo.count_consecutive_missed_days(user_id, today)

    def _safe_get_active_dates(self, user_id: str) -> set:
        """Fetch the set of active dates from daily_stats."""
        if self.db is None:
            return set()
        query = (
            self.db.table("daily_stats")
            .select("stats_date")
            .eq("user_id", user_id)
            .eq("is_active", True)
        )
        result = self.db.execute(query, "fetch active dates for prediction")
        active = set()
        for r in result.data or []:
            try:
                active.add(date.fromisoformat(r["stats_date"]))
            except (ValueError, TypeError):
                continue
        return active

    def _compute_consistency_with_db(
        self, user_id: str, plan_start: Optional[date], today: date
    ) -> Tuple[int, int, float]:
        """Compute consistency using DB-backed active dates."""
        active_dates = self._safe_get_active_dates(user_id)
        return self._compute_consistency(user_id, plan_start, today, active_dates)

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------
    def _store_history(
        self, user_id: str, run_date: date, result: Dict[str, Any]
    ) -> None:
        """Store a prediction snapshot in the prediction_history table."""
        if self.db is None:
            return

        try:
            payload = {
                "user_id": user_id,
                "run_date": run_date.isoformat(),
                "preparation_percentage": result["preparation_percentage"],
                "estimated_band": result["estimated_band"],
                "study_consistency": result["study_consistency"],
                "completion_rate": result["completion_rate"],
                "risk_level": result["risk_level"],
                "readiness_score": result["readiness_score"],
                "current_band": result.get("current_band"),
                "target_band": result.get("target_band"),
                "days_remaining": result["days_remaining"],
                "intensity": result["intensity"],
                "metrics_json": result["metrics"],
                "formulas_json": result["formulas"],
                "recommendations": result["recommendations"],
            }
            query = self.db.table("prediction_history").upsert(
                payload, on_conflict="user_id,run_date"
            )
            self.db.execute(query, "store prediction history")

            # Update cache
            cache_payload = {
                "user_id": user_id,
                "last_run_date": run_date.isoformat(),
                "readiness_score": result["readiness_score"],
                "risk_level": result["risk_level"],
                "estimated_band": result["estimated_band"],
            }
            cache_query = self.db.table("prediction_cache").upsert(
                cache_payload, on_conflict="user_id"
            )
            self.db.execute(cache_query, "update prediction cache")

            logger.info(
                "prediction stored user=%s date=%s readiness=%.1f risk=%s",
                user_id, run_date.isoformat(),
                result["readiness_score"], result["risk_level"],
            )
        except Exception as exc:
            logger.warning("prediction history store failed user=%s: %s", user_id, exc)


# Singleton bound to the shared DB session.
from app.db.session import db_session

prediction_engine_service = PredictionEngineService(db_session)
