from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# This defines what an IELTS Assessment result looks like
class IELTSAssessmentBase(BaseModel):
    task_type: str = Field(..., example="Writing Task 2")
    user_input: str
    band_score: Optional[float] = Field(None, ge=0, le=9.0)
    feedback: Optional[str] = None
    corrections: Optional[List[str]] = None

# This is what we store in the Database
class IELTSAssessmentCreate(IELTSAssessmentBase):
    user_id: str

# This is what we send back to the Frontend (includes ID and Timestamp)
class IELTSAssessment(IELTSAssessmentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# This is for basic User Profile updates
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    target_band_score: Optional[float] = None