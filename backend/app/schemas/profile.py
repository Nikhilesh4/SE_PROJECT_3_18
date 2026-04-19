from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    duration: str = ""
    summary: str = ""


class ProfileStructured(BaseModel):
    skills: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)


class ProfileOut(ProfileStructured):
    updated_at: Optional[datetime] = None
    from_cache: bool = False

    class Config:
        from_attributes = True
