import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.routers import auth, feeds
from app.db import engine, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
)

# Enable pgvector extension, then create all tables on startup
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background tasks (RSS refresh worker)."""
    from app.config import settings
    from app.workers.rss_refresh_worker import rss_refresh_loop

    task = None
    if getattr(settings, "RSS_REFRESH_ENABLED", True):
        task = asyncio.create_task(rss_refresh_loop())
        logging.getLogger("app").info("RSS background refresh worker started")

    yield  # app is running

    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logging.getLogger("app").info("RSS background refresh worker stopped")


app = FastAPI(
    title="UniCompass API",
    description="AI-powered opportunity discovery platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — must be added BEFORE routers so preflight OPTIONS requests
# are handled by the middleware and never reach the route layer.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(feeds.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "UniCompass API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
