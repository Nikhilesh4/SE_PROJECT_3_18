# UniCompass — Prototype Coding Tasks

---

# Proposed Prototype (Core Scope)

---


## 1. Project Setup & Database

Set up the full development environment. Initialize a FastAPI backend and a Next.js frontend. Set up PostgreSQL as the primary database and install the pgvector extension for vector similarity search. Set up Redis for caching. Design the database schema with tables for users, opportunities, bookmarks, and profiles. Create SQLAlchemy models for all tables and wire up the database connection in FastAPI. Create a `.env` file to store API keys for Gemini, Adzuna, and Jooble. Push everything to a GitHub repository.

---

## 2. User Authentication

Build user registration and login. The registration endpoint (`POST /auth/register`) accepts name, email, password, skills, and interests. Hash the password using bcrypt before storing. The login endpoint (`POST /auth/login`) verifies credentials and returns a JWT token. Add middleware that protects all other routes by validating the JWT. Build the corresponding frontend pages — a registration form and a login form. Store the JWT in the browser and attach it to all API requests.

---

## 3. RSS Ingestion Engine (Facade + Adapter Pattern)

This is the core data pipeline. Build three adapters that each fetch opportunities from a different source and convert them into a standard `OpportunityCard` format: (1) **RSSAdapter** — uses `feedparser` to parse RSS feeds from sources like Internshala, HackerEarth, DevPost, etc. (2) **AdzunaAdapter** — calls the Adzuna job search API. (3) **JoobleAdapter** — calls the Jooble API. Additionally, consider a **SemanticScholarAdapter** for research opportunities as mentioned in the proposal. Then build an **AggregatorFacade** that provides a single `fetch_all_opportunities()` method which calls all adapters and merges the results. Build a **background worker** that runs ingestion periodically, deduplicates by source URL, and upserts into PostgreSQL.

---

## 4. Discovery Feed API & Frontend

Build the main user-facing feature. The backend exposes a `GET /feed` endpoint returning paginated opportunities from the database. Support **filtering** by category (internship, hackathon, research, course) and **sorting** using the Strategy pattern — by "latest" (date descending) or "most relevant". Add a `POST /feed/{id}/bookmark` endpoint for saving opportunities and `GET /feed/{id}` for viewing details. On the frontend, build the Discovery Feed page with opportunity cards showing title, source, category, deadline, and a bookmark button. Add a filter bar and sort toggle.

---

## 5. Resume Upload & AI Profile Builder

Let users upload a PDF resume and automatically extract a structured profile. The backend endpoint (`POST /profile/upload-resume`) accepts a PDF, uses **PyMuPDF** to extract raw text, then sends it to the **Gemini API** with a prompt to return structured JSON containing skills, education, experience, and interests. Store the parsed profile in the database. Build a `GET /profile/me` endpoint to return profile data. On the frontend, build the Profile page with a file upload component and a section displaying the extracted skills, education, and experience.

---

## 6. Caching with Redis

Add Redis caching at the following points to improve performance:

- **Discovery Feed Results** — Cache the response of `GET /feed?category=...&sort=...&page=...` using cache key `feed:{category}:{sort}:{page}`. Set TTL to 5–10 minutes. Invalidate when the ingestion worker finishes a new batch. This is the biggest performance win since the feed is the most frequently hit endpoint.
- **Individual Opportunity Details** — Cache the response of `GET /feed/{id}` using cache key `opportunity:{id}`. Set TTL to 30 minutes. Popular opportunities will be viewed by many users.
- **User Profile (Parsed Resume)** — Cache the response of `GET /profile/me` using cache key `profile:{user_id}`. Set TTL to 1 hour. Invalidate when the user uploads a new resume.
- **RSS/API Raw Responses (Ingestion Side)** — Cache raw responses from external sources using cache key `source:{source_name}:latest`. Set TTL to 30 minutes. Prevents redundant external API calls if the worker retries after a crash, and helps avoid hitting rate limits.

**Where NOT to use cache**: Authentication/login (JWTs are stateless), bookmarks (user-specific writes with little read benefit), resume upload (one-time operation).

---

## 7. Integration & Testing

Connect resume profiles with the discovery feed. When a user has a profile, the feed should be able to use their extracted skills/interests for relevance-based sorting. Test the full pipeline end-to-end: user registers → uploads resume → profile is extracted → browses feed → filters/sorts → bookmarks opportunities. Verify that caching works correctly — first request hits DB, subsequent requests served from Redis, and invalidation clears stale data. Refine the UI, fix bugs, and ensure everything works together. Write the README with setup instructions.

---

# Additional Features (Beyond Proposed Prototype)

---

## 8. Semantic Matching & Ranking

Generate embedding vectors for both opportunities (using sentence-transformers) and user profiles, storing them via pgvector. When a user requests the feed sorted by "relevance", perform cosine similarity search between the user's profile embedding and opportunity embeddings. Return opportunities ranked by match score. This makes the feed personalized — a CS student interested in web development sees relevant opportunities ranked higher.

---

## 9. Real-Time Notifications (Observer / Pub-Sub Pattern)

When the ingestion worker stores new opportunities, check if any match existing user profiles above a relevance threshold. Set up a **WebSocket endpoint** (`/ws/notifications`) in FastAPI. The Matching Engine scans new opportunities against user profiles, and the Notification Service pushes alerts to matched users via WebSocket. On the frontend, build a notification bell in the navbar with a badge count and dropdown listing matched opportunities.

---

## 10. Frontend Polish

Build a landing page with a hero section and call-to-action. Add a polished navbar with auth state, navigation links, and the notification bell. Handle loading states and error messages across all pages. Make the UI responsive for desktop and mobile. Add hover effects, smooth transitions, and clean typography.

---

## 11. Semantic Scholar Integration

Add a **SemanticScholarAdapter** to the ingestion engine. Use the Semantic Scholar API to fetch active research openings, published papers, and lab opportunities. This extends UniCompass to serve postgraduate aspirants and researchers — one of the two stakeholder groups identified in the proposal.

---

## 12. Architecture Benchmarking

Benchmark the prototype for the architecture analysis section of the report. Use `wrk` or Apache Bench to measure response time (p50, p95 latency) and throughput (requests/sec) on the `/feed` endpoint. Compare against an alternative (e.g., disable Redis caching to show the performance difference, or replace WebSocket with polling and measure latency). Record the results for the trade-off analysis.
