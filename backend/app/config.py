import logging
import os
import secrets
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local overrides first, then fallback defaults.
load_dotenv(BASE_DIR / ".env.local")
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("config")

MIN_SECRET_KEY_LENGTH = 32
_PLACEHOLDER_SECRETS = {"change-me", "changeme", "secret", "your-secret-key"}
_SECRET_KEY_FILE = BASE_DIR / ".secret_key"


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in _PLACEHOLDER_SECRETS or "change-me" in lowered or "change-this" in lowered


def resolve_secret_key(value: str | None, key_file: Path = _SECRET_KEY_FILE) -> str:
    """Return the JWT signing key, refusing placeholder or weak values.

    An explicit SECRET_KEY must be at least 32 characters and not a known
    placeholder, otherwise startup fails. When none is set (typical local dev),
    a random key is generated once and kept in a gitignored file next to the
    backend so tokens survive restarts. That removes the old behaviour of
    silently signing every token with a publicly known default.
    """
    hint = 'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    if value:
        if _is_placeholder(value):
            raise RuntimeError(f"SECRET_KEY is a placeholder value. {hint}")
        if len(value) < MIN_SECRET_KEY_LENGTH:
            raise RuntimeError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters. {hint}"
            )
        return value

    try:
        existing = key_file.read_text().strip()
        if len(existing) >= MIN_SECRET_KEY_LENGTH:
            return existing
    except OSError:
        pass

    generated = secrets.token_urlsafe(48)
    try:
        key_file.touch(mode=0o600, exist_ok=True)
        key_file.write_text(generated)
        logger.warning("SECRET_KEY not set; generated a local key in %s", key_file.name)
    except OSError:
        logger.warning(
            "SECRET_KEY not set and %s is not writable; using a temporary key "
            "(logins will not survive a restart)",
            key_file.name,
        )
    return generated


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/unicompass"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    SECRET_KEY: str = resolve_secret_key(os.getenv("SECRET_KEY"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Anthropic API (Compass Agent with AGENT_PROVIDER=anthropic). When empty,
    # the SDK falls back to ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Compass Agent (in-app assistant)
    AGENT_PROVIDER: str = os.getenv("AGENT_PROVIDER", "groq")  # "groq" | "anthropic"
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "")  # empty → provider default
    # Cap on one tool result fed back to the model. Groq's free tier allows only 8k tokens/minute and the
    # whole conversation is re-sent every round, so keep this small there; raise it for Claude.
    GROQ_MAX_OUTPUT_TOKENS: int = int(os.getenv("GROQ_MAX_OUTPUT_TOKENS", "1500"))
    AGENT_TOOL_RESULT_CHARS: int = int(os.getenv("AGENT_TOOL_RESULT_CHARS", "5000"))
    # JSON file listing external MCP servers the agent may use (see services/agent/mcp_clients.py); empty = bundled default
    MCP_CLIENTS_PATH: str = os.getenv("MCP_CLIENTS_PATH", "")
    AGENT_MAX_TOOL_ROUNDS: int = 8
    AGENT_MAX_MESSAGES_PER_CONVERSATION: int = 200

    # Resume parser provider preference
    PROFILE_AI_PROVIDER: str = os.getenv("PROFILE_AI_PROVIDER", "groq")

    # Adzuna API
    ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")

    # Jooble API
    JOOBLE_API_KEY: str = os.getenv("JOOBLE_API_KEY", "")

    # Apply Alembic migrations when the API starts (disable when a deploy
    # step runs `alembic upgrade head` instead)
    RUN_MIGRATIONS_ON_STARTUP: bool = True

    # Semantic matching (FR-4). all-MiniLM-L6-v2 produces 384-dim vectors,
    # matching the vector(384) columns. Runs locally via fastembed (ONNX).
    EMBEDDINGS_ENABLED: bool = True
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_CACHE_DIR: str = str(BASE_DIR / ".cache" / "fastembed")

    # Rate limiting (per client IP; uploads are per user). Use the Redis URL as
    # the storage when running more than one API process so counts are shared.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    LOGIN_RATE_LIMIT: str = "10/minute"
    REGISTER_RATE_LIMIT: str = "10/hour"
    UPLOAD_RATE_LIMIT: str = "10/hour"

    # Run the background workers inside the API process (convenient for a
    # one-command dev start). In production set this to false and run
    # `python -m app.worker_main` as its own process/container.
    RUN_WORKERS_IN_API: bool = True

    # Comma-separated emails allowed to trigger discovery runs and review agent traces
    ADMIN_EMAILS: str = os.getenv("ADMIN_EMAILS", "")

    # Discovery channels (phase 6). All optional; a channel with no credentials is skipped.
    DISCOVERY_ENABLED: bool = True
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    # JSON file with the company watchlist for ATS career boards
    ATS_WATCHLIST_PATH: str = str(BASE_DIR / "app" / "services" / "discovery" / "ats_watchlist.json")
    # Domains the browser/fetch agents may open for the enricher (comma-separated; empty = any public http(s) host)
    FETCH_ALLOWED_DOMAINS: str = os.getenv("FETCH_ALLOWED_DOMAINS", "")

    # RSS Refresh
    RSS_REFRESH_ENABLED: bool = True
    RSS_DEFAULT_TTL_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
