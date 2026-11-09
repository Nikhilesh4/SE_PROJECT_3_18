import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db import get_db
from app.models.user import User
from app.config import settings
from app.schemas.profile import ResumePreview
from app.schemas.user import (
    OTPSendRequest,
    OTPSendResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
)
from app.services import otp as otp_service
from app.services.errors import InvalidPDFError
from app.services.mailer import MailerError, send_email
from app.services.resume_service import ResumeProfileService
from app.middleware.auth import create_access_token
from app.rate_limit import limiter, login_limit, otp_limit, register_limit, upload_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DUMMY_HASH = pwd_context.hash("not-a-real-password")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_MAX_RESUME_BYTES = 5 * 1024 * 1024
_resume_service = ResumeProfileService()


def _valid_email(email: str) -> str:
    cleaned = email.strip()
    if len(cleaned) > 254 or not _EMAIL_PATTERN.match(cleaned):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address.")
    return cleaned


class RegisterResponse(UserResponse):
    """Extended registration response that also includes a JWT so the
    frontend can auto-login without a second round-trip.

    Pattern: Data Transfer Object (DTO) — extends UserResponse with the
    access_token field only for the registration endpoint.
    """
    access_token: str


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(register_limit)
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user and return a JWT so the client can auto-login.

    Flow:
      1. Validate email uniqueness
      2. Hash password with bcrypt
      3. Persist User row
      4. Issue JWT (same logic as /auth/login)
      5. Return user fields + access_token

    This eliminates the register → login redirect round-trip and enables
    the frontend to redirect directly to /profile after registration.
    """
    if settings.REQUIRE_EMAIL_VERIFICATION and not otp_service.token_matches_email(
        user_data.verification_token, user_data.email
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verify your email address before creating the account.",
        )

    # Check if email already exists
    existing = db.query(User).filter(func.lower(User.email) == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    hashed_password = pwd_context.hash(user_data.password)

    # Create user
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password,
        skills=user_data.skills,
        interests=user_data.interests,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Issue JWT immediately so the client doesn't need a second login call
    access_token = create_access_token(data={"sub": str(new_user.id)})

    # Build response from an explicit dict so Pydantic gets access_token
    # at validation time — model_validate(orm_object) fails because the User
    # ORM object has no access_token field and it is required (no default).
    return RegisterResponse(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        skills=new_user.skills or [],
        interests=new_user.interests or [],
        created_at=new_user.created_at,
        access_token=access_token,
    )


@router.post("/login", response_model=Token)
@limiter.limit(login_limit)
def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT token.
    Verifies email and password, then generates an access token.
    """
    # Find user by email
    user = db.query(User).filter(func.lower(User.email) == user_data.email).first()
    if not user:
        # Spend the same time as a real check so response timing doesn't reveal which emails exist.
        pwd_context.verify(user_data.password, _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not pwd_context.verify(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token)


@router.post("/resume-preview", response_model=ResumePreview)
@limiter.limit(upload_limit)
async def resume_preview(request: Request, file: UploadFile = File(...)):
    """Read the name, email and links from a resume to pre-fill signup. Nothing is stored."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are accepted")
    pdf_bytes = await file.read(_MAX_RESUME_BYTES + 1)
    if len(pdf_bytes) > _MAX_RESUME_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size must be under 5MB")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid PDF")
    try:
        return await _resume_preview(pdf_bytes)
    except InvalidPDFError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


async def _resume_preview(pdf_bytes: bytes) -> ResumePreview:
    return await _resume_service.preview_resume(pdf_bytes)


@router.post("/otp/send", response_model=OTPSendResponse)
@limiter.limit(otp_limit)
async def send_otp(request: Request, body: OTPSendRequest, db: Session = Depends(get_db)):
    """Email a 6-digit code that proves the address belongs to the person signing up."""
    email = _valid_email(body.email)
    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    try:
        code = otp_service.issue_code(email)
    except otp_service.OTPError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    try:
        delivered = await send_email(
            email,
            "Your UniCompass verification code",
            f"Your UniCompass verification code is {code}.\n\n"
            "It expires in 10 minutes. If you did not request it, you can ignore this email.",
        )
    except MailerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return OTPSendResponse(sent=True, delivered=delivered)


@router.post("/otp/verify", response_model=OTPVerifyResponse)
@limiter.limit(otp_limit)
def verify_otp(request: Request, body: OTPVerifyRequest):
    """Exchange a correct code for a short-lived token that /auth/register accepts."""
    email = _valid_email(body.email)
    try:
        token = otp_service.check_code(email, body.code)
    except otp_service.OTPError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return OTPVerifyResponse(verification_token=token)
