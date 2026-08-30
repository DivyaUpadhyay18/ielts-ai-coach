"""
Speaking Error Analysis API endpoints.

Provides detailed error analysis for a student's spoken Speaking response:

  - POST /api/v1/speaking-error-analysis/{response_id}
      → analyse a recorded response's transcript for specific issues
  - GET  /api/v1/speaking-error-analysis/{response_id}
      → fetch the most recent analysis for a response
  - GET  /api/v1/speaking-error-analysis
      → list all analyses for the current user

Analysed issue types:
  Grammar, Repeated Vocabulary, Weak Vocabulary, Unnatural Expression,
  Filler Words, Repetition, Incomplete Sentence, Hesitation Indicator,
  Coherence Problem, Pronunciation (only with audio support).

Each issue includes: original phrase, issue type, explanation (What?),
why it's a problem (Why?), suggested improvement (How?), criterion affected,
and severity.  Feedback is always constructive — never shaming.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_speaking_error_analysis_engine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.writing_workspace import (
    SpeakingErrorAnalysisResponse,
    SpeakingErrorAnalysisListResponse,
)
from app.services.speaking_error_analysis_engine import SpeakingErrorAnalysisEngine


router = APIRouter()


@router.post(
    "/{response_id}",
    response_model=SpeakingErrorAnalysisResponse,
    summary="Analyse a Speaking response transcript for specific errors",
)
async def analyze_speaking_errors(
    response_id: str,
    part: str = "part_1",
    topic: str = "",
    user_id: str = Depends(get_current_user),
    engine: SpeakingErrorAnalysisEngine = Depends(get_speaking_error_analysis_engine),
):
    """
    Generate a detailed error analysis for a recorded Speaking response.

    The analysis covers:
    - Grammar errors
    - Repeated / weak vocabulary
    - Unnatural expressions
    - Filler words and hesitation indicators
    - Incomplete sentences
    - Coherence problems
    - Pronunciation issues (only when supported by transcript evidence)

    For every issue the response includes the original phrase (verbatim),
    issue type, explanation (What happened?), why it's a problem, and a
    suggested improvement (How should I improve it?).

    The user's original transcript is never modified.
    """
    try:
        result = await engine.analyze_transcript(user_id, response_id, part, topic)
        return SpeakingErrorAnalysisResponse(**result)
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
    "/{response_id}",
    response_model=SpeakingErrorAnalysisResponse,
    summary="Get speaking error analysis for a response",
)
async def get_speaking_error_analysis(
    response_id: str,
    user_id: str = Depends(get_current_user),
    engine: SpeakingErrorAnalysisEngine = Depends(get_speaking_error_analysis_engine),
):
    """Fetch the most recent error analysis for a Speaking response."""
    try:
        result = engine.get_analysis(user_id, response_id)
        return SpeakingErrorAnalysisResponse(**result)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No speaking error analysis found for this response",
        )


@router.get(
    "",
    response_model=SpeakingErrorAnalysisListResponse,
    summary="List all speaking error analyses for the current user",
)
async def list_speaking_error_analyses(
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    engine: SpeakingErrorAnalysisEngine = Depends(get_speaking_error_analysis_engine),
):
    """List the current user's speaking error analyses (most recent first)."""
    result = engine.list_analyses(user_id, limit)
    return SpeakingErrorAnalysisListResponse(**result)
