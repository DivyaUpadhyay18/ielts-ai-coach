"""
Pydantic schemas for the AI Mentor domain.

The AI Mentor is an experienced IELTS tutor that coaches the student inside
**their existing study roadmap** — it never generates a study plan from
scratch. The service that consumes these schemas:

  - gathers the full learner context (profile, diagnostic, progress, study
    history, missed tasks, weakest/strongest skills, target band, exam date,
    current roadmap, scheduler history, prediction),
  - runs a deterministic coaching analysis of the existing roadmap,
  - renders a natural-language coaching message (LLM polish with a
    deterministic template fallback).

Every coaching response carries structured `insights`, actionable
`directives` (each referencing existing roadmap items), and a `guardrails`
block confirming the "never generate a plan" contract.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Coaching modes the mentor can run.
MENTOR_MODES = ("daily_coaching", "roadmap_analysis", "risk_check", "ask_mentor", "missed_day", "general")

# Severity levels for insights/directives.
SEVERITY_POSITIVE = "positive"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_LEVELS = (SEVERITY_POSITIVE, SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH)

# Insight types emitted by the deterministic analysis engine.
INSIGHT_TYPES = (
    "roadmap_missing",          # no active roadmap -> coaching guidance only
    "roadmap_progress",         # completion % through the existing roadmap
    "missed_tasks",             # tasks the scheduler marked missed / carried forward
    "overdue_pending",          # pending tasks past their schedule date
    "study_consistency",        # active days vs days since plan start
    "streak_at_risk",           # streak will break if today has no activity
    "missed_day",               # student returned after missing one or more days
    "weekly_budget",            # minutes this week vs budget
    "band_gap",                 # current vs target band gap
    "crunch_window",            # final-stretch protection window
    "roadmap_overload",         # days carrying > safe workload
    "weak_skill_coverage",      # weakest skills presence in upcoming roadmap days
    "mock_readiness",           # mock frequency vs exam proximity
    "readiness_risk",           # prediction-engine readiness / risk
)

# Directive actions the mentor emits (all reference existing roadmap items).
DIRECTIVE_ACTIONS = (
    "complete_task",            # complete a specific scheduled task
    "prioritize_task",          # raise focus on a carried-forward/missed task
    "focus_skill",              # shift attention to a skill in the roadmap
    "protect_revision",         # stick to protected revision/mock window
    "keep_streak",              # log activity today to protect the streak
    "recover_gently",           # light restart directive after missed days
    "reach_budget",             # reach the daily/weekly minute budget
    "generate_roadmap",         # first step: build the roadmap (never done for them)
    "review_assessment",        # take the mock/assessment scheduled on the roadmap
)

# Tone labels used when rendering the coaching message.
MENTOR_TONES = ("encouraging", "firm", "urgent", "neutral")
# ---------------------------------------------------------------------------
# Learner context
# ---------------------------------------------------------------------------
class SkillProfile(BaseModel):
    """Per-skill band snapshot (diagnostic-first)."""
    skill: str
    band: Optional[float] = None
    label: Optional[str] = None


class LearnerProfileContext(BaseModel):
    """User-profile slice the mentor understands."""
    user_id: str
    full_name: Optional[str] = None
    module: str = "academic"
    plan: str = "free"
    daily_minutes_budget: int = 60
    current_band: Optional[float] = None
    target_band: Optional[float] = None
    exam_date: Optional[date] = None
    profile_source: str = "unknown"  # diagnostic | profile | default
    has_diagnostic: bool = False
    diagnostic_attempt_id: Optional[str] = None
    weakest_skills: List[str] = Field(default_factory=list)
    strongest_skills: List[str] = Field(default_factory=list)
    skill_bands: Dict[str, float] = Field(default_factory=dict)


class RoadmapContext(BaseModel):
    """Snapshot of the student's existing roadmap."""
    has_active_plan: bool = False
    study_plan_id: Optional[str] = None
    title: Optional[str] = None
    version: Optional[int] = None
    start_date: Optional[date] = None
    exam_date: Optional[date] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    progress_percent: float = 0.0
    missed_tasks: int = 0
    pending_tasks: int = 0
    current_phase_index: Optional[int] = None
    total_phases: int = 0
    upcoming_task_count_7d: int = 0
    upcoming_by_skill_7d: Dict[str, int] = Field(default_factory=dict)
    days_since_start: int = 0
    roadmap_generated_from: Optional[str] = None  # meta.source


class StudyHistoryContext(BaseModel):
    """Study activity the mentor sees."""
    total_minutes: int = 0
    total_tasks_completed: int = 0
    total_xp: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: Optional[date] = None
    active_days: int = 0
    minutes_this_week: int = 0
    week_budget_minutes: int = 0
    week_percent: float = 0.0
    consistency_percent: float = 0.0
    recent_sessions: List[Dict[str, Any]] = Field(default_factory=list)


class MissedTaskInfo(BaseModel):
    """A single missed / carried-forward task."""
    task_id: str
    title: str
    skill: str
    task_type: str
    scheduled_date: Optional[date] = None
    rescheduled_to: Optional[date] = None
    status: str = "missed"
    priority: int = 1
    reason: Optional[str] = None


class MissedTasksContext(BaseModel):
    """Aggregated view of missed + overdue work."""
    total_missed: int = 0
    recent_missed_7d: int = 0
    overdue_pending: int = 0
    by_skill: Dict[str, int] = Field(default_factory=dict)
    examples: List[MissedTaskInfo] = Field(default_factory=list)
    last_scheduler_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
class PredictionContext(BaseModel):
    """Readiness / risk from the deterministic prediction engine."""
    has_prediction: bool = False
    estimated_band: Optional[float] = None
    readiness_score: Optional[float] = None
    risk_level: Optional[str] = None
    preparation_percentage: Optional[float] = None
    completion_rate: Optional[float] = None
    study_consistency: Optional[float] = None


class ExamContext(BaseModel):
    """Exam countdown context."""
    exam_date: Optional[date] = None
    days_remaining: Optional[int] = None
    weeks_remaining: Optional[int] = None
    intensity: Optional[str] = None  # normal | focused | intensive | final
    in_crunch_window: bool = False


class MentorContextResponse(BaseModel):
    """The full learner-context snapshot the AI Mentor understands.

    This is the human-readable answer to "what does the mentor know about me?"
    """
    generated_at: datetime
    profile: LearnerProfileContext
    exam: ExamContext
    roadmap: RoadmapContext
    study_history: StudyHistoryContext
    missed_tasks: MissedTasksContext
    prediction: PredictionContext
    band_gap: Optional[float] = None
    skill_labels: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Coaching analysis
# ---------------------------------------------------------------------------
class MentorInsight(BaseModel):
    """One deterministic finding from analysing the learner + roadmap."""
    type: str
    severity: str = "low"
    title: str = ""
    detail: str = ""
    skill: Optional[str] = None
    metric: Dict[str, Any] = Field(default_factory=dict)


class CoachingDirective(BaseModel):
    """One actionable coaching instruction referencing an existing roadmap item."""
    priority: int = Field(3, ge=1, le=5)
    action: str
    detail: str = ""
    skill: Optional[str] = None
    ref: Optional[Dict[str, Any]] = None  # e.g. {task_id, task_title, scheduled_date}


class MentorGuardrails(BaseModel):
    """Explicit proof of the mentor's hard contract."""
    never_generates_plan: bool = True
    plan_generation_triggered: bool = False
    analysis_source: str = "existing_roadmap"
    note: str = (
        "The AI Mentor coaches within the student's existing roadmap and never "
        "generates a study plan from scratch."
    )


# ---------------------------------------------------------------------------
# Coach request / response
# ---------------------------------------------------------------------------
class CoachRequest(BaseModel):
    """Request a coaching session in a specific mode."""
    mode: str = Field("daily_coaching", pattern="^(daily_coaching|roadmap_analysis|risk_check|ask_mentor|missed_day)$")
    message: Optional[str] = Field(None, max_length=2000)


class AskRequest(BaseModel):
    """Ask the mentor a question (answered strictly within the existing roadmap)."""
    question: str = Field(..., min_length=2, max_length=2000)


class MentorMessageContent(BaseModel):
    """The rendered coaching message."""
    role: str = "mentor"
    content: str
    generated_by: str = "template"  # llm | template
    tone: str = "neutral"


class CoachResponse(BaseModel):
    """Full coaching payload returned by the AI Mentor."""
    conversation_id: str
    mode: str
    created_at: datetime
    title: str = "Coaching session"
    message: MentorMessageContent
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    insights: List[MentorInsight] = Field(default_factory=list)
    directives: List[CoachingDirective] = Field(default_factory=list)
    guardrails: MentorGuardrails = Field(default_factory=MentorGuardrails)


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------
class MentorMessageResponse(BaseModel):
    """A stored mentor/user message."""
    id: str
    conversation_id: str
    user_id: str
    role: str  # user | mentor
    content: str
    structured: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class MentorConversationItem(BaseModel):
    """A summary row for the conversation list."""
    id: str
    mode: str
    title: str
    status: str = "active"
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MentorConversationResponse(BaseModel):
    """One conversation including all its messages."""
    id: str
    user_id: str
    mode: str
    title: str
    status: str = "active"
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)
    messages: List[MentorMessageResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MentorConversationListResponse(BaseModel):
    """Paginated conversation history."""
    items: List[MentorConversationItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0