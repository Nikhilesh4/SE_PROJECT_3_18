from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime


# --- Request schemas ---


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt ignores (or rejects) anything beyond this


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    verification_token: Optional[str] = None
    skills: List[str] = []
    interests: List[str] = []

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not 1 <= len(value) <= 120:
            raise ValueError("Enter a username between 1 and 120 characters.")
        return value

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("Password is too long (max 72 bytes).")
        return value


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return value.strip().lower()


# --- Response schemas ---


class UserResponse(BaseModel):
    id: int
    name: Optional[str] = None
    email: str
    skills: List[str] = []
    interests: List[str] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OTPSendRequest(BaseModel):
    email: str


class OTPVerifyRequest(BaseModel):
    email: str
    code: str


class OTPVerifyResponse(BaseModel):
    verification_token: str


class OTPSendResponse(BaseModel):
    sent: bool
    # False when the server has no SMTP configured (the code is only in the server log).
    delivered: bool = True
