import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.routers import auth, feeds, profile
from app.db import engine, Base
from app.workers.rss_refresh_worker import rss_refresh_loop

# Enable pgvector extension, then create all tables on startup
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
Base.metadata.create_all(bind=engine)
with engine.connect() as conn:
    # Lightweight schema hardening for existing databases without migrations.
    conn.execute(
        text(
            """
            ALTER TABLE IF EXISTS rss_items
            ADD COLUMN IF NOT EXISTS application_deadline TIMESTAMPTZ
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_rss_items_application_deadline
            ON rss_items (application_deadline)
            """
        )
    )
    conn.execute(
        text(
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS parsed_interests VARCHAR[] DEFAULT '{}'"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
        )
    )
    conn.commit()

@asynccontextmanager
async def lifespan(_: FastAPI):
    worker_task = asyncio.create_task(rss_refresh_loop(), name="rss-refresh-worker")
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="UniCompass API",
    description="AI-powered opportunity discovery platform",
    version="1.0.0",
    lifespan=lifespan,
)

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
app.include_router(feeds.router, prefix="/api")
app.include_router(profile.router)


@app.get("/")
def root():
    return {"message": "UniCompass API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
