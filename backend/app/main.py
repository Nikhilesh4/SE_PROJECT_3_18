import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.migrations import run_migrations
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import agent, auth, bookmark, feeds, profile, rag
from app.workers.rss_refresh_worker import rss_refresh_loop
from app.workers.ingestion_worker import ingestion_loop
from app.workers.embedding_worker import embedding_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema is managed by Alembic (backend/alembic/versions). Migrating here
    # keeps `uvicorn app.main:app` a one-command start for local development.
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        await asyncio.to_thread(run_migrations)

    rss_task = asyncio.create_task(rss_refresh_loop(), name="rss-refresh-worker")
    ingestion_task = asyncio.create_task(ingestion_loop(), name="ingestion-worker")
    embedding_task = asyncio.create_task(embedding_loop(), name="embedding-worker")
    try:
        yield
    finally:
        tasks = (rss_task, ingestion_task, embedding_task)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


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


@app.get("/")
def root():
    return {"message": "UniCompass API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
