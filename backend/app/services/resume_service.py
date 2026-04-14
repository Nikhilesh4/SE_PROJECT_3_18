import json
from typing import Any, List

from sqlalchemy.orm import Session

from app.repositories.profile_repository import ProfileRepository
from app.schemas.profile import EducationItem, ExperienceItem, ProfileOut
from app.services.adapters.ai_profile_adapter import AIProfileAdapter
from app.services.adapters.pdf_extractor import PDFExtractor
from app.services.events import publish_profile_updated


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

        # Event publication is best-effort and should not fail user-facing flow.
        publish_profile_updated(user_id)

        return self._to_profile_out(profile)

    def get_profile(self, db: Session, user_id: int) -> ProfileOut | None:
        profile = self._repository.get_by_user_id(db, user_id)
        if profile is None:
            return None
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

        return ProfileOut(
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
