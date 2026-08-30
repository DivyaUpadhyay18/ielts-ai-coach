"""
Speaking Progress Analytics Service.

Computes Speaking Progress Analytics metrics from stored evaluation,
practice-session, error-analysis, and test-response data.

Metrics:
  - Speaking Band History       (chronological overall + per-criterion bands)
  - Fluency / Lexical / Grammar / Pronunciation History
  - Average Speaking Duration
  - Average Filler Words
  - Common Grammar Errors
  - Common Vocabulary Errors
  - Strongest / Weakest Criterion
  - Improvement Rate (linear regression slope)
  - Attempt History (chronological with error counts + fillers)

All DB access is defensive (safe wrappers return empty values) so the
service never crashes a request because of a missing table or transient
read failure — mirroring the writing_analytics_service / prediction_engine.

The service integrates with:
  - Dashboard           (single comprehensive payload)
  - AI Mentor           (weakness data for mentor context)
  - Readiness Score     (criterion averages + improvement rate)
  - Band Prediction     (trend slopes as features)
  - Adaptive Scheduler  (strongest/weakest for exercise recommendation)
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.session import DatabaseSession
from app.repositories.speaking_analytics_repo import SpeakingAnalyticsRepository

logger = logging.getLogger(__name__)

# IELTS Speaking criteria (display order).
SPEAKING_CRITERIA_KEYS = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range",
    "pronunciation",
)

CRITERION_LABELS = {
    "fluency_coherence": "Fluency & Coherence",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammatical Range & Accuracy",
    "pronunciation": "Pronunciation",
}

CRITERION_SHORT_LABELS = {
    "fluency_coherence": "Fluency",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammar",
    "pronunciation": "Pronunciation",
}

# Filler word patterns for deterministic counting.
_FILLER_PATTERN = re.compile(
    r"\b(um|uh|er|ah|like|you know|i mean|so|well|actually|basically|literally)\b",
    re.IGNORECASE,
)

# Common grammar error patterns (from evaluation feedback or error analysis).
_GRAMMAR_ERROR_KEYWORDS = (
    "tense", "subject-verb", "article", "auxiliary", "preposition",
    "plural", "singular", "word order", "conditional", "passive",
)

# Common vocabulary error patterns.
_VOCAB_ERROR_KEYWORDS = (
    "informal", "collocation", "word choice", "synonym",
    "repetition", "memorised", "formal",
)


class SpeakingAnalyticsService:
    """
    Service for Speaking Progress Analytics.

    All operations are read-only and owner-scoped.  Defensive DB access
    ensures graceful degradation when tables are unreachable.
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db
        self.repo = SpeakingAnalyticsRepository(db)

    # ------------------------------------------------------------------
    # Dashboard (single comprehensive payload)
    # ------------------------------------------------------------------
    def get_dashboard(
        self,
        user_id: str,
        days: int = 90,
        part: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the full Speaking Progress Analytics dashboard."""
        band_history = self._band_history(user_id, days, part)
        metrics = self._metrics(user_id, days, part)
        common_errors = self._common_errors(user_id, days)
        strongest = metrics["strongest_criterion"] or None
        weakest = metrics["weakest_criterion"] or None
        improvement = self._improvement_rate(user_id, days, part, "overall")
        attempt_history = self._attempt_history(user_id, days)

        return {
            "band_history": band_history,
            "metrics": metrics,
            "common_errors": common_errors,
            "strongest_criterion": strongest,
            "weakest_criterion": weakest,
            "improvement_rate": improvement,
            "attempt_history": attempt_history,
            "total_evaluations": metrics["total_evaluations"],
        }

    # ------------------------------------------------------------------
    # Band History
    # ------------------------------------------------------------------
    def band_history(
        self,
        user_id: str,
        days: int = 90,
        part: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Speaking Band History — chronological overall + per-criterion bands."""
        return {"results": self._band_history(user_id, days, part), "total": len(self._band_history(user_id, days, part))}

    def _band_history(
        self, user_id: str, days: Optional[int] = None, part: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Internal: compute band history points from evaluations + practice sessions."""
        points = []

        # From speaking_evaluations
        for eval_row in self._safe_evaluations(user_id, days, part):
            criteria = eval_row.get("criteria") or {}
            points.append({
                "evaluation_id": eval_row.get("id"),
                "date": self._date_from(eval_row.get("created_at")),
                "overall_band": float(b) if (b := eval_row.get("overall_band")) else None,
                "fluency_coherence_band": self._safe_band(criteria.get("fluency_coherence")),
                "lexical_resource_band": self._safe_band(criteria.get("lexical_resource")),
                "grammatical_range_band": self._safe_band(criteria.get("grammatical_range")),
                "pronunciation_band": self._safe_band(criteria.get("pronunciation")),
                "part": eval_row.get("part", "part_1"),
                "title": eval_row.get("title") or eval_row.get("speaking_test_responses", {}).get("title", ""),
                "confidence": self._safe_float(eval_row.get("confidence")),
            })

        # From speaking_practice_sessions (evaluated)
        for sess in self._safe_practice_sessions(user_id, days, part):
            points.append({
                "evaluation_id": sess.get("id"),
                "date": self._date_from(sess.get("created_at")),
                "overall_band": self._safe_float(sess.get("overall_band")),
                "fluency_coherence_band": self._safe_float(sess.get("fluency_coherence_band")),
                "lexical_resource_band": self._safe_float(sess.get("lexical_resource_band")),
                "grammatical_range_band": self._safe_float(sess.get("grammatical_range_band")),
                "pronunciation_band": self._safe_float(sess.get("pronunciation_band")),
                "part": sess.get("part", "part_1"),
                "title": sess.get("title", sess.get("prompt_text", "")),
                "confidence": None,
            })

        # Sort chronological (oldest first).
        points.sort(key=lambda p: p.get("date") or "")
        return points

    # ------------------------------------------------------------------
    # Criterion History
    # ------------------------------------------------------------------
    def criterion_history(
        self,
        user_id: str,
        criterion: str,
        days: int = 90,
        part: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Per-criterion band history."""
        if criterion not in CRITERION_LABELS:
            criterion = "fluency_coherence"
        label = CRITERION_LABELS[criterion]

        points = []
        for hp in self._band_history(user_id, days, part):
            field = f"{criterion}_band"
            points.append({
                "evaluation_id": hp["evaluation_id"],
                "date": hp["date"],
                "band": hp.get(field),
                "part": hp["part"],
                "title": hp.get("title"),
            })

        return {
            "criterion": criterion,
            "label": label,
            "results": points,
            "total": len(points),
        }

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def metrics(
        self,
        user_id: str,
        days: int = 90,
        part: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate speaking metrics."""
        return self._metrics(user_id, days, part)

    def _metrics(
        self, user_id: str, days: Optional[int] = None, part: Optional[str] = None
    ) -> Dict[str, Any]:
        """Internal: compute aggregate metrics."""
        points = self._band_history(user_id, days, part)
        total = len(points)

        bands = [p["overall_band"] for p in points if p.get("overall_band") is not None]
        fluency = [p["fluency_coherence_band"] for p in points if p.get("fluency_coherence_band") is not None]
        lexical = [p["lexical_resource_band"] for p in points if p.get("lexical_resource_band") is not None]
        grammar = [p["grammatical_range_band"] for p in points if p.get("grammatical_range_band") is not None]
        pronunciation = [p["pronunciation_band"] for p in points if p.get("pronunciation_band") is not None]

        avg_overall = self._avg(bands)
        avg_fluency = self._avg(fluency)
        avg_lexical = self._avg(lexical)
        avg_grammar = self._avg(grammar)
        avg_pron = self._avg(pronunciation)

        avg_bands = {
            "fluency_coherence": avg_fluency,
            "lexical_resource": avg_lexical,
            "grammatical_range": avg_grammar,
            "pronunciation": avg_pron,
        }

        strongest = self._strongest_criterion_from_bands(avg_bands)
        weakest = self._weakest_criterion_from_bands(avg_bands)

        # Duration from test responses.
        avg_duration = self._average_duration(user_id, days)

        # Filler words from practice sessions + error analysis.
        avg_fillers = self._average_fillers(user_id, days)

        return {
            "total_evaluations": total,
            "average_band": avg_overall,
            "average_fluency_band": avg_fluency,
            "average_lexical_band": avg_lexical,
            "average_grammar_band": avg_grammar,
            "average_pronunciation_band": avg_pron,
            "average_duration": avg_duration,
            "average_filler_words": avg_fillers,
            "strongest_criterion": strongest,
            "strongest_criterion_label": CRITERION_LABELS.get(strongest, strongest) if strongest else None,
            "weakest_criterion": weakest,
            "weakest_criterion_label": CRITERION_LABELS.get(weakest, weakest) if weakest else None,
        }

    # ------------------------------------------------------------------
    # Common Errors
    # ------------------------------------------------------------------
    def common_errors(
        self, user_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Common grammar and vocabulary errors from error analysis."""
        return self._common_errors(user_id, days)

    def _common_errors(self, user_id: str, days: Optional[int] = None) -> Dict[str, Any]:
        """Internal: compute common grammar/vocabulary errors."""
        grammar_counts: Dict[str, int] = {}
        vocab_counts: Dict[str, int] = {}

        # From speaking_error_analysis issues
        for ea in self._safe_error_analysis(user_id, days):
            issues = ea.get("issues") or []
            for issue in issues:
                issue_type = issue.get("issue_type", "")
                explanation = issue.get("explanation", "")
                combined = f"{issue_type} {explanation}".lower()

                if issue_type in ("Grammar", "Grammatical Range"):
                    for kw in _GRAMMAR_ERROR_KEYWORDS:
                        if kw in combined:
                            grammar_counts[kw] = grammar_counts.get(kw, 0) + 1
                elif issue_type in ("Vocabulary", "Weak Vocabulary", "Repeated Vocabulary"):
                    for kw in _VOCAB_ERROR_KEYWORDS:
                        if kw in combined:
                            vocab_counts[kw] = vocab_counts.get(kw, 0) + 1

                # Also check explanation text for patterns
                if issue_type == "Grammar":
                    for kw in _GRAMMAR_ERROR_KEYWORDS:
                        if kw in combined:
                            grammar_counts[kw] = grammar_counts.get(kw, 0) + 1
                elif issue_type in ("Vocabulary", "Weak Vocabulary", "Repeated Vocabulary"):
                    for kw in _VOCAB_ERROR_KEYWORDS:
                        if kw in combined:
                            vocab_counts[kw] = vocab_counts.get(kw, 0) + 1

        # Sort and format
        sorted_grammar = sorted(grammar_counts.items(), key=lambda x: x[1], reverse=True)
        sorted_vocab = sorted(vocab_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "common_grammar_errors": [{"error": k, "count": v} for k, v in sorted_grammar[:10]],
            "common_vocabulary_errors": [{"error": k, "count": v} for k, v in sorted_vocab[:10]],
            "total_grammar_errors": sum(grammar_counts.values()),
            "total_vocabulary_errors": sum(vocab_counts.values()),
        }

    # ------------------------------------------------------------------
    # Strongest / Weakest Criterion
    # ------------------------------------------------------------------
    def strongest_criterion(
        self, user_id: str, days: int = 90, part: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return the user's strongest speaking criterion."""
        m = self._metrics(user_id, days, part)
        key = "fluent"
        return {"criterion": m["strongest_criterion"], "label": m["strongest_criterion_label"]}

    def weakest_criterion(
        self, user_id: str, days: int = 90, part: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return the user's weakest speaking criterion."""
        m = self._metrics(user_id, days, part)
        return {"criterion": m["weakest_criterion"], "label": m["weakest_criterion_label"]}

    # ------------------------------------------------------------------
    # Improvement Rate
    # ------------------------------------------------------------------
    def improvement_rate(
        self, user_id: str, days: int = 90, criterion: str = "overall",
        part: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute the improvement rate (slope) for a criterion or overall band."""
        return self._improvement_rate(user_id, days, part, criterion)

    def _improvement_rate(
        self,
        user_id: str,
        days: Optional[int] = None,
        part: Optional[str] = None,
        criterion: str = "overall",
    ) -> Dict[str, Any]:
        """Internal: compute linear regression slope of band vs. chronological order."""
        points = self._band_history(user_id, days, part)

        if criterion == "overall":
            label = "Overall Band"
            values = [p.get("overall_band") for p in points if p.get("overall_band") is not None]
        else:
            label = CRITERION_LABELS.get(criterion, criterion)
            field = f"{criterion}_band"
            values = [p.get(field) for p in points if p.get(field) is not None]

        if len(values) < 2:
            return {
                "criterion": criterion,
                "label": label,
                "improvement_rate": 0.0,
                "total_points": len(values),
                "first_band": values[0] if values else None,
                "latest_band": values[-1] if values else None,
                "trend": "stable",
            }

        slope = self._linear_slope(values)
        first_band = values[0]
        latest_band = values[-1]

        if slope > 0.1:
            trend = "improving"
        elif slope < -0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "criterion": criterion,
            "label": label,
            "improvement_rate": round(slope, 2),
            "total_points": len(values),
            "first_band": first_band,
            "latest_band": latest_band,
            "trend": trend,
        }

    # ------------------------------------------------------------------
    # Attempt History
    # ------------------------------------------------------------------
    def attempt_history(
        self, user_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Full attempt history with durations, errors, and fillers."""
        return {"results": self._attempt_history(user_id, days), "total": len(self._attempt_history(user_id, days))}

    def _attempt_history(
        self, user_id: str, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Internal: compute attempt history from evaluations + practice sessions."""
        items = []

        for eval_row in self._safe_evaluations(user_id, days):
            responses = eval_row.get("speaking_test_responses") or {}
            items.append({
                "evaluation_id": eval_row.get("id"),
                "date": self._date_from(eval_row.get("created_at")),
                "overall_band": self._safe_float(eval_row.get("overall_band")),
                "part": eval_row.get("part", "part_1"),
                "title": responses.get("title", ""),
                "error_count": 0,
                "filler_words": 0,
                "duration_seconds": responses.get("duration_seconds", 0),
                "confidence": self._safe_float(eval_row.get("confidence")),
                "source": eval_row.get("source"),
            })

        for sess in self._safe_practice_sessions(user_id, days):
            items.append({
                "evaluation_id": sess.get("id"),
                "date": self._date_from(sess.get("created_at")),
                "overall_band": self._safe_float(sess.get("overall_band")),
                "part": sess.get("part", "part_1"),
                "title": sess.get("title", sess.get("prompt_text", "")),
                "error_count": sess.get("error_count", 0),
                "filler_words": sess.get("filler_words_count", 0),
                "duration_seconds": sess.get("duration_seconds", 0),
                "confidence": None,
                "source": "practice",
            })

        items.sort(key=lambda i: i.get("date") or "", reverse=True)
        return items

    # ------------------------------------------------------------------
    # Integration helper
    # ------------------------------------------------------------------
    def dashboard_brief(
        self,
        user_id: str,
        days: int = 90,
    ) -> Dict[str, Any]:
        """
        Compact speaking-analytics snapshot for the AI Mentor / mission system.

        Never raises — returns honest empty values when there is no data yet.
        """
        try:
            metrics = self._metrics(user_id, days, None)
            improvement = self._improvement_rate(user_id, days, None, "overall")
            strongest = metrics["strongest_criterion"]
            weakest = metrics["weakest_criterion"]
            errors = self._common_errors(user_id, days)
            history = self._attempt_history(user_id, days)
            return {
                "has_speaking_data": metrics["total_evaluations"] > 0,
                "total_evaluations": metrics["total_evaluations"],
                "average_band": metrics["average_band"],
                "average_duration": metrics["average_duration"],
                "average_filler_words": metrics["average_filler_words"],
                "average_fluency_band": metrics["average_fluency_band"],
                "average_lexical_band": metrics["average_lexical_band"],
                "average_grammar_band": metrics["average_grammar_band"],
                "average_pronunciation_band": metrics["average_pronunciation_band"],
                "strongest_criterion": strongest,
                "strongest_criterion_label": metrics["strongest_criterion_label"],
                "weakest_criterion": weakest,
                "weakest_criterion_label": metrics["weakest_criterion_label"],
                "improvement": {
                    "slope": improvement["improvement_rate"],
                    "direction": improvement["trend"],
                    "first_band": improvement["first_band"],
                    "latest_band": improvement["latest_band"],
                },
                "common_errors": {
                    "grammar": errors["common_grammar_errors"][:5],
                    "vocabulary": errors["common_vocabulary_errors"][:5],
                },
                "recent_attempts": history[:5],
            }
        except Exception as exc:
            logger.warning("speaking analytics brief failed user=%s: %s", user_id, exc)
            return {"has_speaking_data": False}

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------
    def get_weaknesses_summary(
        self, user_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Return a weaknesses summary for AI Mentor integration."""
        m = self._metrics(user_id, days)
        return {
            "weakest_criterion": m["weakest_criterion"],
            "weakest_criterion_label": m["weakest_criterion_label"],
            "weakest_band": m.get(f"average_{m['weakest_criterion']}_band") if m["weakest_criterion"] else None,
            "total_evaluations": m["total_evaluations"],
            "average_band": m["average_band"],
            "trend": self._improvement_rate(user_id, days, criterion=m["weakest_criterion"] or "overall")["trend"],
        }

    def get_readiness_factors(
        self, user_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Return factors for Readiness Score integration."""
        m = self._metrics(user_id, days)
        avg_overall = m["average_band"] or 0
        # Readiness proxy: average band >= target (default 6.5) AND positive trend
        improvement = self._improvement_rate(user_id, days)
        return {
            "speaking_average_band": avg_overall,
            "speaking_weakest_criterion": m["weakest_criterion"],
            "speaking_strongest_criterion": m["strongest_criterion"],
            "speaking_improvement_trend": improvement["trend"],
            "speaking_total_evaluations": m["total_evaluations"],
            "speaking_avg_fillers": m["average_filler_words"],
        }

    def get_prediction_features(
        self, user_id: str, days: int = 90
    ) -> Dict[str, Any]:
        """Return features for Band Prediction integration."""
        m = self._metrics(user_id, days)
        return {
            "speaking_avg_band": m["average_band"],
            "speaking_avg_fluency": m["average_fluency_band"],
            "speaking_avg_lexical": m["average_lexical_band"],
            "speaking_avg_grammar": m["average_grammar_band"],
            "speaking_avg_pronunciation": m["average_pronunciation_band"],
            "speaking_total_evaluations": m["total_evaluations"],
            "speaking_improvement_rate": self._improvement_rate(user_id, days)["improvement_rate"],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _safe_evaluations(
        self, user_id: str, days: Optional[int] = None, part: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.list_evaluations(user_id, part=part, limit=500, days=days)
        except Exception as exc:
            logger.warning("speaking analytics evaluations read failed: %s", exc)
            return []

    def _safe_practice_sessions(
        self, user_id: str, days: Optional[int] = None, part: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.list_practice_sessions(user_id, limit=500, days=days)
        except Exception as exc:
            logger.warning("speaking analytics practice read failed: %s", exc)
            return []

    def _safe_error_analysis(
        self, user_id: str, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.list_error_analysis(user_id, limit=500, days=days)
        except Exception as exc:
            logger.warning("speaking analytics error analysis read failed: %s", exc)
            return []

    def _average_duration(
        self, user_id: str, days: Optional[int] = None
    ) -> Optional[float]:
        if self.db is None:
            return None
        try:
            sessions = self._safe_practice_sessions(user_id, days)
            # Also check test responses for durations.
            evaluations = self._safe_evaluations(user_id, days)
            durations = []
            for sess in sessions:
                d = sess.get("duration_seconds")
                if d:
                    durations.append(float(d))
            for ev in evaluations:
                responses = ev.get("speaking_test_responses") or {}
                d = responses.get("duration_seconds")
                if d:
                    durations.append(float(d))
            return self._avg(durations)
        except Exception:
            return None

    def _average_fillers(
        self, user_id: str, days: Optional[int] = None
    ) -> Optional[float]:
        """Average filler word count per response."""
        counts = []

        # From practice sessions (pre-computed filler_words_count).
        for sess in self._safe_practice_sessions(user_id, days):
            f = sess.get("filler_words_count")
            if f is not None:
                counts.append(float(f))

        # From test responses (count fillers in transcript).
        for resp in self._safe_test_responses(user_id, days):
            transcript = resp.get("transcript", "")
            if transcript:
                counts.append(self._count_fillers(transcript))

        # From error analysis (Filler Words issue count).
        for ea in self._safe_error_analysis(user_id, days):
            issues = ea.get("issues") or []
            fcount = sum(1 for i in issues if i.get("issue_type") == "Filler Words")
            if fcount:
                counts.append(float(fcount))

        return self._avg(counts)

    def _safe_test_responses(
        self, user_id: str, days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if self.db is None:
            return []
        try:
            return self.repo.list_test_responses(user_id, limit=500)
        except Exception as exc:
            logger.warning("speaking analytics test responses read failed: %s", exc)
            return []

    def _count_fillers(self, text: str) -> int:
        """Count filler words in a transcript."""
        if not text:
            return 0
        return len(_FILLER_PATTERN.findall(text))

    @staticmethod
    def _safe_band(val) -> Optional[float]:
        if val is None:
            return None
        try:
            f = float(val)
            return round(f, 1) if 0 <= f <= 9 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    @staticmethod
    def _date_from(ts) -> str:
        if not ts:
            return ""
        try:
            return str(ts)[:10] if len(str(ts)) >= 10 else str(ts)
        except Exception:
            return ""

    @staticmethod
    def _linear_slope(values: List[float]) -> float:
        """Simple linear regression slope of values vs. their index order."""
        n = len(values)
        if n < 2:
            return 0.0
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        den = sum((xi - x_mean) ** 2 for xi in x)
        return num / den if den else 0.0

    @staticmethod
    def _strongest_criterion_from_bands(bands: Dict[str, Optional[float]]) -> Optional[str]:
        valid = {k: v for k, v in bands.items() if v is not None}
        if not valid:
            return None
        return max(valid, key=valid.get)

    @staticmethod
    def _weakest_criterion_from_bands(bands: Dict[str, Optional[float]]) -> Optional[str]:
        valid = {k: v for k, v in bands.items() if v is not None}
        if not valid:
            return None
        return min(valid, key=valid.get)
