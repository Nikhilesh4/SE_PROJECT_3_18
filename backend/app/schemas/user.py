from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


# --- Request schemas ---


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    skills: List[str] = []
    interests: List[str] = []


class UserLogin(BaseModel):
    email: str
    password: str


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
