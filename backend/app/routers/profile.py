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

router = APIRouter(prefix="/profile", tags=["Profile"])
service = ResumeProfileService()

MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024


@router.post("/upload-resume", response_model=ProfileOut, status_code=status.HTTP_200_OK)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
        return await service.process_resume_upload(
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


@router.get("/me", response_model=ProfileOut)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = service.get_profile(db=db, user_id=current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload a resume to get started.",
        )
    return profile
