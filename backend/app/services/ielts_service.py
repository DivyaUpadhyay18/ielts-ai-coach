from typing import List
from app.models.schemas import IELTSAssessmentCreate
from app.db.supabase import supabase

class IELTSService:
    @staticmethod
    def save_assessment(assessment_data: IELTSAssessmentCreate):
        """
        Logic to save an AI-generated assessment into Supabase.
        """
        # Convert Pydantic model to a dictionary for Supabase
        data = assessment_data.model_dump()
        
        result = supabase.table("assessments").insert(data).execute()
        return result.data

    @staticmethod
    def get_user_results(user_id: str):
        """
        Fetch all past assessment results for a specific user from Supabase.
        """
        result = supabase.table("assessments").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return result.data

    @staticmethod
    def calculate_overall_band(scores: List[float]) -> float:
        """
        IELTS scores are rounded to the nearest 0.5.
        This is a specific business logic rule for IELTS.
        """
        if not scores:
            return 0.0
        avg = sum(scores) / len(scores)
        return round(avg * 2) / 2

# Create an instance to be used by the API routes
ielts_service = IELTSService()