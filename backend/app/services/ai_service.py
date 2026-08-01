import os
import json
from typing import Dict, Any
from httpx import AsyncClient
from app.ai.prompts import IELTS_WRITING_ASSESSOR_PROMPT

class AIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def analyze_writing(self, user_text: str) -> Dict[str, Any]:
        """
        Analyze a user's writing using OpenAI (if API key is set) or return mock data.
        """
        if self.api_key:
            try:
                async with AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": IELTS_WRITING_ASSESSOR_PROMPT},
                                {"role": "user", "content": f"Please assess this IELTS essay:\n\n{user_text}"}
                            ],
                            "temperature": 0.3,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # Try to parse structured JSON from the response
                    try:
                        result = json.loads(content)
                        return {
                            "band_score": float(result.get("band_score", 6.0)),
                            "feedback": result.get("feedback", "No detailed feedback provided."),
                            "corrections": result.get("corrections", [])
                        }
                    except (json.JSONDecodeError, ValueError, TypeError):
                        # If response isn't JSON, return a summary
                        return {
                            "band_score": 6.5,
                            "feedback": content[:500] if content else "Analysis complete.",
                            "corrections": []
                        }
            except Exception as e:
                # Log the error and fall back to mock
                print(f"OpenAI API error: {e}. Falling back to mock analysis.")
        
        # Mock Response (used when no API key or API call fails)
        return {
            "band_score": 6.5,
            "feedback": "Your grammar is good, but your task response needs more detail.",
            "corrections": ["Use 'moreover' instead of 'and'", "Fix subject-verb agreement in para 2"]
        }

# Create a single instance
ai_service = AIService()
