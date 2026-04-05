from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.routers import auth
from app.db import engine, Base

# Enable pgvector extension, then create all tables on startup
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="UniCompass API",
    description="AI-powered opportunity discovery platform",
    version="1.0.0",
)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "UniCompass API is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
