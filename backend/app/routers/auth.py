from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.middleware.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterResponse(UserResponse):
    """Extended registration response that also includes a JWT so the
    frontend can auto-login without a second round-trip.

    Pattern: Data Transfer Object (DTO) — extends UserResponse with the
    access_token field only for the registration endpoint.
    """
    access_token: str


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
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
    # Check if email already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
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
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT token.
    Verifies email and password, then generates an access token.
    """
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user:
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
