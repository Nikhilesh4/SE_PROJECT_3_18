from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


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


class ProfileUpdate(BaseModel):
    """Partial update for user-editable profile lists (omitted fields are left unchanged)."""

    skills: Optional[List[str]] = Field(default=None, max_length=100)
    interests: Optional[List[str]] = Field(default=None, max_length=100)

    @field_validator("skills", "interests")
    @classmethod
    def _clean(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is None:
            return None
        cleaned: List[str] = []
        seen: set[str] = set()
        for value in values:
            value = " ".join(value.split())[:60]
            if value and value.lower() not in seen:
                seen.add(value.lower())
                cleaned.append(value)
        return cleaned
