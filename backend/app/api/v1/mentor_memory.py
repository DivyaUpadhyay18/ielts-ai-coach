"""
AI Mentor Memory API endpoints.

GET  /api/v1/mentor-memory            — get the user's consolidated memory profile
POST /api/v1/mentor-memory/extract     — extract and store memories from all sources
GET  /api/v1/mentor-memory/types       — list available memory types
GET  /api/v1/mentor-memory/list        — list raw memories (filterable)
POST /api/v1/mentor-memory             — manually add a memory
PATCH /api/v1/mentor-memory/{id}       — update a memory
DELETE /api/v1/mentor-memory/{id}      — soft-delete a memory
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status, Body

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.models.mentor_memory import (
    MemoryProfileResponse,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    MemoryEntry,
    ExtractionResult,
)
from app.services.mentor_memory_service import MentorMemoryService, mentor_memory_service

router = APIRouter()


def get_mentor_memory_service() -> MentorMemoryService:
    return mentor_memory_service


@router.get(
    "",
    response_model=MemoryProfileResponse,
    summary="Get your consolidated mentor memory profile",
)
async def get_memory_profile(
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """
    Fetch the user's consolidated AI mentor memory profile.

    This profile aggregates:
      - Recurring mistakes
      - Frequently asked questions
      - Weak grammar topics
      - Weak vocabulary
      - Learning preferences
      - Motivation style
      - Previous conversation insights
    """
    return service.get_memory_profile(user_id)


@router.post(
    "/extract",
    response_model=ExtractionResult,
    summary="Extract and store memories from all data sources",
)
async def extract_memories(
    force: bool = Query(False, description="Force re-extraction even if recently done"),
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """Trigger extraction of memories from diagnostic, progress, and conversation data."""
    return service.extract_and_store_memories(user_id, force=force)


@router.get(
    "/types",
    response_model=list,
    summary="List available memory types",
)
async def get_memory_types(
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """Return the available memory types and their schema."""
    return service.get_memory_types()


@router.get(
    "/list",
    response_model=list,
    summary="List raw memories (filterable)",
)
async def list_memories(
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """List the user's raw memory entries, optionally filtered."""
    return service.get_memories(user_id, memory_type=memory_type, category=category, limit=limit)


@router.post(
    "",
    response_model=MemoryEntry,
    summary="Manually add a memory entry",
)
async def create_memory(
    data: MemoryCreateRequest = Depends(),
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """Manually add a memory entry to the user's mentor memory."""
    try:
        result = service.add_memory(
            user_id=user_id,
            memory_type=data.memory_type,
            content=data.content,
            category=data.category,
            subcategory=data.subcategory,
            structured_data=data.structured_data,
            confidence=data.confidence,
        )
        return MemoryEntry(**result) if isinstance(result, dict) else result
    except ValidationError:
        raise


@router.patch(
    "/{memory_id}",
    response_model=MemoryEntry,
    summary="Update a memory entry",
)
async def update_memory(
    memory_id: str,
    data: MemoryUpdateRequest = Depends(),
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """Update a memory entry (owner-scoped)."""
    try:
        update_data = {k: v for k, v in data.dict(exclude_unset=True).items()}
        result = service.update_memory(user_id, memory_id, update_data)
        return MemoryEntry(**result) if isinstance(result, dict) else result
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Memory not found")
    except ValidationError:
        raise


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a memory entry",
)
async def delete_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user),
    service: MentorMemoryService = Depends(get_mentor_memory_service),
):
    """Soft-delete a memory entry (sets is_active = False)."""
    try:
        service.delete_memory(user_id, memory_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Memory not found")
