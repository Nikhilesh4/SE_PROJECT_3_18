from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileOut
from app.services.errors import (
    AIResponseParseError,
    AIServiceTimeoutError,
    AIServiceUnavailableError,
    InvalidPDFError,
)
from app.services.resume_service import ResumeProfileService
from app.services.redis_cache import redis_cache

router = APIRouter(prefix="/profile", tags=["Profile"])
service = ResumeProfileService()

MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024

# TTL: 1 hour — profile data changes only when a new resume is uploaded.
_PROFILE_TTL_SECONDS = 3600


def _profile_cache_key(user_id: int) -> str:
    """Canonical cache key for a user's parsed profile."""
    return f"profile:{user_id}"


@router.post("/upload-resume", response_model=ProfileOut, status_code=status.HTTP_200_OK)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parse a PDF resume with AI and save the result.

    Caching Tactic:
        Invalidation — After a successful upload, the old profile cache for
        this user is deleted so GET /profile/me immediately reflects the new data.
        Key deleted: profile:{user_id}
    """
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be under 5MB",
        )

    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF",
        )

    try:
        result = await service.process_resume_upload(
            db=db,
            user_id=current_user.id,
            pdf_bytes=pdf_bytes,
        )
    except InvalidPDFError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except AIServiceTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (AIResponseParseError, AIServiceUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # ── Invalidate the stale profile cache for this user ────────────────
    # Tactic: Cache Invalidation — ensures the next GET /profile/me call
    # fetches the freshly parsed data instead of serving the old cached version.
    redis_cache.delete(_profile_cache_key(current_user.id))

    # Mark as fresh DB result
    result.from_cache = False
    return result


@router.get("/me", response_model=ProfileOut)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the current user's parsed profile.

    Architecture:
        Cache-Aside Pattern — Redis key: profile:{user_id}
        TTL: 1 hour (3600 seconds)
        Invalidated by: POST /profile/upload-resume on successful parse.
        Rationale: Profile data is expensive to reconstruct (AI parsing) and
        rarely changes; 1-hour TTL significantly reduces DB read load.
    """
    # ── Cache-Aside: Check Redis first ──────────────────────────────────
    cache_key = _profile_cache_key(current_user.id)
    cached = redis_cache.get(cache_key)
    if cached is not None:
        data = ProfileOut(**cached)
        data.from_cache = True
        return data

    # ── Cache MISS: load from DB ─────────────────────────────────────────
    profile = service.get_profile(db=db, user_id=current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload a resume to get started.",
        )

    # ── Store in Redis with 1-hour TTL ───────────────────────────────────
    # Store raw DB model, set flag only for the current response
    redis_cache.set(cache_key, profile.model_dump(mode="json"), ttl_seconds=_PROFILE_TTL_SECONDS)
    profile.from_cache = False

    return profile
