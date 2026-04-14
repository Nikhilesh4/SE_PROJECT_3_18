import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local overrides first, then fallback defaults.
load_dotenv(BASE_DIR / ".env.local")
load_dotenv(BASE_DIR / ".env")
class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/unicompass"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Resume parser provider preference
    PROFILE_AI_PROVIDER: str = os.getenv("PROFILE_AI_PROVIDER", "groq")

    # Adzuna API
    ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")

    # Jooble API
    JOOBLE_API_KEY: str = os.getenv("JOOBLE_API_KEY", "")

    # RSS Refresh
    RSS_REFRESH_ENABLED: bool = True
    RSS_DEFAULT_TTL_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
