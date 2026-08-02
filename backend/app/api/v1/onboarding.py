"""
Onboarding endpoints: submit onboarding data, check status, and
generate a deterministic placeholder roadmap (no AI yet).
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from datetime import date, datetime, timedelta, timezone
from app.db.supabase import supabase
from app.api.deps import get_current_user
from app.models.onboarding import (
    OnboardingData,
    OnboardingStatus,
    RoadmapResponse,
    RoadmapPhase,
    RoadmapTask,
)

router = APIRouter()

# Phase template used by the placeholder roadmap generator.
PHASE_TEMPLATES = [
    {
        "title": "Foundation & Gap Closure",
        "description": "Build the core skills and close your biggest gaps first.",
        "tasks": [
            ("Diagnostic Review", "general", 15),
            ("Grammar Fundamentals", "grammar", 20),
            ("Core Vocabulary Building", "vocabulary", 15),
        ],
    },
    {
        "title": "Skill Building",
        "description": "Develop all four IELTS criteria through consistent practice.",
        "tasks": [
            ("Writing Task 2: Opinion Essays", "writing", 40),
            ("Speaking Part 1: Familiar Topics", "speaking", 15),
            ("Reading: Skimming & Scanning", "reading", 25),
            ("Listening: Section Practice", "listening", 20),
        ],
    },
    {
        "title": "Advanced Techniques",
        "description": "Refine complex structures and high-band vocabulary.",
        "tasks": [
            ("Writing Task 1: Data Trends", "writing", 35),
            ("Speaking Part 2: Long Turn", "speaking", 15),
            ("Lexical Resource: Collocations", "vocabulary", 20),
            ("Grammar: Complex Sentences", "grammar", 20),
        ],
    },
    {
        "title": "Mock Test Marathon",
        "description": "Full-length timed practice under exam conditions.",
        "tasks": [
            ("Full Mock Test — Listening & Reading", "mock", 90),
            ("Full Mock Test — Writing & Speaking", "mock", 90),
            ("Mistake Review & Analysis", "general", 30),
        ],
    },
    {
        "title": "Final Revision & Strategy",
        "description": "Protected revision window before your exam.",
        "tasks": [
            ("Vocabulary Rapid Review", "vocabulary", 15),
            ("Exam Strategy & Time Management", "general", 20),
            ("Confidence & Mental Prep", "general", 10),
        ],
    },
]

# Task skill weights for weak/strong skill emphasis.
SKILL_FOCUS = {
    "writing": ("Writing Task 2: Timed Practice", "writing", 40),
    "speaking": ("Speaking Part 3: Discussion", "speaking", 20),
    "reading": ("Reading: Passage Analysis", "reading", 25),
    "listening": ("Listening: Full Section", "listening", 20),
    "vocabulary": ("Academic Word List Review", "vocabulary", 15),
    "grammar": ("Grammar: Error Correction", "grammar", 20),
    "pronunciation": ("Pronunciation: Intonation Drill", "speaking", 15),
    "coherence": ("Coherence: Essay Structure", "writing", 30),
}


def _build_placeholder_roadmap(user_row: dict) -> RoadmapResponse:
    """Build a deterministic placeholder roadmap from user profile data."""
    current_band = float(user_row.get("current_band") or 5.5)
    target_band = float(user_row.get("target_band") or 7.0)
    exam_date = datetime.strptime(user_row["exam_date"], "%Y-%m-%d").date() if user_row.get("exam_date") else date.today() + timedelta(days=90)
    daily_minutes = int(user_row.get("daily_minutes_budget") or 60)
    weak = user_row.get("weakest_skill") or []
    strong = user_row.get("strongest_skill") or []

    today = date.today()
    total_days = max((exam_date - today).days, 14)
    band_gap = max(target_band - current_band, 0.0)

    # Scale total weeks: base 8, +2 weeks per 1.0 band gap, capped at 40.
    total_weeks = max(4, min(40, int(8 + band_gap * 2)))
    # Derive total weeks from the actual exam window if it is shorter.
    total_weeks = min(total_weeks, max(total_days // 7, 4))

    phase_weights = [0.28, 0.27, 0.20, 0.15, 0.10]
    phases: list[RoadmapPhase] = []
    cursor = today

    for idx, template in enumerate(PHASE_TEMPLATES):
        duration_days = max(7, int(total_days * phase_weights[idx]))
        start_date = cursor
        end_date = cursor + timedelta(days=duration_days - 1)
        phase_status = "active" if idx == 0 else ("locked" if idx > 1 else "active")

        tasks = []
        for title, skill, dur in template["tasks"]:
            tasks.append(
                RoadmapTask(
                    title=title,
                    skill=skill,
                    duration_minutes=dur,
                    status="pending",
                )
            )

        # Add weak-skill focused tasks in Skill Building / Advanced phases.
        if idx in (1, 2):
            for skill in weak:
                if skill in SKILL_FOCUS and len(tasks) < 8:
                    title, s, dur = SKILL_FOCUS[skill]
                    tasks.append(RoadmapTask(title=title, skill=s, duration_minutes=dur, status="pending"))
            # Remove redundant duplicates while keeping ordering.
            seen = set()
            deduped = []
            for t in tasks:
                key = t.title
                if key not in seen:
                    seen.add(key)
                    deduped.append(t)
            tasks = deduped

        phases.append(
            RoadmapPhase(
                order_index=idx,
                title=template["title"],
                description=template["description"],
                status=phase_status,
                duration_days=duration_days,
                start_date=start_date,
                end_date=end_date,
                tasks=tasks,
            )
        )
        cursor = end_date + timedelta(days=1)

    estimated_date = phases[-1].end_date if phases else exam_date
    confidence = min(95, max(55, int(80 - band_gap * 5)))

    return RoadmapResponse(
        title="Personalized Study Roadmap",
        target_band=target_band,
        start_band=current_band,
        total_weeks=total_weeks,
        estimated_achievement_date=estimated_date,
        confidence_score=confidence,
        phases=phases,
    )


@router.post(
    "/submit",
    response_model=dict,
    summary="Submit onboarding data",
    responses={
        200: {"description": "Onboarding data saved"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
    },
)
async def submit_onboarding(
    data: OnboardingData,
    user_id: str = Depends(get_current_user),
):
    """Save the onboarding form data to the user's profile and mark onboarding complete."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_payload = {
            "full_name": data.full_name,
            "country": data.country,
            "timezone": data.timezone or "UTC",
            "module": data.module,
            "current_band": data.current_band,
            "target_band": data.target_band,
            "exam_date": data.exam_date.isoformat(),
            "daily_minutes_budget": data.daily_minutes_budget,
            "preferred_study_time": data.preferred_study_time,
            "weakest_skill": data.weakest_skill,
            "strongest_skill": data.strongest_skill,
            "previous_ielts_attempt": data.previous_ielts_attempt,
            "is_onboarding_complete": True,
            "onboarded_at": now,
            "updated_at": now,
        }
        result = (
            supabase.table("users")
            .update(update_payload)
            .eq("id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return {
            "success": True,
            "message": "Onboarding complete",
            "is_onboarding_complete": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save onboarding data: {str(e)}",
        )


@router.get(
    "/status",
    response_model=OnboardingStatus,
    summary="Get onboarding status",
    responses={
        200: {"description": "Onboarding status returned"},
        401: {"description": "Not authenticated"},
    },
)
async def get_onboarding_status(
    user_id: str = Depends(get_current_user),
):
    """Return whether the user has completed onboarding."""
    try:
        result = (
            supabase.table("users")
            .select("id, is_onboarding_complete, onboarded_at")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        # Check if a roadmap already exists
        roadmap = (
            supabase.table("roadmaps")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return OnboardingStatus(
            is_onboarding_complete=bool(result.data.get("is_onboarding_complete", False)),
            onboarded_at=result.data.get("onboarded_at"),
            has_roadmap=bool(roadmap.data),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch onboarding status: {str(e)}",
        )


@router.post(
    "/roadmap/generate",
    response_model=RoadmapResponse,
    summary="Generate placeholder roadmap",
    responses={
        200: {"description": "Placeholder roadmap generated and stored"},
        401: {"description": "Not authenticated"},
        400: {"description": "Onboarding not complete"},
    },
)
async def generate_roadmap(
    user_id: str = Depends(get_current_user),
):
    """Generate a deterministic placeholder roadmap and persist it."""
    try:
        result = (
            supabase.table("users")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        user_row = result.data

        if not user_row.get("is_onboarding_complete"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please complete onboarding before generating a roadmap",
            )

        # Archive any existing active roadmap for this user.
        supabase.table("roadmaps").update({"status": "archived"}).eq("user_id", user_id).eq("status", "active").execute()

        roadmap = _build_placeholder_roadmap(user_row)
        now = datetime.now(timezone.utc).isoformat()

        # Insert roadmap header.
        roadmap_res = (
            supabase.table("roadmaps")
            .insert({
                "user_id": user_id,
                "version": 1,
                "title": roadmap.title,
                "target_band": roadmap.target_band,
                "start_band": roadmap.start_band,
                "status": "active",
                "total_weeks": roadmap.total_weeks,
                "meta": {
                    "source": "placeholder",
                    "generated_at": now,
                    "confidence": roadmap.confidence_score,
                    "estimated_achievement_date": roadmap.estimated_achievement_date.isoformat() if roadmap.estimated_achievement_date else None,
                },
            })
            .execute()
        )
        roadmap_id = roadmap_res.data[0]["id"]

        # Insert phases and tasks.
        for phase in roadmap.phases:
            phase_res = (
                supabase.table("roadmap_phases")
                .insert({
                    "roadmap_id": roadmap_id,
                    "order_index": phase.order_index,
                    "title": phase.title,
                    "description": phase.description,
                    "status": phase.status,
                    "duration_days": phase.duration_days,
                    "start_date": phase.start_date.isoformat() if phase.start_date else None,
                    "end_date": phase.end_date.isoformat() if phase.end_date else None,
                })
                .execute()
            )
            phase_id = phase_res.data[0]["id"]
            for task in phase.tasks:
                supabase.table("roadmap_tasks").insert({
                    "phase_id": phase_id,
                    "title": task.title,
                    "skill": task.skill,
                    "duration_minutes": task.duration_minutes,
                    "status": "pending",
                }).execute()

        # Set the roadmap id for the response.
        roadmap.id = roadmap_id
        return roadmap

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate roadmap: {str(e)}",
        )


@router.get(
    "/roadmap",
    response_model=RoadmapResponse,
    summary="Get active roadmap",
    responses={
        200: {"description": "Active roadmap returned"},
        401: {"description": "Not authenticated"},
        404: {"description": "No roadmap found"},
    },
)
async def get_roadmap(
    user_id: str = Depends(get_current_user),
):
    """Return the user's active roadmap with phases and tasks."""
    try:
        roadmap_res = (
            supabase.table("roadmaps")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not roadmap_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active roadmap found. Please generate one first.",
            )
        roadmap_row = roadmap_res.data[0]

        phases_res = (
            supabase.table("roadmap_phases")
            .select("*")
            .eq("roadmap_id", roadmap_row["id"])
            .order("order_index")
            .execute()
        )

        phases = []
        for phase_row in phases_res.data or []:
            tasks_res = (
                supabase.table("roadmap_tasks")
                .select("*")
                .eq("phase_id", phase_row["id"])
                .order("id")
                .execute()
            )
            tasks = [
                RoadmapTask(
                    id=t.get("id", ""),
                    title=t["title"],
                    skill=t["skill"],
                    duration_minutes=t["duration_minutes"],
                    status=t.get("status", "pending"),
                )
                for t in (tasks_res.data or [])
            ]
            phases.append(
                RoadmapPhase(
                    id=phase_row.get("id", ""),
                    order_index=phase_row["order_index"],
                    title=phase_row["title"],
                    description=phase_row.get("description", ""),
                    status=phase_row.get("status", "locked"),
                    duration_days=phase_row.get("duration_days", 7),
                    start_date=phase_row.get("start_date"),
                    end_date=phase_row.get("end_date"),
                    tasks=tasks,
                )
            )

        meta = roadmap_row.get("meta") or {}
        return RoadmapResponse(
            id=roadmap_row.get("id", ""),
            version=roadmap_row.get("version", 1),
            title=roadmap_row.get("title", "Personalized Study Roadmap"),
            target_band=roadmap_row["target_band"],
            start_band=roadmap_row["start_band"],
            total_weeks=roadmap_row.get("total_weeks", 8),
            estimated_achievement_date=meta.get("estimated_achievement_date"),
            confidence_score=meta.get("confidence", 80),
            phases=phases,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch roadmap: {str(e)}",
        )

