import json
from typing import List, Optional

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

        socials_json = json.dumps([self._item_to_dict(item) for item in parsed_profile.socials])

        if profile is None:
            profile = Profile(
                parsed_name=parsed_profile.name or None,
                parsed_socials=socials_json,
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
            profile.parsed_name = parsed_profile.name or None
            profile.parsed_socials = socials_json
            profile.parsed_skills = parsed_profile.skills
            profile.parsed_interests = parsed_profile.interests
            profile.parsed_education = education_json
            profile.parsed_experience = experience_json
            profile.profile_embedding = None  # stale; recomputed by the service/worker

        db.commit()
        db.refresh(profile)
        return profile

    def save_manual(self, db: Session, user_id: int, data: ProfileStructured) -> Profile:
        """Create or replace the profile fields from user-entered data, keeping any stored resume text."""
        profile = self.get_by_user_id(db, user_id)
        fields = dict(
            parsed_name=data.name or None,
            parsed_socials=json.dumps([self._item_to_dict(i) for i in data.socials]),
            parsed_skills=data.skills,
            parsed_interests=data.interests,
            parsed_education=json.dumps([self._item_to_dict(i) for i in data.education]),
            parsed_experience=json.dumps([self._item_to_dict(i) for i in data.experience]),
            profile_embedding=None,  # stale; recomputed by the service/worker
        )
        if profile is None:
            profile = Profile(user_id=user_id, raw_text="", **fields)
            db.add(profile)
        else:
            for key, value in fields.items():
                setattr(profile, key, value)
        db.commit()
        db.refresh(profile)
        return profile

    def update_lists(
        self,
        db: Session,
        user_id: int,
        skills: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
    ) -> Optional[Profile]:
        """Overwrite skills and/or interests; None means leave that field unchanged."""
        profile = self.get_by_user_id(db, user_id)
        if profile is None:
            return None

        if skills is not None:
            profile.parsed_skills = skills
        if interests is not None:
            profile.parsed_interests = interests
        profile.profile_embedding = None  # stale; recomputed by the service/worker

        db.commit()
        db.refresh(profile)
        return profile

    def set_embedding(self, db: Session, profile_id: int, vector: List[float]) -> None:
        db.query(Profile).filter(Profile.id == profile_id).update(
            {Profile.profile_embedding: vector}, synchronize_session=False
        )
        db.commit()

    def get_missing_embedding(self, db: Session, limit: int = 64) -> List[Profile]:
        return (
            db.query(Profile)
            .filter(Profile.profile_embedding.is_(None))
            .order_by(Profile.id)
            .limit(limit)
            .all()
        )
