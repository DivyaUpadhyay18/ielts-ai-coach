"""
Mission Reflection API endpoints.

After each completed daily mission, the ReflectionEngine synthesises a
structured post-mission analysis and stores it. These endpoints let students
review their reflection history.

Endpoints:
- GET    /api/v1/reflections              → list reflections (paginated)
- GET    /api/v1/reflections/latest       → latest N reflections
- GET    /api/v1/reflections/count        → total reflection count
- GET    /api/v1/reflections/{id}         → one reflection by ID
"""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_current_user,
    get_mission_reflection_repo,
)
from app.models.mission_reflection import (
    MissionReflectionListResponse,
    MissionReflectionResponse,
)
from app.repositories.mission_reflection_repo import MissionReflectionRepository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=MissionReflectionListResponse,
    summary="List the current user's mission reflections",
)
def list_reflections(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    skill: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: MissionReflectionRepository = Depends(get_mission_reflection_repo),
):
    """
    Return the student's reflection history, newest first.

    Optional ``skill`` filter limits results to a single skill area
    (e.g. ``writing``, ``listening``).
    """
    items = repo.latest_for_user(
        user_id=user_id,
        limit=limit,
        offset=offset,
        skill=skill,
    )
    total = repo.count_for_user(user_id)
    return MissionReflectionListResponse(
        items=[MissionReflectionResponse(**r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/latest",
    response_model=List[MissionReflectionResponse],
    summary="Get the latest N mission reflections",
)
def latest_reflections(
    limit: int = Query(10, ge=1, le=50),
    skill: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
    repo: MissionReflectionRepository = Depends(get_mission_reflection_repo),
):
    """
    Return the most recent reflections (no pagination wrapper), useful for
    dashboard widgets.
    """
    items = repo.latest_for_user(
        user_id=user_id,
        limit=limit,
        skill=skill,
    )
    return [MissionReflectionResponse(**r) for r in items]


@router.get(
    "/count",
    summary="Get the total number of stored reflections",
)
def reflection_count(
    user_id: str = Depends(get_current_user),
    repo: MissionReflectionRepository = Depends(get_mission_reflection_repo),
):
    """Return the total number of reflections stored for the current user."""
    return {"count": repo.count_for_user(user_id)}


@router.get(
    "/{reflection_id}",
    response_model=MissionReflectionResponse,
    summary="Get a single mission reflection by ID",
)
def get_reflection(
    reflection_id: str,
    user_id: str = Depends(get_current_user),
    repo: MissionReflectionRepository = Depends(get_mission_reflection_repo),
):
    """
    Return one stored reflection by its ID.

    The repository's ``get_by_id`` enforces owner scoping, so a user can
    never fetch another user's reflection.
    """
    reflection = repo.get_by_id(reflection_id, user_id=user_id)
    return MissionReflectionResponse(**reflection)
