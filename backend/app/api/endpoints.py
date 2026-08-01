from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from app.models.schemas import IELTSAssessment, IELTSAssessmentCreate
from app.services.ielts_service import ielts_service
from app.services.ai_service import ai_service
from app.db.supabase import supabase

# Create a router that we will include in main.py
router = APIRouter()

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency to verify the Supabase JWT token from the Authorization header.
    Returns the user_id if valid, or None for unauthenticated access.
    """
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        return user.user.id if user.user else None
    except Exception:
        return None

@router.get("/health")
async def health_check():
    """Check if the API is alive."""
    return {"status": "healthy", "service": "IELTS AI Coach"}

@router.post("/assess", response_model=IELTSAssessment)
async def create_assessment(
    assessment: IELTSAssessmentCreate,
    user_id: Optional[str] = Depends(get_current_user)
):
    """
    Endpoint for the Frontend to submit a user's writing or speaking
    for AI assessment and storage.
    """
    try:
        # Override user_id with authenticated user if available
        if user_id:
            assessment.user_id = user_id

        # If band_score/feedback not provided, run AI analysis
        if assessment.band_score is None or assessment.feedback is None:
            ai_result = await ai_service.analyze_writing(assessment.user_input)
            assessment.band_score = ai_result["band_score"]
            assessment.feedback = ai_result["feedback"]
            assessment.corrections = ai_result.get("corrections", [])

        # We call the service layer to handle the database work
        result = ielts_service.save_assessment(assessment)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to save assessment")
        return result[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{user_id}", response_model=list[IELTSAssessment])
async def get_user_results(
    user_id: str,
    auth_user_id: Optional[str] = Depends(get_current_user)
):
    """Fetch all past IELTS results for a specific user."""
    try:
        # Only allow users to fetch their own results (unless no auth, then allow)
        if auth_user_id and auth_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        result = ielts_service.get_user_results(user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
