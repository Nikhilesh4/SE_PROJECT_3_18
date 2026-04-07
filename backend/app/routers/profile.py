"""
Profile Router — Resume upload and profile retrieval endpoints.

POST /profile/upload-resume  — Upload a PDF resume → extract → parse → store
GET  /profile/me             — Retrieve the current user's parsed profile
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileResponse, ProfileUploadResponse
from app.repositories import profile_repo
from app.services.profile_service import extract_text_from_pdf, parse_resume_with_gemini

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.post(
    "/upload-resume",
    response_model=ProfileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept a PDF resume upload.

    Pipeline:
    1. Validate file type (must be PDF)
    2. Extract raw text using PyMuPDF
    3. Send text to Gemini API for structured parsing
    4. Upsert the parsed profile into the database
    """
    # --- Validate file type ---
    if file.content_type not in ("application/pdf",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # --- Read file bytes ---
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # --- Step 1: Extract text from PDF ---
    try:
        raw_text = extract_text_from_pdf(contents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract text from PDF: {str(e)}",
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any text from the PDF. Is it a scanned image?",
        )

    # --- Step 2: Parse with Gemini ---
    try:
        parsed = parse_resume_with_gemini(raw_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI parsing failed: {str(e)}",
        )

    # --- Step 3: Store in database ---
    profile = profile_repo.upsert_profile(
        db=db,
        user_id=current_user.id,
        raw_text=raw_text,
        skills=parsed.get("skills", []),
        education=parsed.get("education", ""),
        experience=parsed.get("experience", ""),
    )

    return ProfileUploadResponse(
        message="Resume parsed and profile updated successfully.",
        profile=ProfileResponse.model_validate(profile),
    )


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's parsed profile, or 404 if none exists."""
    profile = profile_repo.get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload a resume to create your profile.",
        )
    return profile
