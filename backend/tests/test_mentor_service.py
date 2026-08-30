"""
Test suite for the AI Mentor service.

The AI Mentor behaves like an experienced IELTS tutor that coaches the student
inside their EXISTING study roadmap — it never generates a study plan from
scratch. These tests validate the deterministic coaching engine (no AI needed):

    1. Guardrail contract — the mentor never proposes a new plan.
    2. Context gathering — the learner snapshot is shaped correctly.
    3. Roadmap-missing → generates_roadmap directive (never an auto plan).
    4. Daily coaching — good-day vs missed-tasks branches + deterministic tone.
    5. Mode rendering — daily / roadmap_analysis / risk_check / ask_mentor.
    6. Prediction integration — readiness / risk / tone selection.
    7. Crunch window + mock-readiness windows.
    8. LLM polish failure → deterministic template fallback.
    9. Persistence safety — nothing crashes with db=None; history is empty.
   10. Pydantic model contracts.

The service is designed to be testable with ``db=None``: every DB call is a
defensive ``_safe_*`` helper returning an empty value, so the whole pipeline
runs end-to-end without Supabase.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from contextlib import contextmanager

from app.core.exceptions import NotFoundError
from app.services import ai_mentor_service as mentor_module
from app.services.ai_mentor_service import AIMentorService, MISSED_HIGH_THRESHOLD
from app.models.mentor import (
    CoachRequest,
    AskRequest,
    MentorGuardrails,
    MentorConversationListResponse,
)

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------
FAR_EXAM = "2099-01-01"  # very large days_remaining -> no crunch / no near-exam

BASE_PROFILE = {
    "id": "u-1",
    "full_name": "Divya Patel",
    "module": "academic",
    "plan": "free",
    "daily_minutes_budget": 90,
    "current_band": 7.0,
    "target_band": 7.5,
    "exam_date": FAR_EXAM,
    "weakest_skill": ["writing"],
    "strongest_skill": ["reading"],
}

BASE_DIAG = {
    "source": "diagnostic",
    "has_diagnostic": True,
    "attempt_id": "att-1",
    "current_band": 7.0,
    "target_band": 7.5,
    "profile_exam_date": FAR_EXAM,
    "weakest_skills": ["writing"],
    "strongest_skills": ["reading"],
    "skill_bands": {"reading": 7.0, "listening": 7.0, "writing": 6.5, "speaking": 7.0},
}

BASE_PLAN = {
    "id": "plan-1",
    "title": "IELTS Academic -> 7.5",
    "version": 1,
    "status": "active",
    "start_date": "2020-01-01",
    "exam_date": FAR_EXAM,
}


def _task(task_id, title, status="completed", skill="reading",
          task_type="general", scheduled_date=None, priority=1):
    return {
        "id": task_id, "title": title, "status": status, "skill": skill,
        "task_type": task_type, "scheduled_date": scheduled_date, "priority": priority,
    }


def _progress_tasks(completed=4, total=10):
    tasks = [_task(f"c{i}", f"Task {i}", status="completed") for i in range(completed)]
    tasks += [_task(f"p{i}", f"Pending {i}", status="pending",
                    scheduled_date=(date.today() + timedelta(days=30)).isoformat())
              for i in range(total - completed)]
    return tasks


class _FakePrediction:
    """Stand-in for the prediction_engine_service singleton."""

    def __init__(self, payload):
        self.payload = payload

    def get_prediction(self, user_id, run_date=None):
        return self.payload


@contextmanager
def _with_prediction(payload):
    """Patch the mentor's prediction_engine_service with a controlled payload."""
    fake = _FakePrediction(payload)
    with patch.object(mentor_module, "prediction_engine_service", fake):
        yield


class _BrokenHTTPClient:
    """An httpx.Client stand-in that always raises (simulates LLM failure)."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *a, **k):
        raise RuntimeError("LLM polish endpoint unavailable")


def _make_service(plan=None, profile=None, diag=None, tasks=None, state=None,
                  day_stats=None, week=None, active_days=30, recent_sessions=None,
                  adjustments=None):
    """
    Build an AIMentorService(db=None) with the defensive _safe_* helpers wired
    to deterministic learner data. No real DB / Supabase required.
    """
    svc = AIMentorService(db=None)
    svc._safe_get_profile = lambda uid: profile if profile is not None else BASE_PROFILE
    svc._safe_resolve_profile = lambda uid: diag if diag is not None else BASE_DIAG
    svc._safe_get_active_plan = lambda uid: plan
    svc._safe_list_tasks = lambda uid, pid: tasks if tasks is not None else []
    svc._safe_get_progress_state = lambda uid: state or {}
    svc._safe_get_day_stats = lambda uid, day: day_stats or {}
    svc._safe_get_period_progress = lambda uid, s, e: week or {}
    svc._safe_count_active_days = lambda uid: active_days
    svc._safe_get_history = lambda uid, limit: recent_sessions or []
    svc._safe_list_adjustments = lambda uid, limit: adjustments or []
    return svc


@pytest.fixture(autouse=True)
def _no_openai_key(monkeypatch):
    """No OPENAI_API_KEY in tests -> _llm_polish returns None -> template used."""
    monkeypatch.setattr(mentor_module.settings, "OPENAI_API_KEY", None, raising=False)


# ---------------------------------------------------------------------------
# 1. Guardrail contract — the heart of the mentor
# ---------------------------------------------------------------------------
class TestGuardrails:
    """The mentor NEVER generates a study plan; it coaches the existing one."""

    def test_guardrails_always_present_and_contractual(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")

        g = result["guardrails"]
        assert g["never_generates_plan"] is True
        assert g["plan_generation_triggered"] is False
        assert g["analysis_source"] == "existing_roadmap"
        assert "never" in g["note"].lower()

    def test_coaching_message_never_proposes_a_new_plan(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN)
            result = svc.coach("u-1", mode="daily_coaching")

        message = result["message"]["content"].lower()
        assert "create a new plan" not in message
        assert "invent a new plan" not in message
        assert "generate a plan for you" not in message

    def test_roadmap_missing_directive_is_generate_roadmap_not_auto_build(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")

        assert "roadmap_missing" in [i["type"] for i in result["insights"]]
        actions = [d["action"] for d in result["directives"]]
        assert "generate_roadmap" in actions
        gen = next(d for d in result["directives"] if d["action"] == "generate_roadmap")
        # The directive must tell the student to build it themselves, not that
        # the mentor did it for them.
        assert "you" in gen["detail"].lower() or "your" in gen["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Context gathering
# ---------------------------------------------------------------------------
class TestContextGathering:
    def test_get_context_returns_full_learner_snapshot(self):
        with _with_prediction({"has_prediction": True,
                               "estimated_band": 7.2,
                               "readiness_score": 65.0,
                               "risk_level": "low",
                               "preparation_percentage": 50,
                               "completion_rate": 60.0,
                               "study_consistency": 70.0}):
            svc = _make_service(plan=BASE_PLAN,
                                tasks=[_task("t1", "Reading Q1"),
                                       _task("t2", "Writing Task 1", status="completed")])
            ctx = svc.get_context("u-1")

        for key in ("profile", "exam", "roadmap", "study_history",
                    "missed_tasks", "prediction", "band_gap", "skill_labels"):
            assert key in ctx
        assert ctx["profile"]["target_band"] == 7.5
        assert ctx["profile"]["has_diagnostic"] is True
        assert ctx["roadmap"]["has_active_plan"] is True
        assert ctx["band_gap"] == pytest.approx(0.5)
        assert ctx["prediction"]["readiness_score"] == 65.0
        assert ctx["skill_labels"]["writing"] == "Writing"

    def test_get_context_without_profile_raises_not_found(self):
        # db=None -> _safe_get_profile returns None -> user must exist to coach.
        svc = AIMentorService(db=None)
        with pytest.raises(NotFoundError):
            svc.get_context("unknown-user")


# ---------------------------------------------------------------------------
# 3. Daily coaching: good-day branch
# ---------------------------------------------------------------------------
class TestDailyCoaching:
    def test_good_day_renders_encouraging_message(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(
                plan=BASE_PLAN,
                tasks=_progress_tasks(completed=4, total=10),
                state={"current_streak": 0},
                day_stats={"minutes": 45, "tasks_completed": 1},
                week={"minutes": 400, "percent": 63},
                active_days=30,
            )
            result = svc.coach("u-1", mode="daily_coaching")

        assert result["mode"] == "daily_coaching"
        assert result["message"]["role"] == "mentor"
        assert result["message"]["content"]
        assert result["message"]["tone"] in ("encouraging", "firm", "neutral")
        assert result["message"]["generated_by"] == "template"
        assert not any(i["type"] == "roadmap_missing" for i in result["insights"])
        assert "roadmap" in result["message"]["content"].lower()

    def test_coach_with_message_stores_user_turn(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching", message="Hi coach")
        assert result["message"]["content"]
        assert result["guardrails"]["never_generates_plan"] is True


# ---------------------------------------------------------------------------
# 4. Daily coaching: missed-tasks branch
# ---------------------------------------------------------------------------
class TestDailyCoachingMissed:
    def test_missed_tasks_triggers_recovery_template_and_directives(self):
        today = date.today()
        missed = [
            _task("m1", "Missed Reading Practice", status="missed", skill="reading",
                  scheduled_date=(today - timedelta(days=3)).isoformat(), priority=2),
            _task("m2", "Missed Writing Review", status="missed", skill="writing",
                  scheduled_date=(today - timedelta(days=2)).isoformat(), priority=3),
        ]
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(
                plan=BASE_PLAN, tasks=missed, state={"current_streak": 0},
                day_stats={}, week={"minutes": 0, "percent": 0}, active_days=5,
            )
            result = svc.coach("u-1", mode="daily_coaching")

        insight_types = {i["type"] for i in result["insights"]}
        assert "missed_tasks" in insight_types
        # Directives must reference the carried-forward roadmap task.
        prio = next(d for d in result["directives"] if d["action"] == "prioritize_task")
        assert prio["ref"]["task_id"] in ("m1", "m2")
        assert prio["detail"].startswith("Complete the carried-forward task")
        assert result["message"]["generated_by"] == "template"

    def test_high_missed_count_sets_high_severity(self):
        today = date.today()
        missed = [
            _task(f"m{i}", f"Missed {i}", status="missed", skill="writing",
                  scheduled_date=(today - timedelta(days=1)).isoformat(), priority=1)
            for i in range(MISSED_HIGH_THRESHOLD)  # 5 -> high
        ]
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=missed,
                                state={}, active_days=2)
            result = svc.coach("u-1", mode="daily_coaching")

        sev = next(i["severity"] for i in result["insights"] if i["type"] == "missed_tasks")
        assert sev == "high"


# ---------------------------------------------------------------------------
# 5. Mode-specific rendering
# ---------------------------------------------------------------------------
class TestCoachModes:
    def test_roadmap_analysis_mode(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.coach("u-1", mode="roadmap_analysis")

        assert result["mode"] == "roadmap_analysis"
        assert "roadmap_progress" in {i["type"] for i in result["insights"]}
        assert result["message"]["content"]

    def test_ask_mentor_grounded_question(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Which skill should I practice tomorrow?")

        assert result["mode"] == "ask_mentor"
        assert result["message"]["role"] == "mentor"
        assert result["message"]["content"]
        # Grounded answers anchor the coaching in the learner's real numbers.
        assert "right now" in result["message"]["content"].lower()

    def test_ask_mentor_plan_question_is_refused_with_existing_plan(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Can you make me a brand new study plan?")

        msg = result["message"]["content"].lower()
        assert "existing roadmap" in msg
        assert result["guardrails"]["plan_generation_triggered"] is False

    def test_ask_mentor_plan_question_without_plan_points_to_generation(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.ask("u-1", "Please build me a new schedule")

        assert "roadmap" in result["message"]["content"].lower()
        assert "generate_roadmap" in {d["action"] for d in result["directives"]}


# ---------------------------------------------------------------------------
# 6. Prediction integration -> tone selection
# ---------------------------------------------------------------------------
class TestPredictionIntegration:
    def test_high_risk_sets_urgent_tone(self):
        pred = {"has_prediction": True, "estimated_band": 6.0,
                "readiness_score": 30.0, "risk_level": "high",
                "preparation_percentage": 30, "completion_rate": 30.0,
                "study_consistency": 40.0}
        with _with_prediction(pred):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks())
            result = svc.coach("u-1", mode="risk_check")

        assert result["message"]["tone"] == "urgent"
        assert "readiness_risk" in {i["type"] for i in result["insights"]}

    def test_medium_risk_sets_firm_tone(self):
        pred = {"has_prediction": True, "estimated_band": 6.5,
                "readiness_score": 60.0, "risk_level": "medium",
                "preparation_percentage": 50, "completion_rate": 55.0,
                "study_consistency": 60.0}
        with _with_prediction(pred):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks())
            result = svc.coach("u-1", mode="risk_check")

        assert result["message"]["tone"] == "firm"

    def test_low_readiness_overrides_insight_severity_when_risk_low(self):
        # readiness < READINESS_LOW_THRESHOLD forces the insight severity to
        # "high" even though the prediction's risk_level is "low".
        pred = {"has_prediction": True, "estimated_band": 7.0,
                "readiness_score": 20.0, "risk_level": "low",
                "preparation_percentage": 50, "completion_rate": 60.0,
                "study_consistency": 70.0}
        with _with_prediction(pred):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks())
            result = svc.coach("u-1", mode="risk_check")

        rr = next(i for i in result["insights"] if i["type"] == "readiness_risk")
        assert rr["severity"] == "high"
        assert rr["metric"]["risk_level"] == "low"
        # _pick_tone keys off risk_level ("low" -> fallback "firm"), not readiness.
        assert result["message"]["tone"] == "firm"


# ---------------------------------------------------------------------------
# 7. Crunch window + mock readiness
# ---------------------------------------------------------------------------
class TestCrunchWindow:
    @staticmethod
    def _near_exam_plan(days):
        today = date.today()
        return {
            "id": "plan-1", "title": "Final stretch", "version": 1, "status": "active",
            "start_date": (today - timedelta(days=days + 20)).isoformat(),
            "exam_date": (today + timedelta(days=days)).isoformat(),
        }

    @staticmethod
    def _near_exam_profile(days):
        today = date.today()
        d = (today + timedelta(days=days)).isoformat()
        return dict(BASE_PROFILE, exam_date=d), dict(BASE_DIAG, profile_exam_date=d)

    def test_in_crunch_window_flags_final_stretch(self):
        today = date.today()
        profile, diag = self._near_exam_profile(10)  # <= CRUNCH_WINDOW_DAYS
        plan = self._near_exam_plan(10)
        tasks = [_task("t1", "Mock test", status="pending", task_type="full_mock",
                       scheduled_date=(today + timedelta(days=3)).isoformat())]
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=plan, profile=profile, diag=diag, tasks=tasks)
            result = svc.coach("u-1", mode="daily_coaching")

        types = {i["type"] for i in result["insights"]}
        assert "crunch_window" in types
        assert "protect_revision" in {d["action"] for d in result["directives"]}

    def test_no_mock_near_exam_flags_mock_readiness(self):
        profile, diag = self._near_exam_profile(20)  # <= MOCK_NEAR_EXAM_DAYS, no mocks
        plan = self._near_exam_plan(20)
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=plan, profile=profile, diag=diag, tasks=[])
            result = svc.coach("u-1", mode="daily_coaching")

        types = {i["type"] for i in result["insights"]}
        assert "mock_readiness" in types
        assert "review_assessment" in {d["action"] for d in result["directives"]}


# ---------------------------------------------------------------------------
# 8. LLM polish failure -> deterministic template fallback
# ---------------------------------------------------------------------------
class TestLLMFallback:
    def test_no_api_key_uses_template(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")
        assert result["message"]["generated_by"] == "template"
        assert result["message"]["content"]

    def test_llm_failure_falls_back_to_template(self, monkeypatch):
        monkeypatch.setattr(mentor_module.settings, "OPENAI_API_KEY", "sk-test", raising=False)
        monkeypatch.setattr(mentor_module.httpx, "Client", _BrokenHTTPClient)
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")
        assert result["message"]["generated_by"] == "template"
        assert result["message"]["content"]


# ---------------------------------------------------------------------------
# 9. Persistence safety (db=None) + conversation history
# ---------------------------------------------------------------------------
class TestPersistenceSafety:
    def test_coach_does_not_crash_without_db(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")
        # No DB -> no conversation row, but coaching still succeeds.
        assert result["conversation_id"] is None
        assert result["guardrails"]["never_generates_plan"] is True

    def test_list_conversations_empty_without_db(self):
        svc = AIMentorService(db=None)
        result = svc.list_conversations("u-1")
        assert result["items"] == []
        assert result["total"] == 0
        assert result["limit"] == 20
        assert result["offset"] == 0

    def test_get_conversation_raises_when_absent(self):
        svc = AIMentorService(db=None)
        with pytest.raises(NotFoundError):
            svc.get_conversation("conv-x", "u-1")

    def test_context_summary_populated(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=None)
            result = svc.coach("u-1", mode="daily_coaching")
        cs = result["context_summary"]
        for key in ("current_band", "target_band", "band_gap", "risk_level",
                    "streak", "has_active_roadmap"):
            assert key in cs


# ---------------------------------------------------------------------------
# 10. Pydantic model contracts
# ---------------------------------------------------------------------------
class TestPydanticModels:
    def test_coach_request_rejects_unknown_mode(self):
        with pytest.raises(Exception):
            CoachRequest(mode="make_a_new_plan")

    def test_coach_request_accepts_valid_modes(self):
        for m in ("daily_coaching", "roadmap_analysis", "risk_check", "ask_mentor"):
            assert CoachRequest(mode=m).mode == m

    def test_ask_request_requires_nontrivial_question(self):
        with pytest.raises(Exception):
            AskRequest(question="x")
        assert AskRequest(question="How do I improve my writing?").question

    def test_guardrails_defaults_match_contract(self):
        g = MentorGuardrails()
        assert g.never_generates_plan is True
        assert g.plan_generation_triggered is False
        assert g.analysis_source == "existing_roadmap"

    def test_conversation_list_default_shape(self):
        empty = MentorConversationListResponse()
        assert empty.items == []
        assert empty.total == 0


# ---------------------------------------------------------------------------
# 11. Missed-day coaching
# ---------------------------------------------------------------------------
class TestMissedDayCoaching:
    @staticmethod
    def _fixture():
        today = date.today()
        yesterday = today - timedelta(days=1)
        tasks = [
            _task("m1", "Missed Listening Drill", status="missed", skill="listening",
                  scheduled_date=(today - timedelta(days=3)).isoformat(), priority=2),
            _task("m2", "Missed Writing Review", status="missed", skill="writing",
                  scheduled_date=(today - timedelta(days=1)).isoformat(), priority=3),
        ]
        pred = {"has_prediction": True, "estimated_band": 6.5,
                "readiness_score": 45.0, "risk_level": "medium",
                "preparation_percentage": 40, "completion_rate": 50.0,
                "study_consistency": 55.0}
        return tasks, yesterday, pred

    def test_daily_coaching_auto_routes_to_missed_day_briefing(self):
        tasks, yesterday, pred = self._fixture()
        with _with_prediction(pred):
            svc = _make_service(
                plan=BASE_PLAN, tasks=tasks,
                state={"current_streak": 5, "last_active_date": yesterday.isoformat()},
                day_stats={}, week={"minutes": 120, "percent": 40}, active_days=12,
                adjustments=[{"id": 1, "reason": "rebalance"}],
            )
            result = svc.coach("u-1", mode="daily_coaching")

        content = result["message"]["content"]
        assert result["mode"] == "daily_coaching"
        assert result["message"]["generated_by"] == "template"
        assert result["message"]["tone"] in ("encouraging", "firm", "urgent")
        assert "missed_day" in {i["type"] for i in result["insights"]}
        assert "recover_gently" in {d["action"] for d in result["directives"]}

        # What changed (Adaptive Scheduler integration)
        assert "away for" in content
        assert "Adaptive Scheduler" in content
        assert "adjustment(s)" in content

        # Encouragement and a strict no-shame contract
        assert "rebuild momentum" in content
        assert "shame" not in content.lower()
        for phrase in ("you should have", "you failed", "lazy", "gave up", "worthless"):
            assert phrase not in content.lower()

        # Today's updated workload (a real task is scheduled for today)
        assert "updated workload" in content

        # Estimated impact on target band
        assert "readiness" in content.lower()
        assert "target" in content.lower()

        assert result["guardrails"]["never_generates_plan"] is True

    def test_explicit_missed_day_mode(self):
        tasks, yesterday, pred = self._fixture()
        with _with_prediction(pred):
            svc = _make_service(
                plan=BASE_PLAN, tasks=tasks,
                state={"current_streak": 0, "last_active_date": yesterday.isoformat()},
                day_stats={}, week={"minutes": 0, "percent": 0}, active_days=12,
                adjustments=[],
            )
            result = svc.coach("u-1", mode="missed_day")

        content = result["message"]["content"]
        assert result["mode"] == "missed_day"
        assert result["title"] == "Missed day coaching"
        assert "away for" in content
        assert "Adaptive Scheduler" in content

    def test_missed_day_severity_scales_with_consecutive_days(self):
        today = date.today()
        for days_missed, expected_sev in ((1, "low"), (2, "medium"),
                                          (3, "medium"), (5, "high")):
            d = today - timedelta(days=days_missed)
            with _with_prediction({"has_prediction": False}):
                svc = _make_service(
                    plan=BASE_PLAN, tasks=[],
                    state={"current_streak": 0, "last_active_date": d.isoformat()},
                    day_stats={}, week={"minutes": 0, "percent": 0},
                    active_days=days_missed + 5,
                )
                result = svc.coach("u-1", mode="daily_coaching")

            insight = next(i for i in result["insights"] if i["type"] == "missed_day")
            assert insight["severity"] == expected_sev, (days_missed, expected_sev)
            assert insight["metric"]["consecutive_missed_days"] == days_missed


class TestMissedDayModeModel:
    def test_coach_request_accepts_missed_day_mode(self):
        from app.models.mentor import MENTOR_MODES, INSIGHT_TYPES, DIRECTIVE_ACTIONS
        assert CoachRequest(mode="missed_day").mode == "missed_day"
        assert "missed_day" in MENTOR_MODES
        assert "missed_day" in INSIGHT_TYPES
        assert "recover_gently" in DIRECTIVE_ACTIONS


# ---------------------------------------------------------------------------
# Ask-the-mentor: grounded answers to real student questions
# ---------------------------------------------------------------------------
class TestAskMentorAnswers:
    """The mentor must actually ANSWER questions, not give a generic reply.

    Covers the documented examples: question-type explanations and predicted-band
    diagnosis, plus the invariant that answers never trigger plan generation.
    """

    def test_explain_true_false_not_given(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Explain True/False/Not Given.")

        assert result["mode"] == "ask_mentor"
        assert result["message"]["generated_by"] == "template"
        content = result["message"]["content"].lower()
        # Real explanation of the question type (anchored in the passage).
        assert "true" in content and "false" in content
        assert "not given" in content
        assert "passage" in content

    def test_explain_yes_no_not_given(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "What is Yes/No/Not Given?")

        content = result["message"]["content"].lower()
        assert "yes" in content and "not given" in content

    def test_explain_matching_routing(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Explain how to answer matching questions.")
        assert "matching" in result["message"]["content"].lower()

    def test_band_diagnosis_is_grounded(self):
        pred = {"has_prediction": True, "estimated_band": 7.0, "readiness_score": 60.0,
                "risk_level": "medium", "preparation_percentage": 50,
                "completion_rate": 55.0, "study_consistency": 65.0}
        with _with_prediction(pred):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Why is my predicted band lower than my target?")

        assert result["mode"] == "ask_mentor"
        g = result["guardrails"]
        assert g["never_generates_plan"] is True
        assert g["plan_generation_triggered"] is False
        content = result["message"]["content"].lower()
        assert "estimated band" in content
        assert "readiness" in content
        assert "completion rate" in content
        # Weakest skill is Writing in BASE_DIAG; the diagnosis flags it.
        assert "weakest" in content and "writing" in content
        # The guardrail contract holds even on a band question.
        assert "generate a plan" not in content

    def test_plan_question_still_refused_on_band_context(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Make me a brand new study plan.")
        msg = result["message"]["content"].lower()
        assert "existing roadmap" in msg
        assert result["guardrails"]["plan_generation_triggered"] is False

    def test_general_skill_practice_question_is_grounded(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.ask("u-1", "Which skill should I practice tomorrow?")
        content = result["message"]["content"].lower()
        assert "right now" in content
        # Writing is the weakest skill in BASE_DIAG; the answer names it.
        assert "writing" in content
        assert result["guardrails"]["plan_generation_triggered"] is False

    def test_ask_without_question_uses_knowledge_default(self):
        with _with_prediction({"has_prediction": False}):
            svc = _make_service(plan=BASE_PLAN, tasks=_progress_tasks(completed=4, total=10))
            result = svc.coach("u-1", mode="ask_mentor")
        assert result["mode"] == "ask_mentor"
        assert result["message"]["content"]

