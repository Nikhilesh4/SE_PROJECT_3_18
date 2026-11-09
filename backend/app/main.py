import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.migrations import run_migrations
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import agent, applications, auth, bookmark, coach, feeds, insights, missions, notifications, profile, rag
from app.workers.runner import start_workers, stop_workers


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is managed by Alembic (backend/alembic/versions). Migrating here
    # keeps `uvicorn app.main:app` a one-command start for local development.
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        await asyncio.to_thread(run_migrations)

    tasks = start_workers() if settings.RUN_WORKERS_IN_API else []
    try:
        yield
    finally:
        await stop_workers(tasks)


app = FastAPI(
    title="UniCompass API",
    description="AI-powered opportunity discovery platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS — allow the Next.js frontend (and any localhost port for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Routers
app.include_router(auth.router)
app.include_router(bookmark.router, prefix="/api")
app.include_router(feeds.router, prefix="/api")
app.include_router(profile.router)
app.include_router(agent.router)
app.include_router(rag.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(missions.router, prefix="/api")
app.include_router(coach.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "UniCompass API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
