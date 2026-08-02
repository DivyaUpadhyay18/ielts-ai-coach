"""
Task CRUD endpoints.
"""
from datetime import date
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_task_repo, get_user_repo
from app.models.task import (
    TaskCreate,
    TaskUpdate,
    TaskComplete,
    TaskResponse,
    TaskResourceLink,
    TaskWithResourcesResponse,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="List tasks",
)
async def list_tasks(
    status: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    scheduled_date: Optional[date] = Query(None),
    study_plan_id: Optional[str] = Query(None),
    daily_plan_id: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """
    List tasks for the current user with optional filters:
    status, skill, scheduled_date, study_plan_id, daily_plan_id.
    """
    return repo.list_for_user(
        user_id=user_id,
        status=status,
        skill=skill,
        scheduled_date=scheduled_date,
        study_plan_id=study_plan_id,
        daily_plan_id=daily_plan_id,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Create a task",
)
async def create_task(
    data: TaskCreate,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Create a new task for the current user."""
    payload = data.model_dump()
    if payload.get("scheduled_date"):
        payload["scheduled_date"] = payload["scheduled_date"].isoformat()
    if payload.get("due_at"):
        payload["due_at"] = payload["due_at"].isoformat()
    return repo.create(user_id, payload)


@router.get(
    "/{task_id}",
    response_model=TaskWithResourcesResponse,
    summary="Get a task by ID",
)
async def get_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Fetch a task by ID (scoped to the current user), including attached resources."""
    task = repo.get_by_id(task_id, user_id=user_id)
    resources = repo.list_resources(task_id)
    return {**task, "resources": resources}


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
)
async def update_task(
    task_id: str,
    data: TaskUpdate,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Partially update a task (title, skill, status, dates, etc.)."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(task_id, user_id=user_id)

    if payload.get("scheduled_date"):
        payload["scheduled_date"] = payload["scheduled_date"].isoformat()
    if payload.get("due_at"):
        payload["due_at"] = payload["due_at"].isoformat()

    updated = repo.update(task_id, payload, user_id=user_id)

    # Refresh the daily plan summary if the task belongs to one.
    if updated.get("daily_plan_id"):
        repo.refresh_daily_plan_summary(updated["daily_plan_id"])

    return updated


@router.delete(
    "/{task_id}",
    status_code=204,
    summary="Delete a task",
)
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Delete a task (scoped to the current user)."""
    task = repo.get_by_id(task_id, user_id=user_id)
    repo.delete(task_id, user_id=user_id)

    # Refresh the daily plan summary if the task belonged to one.
    if task.get("daily_plan_id"):
        repo.refresh_daily_plan_summary(task["daily_plan_id"])

    return None


@router.post(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Mark a task as completed",
)
async def complete_task(
    task_id: str,
    data: TaskComplete,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """
    Mark a task as completed. Optionally records the actual duration,
    output, or notes in the task's content payload.
    """
    # Ensure the task exists and belongs to the user.
    task = repo.get_by_id(task_id, user_id=user_id)

    updated = repo.complete(
        task_id,
        user_id=user_id,
        duration_minutes=data.duration_minutes,
    )

    # Merge output / notes into content_payload if provided.
    if data.output is not None or data.notes is not None:
        content = dict(task.get("content_payload") or {})
        if data.output is not None:
            content["output"] = data.output
        if data.notes is not None:
            content["notes"] = data.notes
        updated = repo.update(
            task_id,
            {"content_payload": content},
            user_id=user_id,
        )

    return updated


@router.post(
    "/{task_id}/resources",
    response_model=dict,
    status_code=201,
    summary="Attach a resource to a task",
)
async def link_resource(
    task_id: str,
    data: TaskResourceLink,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Attach a resource to a task via the task_resources join table."""
    # Verify ownership first.
    repo.get_by_id(task_id, user_id=user_id)
    link = repo.link_resource(task_id, data.resource_id, data.relation)
    return link


@router.delete(
    "/{task_id}/resources/{resource_id}",
    status_code=204,
    summary="Detach a resource from a task",
)
async def unlink_resource(
    task_id: str,
    resource_id: str,
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
):
    """Detach a resource from a task."""
    # Verify ownership first.
    repo.get_by_id(task_id, user_id=user_id)
    repo.unlink_resource(task_id, resource_id)
    return None


@router.get(
    "/timeline",
    summary="Get timeline view of all tasks until exam date",
)
async def get_timeline(
    user_id: str = Depends(get_current_user),
    repo: TaskRepository = Depends(get_task_repo),
    user_repo = Depends(get_user_repo),
):
    """
    Get a complete timeline of all days from today until the exam date.
    Each day shows:
    - Tasks with status and completion
    - Estimated time
    - Resources linked
    - Revision tasks
    - Mock tests
    - Missed tasks
    - Upcoming tasks
    """
    from datetime import date, timedelta
    
    # Get user's exam date
    user = user_repo.get_profile(user_id)
    exam_date_raw = user.get("exam_date")
    if not exam_date_raw:
        from app.core.exceptions import ValidationError
        raise ValidationError("Please set your exam date to view the timeline.")
    
    exam_date = date.fromisoformat(str(exam_date_raw))
    today = date.today()
    
    if exam_date < today:
        return {
            "exam_date": exam_date.isoformat(),
            "days": [],
            "message": "Exam date has passed."
        }
    
    # Generate all days from today to exam date
    days = []
    current = today
    while current <= exam_date:
        # Get all tasks for this day
        tasks = repo.list_for_date(user_id, current)
        
        # Categorize tasks
        all_tasks = []
        completed_tasks = []
        pending_tasks = []
        missed_tasks = []
        revision_tasks = []
        mock_tests = []
        upcoming_tasks = []
        
        total_minutes = 0
        completed_minutes = 0
        
        for task in tasks:
            task_minutes = int(task.get("duration_minutes") or 0)
            task_status = task.get("status", "pending")
            task_type = task.get("task_type", "")
            
            all_tasks.append(task)
            total_minutes += task_minutes
            
            if task_status == "completed":
                completed_tasks.append(task)
                completed_minutes += task_minutes
            elif task_status == "pending":
                if current < today:
                    missed_tasks.append(task)
                else:
                    pending_tasks.append(task)
                    if current > today:
                        upcoming_tasks.append(task)
            
            if task_type in ("revision", "review"):
                revision_tasks.append(task)
            
            if task_type in ("full_mock", "mock_section"):
                mock_tests.append(task)
        
        # Calculate completion percentage
        completion_percent = round((len(completed_tasks) / len(all_tasks)) * 100) if all_tasks else 0
        
        day_info = {
            "date": current.isoformat(),
            "display_date": current.strftime("%A, %b %d"),
            "is_today": current == today,
            "is_exam_day": current == exam_date,
            "total_tasks": len(all_tasks),
            "completed_tasks": len(completed_tasks),
            "pending_tasks": len(pending_tasks),
            "missed_tasks": len(missed_tasks),
            "upcoming_tasks": len(upcoming_tasks),
            "revision_tasks": len(revision_tasks),
            "mock_tests": len(mock_tests),
            "total_minutes": total_minutes,
            "completed_minutes": completed_minutes,
            "completion_percent": completion_percent,
            "tasks": all_tasks,
            "resources": [],  # Will be populated if needed
        }
        
        days.append(day_info)
        current += timedelta(days=1)
    
    return {
        "exam_date": exam_date.isoformat(),
        "today": today.isoformat(),
        "total_days": len(days),
        "days": days
    }
