"""
Profile Repository — database access layer for the profiles table.

Uses the Repository pattern to abstract all DB queries from the router/service.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.profile import Profile


def get_profile_by_user_id(db: Session, user_id: int) -> Optional[Profile]:
    """Fetch the profile for a given user, or None if it doesn't exist."""
    return db.query(Profile).filter(Profile.user_id == user_id).first()


def upsert_profile(
    db: Session,
    user_id: int,
    raw_text: str,
    skills: list[str],
    education: str,
    experience: str,
) -> Profile:
    """
    Create a new profile or update the existing one for the given user.
    This allows re-uploading a resume to overwrite old data.
    """
    existing = get_profile_by_user_id(db, user_id)

    if existing:
        existing.raw_text = raw_text
        existing.parsed_skills = skills
        existing.parsed_education = education
        existing.parsed_experience = experience
        db.commit()
        db.refresh(existing)
        return existing

    new_profile = Profile(
        user_id=user_id,
        raw_text=raw_text,
        parsed_skills=skills,
        parsed_education=education,
        parsed_experience=experience,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile
