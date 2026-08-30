"""
Writing Progress Analytics service.

Computes all the Writing Progress Analytics metrics from evaluated essays
stored in the ``writing_evaluations`` table.  This service is deterministic
and read-only — it never writes and never fabricates data.  Every metric
requested by the product is computed here:

  - Writing Band History      (chronological overall-band trajectory)
  - Task 1 History / Task 2 History
  - Per-criterion breakdown   (Task Response, Coherence & Cohesion,
                               Lexical Resource, Grammar)
  - Average Word Count / Average Writing Time
  - Common Errors             (aggregated error-type frequency)
  - Improvement Rate          (linear-regression slope of band vs. order)
  - Strongest / Weakest Criterion
  - Trends                    (daily chart data series)
  - Essays                    (every submitted essay with evaluation status)

All DB access is defensive (safe wrappers return honest empty values) so the
service never crashes a request because of a missing table or a transient read
failure — mirroring the prediction_engine / band_estimation services.
"""
import logging
import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import DatabaseSession
from app.repositories.writing_analytics_repo import WritingAnalyticsRepository

logger = logging.getLogger(__name__)

# Criterion keys (display order) and labels.
CRITERIA_KEYS = (
    "task_response",
    "coherence_cohesion",
    "lexical_resource",
    "grammatical_range_accuracy",
)

CRITERION_LABELS: Dict[str, str] = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence and Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammatical Range and Accuracy",
}

CRITERION_SHORT_LABELS: Dict[str, str] = {
    "task_response": "Task Response",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range_accuracy": "Grammar",
}

ERROR_TYPE_TO_CRITERION: Dict[str, str] = {
    "Grammar": "grammatical_range_accuracy",
    "Spelling": "grammatical_range_accuracy",
    "Punctuation": "grammatical_range_accuracy",
    "Sentence Structure": "grammatical_range_accuracy",
    "Vocabulary": "lexical_resource",
    "Repetition": "lexical_resource",
    "Word Choice": "lexical_resource",
    "Cohesion": "coherence_cohesion",
    "Task Response": "task_response",
}

# Improvement-rate thresholds (band points per essay).
IMPROVE_THRESHOLD = 0.05   # slope >= this is "improving"
DECLINE_THRESHOLD = -0.05  # slope <= this is "declining"

# Trend threshold for criterion/band trend labelling.
TREND_BAND_THRESHOLD = 0.25

# Cap on how many evaluations are scanned for analytics.
MAX_EVALUATIONS = 2000

# Default band gap used when no target band is known.
DEFAULT_TARGET_GAP = 1.0

# ---------------------------------------------------------------------------
# Band descriptor mapping — target per-criterion bands for each overall band.
#
# The average of these four criterion bands (rounded to 0.5) equals the
# overall target band, so the distribution is always achievable.  At higher
# bands one criterion sits 0.5 below the overall to reflect the realistic
# variation allowed by the official IELTS descriptors (an overall 7 does not
# require all four criteria to be exactly 7).
# ---------------------------------------------------------------------------
BAND_CRITERION_TARGETS: Dict[float, Dict[str, float]] = {
    5.0: {"task_response": 5.0, "coherence_cohesion": 5.0, "lexical_resource": 5.0, "grammatical_range_accuracy": 5.0},
    5.5: {"task_response": 5.5, "coherence_cohesion": 5.5, "lexical_resource": 5.5, "grammatical_range_accuracy": 5.5},
    6.0: {"task_response": 6.0, "coherence_cohesion": 6.0, "lexical_resource": 6.0, "grammatical_range_accuracy": 6.0},
    6.5: {"task_response": 6.5, "coherence_cohesion": 6.5, "lexical_resource": 6.5, "grammatical_range_accuracy": 6.5},
    7.0: {"task_response": 7.0, "coherence_cohesion": 7.0, "lexical_resource": 7.0, "grammatical_range_accuracy": 6.5},
    7.5: {"task_response": 7.5, "coherence_cohesion": 7.5, "lexical_resource": 7.5, "grammatical_range_accuracy": 7.0},
    8.0: {"task_response": 8.0, "coherence_cohesion": 7.5, "lexical_resource": 7.5, "grammatical_range_accuracy": 8.0},
    8.5: {"task_response": 8.5, "coherence_cohesion": 8.5, "lexical_resource": 8.5, "grammatical_range_accuracy": 8.0},
    9.0: {"task_response": 9.0, "coherence_cohesion": 9.0, "lexical_resource": 8.5, "grammatical_range_accuracy": 9.0},
}

# Keyword → concise reason phrase, searched (lowercased) inside the criterion's
# weakness/suggestions text to produce the short label shown in the report
# (e.g. "Stronger examples", "Better paragraph linking").
_CRITERION_REASON_KEYWORDS: Dict[str, List[Tuple[str, str]]] = {
    "task_response": [
        ("example", "Stronger examples"),
        ("develop", "More developed arguments"),
        ("address", "Fully addresses the task"),
        ("position", "Clearer position throughout"),
        ("fully", "Fully addresses all parts"),
        ("idea", "More developed ideas"),
    ],
    "coherence_cohesion": [
        ("link", "Better paragraph linking"),
        ("cohes", "Better cohesion"),
        ("paragraph", "Clearer paragraph structure"),
        ("structure", "Clearer paragraph structure"),
        ("signpos", "Better signposting"),
        ("connect", "Better connections between ideas"),
    ],
    "lexical_resource": [
        ("vocab", "Stronger vocabulary"),
        ("synonym", "Better word variety"),
        ("repetition", "Reduced repetition"),
        ("word choice", "More precise word choice"),
        ("lexical", "Stronger lexical range"),
        ("collocation", "Better collocations"),
    ],
    "grammatical_range_accuracy": [
        ("error", "Fewer grammatical errors"),
        ("sentence", "Better sentence structure"),
        ("accuracy", "Higher accuracy"),
        ("complex", "More complex structures"),
        ("range", "Wider grammatical range"),
        ("agreement", "Better subject-verb agreement"),
    ],
}


def _round_band(value: float) -> float:
    """Round to the nearest 0.5 and clamp to [0, 9]."""
    return round(max(0.0, min(9.0, float(value))) * 2) / 2


def _direction(change: float) -> str:
    """Classify a band change into a direction label."""
    if change > 0:
        return "improving"
    if change < 0:
        return "declining"
    return "maintained"


class WritingAnalyticsService:
    """Deterministic, read-only Writing Progress Analytics engine."""

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = WritingAnalyticsRepository(db)
# ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_band_history(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Chronological overall-band history (newest last)."""
        rows = self._safe_list_evaluations(user_id, task_type, days=days)
        points = self._build_band_history_points(rows, task_type)
        total = len(points)
        averages = {
            "overall_band": 0.0,
            "task1_band": 0.0,
            "task2_band": 0.0,
            "word_count": 0.0,
        }

        bands = [p["overall_band"] for p in points if p["overall_band"] is not None]
        if bands:
            averages["overall_band"] = round(sum(bands) / len(bands), 2)
        if points:
            averages["word_count"] = round(
                sum(p["word_count"] for p in points) / len(points), 1
            )
        t1 = [p["overall_band"] for p in points if p["overall_band"] is not None and p["task_type"] == "task_1"]
        t2 = [p["overall_band"] for p in points if p["overall_band"] is not None and p["task_type"] == "task_2"]
        if t1:
            averages["task1_band"] = round(sum(t1) / len(t1), 2)
        if t2:
            averages["task2_band"] = round(sum(t2) / len(t2), 2)

        return {
            "task_type": task_type,
            "total_essays": total,
            "points": points,
            "averages": averages,
            "trend": self._band_trend(points),
        }

    def get_task1_history(
        self, user_id: str, days: Optional[int] = None
    ) -> Dict[str, Any]:
        return self.get_band_history(user_id, task_type="task_1", days=days)

    def get_task2_history(
        self, user_id: str, days: Optional[int] = None
    ) -> Dict[str, Any]:
        return self.get_band_history(user_id, task_type="task_2", days=days)

    def get_criterion_breakdown(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Per-criterion average, best, worst and trend."""
        rows = self._safe_list_evaluations(user_id, task_type, days=days)
        criteria = []
        for key in CRITERIA_KEYS:
            items = []
            for row in rows:
                bands = row.get("criteria_bands") or {}
                b = bands.get(key)
                if b is None:
                    detail = (row.get("criteria_detail") or {}).get(key) or {}
                    b = detail.get("band")
                if b is not None:
                    items.append((row.get("created_at") or "", float(b)))
            items.sort(key=lambda x: x[0])
            bands_only = [b for _, b in items]
            average = round(sum(bands_only) / len(bands_only), 2) if bands_only else 0.0
            latest = bands_only[-1] if bands_only else None
            best = max(bands_only) if bands_only else 0.0
            worst = min(bands_only) if bands_only else 0.0
            trend = self._trend_from_bands(bands_only)
            label = CRITERION_LABELS.get(key, key)
            if task_type == "task_1" and key == "task_response":
                label = "Task Achievement"
            criteria.append({
                "criterion": key,
                "label": label,
                "average_band": average,
                "latest_band": latest,
                "best_band": best,
                "worst_band": worst,
                "submissions_count": len(bands_only),
                "trend": trend,
            })
        return {"task_type": task_type, "criteria": criteria}

    def get_criterion_histories(
        self, user_id: str, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Band history for all four criteria (for the criterion chart)."""
        return [
            self.get_criterion_history(user_id, key, days=days) for key in CRITERIA_KEYS
        ]

    def get_criterion_history(
        self,
        user_id: str,
        criterion: str,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Band history for a single criterion (chronological)."""
        if criterion not in CRITERIA_KEYS:
            criterion = "grammatical_range_accuracy"
        rows = self._safe_list_evaluations(user_id, None, days=days)
        points = []
        for row in rows:
            bands = row.get("criteria_bands") or {}
            b = bands.get(criterion)
            if b is None:
                detail = (row.get("criteria_detail") or {}).get(criterion) or {}
                b = detail.get("band")
            if b is not None:
                points.append({
                    "date": self._date_label(row.get("created_at")),
                    "band": round(float(b), 1),
                    "label": CRITERION_LABELS.get(criterion, criterion),
                })
        points.sort(key=lambda x: x["date"])
        bands_only = [p["band"] for p in points]
        return {
            "criterion": criterion,
            "label": CRITERION_LABELS.get(criterion, criterion),
            "points": points,
            "average_band": round(sum(bands_only) / len(bands_only), 2) if bands_only else 0.0,
            "latest_band": bands_only[-1] if bands_only else None,
        }
    def get_metrics(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aggregate metrics: average band, word count, writing time, confidence."""
        rows = self._safe_list_evaluations(user_id, task_type, days=days)
        evaluated = len(rows)
        bands = []
        counts = []
        times = []
        confs = []
        total_words = 0
        total_time = 0

        for row in rows:
            b = row.get("overall_band")
            if b is not None:
                bands.append(float(b))
            wc = int(row.get("word_count") or 0)
            counts.append(wc)
            total_words += wc
            wt = self._writing_time(row)
            times.append(wt)
            total_time += int(wt)
            c = row.get("confidence")
            if c is not None:
                confs.append(float(c))

        def _avg(nums):
            return round(sum(nums) / len(nums), 2) if nums else None

        avg_band = _avg(bands)
        avg_wc = round(sum(counts) / len(counts), 1) if counts else 0.0
        avg_time = round(sum(times) / len(times), 1) if times else 0.0
        avg_time_min = round(avg_time / 60, 1) if times else 0.0
        avg_conf = _avg(confs)

        return {
            "task_type": task_type,
            "total_essays": self.repo.count_submissions(user_id, task_type),
            "evaluated_essays": evaluated,
            "average_band": avg_band,
            "average_word_count": avg_wc,
            "average_writing_time_seconds": avg_time,
            "average_writing_time_minutes": avg_time_min,
            "average_confidence": avg_conf,
            "average_task1_band": self._sub_avg_band(rows, "task_1"),
            "average_task2_band": self._sub_avg_band(rows, "task_2"),
            "total_word_count": total_words,
            "total_writing_time_seconds": total_time,
        }

    def get_common_errors(
        self,
        user_id: str,
        limit: int = 10,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aggregate error-type frequency across all evaluated essays."""
        rows = self._safe_list_evaluations(user_id, None, days=days)
        buckets: Dict[str, Dict[str, Any]] = {}
        total_errors = 0

        for row in rows:
            error_analysis = row.get("error_analysis") or []
            if isinstance(error_analysis, dict):
                error_analysis = error_analysis.get("errors", []) or []
            for err in error_analysis:
                if not isinstance(err, dict):
                    continue
                etype = (err.get("error_type") or "Grammar").strip() or "Grammar"
                severity = (err.get("severity") or "minor").lower()
                if severity not in ("critical", "major", "minor"):
                    severity = "minor"
                bucket = buckets.setdefault(
                    etype,
                    {
                        "error_type": etype,
                        "criterion": ERROR_TYPE_TO_CRITERION.get(etype, "grammatical_range_accuracy"),
                        "count": 0,
                        "percentage": 0.0,
                        "severity_breakdown": {"critical": 0, "major": 0, "minor": 0},
                        "top_examples": [],
                    },
                )
                bucket["count"] += 1
                bucket["severity_breakdown"][severity] += 1
                total_errors += 1
                example = err.get("original") or err.get("explanation") or ""
                if example and example not in bucket["top_examples"]:
                    bucket["top_examples"].append(str(example)[:160])

        errors = list(buckets.values())
        errors.sort(key=lambda x: x["count"], reverse=True)
        for e in errors:
            e["percentage"] = round((e["count"] / total_errors) * 100, 1) if total_errors else 0.0
            e["top_examples"] = e["top_examples"][:5]

        return {
            "total_errors": total_errors,
            "total_unique_types": len(errors),
            "limit": limit,
            "errors": errors[:limit],
        }
    def get_improvement_rate(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Linear-regression slope of overall_band vs. submission order."""
        rows = self._safe_list_evaluations(user_id, task_type, days=days)
        rows_sorted = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
        bands = [float(r["overall_band"]) for r in rows_sorted if r.get("overall_band") is not None]
        n = len(bands)
        slope = 0.0
        r_sq = 0.0
        first = bands[0] if bands else None
        latest = bands[-1] if bands else None

        if n >= 2:
            slope, r_sq = self._linear_regression(list(range(n)), bands)

        if slope >= IMPROVE_THRESHOLD:
            direction = "improving"
        elif slope <= DECLINE_THRESHOLD:
            direction = "declining"
        else:
            direction = "stable"

        band_change = (latest - first) if first is not None and latest is not None else 0.0

        if n < 2:
            description = "Submit and evaluate at least 2 essays to see your improvement rate trend."
        elif direction == "improving":
            description = f"Your writing band is trending up by about {abs(band_change):.1f} bands overall (slope {slope:+.3f}/essay)."
        elif direction == "declining":
            description = f"Your writing band is trending down by about {abs(band_change):.1f} bands overall (slope {slope:+.3f}/essay)."
        else:
            description = "Your writing band has been stable — consistency is the foundation for the next step up."

        return {
            "task_type": task_type,
            "total_essays": n,
            "slope": round(slope, 4),
            "direction": direction,
            "description": description,
            "band_change": round(band_change, 2),
            "first_band": first,
            "latest_band": latest,
            "r_squared": round(r_sq, 4),
        }

    def get_strongest_criterion(
        self, user_id: str, task_type: Optional[str] = None, days: Optional[int] = None
    ) -> Dict[str, Any]:
        breakdown = self.get_criterion_breakdown(user_id, task_type, days)["criteria"]
        valid = [c for c in breakdown if c["submissions_count"] > 0 and c["average_band"] > 0]
        if not valid:
            return self._criterion_summary(None)
        top = max(valid, key=lambda c: c["average_band"])
        return self._criterion_summary(top)

    def get_weakest_criterion(
        self, user_id: str, task_type: Optional[str] = None, days: Optional[int] = None
    ) -> Dict[str, Any]:
        breakdown = self.get_criterion_breakdown(user_id, task_type, days)["criteria"]
        valid = [c for c in breakdown if c["submissions_count"] > 0 and c["average_band"] > 0]
        if not valid:
            return self._criterion_summary(None)
        bottom = min(valid, key=lambda c: c["average_band"])
        return self._criterion_summary(bottom)

    def get_trends(
        self, user_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Daily bucketed trend series for band, word count and writing time."""
        rows = self._safe_list_evaluations(user_id, None, days=days)
        points = self._build_trend_points(rows, days)
        return {"days": days, "points": points} | {
            "series": ["band", "word_count", "writing_time_minutes"]
        }

    def get_essays(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Every submitted essay (draft + submitted) with evaluation status."""
        rows = self.repo.list_submissions(user_id, task_type, limit=limit, offset=offset)
        records = [self._build_essay_record(row) for row in rows]
        total = self.repo.count_submissions(user_id, task_type)
        return {"results": records, "total": total, "limit": limit, "offset": offset}
    def get_dashboard(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        days: Optional[int] = 90,
    ) -> Dict[str, Any]:
        """Comprehensive Writing Progress Analytics dashboard payload."""
        band_history = self.get_band_history(user_id, task_type, days)
        task1_history = self.get_band_history(user_id, "task_1", days)
        task2_history = self.get_band_history(user_id, "task_2", days)
        criterion_breakdown = self.get_criterion_breakdown(user_id, task_type, days)
        criterion_histories = self.get_criterion_histories(user_id, days)
        common_errors = self.get_common_errors(user_id, limit=10, days=days)
        trends = self.get_trends(user_id, days=days or 30)
        metrics = self.get_metrics(user_id, task_type, days)
        metrics_task1 = self.get_metrics(user_id, "task_1", days)
        metrics_task2 = self.get_metrics(user_id, "task_2", days)
        improvement_rate = self.get_improvement_rate(user_id, task_type, days)
        improvement_rate_task1 = self.get_improvement_rate(user_id, "task_1", days)
        improvement_rate_task2 = self.get_improvement_rate(user_id, "task_2", days)
        strongest = self.get_strongest_criterion(user_id, task_type, days)
        weakest = self.get_weakest_criterion(user_id, task_type, days)
        essays = self.get_essays(user_id, task_type, limit=200, offset=0)

        summary = {
            "total_essays": metrics["total_essays"],
            "evaluated_essays": metrics["evaluated_essays"],
            "average_band": metrics["average_band"] or 0.0,
            "average_word_count": metrics["average_word_count"],
            "average_writing_time_seconds": metrics["average_writing_time_seconds"],
            "average_writing_time_minutes": metrics["average_writing_time_minutes"],
            "average_confidence": metrics["average_confidence"] or 0.0,
            "improvement_rate": improvement_rate["slope"],
            "improvement_direction": improvement_rate["direction"],
            "strongest_criterion": strongest.get("criterion"),
            "weakest_criterion": weakest.get("criterion"),
        }

        return {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "task_type": task_type,
            "days": days or 0,
            "summary": summary,
            "band_history": band_history["points"],
            "task1_history": task1_history["points"],
            "task2_history": task2_history["points"],
            "criterion_breakdown": criterion_breakdown["criteria"],
            "criterion_histories": criterion_histories,
            "common_errors": common_errors["errors"],
            "trends": trends["points"],
            "essays": essays["results"],
            "total_essays": essays["total"],
            "metrics": metrics,
            "metrics_task1": metrics_task1,
            "metrics_task2": metrics_task2,
            "improvement_rate": improvement_rate,
            "improvement_rate_task1": improvement_rate_task1,
            "improvement_rate_task2": improvement_rate_task2,
            "strongest_criterion": strongest,
            "weakest_criterion": weakest,
        }

    def context_brief(
        self,
        user_id: str,
        days: Optional[int] = 90,
    ) -> Dict[str, Any]:
        """
        Compact writing-analytics snapshot for the AI Mentor / dashboard
        integrations.  Never raises — returns honest empty values when there
        is no data yet.
        """
        try:
            metrics = self.get_metrics(user_id, None, days)
            improvement = self.get_improvement_rate(user_id, None, days)
            strongest = self.get_strongest_criterion(user_id, None, days)
            weakest = self.get_weakest_criterion(user_id, None, days)
            common_errors = self.get_common_errors(user_id, limit=5, days=days)
            return {
                "has_writing_data": metrics["evaluated_essays"] > 0,
                "evaluated_essays": metrics["evaluated_essays"],
                "average_band": metrics["average_band"],
                "average_word_count": metrics["average_word_count"],
                "average_writing_time_minutes": metrics["average_writing_time_minutes"],
                "average_confidence": metrics["average_confidence"],
                "improvement": {
                    "slope": improvement["slope"],
                    "direction": improvement["direction"],
                    "band_change": improvement["band_change"],
                    "first_band": improvement["first_band"],
                    "latest_band": improvement["latest_band"],
                },
                "strongest_criterion": strongest.get("criterion"),
                "weakest_criterion": weakest.get("criterion"),
                "top_error_types": [
                    {"error_type": e["error_type"], "count": e["count"]}
                    for e in common_errors["errors"][:5]
                ],
            }
        except Exception as exc:  # pragma: no cover - defensive only
            logger.warning("writing analytics context_brief failed user=%s: %s", user_id, exc)
            return {
                "has_writing_data": False,
                "evaluated_essays": 0,
                "average_band": None,
                "average_word_count": 0.0,
                "average_writing_time_minutes": 0.0,
                "average_confidence": None,
                "improvement": {
                    "slope": 0.0,
                    "direction": "stable",
                    "band_change": 0.0,
                    "first_band": None,
                    "latest_band": None,
                },
                "strongest_criterion": None,
                "weakest_criterion": None,
                "top_error_types": [],
            }

    # ------------------------------------------------------------------
    # Band improvement report (current vs. target criteria comparison)
    # ------------------------------------------------------------------
    def get_band_improvement_report(
        self,
        user_id: str,
        target_band: Optional[float] = None,
        days: Optional[int] = 90,
    ) -> Dict[str, Any]:
        """
        Generate a band improvement report comparing the student's current
        per-criterion bands against the target criterion bands needed to
        reach their target overall band.

        The report is deterministic (no AI) and never raises — it returns
        an empty report when no evaluations exist.
        """
        rows = self._safe_list_evaluations(user_id, None, days=days)
        if not rows:
            return self._empty_improvement_report(user_id)

        latest = rows[0]  # newest first (repo orders by created_at desc)
        current_band = _round_band(float(latest.get("overall_band") or 0.0))
        criteria_bands = latest.get("criteria_bands") or {}
        criteria_detail = latest.get("criteria_detail") or {}

        resolved_target = self._resolve_target_band(user_id, current_band, target_band)
        target_criteria = _target_criterion_bands(resolved_target)

        criteria_results: List[Dict[str, Any]] = []
        for key in CRITERIA_KEYS:
            current = _round_band(float(criteria_bands.get(key, 0.0)))
            target = _round_band(target_criteria.get(key, resolved_target))
            change = round(target - current, 1)
            direction = _direction(change)
            reason = _criterion_reason(key, criteria_detail, direction)
            criteria_results.append({
                "criterion": key,
                "label": CRITERION_SHORT_LABELS.get(key, key),
                "current_band": current,
                "target_band": target,
                "change": change,
                "direction": direction,
                "reason": reason,
            })

        overall_improvement = round(resolved_target - current_band, 1)

        improved = [c for c in criteria_results if c["change"] > 0]
        biggest = max(improved, key=lambda c: c["change"]) if improved else None

        return {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "current_band": current_band,
            "target_band": resolved_target,
            "overall_improvement": overall_improvement,
            "task_type": latest.get("task_type"),
            "total_evaluated_essays": len(rows),
            "criteria": criteria_results,
            "biggest_improvement": biggest,
        }

    def _resolve_target_band(
        self,
        user_id: str,
        current_band: float,
        explicit: Optional[float],
    ) -> float:
        """Resolve the target overall band for the improvement report.

        Priority:
          1. Explicit target_band parameter.
          2. User profile target_band (via diagnostic_roadmap_service).
          3. ``current_band + DEFAULT_TARGET_GAP`` (1.0), capped at 9.0.
        """
        if explicit is not None:
            return _round_band(float(explicit))
        try:
            from app.services.diagnostic_roadmap_service import (
                diagnostic_roadmap_service,
            )
            profile = diagnostic_roadmap_service.resolve_profile(user_id)
            profile_target = profile.get("profile_target_band")
            if profile_target is not None and float(profile_target) >= current_band:
                return _round_band(float(profile_target))
        except Exception:
            pass
        return _round_band(min(9.0, current_band + DEFAULT_TARGET_GAP))

    @staticmethod
    def _empty_improvement_report(user_id: str) -> Dict[str, Any]:
        """Return an empty improvement report when no evaluations exist."""
        return {
            "user_id": user_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "current_band": 0.0,
            "target_band": 0.0,
            "overall_improvement": 0.0,
            "task_type": None,
            "total_evaluated_essays": 0,
            "criteria": [],
            "biggest_improvement": None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _safe_list_evaluations(
        self,
        user_id: str,
        task_type: Optional[str],
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Defensively fetch evaluated essays for analytics."""
        if self.db is None:
            return []
        try:
            return self.repo.list_evaluations(
                user_id, task_type=task_type, limit=MAX_EVALUATIONS, days=days
            )
        except Exception as exc:
            logger.warning("writing analytics list_evaluations failed user=%s: %s", user_id, exc)
            return []

    def _build_band_history_points(
        self,
        rows: List[Dict[str, Any]],
        task_type: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Map evaluation rows to chronological band-history points."""
        points = []
        for row in rows:
            if task_type and row.get("task_type") != task_type:
                continue
            points.append({
                "submission_id": row.get("submission_id") or "",
                "date": self._date_label(row.get("created_at") or row.get("evaluated_at")),
                "overall_band": row.get("overall_band"),
                "task_type": row.get("task_type") or "task_2",
                "confidence": row.get("confidence"),
                "word_count": int(row.get("word_count") or 0),
                "title": self._submission_title(row),
                "is_estimate": bool(row.get("is_estimate", True)),
            })
        points.sort(key=lambda p: p["date"])
        return points

    def _submission_title(self, row: Dict[str, Any]) -> Optional[str]:
        sub = row.get("writing_workspace_submissions") or row.get("submission") or {}
        if sub:
            return sub.get("title") or None
        return row.get("title") or None

    def _submission_time(self, row: Dict[str, Any]) -> int:
        sub = row.get("writing_workspace_submissions") or row.get("submission") or {}
        if sub and sub.get("time_seconds_spent"):
            return int(sub["time_seconds_spent"])
        return int(row.get("time_seconds_spent") or 0)

    def _writing_time(self, row: Dict[str, Any]) -> float:
        return float(self._submission_time(row) or 0)

    def _band_trend(self, points: List[Dict[str, Any]]) -> Optional[str]:
        bands = [p["overall_band"] for p in points if p["overall_band"] is not None]
        return self._trend_from_bands(bands)

    def _trend_from_bands(self, bands: List[float]) -> Optional[str]:
        if len(bands) < 2:
            return None
        first = bands[0]
        last = bands[-1]
        delta = last - first
        if delta >= TREND_BAND_THRESHOLD:
            return "improving"
        if delta <= -TREND_BAND_THRESHOLD:
            return "declining"
        return "stable"

    def _sub_avg_band(
        self, rows: List[Dict[str, Any]], task_type: str
    ) -> Optional[float]:
        bands = [
            float(r["overall_band"])
            for r in rows
            if r.get("overall_band") is not None and r.get("task_type") == task_type
        ]
        return round(sum(bands) / len(bands), 2) if bands else None

    def _date_label(self, iso: Optional[str]) -> str:
        if not iso:
            return ""
        raw = str(iso)[:10]
        return "".join(ch for ch in raw if ch.isdigit() or ch == "-")

    def _criterion_summary(self, item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not item:
            return {
                "criterion": None,
                "label": None,
                "short_label": None,
                "average_band": 0.0,
                "latest_band": None,
                "best_band": 0.0,
                "submissions_count": 0,
            }
        key = item["criterion"]
        return {
            "criterion": key,
            "label": item.get("label") or CRITERION_LABELS.get(key, key),
            "short_label": CRITERION_SHORT_LABELS.get(key, key),
            "average_band": item.get("average_band") or 0.0,
            "latest_band": item.get("latest_band"),
            "best_band": item.get("best_band") or 0.0,
            "submissions_count": item.get("submissions_count") or 0,
        }

    @staticmethod
    def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
        """Return (slope, r_squared) for a simple linear fit."""
        n = len(xs)
        if n < 2:
            return 0.0, 0.0
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        den = sum((x - x_mean) ** 2 for x in xs)
        if den == 0:
            return 0.0, 0.0
        slope = num / den
        r_sq = 0.0
        sst = sum((y - y_mean) ** 2 for y in ys)
        if sst > 0:
            intercept = y_mean - slope * x_mean
            ssr = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
            r_sq = 1.0 - (ssr / sst)
        return slope, max(0.0, r_sq)

    def _build_trend_points(
        self,
        rows: List[Dict[str, Any]],
        days: int,
    ) -> List[Dict[str, Any]]:
        """Bucket evaluations by day and return band / word-count / time series."""
        if days is None or days <= 0:
            days = 30
        buckets: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            label = self._date_label(row.get("created_at") or row.get("evaluated_at"))
            if not label:
                continue
            b = buckets.setdefault(
                label,
                {
                    "date": label,
                    "label": label,
                    "band_sum": 0.0,
                    "band_count": 0,
                    "wc_sum": 0,
                    "wc_count": 0,
                    "time_sum": 0.0,
                    "time_count": 0,
                    "essay_count": 0,
                },
            )
            b["essay_count"] += 1
            band = row.get("overall_band")
            if band is not None:
                b["band_sum"] += float(band)
                b["band_count"] += 1
            wc = int(row.get("word_count") or 0)
            if wc > 0:
                b["wc_sum"] += wc
                b["wc_count"] += 1
            wt = self._writing_time(row)
            if wt > 0:
                b["time_sum"] += wt
                b["time_count"] += 1

        today = date.today()
        points = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            label = d.isoformat()
            b = buckets.get(label)
            if b:
                points.append({
                    "date": label,
                    "label": label,
                    "band": round(b["band_sum"] / b["band_count"], 2) if b["band_count"] else None,
                    "word_count": round(b["wc_sum"] / b["wc_count"], 1) if b["wc_count"] else None,
                    "writing_time_minutes": round(b["time_sum"] / b["time_count"] / 60, 1) if b["time_count"] else None,
                    "essay_count": b["essay_count"],
                })
            else:
                points.append({
                    "date": label,
                    "label": label,
                    "band": None,
                    "word_count": None,
                    "writing_time_minutes": None,
                    "essay_count": 0,
                })
        return points

    def _build_essay_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Map a submission row (with nested evaluations) to an essay record."""
        evals = row.get("writing_evaluations")
        evaluation = None
        if isinstance(evals, list) and evals:
            evaluation = evals[0]
        elif isinstance(evals, dict) and evals:
            evaluation = evals

        task_type = row.get("task_type") or "task_2"
        task_label = "Task 1" if task_type == "task_1" else "Task 2"

        criteria = []
        overall = None
        confidence = None
        strengths: List[str] = []
        weaknesses: List[str] = []
        error_count = 0

        if evaluation:
            overall = evaluation.get("overall_band")
            confidence = evaluation.get("confidence")
            strengths = list((evaluation.get("strengths") or [])[:5])
            weaknesses = list((evaluation.get("weaknesses") or [])[:5])
            ea = evaluation.get("error_analysis") or []
            if isinstance(ea, dict):
                ea = ea.get("errors", []) or []
            error_count = len([e for e in ea if isinstance(e, dict)])
            cb = evaluation.get("criteria_bands") or {}
            for key in CRITERIA_KEYS:
                b = cb.get(key)
                if b is None:
                    detail = (evaluation.get("criteria_detail") or {}).get(key) or {}
                    b = detail.get("band")
                label = CRITERION_LABELS.get(key, key)
                if task_type == "task_1" and key == "task_response":
                    label = "Task Achievement"
                criteria.append({
                    "key": key,
                    "label": label,
                    "band": float(b) if b is not None else 0.0,
                })

        return {
            "id": row.get("id") or "",
            "evaluation_id": evaluation.get("id") if evaluation else None,
            "title": row.get("title") or None,
            "prompt_text": row.get("prompt_text") or None,
            "task_type": task_type,
            "task_label": task_label,
            "word_count": int(row.get("word_count") or 0),
            "time_seconds_spent": int(row.get("time_seconds_spent") or 0),
            "status": row.get("status") or "draft",
            "evaluation_status": (
                evaluation.get("status")
                if evaluation
                else ("pending" if row.get("status") == "submitted" else "not_submitted")
            ),
            "overall_band": overall,
            "confidence": confidence,
            "is_estimate": bool((evaluation or {}).get("is_estimate", True)),
            "criteria": criteria,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "error_count": error_count,
            "submitted_at": row.get("submitted_at"),
            "evaluated_at": evaluation.get("evaluated_at") if evaluation else None,
            "created_at": row.get("created_at"),
        }


# ---------------------------------------------------------------------------
# Band improvement report helpers (module-level, pure / testable)
# ---------------------------------------------------------------------------
def _target_criterion_bands(target_band: float) -> Dict[str, float]:
    """Derive target per-criterion bands for a given overall target band."""
    key = _round_band(target_band)
    mapped = BAND_CRITERION_TARGETS.get(key)
    if mapped:
        return dict(mapped)
    return {k: key for k in CRITERIA_KEYS}


def _criterion_reason(
    criterion_key: str,
    criteria_detail: Dict[str, Any],
    direction: str,
) -> str:
    """Derive a concise reason for a criterion's band change.

    Searches the evaluation's per-criterion ``weakness`` / ``suggestions`` text
    for keywords that map to short, human-friendly labels.  Falls back to a
    generic phrase when no keyword matches.
    """
    if direction == "maintained":
        return "Maintained"

    detail = (criteria_detail or {}).get(criterion_key) or {}
    if direction == "improving":
        weakness = detail.get("weakness", "") or ""
        suggestions = detail.get("suggestions", []) or []
        if not isinstance(suggestions, str):
            suggestions = " ".join(str(s) for s in suggestions)
        text = f"{weakness} {suggestions}".lower()
    else:  # declining
        text = (detail.get("strength", "") or "").lower()

    keywords = _CRITERION_REASON_KEYWORDS.get(criterion_key, [])
    for kw, reason in keywords:
        if kw in text:
            return reason

    # Generic fallback based on the criterion.
    label = CRITERION_SHORT_LABELS.get(criterion_key, criterion_key).lower()
    if direction == "improving":
        return f"Improved {label}"
    return "Needs attention"


# Singleton bound to the shared DB session.
from app.db.session import db_session

writing_analytics_service = WritingAnalyticsService(db_session)