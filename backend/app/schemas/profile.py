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


class SocialLink(BaseModel):
    label: str = ""
    url: str = ""


class ProfileStructured(BaseModel):
    name: str = ""
    socials: List[SocialLink] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)


class ResumePreview(BaseModel):
    """What signup pre-fills from a resume before any account exists."""

    name: str = ""
    email: str = ""
    socials: List[SocialLink] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)


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


class ProfileManual(BaseModel):
    """Full profile typed in by the user (no resume). Replaces the stored profile fields."""

    name: str = Field(default="", max_length=120)
    socials: List[SocialLink] = Field(default_factory=list, max_length=20)
    skills: List[str] = Field(default_factory=list, max_length=100)
    interests: List[str] = Field(default_factory=list, max_length=100)
    education: List[EducationItem] = Field(default_factory=list, max_length=20)
    experience: List[ExperienceItem] = Field(default_factory=list, max_length=20)

    @field_validator("skills", "interests")
    @classmethod
    def _clean_lists(cls, values: List[str]) -> List[str]:
        return ProfileUpdate._clean(values) or []  # reuse the trim / de-duplicate rules

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("education")
    @classmethod
    def _drop_empty_education(cls, items: List[EducationItem]) -> List[EducationItem]:
        return [i for i in items if i.degree.strip() or i.institution.strip()]

    @field_validator("experience")
    @classmethod
    def _drop_empty_experience(cls, items: List[ExperienceItem]) -> List[ExperienceItem]:
        return [i for i in items if i.role.strip() or i.company.strip()]

    @field_validator("socials")
    @classmethod
    def _drop_empty_socials(cls, items: List[SocialLink]) -> List[SocialLink]:
        return [i for i in items if i.url.strip()]
