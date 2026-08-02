"""
Progress tracking endpoints.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from app.api.deps import get_current_user, get_progress_repo
from app.models.progress import (
    ProgressCreate,
    ProgressUpdate,
    ProgressResponse,
    ProgressTimelinePoint,
    SkillGap,
)
from app.repositories.progress_repo import ProgressRepository

router = APIRouter()


@router.get(
    "",
    response_model=List[ProgressResponse],
    summary="List progress records",
)
async def list_progress(
    criterion: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """List progress records for the current user with optional filters."""
    return repo.list_for_criterion(
        user_id=user_id,
        criterion=criterion,
        source_type=source_type,
    )


@router.post(
    "",
    response_model=ProgressResponse,
    status_code=201,
    summary="Create a progress record",
)
async def create_progress(
    data: ProgressCreate,
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Create a new progress record for the current user."""
    payload = data.model_dump()
    if payload.get("recorded_at"):
        payload["recorded_at"] = payload["recorded_at"].isoformat()
    else:
        payload["recorded_at"] = datetime.utcnow().isoformat()
    return repo.create(user_id, payload)


@router.get(
    "/timeline",
    response_model=List[ProgressTimelinePoint],
    summary="Get band-score timeline",
)
async def get_timeline(
    criterion: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Fetch progress records chronologically for a band-score timeline chart."""
    records = repo.get_timeline(user_id=user_id, criterion=criterion)
    return [
        ProgressTimelinePoint(
            recorded_at=record["recorded_at"],
            criterion=record["criterion"],
            band_score=float(record["band_score"]),
        )
        for record in records
    ]


@router.get(
    "/skill-gaps",
    response_model=List[SkillGap],
    summary="Get skill gap analysis",
)
async def get_skill_gaps(
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Compute current vs target band for each IELTS criterion."""
    return repo.get_skill_gaps(user_id)


@router.get(
    "/{progress_id}",
    response_model=ProgressResponse,
    summary="Get a progress record by ID",
)
async def get_progress(
    progress_id: str,
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Fetch a single progress record (scoped to the current user)."""
    return repo.get_by_id(progress_id, user_id=user_id)


@router.patch(
    "/{progress_id}",
    response_model=ProgressResponse,
    summary="Update a progress record",
)
async def update_progress(
    progress_id: str,
    data: ProgressUpdate,
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Update a progress record's band score."""
    payload = data.model_dump(exclude_none=True)
    if not payload:
        return repo.get_by_id(progress_id, user_id=user_id)
    return repo.update(progress_id, payload, user_id=user_id)


@router.delete(
    "/{progress_id}",
    status_code=204,
    summary="Delete a progress record",
)
async def delete_progress(
    progress_id: str,
    user_id: str = Depends(get_current_user),
    repo: ProgressRepository = Depends(get_progress_repo),
):
    """Delete a progress record (scoped to the current user)."""
    repo.delete(progress_id, user_id=user_id)
    return None