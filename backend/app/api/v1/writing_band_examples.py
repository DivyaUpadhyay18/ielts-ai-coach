"""
Writing Band Examples API endpoints.

Provides "Band Improvement Examples" — concrete, personalized examples
showing how to improve an essay at the target band level:

  - POST /api/v1/writing-band-examples/{submission_id}
      → generate examples (optionally with a full sample answer)
  - GET  /api/v1/writing-band-examples/{evaluation_id}
      → fetch a stored set of examples
  - GET  /api/v1/writing-band-examples
      → list the user's examples

All AI calls are on the backend.  Examples are owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.api.deps import get_current_user, get_writing_band_examples_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    BandExampleResponse,
    BandExampleListResponse,
)
from app.services.writing_band_examples_engine import WritingBandExamplesEngine


router = APIRouter()


@router.post(
    "/{submission_id}",
    response_model=BandExampleResponse,
    summary="Generate band-level improvement examples for an essay",
)
async def generate_band_examples(
    submission_id: str,
    target_band: float = Query(
        7.5, ge=0.0, le=9.0,
        description="Target band level for the examples.",
    ),
    generate_sample: bool = Query(
        False,
        description="If true, also generate a complete sample Band X answer.",
    ),
    user_id: str = Depends(get_current_user),
    engine: WritingBandExamplesEngine = Depends(get_writing_band_examples_engine),
):
    """
    Generate band-level improvement examples for a submitted and evaluated essay.

    Returns:
      - Key weaknesses (from actual evaluation data)
      - Improved sentence examples (verbatim original → improved)
      - Better vocabulary alternatives
      - Paragraph structure guidance
      - Example introduction, body paragraph, and conclusion
      - Optional complete sample answer (clearly labeled as AI-generated, never
        claimed to be an official IELTS answer)

    The user's original essay is never overwritten.
    """
    try:
        result = await engine.generate_examples(
            user_id, submission_id, target_band, generate_sample
        )
        return BandExampleResponse(**result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{evaluation_id}",
    response_model=BandExampleResponse,
    summary="Get band examples for an evaluation",
)
async def get_band_examples(
    evaluation_id: str,
    user_id: str = Depends(get_current_user),
    engine: WritingBandExamplesEngine = Depends(get_writing_band_examples_engine),
):
    """Fetch stored band-level examples for an evaluation."""
    try:
        result = engine.get_examples(user_id, evaluation_id)
        return BandExampleResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No band examples found for this evaluation",
        )


@router.get(
    "",
    response_model=BandExampleListResponse,
    summary="List all band examples for the current user",
)
async def list_band_examples(
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    engine: WritingBandExamplesEngine = Depends(get_writing_band_examples_engine),
):
    """List the current user's band-level examples (most recent first)."""
    result = engine.list_examples(user_id, limit)
    return BandExampleListResponse(**result)
