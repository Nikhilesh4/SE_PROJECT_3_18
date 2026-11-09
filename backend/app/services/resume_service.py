import json
import re
from typing import Any, List

from sqlalchemy.orm import Session

from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import EducationItem, ExperienceItem, ProfileManual, ProfileOut, ProfileStructured, ProfileUpdate, ResumePreview, SocialLink
from app.services.adapters.ai_profile_adapter import AIProfileAdapter
from app.services.adapters.pdf_extractor import PDFExtractor
from app.services.events import publish_profile_updated
from app.services.matching.semantic import refresh_profile_embedding


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


def extract_email(text: str) -> str:
    """First email in the resume; an explicit mailto: link wins over text that merely looks like one."""
    mailto = re.search(r"mailto:\s*(" + _EMAIL_RE.pattern + ")", text, re.IGNORECASE)
    if mailto:
        return mailto.group(1).lower()
    found = _EMAIL_RE.search(text)
    return found.group(0).lower() if found else ""


class ResumeProfileService:
    def __init__(self) -> None:
        self._repository = ProfileRepository()
        self._pdf_extractor = PDFExtractor()
        self._ai_adapter = AIProfileAdapter()

    async def process_resume_upload(
        self, db: Session, user_id: int, pdf_bytes: bytes
    ) -> ProfileOut:
        raw_text = self._pdf_extractor.extract(pdf_bytes)
        structured = await self._ai_adapter.structure(raw_text)

        profile = self._repository.upsert_profile(
            db=db,
            user_id=user_id,
            raw_text=raw_text,
            parsed_profile=structured,
        )
        refresh_profile_embedding(db, profile)

        # Event publication is best-effort and should not fail user-facing flow.
        publish_profile_updated(user_id)

        return self._to_profile_out(profile)

    async def preview_resume(self, pdf_bytes: bytes) -> ResumePreview:
        """Read name, email and links from a resume without saving anything (used before signup)."""
        raw_text = self._pdf_extractor.extract(pdf_bytes)
        email = extract_email(raw_text)
        try:
            structured = await self._ai_adapter.structure(raw_text)
        except Exception:
            # The email alone is still useful if the AI step is unavailable.
            return ResumePreview(email=email)
        return ResumePreview(
            name=structured.name,
            email=email,
            socials=structured.socials,
            skills=structured.skills[:40],
            interests=structured.interests[:20],
            education=structured.education[:10],
            experience=structured.experience[:10],
        )

    def get_profile(self, db: Session, user_id: int) -> ProfileOut | None:
        profile = self._repository.get_by_user_id(db, user_id)
        if profile is None:
            return None
        return self._to_profile_out(profile)

    def update_profile(
        self, db: Session, user_id: int, update: ProfileUpdate
    ) -> ProfileOut | None:
        profile = self._repository.update_lists(
            db=db,
            user_id=user_id,
            skills=update.skills,
            interests=update.interests,
        )
        if profile is None:
            return None
        refresh_profile_embedding(db, profile)

        publish_profile_updated(user_id)
        return self._to_profile_out(profile)

    def save_manual_profile(self, db: Session, user_id: int, data: ProfileManual) -> ProfileOut:
        profile = self._repository.save_manual(
            db=db, user_id=user_id, data=ProfileStructured(**data.model_dump())
        )
        refresh_profile_embedding(db, profile)
        publish_profile_updated(user_id)
        return self._to_profile_out(profile)

    def _to_profile_out(self, profile: Any) -> ProfileOut:
        education_items = self._parse_json_list(profile.parsed_education)
        experience_items = self._parse_json_list(profile.parsed_experience)

        education = [
            EducationItem(
                degree=str(item.get("degree", "")).strip(),
                institution=str(item.get("institution", "")).strip(),
                year=str(item.get("year", "")).strip(),
            )
            for item in education_items
        ]

        experience = [
            ExperienceItem(
                role=str(item.get("role", "")).strip(),
                company=str(item.get("company", "")).strip(),
                duration=str(item.get("duration", "")).strip(),
                summary=str(item.get("summary", "")).strip(),
            )
            for item in experience_items
        ]

        socials = [
            SocialLink(label=str(i.get("label", "")).strip(), url=str(i.get("url", "")).strip())
            for i in self._parse_json_list(getattr(profile, "parsed_socials", None))
            if str(i.get("url", "")).strip()
        ]

        return ProfileOut(
            name=getattr(profile, "parsed_name", None) or "",
            socials=socials,
            skills=profile.parsed_skills or [],
            education=education,
            experience=experience,
            interests=profile.parsed_interests or [],
            updated_at=getattr(profile, "updated_at", None),
        )

    def _parse_json_list(self, raw_value: Any) -> List[dict]:
        if not raw_value:
            return []

        if isinstance(raw_value, list):
            return [item for item in raw_value if isinstance(item, dict)]

        if not isinstance(raw_value, str):
            return []

        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, list):
            return []

        return [item for item in parsed if isinstance(item, dict)]
