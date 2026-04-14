import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.schemas.profile import ProfileStructured


class ProfileRepository:
    @staticmethod
    def _item_to_dict(item: object) -> dict:
        if hasattr(item, "model_dump"):
            return item.model_dump()  # type: ignore[no-any-return]
        if hasattr(item, "dict"):
            return item.dict()  # type: ignore[no-any-return]
        return {}

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Profile]:
        return db.query(Profile).filter(Profile.user_id == user_id).first()

    def upsert_profile(
        self, db: Session, user_id: int, raw_text: str, parsed_profile: ProfileStructured
    ) -> Profile:
        profile = self.get_by_user_id(db, user_id)

        education_json = json.dumps(
            [self._item_to_dict(item) for item in parsed_profile.education]
        )
        experience_json = json.dumps(
            [self._item_to_dict(item) for item in parsed_profile.experience]
        )

        if profile is None:
            profile = Profile(
                user_id=user_id,
                raw_text=raw_text,
                parsed_skills=parsed_profile.skills,
                parsed_interests=parsed_profile.interests,
                parsed_education=education_json,
                parsed_experience=experience_json,
            )
            db.add(profile)
        else:
            profile.raw_text = raw_text
            profile.parsed_skills = parsed_profile.skills
            profile.parsed_interests = parsed_profile.interests
            profile.parsed_education = education_json
            profile.parsed_experience = experience_json

        db.commit()
        db.refresh(profile)
        return profile
