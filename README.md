# UniCompass

AI-powered opportunity discovery platform — aggregates internships, hackathons, research positions, and courses, then matches them to your profile using semantic AI.

## Tech Stack

| Layer    | Tech                                    |
| -------- | --------------------------------------- |
| Frontend | Next.js, React, TypeScript, TailwindCSS |
| Backend  | Python, FastAPI                         |
| Database | PostgreSQL + pgvector                   |
| Cache    | Redis                                   |
| AI       | Gemini API, Sentence Transformers       |

## Prerequisites

- **Node.js** ≥ 18
- 
- **Python** ≥ 3.10
- **Docker** & **Docker Compose** (for PostgreSQL + Redis)

## Getting Started

### 1. Start databases

```bash
docker compose up -d
```

This starts PostgreSQL (with pgvector) on port 5432 and Redis on port 6379.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Edit .env with your API keys
cp .env .env.local  # optional

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App at: http://localhost:3000

## API Endpoints

| Method | Endpoint                 | Description                    |
| ------ | ------------------------ | ------------------------------ |
| `POST` | `/auth/register`         | Create user account            |
| `POST` | `/auth/login`            | Login, returns JWT             |
| `GET`  | `/feed`                  | List opportunities (paginated) |
| `GET`  | `/feed/{id}`             | Opportunity detail             |
| `POST` | `/feed/{id}/bookmark`    | Bookmark an opportunity        |
| `POST` | `/profile/upload-resume` | Upload resume PDF              |
| `GET`  | `/profile/me`            | Get parsed profile             |

## Project Structure

```
SE_PROJECT_3_18/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Settings from .env
│   │   ├── db.py             # SQLAlchemy setup
│   │   ├── models/           # DB models (User, Opportunity, Bookmark, Profile)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # API route handlers
│   │   ├── middleware/        # JWT auth middleware
│   │   ├── services/         # Business logic
│   │   ├── repositories/     # Data access layer
│   │   └── workers/          # Background tasks
│   ├── requirements.txt
│   └── .env
├── frontend/
│   └── src/
│       ├── app/              # Next.js App Router pages
│       │   ├── components/   # Shared components
│       │   ├── login/        # Login page
│       │   ├── register/     # Registration page
│       │   ├── feed/         # Discovery feed
│       │   └── profile/      # Profile page
│       └── lib/
│           └── api.ts        # Axios client with JWT interceptor
└── docker-compose.yml
```