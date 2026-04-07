from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ProfileResponse(BaseModel):
    """Response schema for GET /profile/me and POST /profile/upload-resume."""

    id: int
    user_id: int
    parsed_skills: List[str] = []
    parsed_education: Optional[str] = None
    parsed_experience: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProfileUploadResponse(BaseModel):
    """Extended response returned immediately after a resume upload."""

    message: str
    profile: ProfileResponse
