# Task 5 — Resume Upload & AI Profile Builder

---

## 1. Introduction

### 1.1 Feature Overview

Task 5 implements the **Resume Upload & AI Profile Builder** feature for UniCompass — an AI-powered opportunity discovery platform for university students. This feature allows users to upload a PDF resume, which the system automatically parses and structures into a rich profile containing skills, education, experience, and interests.

The feature serves as a critical data source for the platform's personalized opportunity matching: once a user's profile is extracted, it can be used by the discovery feed (Task 4) and semantic matching engine (Task 8) to rank and recommend relevant opportunities.

### 1.2 Functional Requirements

The following functional requirements were derived from the project proposal and task specification:

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Users shall be able to upload a PDF resume (max 5 MB) | Must |
| FR-2 | The system shall extract raw text from the uploaded PDF using PyMuPDF | Must |
| FR-3 | The system shall send extracted text to an AI service (Gemini/Groq) and receive structured JSON | Must |
| FR-4 | The structured profile shall contain: skills, education, experience, interests | Must |
| FR-5 | The parsed profile shall be persisted in PostgreSQL | Must |
| FR-6 | Users shall be able to view their parsed profile via `GET /profile/me` | Must |
| FR-7 | Both endpoints shall be protected by JWT authentication | Must |
| FR-8 | The frontend shall display a file upload component with loading feedback | Must |
| FR-9 | The frontend shall render the parsed profile in a structured layout | Must |
| FR-10 | A `profile_updated` event shall be published to Redis after profile creation | Should |

### 1.3 Endpoints Delivered

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/profile/upload-resume` | Accepts a PDF file, runs extraction pipeline, returns structured profile |
| `GET` | `/profile/me` | Returns the stored profile for the authenticated user |

---

## 2. Architecture Patterns Applied

### 2.1 Pipe and Filter Pattern

#### Motivation

The resume parsing pipeline is a classic example of sequential data transformation. Raw PDF bytes enter the system and must be transformed through multiple independent stages before reaching a usable structured format. Each stage has a well-defined input and output type, and the stages are completely independent of each other.

The **Pipe and Filter** architectural pattern (as defined in the course material) is designed for systems that "transform a discrete stream of data" through a sequence of loosely coupled, reusable components. Each **filter** performs one transformation. Each **pipe** carries one agreed data type between filters.

#### Implementation

```
Source          Pipe        Filter 1           Pipe         Filter 2            Pipe        Sink
──────────   ─────────   ──────────────     ──────────   ──────────────      ─────────   ──────────
PDF Upload  → bytes    → PDFExtractor      → raw str  → AIProfileAdapter   → dict      → PostgreSQL
                          (PyMuPDF)                       (Groq / Gemini)
```

**Filter 1 — `PDFExtractor` (`services/adapters/pdf_extractor.py`):**

This filter accepts raw PDF bytes and produces plain text. It uses the PyMuPDF library (`fitz`) to open the PDF in-memory and extract text from all pages.

```python
class PDFExtractor:
    def extract(self, pdf_bytes: bytes) -> str:
        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                text = "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            raise InvalidPDFError("Unable to read PDF file") from exc

        cleaned = text.strip()
        if not cleaned:
            raise InvalidPDFError("Uploaded PDF appears to be empty")

        return cleaned
```

**Filter 2 — `AIProfileAdapter` (`services/adapters/ai_profile_adapter.py`):**

This filter accepts plain text and produces a validated `ProfileStructured` Pydantic object. It sends the text to an AI provider (Groq as primary, Gemini as fallback) with a carefully engineered prompt that instructs the model to return structured JSON.

```python
class AIProfileAdapter:
    async def structure(self, resume_text: str) -> ProfileStructured:
        text = resume_text[:20000]
        provider_order = self._provider_order()

        for provider in provider_order:
            try:
                if provider == "groq":
                    raw = await self._call_groq(text)
                else:
                    raw = await self._call_gemini(text)
                payload = self._load_json_payload(raw)
                return self._normalize_payload(payload)
            except (AIServiceTimeoutError, AIServiceUnavailableError, AIResponseParseError):
                failures.append(...)

        raise AIServiceUnavailableError("; ".join(failures))
```

**Pipeline Orchestrator — `ResumeProfileService` (`services/resume_service.py`):**

The service class orchestrates the pipeline by calling each filter in sequence. It has no knowledge of how each filter works internally — it only knows the data types at each pipe boundary.

```python
class ResumeProfileService:
    async def process_resume_upload(self, db, user_id, pdf_bytes):
        raw_text   = self._pdf_extractor.extract(pdf_bytes)      # bytes → str
        structured = await self._ai_adapter.structure(raw_text)   # str → ProfileStructured
        profile    = self._repository.upsert_profile(             # ProfileStructured → DB
            db=db, user_id=user_id,
            raw_text=raw_text, parsed_profile=structured,
        )
        publish_profile_updated(user_id)                          # Event notification
        return self._to_profile_out(profile)
```

#### Data Type Contract at Each Pipe Boundary

| Boundary | Data Type | Description |
|----------|-----------|-------------|
| Source → Filter 1 | `bytes` | Raw PDF file content uploaded by user |
| Filter 1 → Filter 2 | `str` | Plain text extracted from all PDF pages |
| Filter 2 → Sink | `ProfileStructured` | Validated Pydantic model with skills, education, experience, interests |

#### Why This Pattern Fits

1. **Loose coupling**: Each filter is completely independent. Swapping PyMuPDF for another PDF library (e.g., `pdfplumber`) only requires modifying `pdf_extractor.py`. Swapping Groq for another LLM only requires modifying `ai_profile_adapter.py`. The pipeline orchestrator (`resume_service.py`) never changes.

2. **Reusability**: Each filter can be reused in other contexts. For example, `PDFExtractor` could be used by a future document analysis feature without any modifications.

3. **Testability**: Each filter can be unit-tested independently by providing the expected input type and asserting the output type.

---

### 2.2 Layered Architecture Pattern

#### Motivation

The backend must cleanly separate HTTP/presentation concerns from business logic and data access. The course material defines the key constraint of the Layered pattern: **no layer may use any layer above it**. This prevents circular dependencies and ensures that changes in one layer do not cascade unpredictably through the system.

#### Implementation

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation Layer  (routers/profile.py)                     │
│  HTTP concerns: FastAPI, UploadFile, JWT auth, HTTPException  │
└──────────────────────┬───────────────────────────────────────┘
                       │ calls ↓
┌──────────────────────▼───────────────────────────────────────┐
│  Business Logic Layer  (services/resume_service.py)           │
│  Pipeline orchestration, data transformation, event publish   │
└──────────────────────┬───────────────────────────────────────┘
                       │ calls ↓
┌──────────────────────▼───────────────────────────────────────┐
│  Data Access Layer  (repositories/profile_repository.py)      │
│  SQLAlchemy queries: upsert, fetch by user_id                 │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│  PostgreSQL + pgvector                                        │
└──────────────────────────────────────────────────────────────┘
```

#### Import Rules Enforced

The following import rules ensure layer boundaries are never violated:

| Layer | File | Allowed Imports | Forbidden Imports |
|-------|------|-----------------|-------------------|
| Presentation | `routers/profile.py` | `services/`, `schemas/`, `middleware/` | No SQLAlchemy, no PyMuPDF, no AI SDK |
| Business Logic | `services/resume_service.py` | `adapters/`, `repositories/`, `schemas/` | No FastAPI, no HTTP types, no raw SQL |
| Data Access | `repositories/profile_repository.py` | `models/`, `schemas/` | No business logic, no AI, no HTTP |

**Verification of actual imports:**

- **`routers/profile.py`** imports: `FastAPI`, `Depends`, `HTTPException`, `ResumeProfileService`, `ProfileOut`, custom errors. ✅ No SQLAlchemy, no PyMuPDF, no AI SDK.

- **`services/resume_service.py`** imports: `ProfileRepository`, `PDFExtractor`, `AIProfileAdapter`, `ProfileOut`, `publish_profile_updated`. ✅ No FastAPI, no HTTP types.

- **`repositories/profile_repository.py`** imports: `Session`, `Profile` (model), `ProfileStructured` (schema). ✅ No business logic, no AI, no HTTP.

---

### 2.3 Publish-Subscribe Pattern

#### Motivation

After a profile is successfully parsed and stored, other components of the system (such as the discovery feed service or the semantic matching engine) may need to react to the change. The **Publish-Subscribe** pattern decouples the publisher (the profile upload endpoint) from any subscribers (feed service, WebSocket manager, etc.).

The course material states: "publishers and subscribers never communicate directly — all routing goes through the connector."

#### Implementation

**Publisher — `services/events.py`:**

After the profile is saved to the database, the resume service calls `publish_profile_updated()`, which publishes a JSON payload to the `profile_updated` Redis channel.

```python
def publish_profile_updated(user_id: int) -> bool:
    payload = {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.publish("profile_updated", json.dumps(payload))
        client.close()
        return True
    except Exception:
        logger.warning("Failed to publish profile_updated event", exc_info=True)
        return False
```

**Key design decisions:**

1. **Best-effort semantics**: The event publication is wrapped in a try/except block. If Redis is unavailable, the profile upload still succeeds. The user-facing operation should never fail due to a downstream subscriber issue.

2. **Loose coupling**: The upload endpoint (`routers/profile.py`) has no knowledge of the feed service. The feed service has no knowledge of the upload flow. They communicate only through the Redis channel.

3. **Event payload**: Contains `user_id` and `updated_at` — enough for any subscriber to trigger their own logic (e.g., re-rank the user's feed based on the new profile).

```
Publisher                    Pub-Sub Connector          Subscriber
─────────────────────        ─────────────────────      ──────────────────────
POST /upload-resume     →    Redis channel              Feed service / WS manager
(after DB upsert)            "profile_updated"          (re-ranks feed, pushes live)
```

---

## 3. Design Patterns Applied

### 3.1 Adapter Pattern — `AIProfileAdapter`

#### Problem

The system needs to call an external AI service (Gemini or Groq) to structure resume text. Each provider has a different SDK, different request format, and different response format. The business logic should not be coupled to any specific provider's API.

#### Solution

The `AIProfileAdapter` class wraps both Google Gemini and Groq behind a single interface: `structure(text: str) -> ProfileStructured`. The business logic layer calls this method without knowing which provider will handle the request.

```python
class AIProfileAdapter:
    def __init__(self):
        self._preferred_provider = (settings.PROFILE_AI_PROVIDER or "groq").lower()
        # Initialize Gemini client if API key is available
        if settings.GEMINI_API_KEY and genai is not None:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")

    async def structure(self, resume_text: str) -> ProfileStructured:
        # Try preferred provider first, then fallback
        for provider in self._provider_order():
            try:
                if provider == "groq":
                    raw = await self._call_groq(text)
                else:
                    raw = await self._call_gemini(text)
                payload = self._load_json_payload(raw)
                return self._normalize_payload(payload)
            except (...):
                failures.append(...)
        raise AIServiceUnavailableError(...)
```

#### Benefits

1. **Provider independence**: The `ResumeProfileService` calls `self._ai_adapter.structure(raw_text)` without importing any AI SDK.
2. **Fallback resilience**: If Groq fails (timeout, rate limit, error), the adapter automatically tries Gemini. The caller is unaware of the retry.
3. **Easy extensibility**: Adding a third provider (e.g., OpenAI, Claude) requires adding one `_call_openai()` method and updating `_provider_order()`. No other file changes.

#### Class Diagram

```
┌──────────────────────────┐        ┌──────────────────────────┐
│   ResumeProfileService   │        │     AIProfileAdapter     │
│──────────────────────────│        │──────────────────────────│
│ _ai_adapter              │───────▶│ + structure(text) -> ProfileStructured
│                          │        │──────────────────────────│
│ process_resume_upload()  │        │ - _call_groq(text)       │
│                          │        │ - _call_gemini(text)     │
│                          │        │ - _load_json_payload()   │
│                          │        │ - _normalize_payload()   │
└──────────────────────────┘        └──────────────────────────┘
```

---

### 3.2 Repository Pattern — `ProfileRepository`

#### Problem

The service layer needs to read and write profile data from PostgreSQL, but should not be coupled to SQLAlchemy query syntax. If the database schema changes (e.g., a column is renamed, a new field is added), the change should be localized to a single file.

#### Solution

The `ProfileRepository` class encapsulates all database queries for the `profiles` table. The service layer calls repository methods (`upsert_profile`, `get_by_user_id`) and never writes SQLAlchemy queries directly.

```python
class ProfileRepository:
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Profile]:
        return db.query(Profile).filter(Profile.user_id == user_id).first()

    def upsert_profile(self, db, user_id, raw_text, parsed_profile) -> Profile:
        profile = self.get_by_user_id(db, user_id)

        if profile is None:
            profile = Profile(user_id=user_id, raw_text=raw_text, ...)
            db.add(profile)
        else:
            profile.raw_text = raw_text
            profile.parsed_skills = parsed_profile.skills
            ...

        db.commit()
        db.refresh(profile)
        return profile
```

#### Benefits

1. **Change localization**: If the `profiles` table schema changes (e.g., `parsed_skills` is renamed to `skills_list`), only `profile_repository.py` is modified.
2. **Testability**: Repository methods can be mocked in unit tests, allowing the service layer to be tested without a real database.
3. **Single responsibility**: The repository's only job is data access. It does not validate data, call external APIs, or manage HTTP responses.

---

## 4. Architectural Tactics Applied

### 4.1 Modifiability — Use an Intermediary & Localize Changes

Both the `AIProfileAdapter` and the `ProfileRepository` act as **intermediaries** that localize change:

| Change Scenario | Files Affected |
|-----------------|---------------|
| Switch from PyMuPDF to `pdfplumber` | `pdf_extractor.py` only |
| Switch from Groq to OpenAI | `ai_profile_adapter.py` only |
| Rename a column in `profiles` table | `profile_repository.py` + `models/profile.py` only |
| Change the AI prompt | `ai_profile_adapter.py` only |
| Add a new field to the profile (e.g., `certifications`) | `models/profile.py` + `schemas/profile.py` + `profile_repository.py` |

In every case, the change is **localized** — the router and the pipeline orchestrator are never modified.

### 4.2 Security — Authorize Users & Limit Access

Both endpoints are protected by JWT authentication via FastAPI's dependency injection:

```python
@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),  # JWT validation
    db: Session = Depends(get_db),
):
    ...
    return await service.process_resume_upload(
        db=db, user_id=current_user.id, pdf_bytes=pdf_bytes
    )

@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),  # JWT validation
    db: Session = Depends(get_db),
):
    profile = service.get_profile(db=db, user_id=current_user.id)
    ...
```

**Critical security property**: All operations are scoped to `current_user.id`. The repository method `get_by_user_id(user_id)` ensures it is **structurally impossible** for one user to access another user's profile data. There is no endpoint that accepts a `user_id` as a URL parameter — the user ID is always derived from the JWT token.

### 4.3 Usability — Feedback to User

AI extraction calls can take 3–15 seconds. To prevent the user from thinking the application is frozen, the frontend provides immediate visual feedback:

1. The `isUploading` state is set to `true` immediately when the file is selected
2. A loading message is displayed: *"Extracting your profile using Groq AI with Gemini fallback. This may take up to 10-15 seconds."*
3. The upload button is disabled to prevent duplicate submissions
4. On completion, the profile is immediately rendered without a page refresh

```typescript
// ResumeUpload.tsx
{isUploading && (
    <p className="mt-4 text-sm text-indigo-600 font-medium">
        Extracting your profile using Groq AI with Gemini fallback.
        This may take up to 10-15 seconds.
    </p>
)}
```

### 4.4 Performance — Bound Execution Times

External AI API calls are inherently unpredictable. To prevent the server from hanging indefinitely when a provider is slow or unresponsive, every AI call is wrapped in a hard timeout:

```python
async with asyncio.timeout(15):
    response = await client.post("https://api.groq.com/...", ...)
```

On `TimeoutError`, the adapter raises `AIServiceTimeoutError`, which the router maps to `HTTP 503 Service Unavailable`. This ensures:
- The FastAPI worker thread is never blocked indefinitely
- The user receives a clear error message instead of a hung request
- The system can fail over to the secondary provider within the same request

### 4.5 Availability — Failover with Dual Providers

The `AIProfileAdapter` implements a failover strategy:

1. Try the preferred provider (configurable via `PROFILE_AI_PROVIDER` env variable, defaults to Groq)
2. If it fails (timeout, rate limit, API error, malformed response), try the fallback provider
3. If both fail, raise `AIServiceUnavailableError` with details from both attempts

This ensures that a temporary outage of one AI provider does not make the entire resume parsing feature unavailable.

---

## 5. Custom Error Hierarchy

A dedicated exception hierarchy was implemented in `services/errors.py` to keep HTTP concerns out of the service and adapter layers:

```python
class ResumeProcessingError(Exception):
    """Base class for resume processing errors."""

class InvalidPDFError(ResumeProcessingError):
    """Raised when uploaded file content is not a valid PDF."""

class AIServiceTimeoutError(ResumeProcessingError):
    """Raised when AI provider takes too long to return."""

class AIServiceUnavailableError(ResumeProcessingError):
    """Raised when all configured AI providers fail."""

class AIResponseParseError(ResumeProcessingError):
    """Raised when AI response is not valid structured JSON."""
```

**The router translates these to HTTP responses:**

| Exception | HTTP Status | Reason |
|-----------|-------------|--------|
| `InvalidPDFError` | `422 Unprocessable Entity` | PDF is corrupted or empty |
| `AIServiceTimeoutError` | `503 Service Unavailable` | AI provider timed out |
| `AIServiceUnavailableError` | `502 Bad Gateway` | All AI providers failed |
| `AIResponseParseError` | `502 Bad Gateway` | AI returned malformed JSON |

This design ensures that service-layer code never imports `HTTPException` — it raises domain-specific exceptions, and the presentation layer decides how to map them to HTTP responses. This is consistent with the layered architecture principle.

---

## 6. Data Model

### 6.1 SQLAlchemy Model — `Profile`

```python
class Profile(Base):
    __tablename__ = "profiles"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                               unique=True, nullable=False)
    raw_text          = Column(Text, nullable=True)
    parsed_skills     = Column(ARRAY(String), default=[])
    parsed_interests  = Column(ARRAY(String), default=[])
    parsed_education  = Column(Text, nullable=True)       # JSON string
    parsed_experience = Column(Text, nullable=True)       # JSON string
    profile_embedding = Column(Vector(384), nullable=True) # pgvector (for Task 8)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(),
                               onupdate=func.now())
```

**Key design decisions:**

1. **`user_id` is `UNIQUE`**: Each user has at most one profile. Uploading a new resume overwrites the previous profile via upsert logic.
2. **`ondelete="CASCADE"`**: If a user is deleted, their profile is automatically removed.
3. **`profile_embedding`**: A 384-dimensional vector column (pgvector) is included for future semantic matching (Task 8). Gracefully falls back to `Text` if pgvector is not installed.
4. **`raw_text`**: The original extracted text is stored for debugging and potential re-processing without requiring the original PDF.

### 6.2 Pydantic Schemas

```python
class EducationItem(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""

class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    duration: str = ""
    summary: str = ""

class ProfileStructured(BaseModel):
    skills: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)

class ProfileOut(ProfileStructured):
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

The `ProfileStructured` schema serves as the **data contract** between Filter 2 (AI adapter) and the repository. The `ProfileOut` schema extends it with `updated_at` for the API response.

---

## 7. Frontend Implementation

### 7.1 Component Architecture

```
profile/
├── page.tsx                     # Page container — state management + layout
└── components/
    ├── ResumeUpload.tsx         # File upload component with validation + loading
    ├── ProfileDisplay.tsx       # Profile renderer (skills, education, experience)
    └── types.ts                 # Shared TypeScript interfaces
```

### 7.2 State Management — `page.tsx`

The profile page manages four pieces of state:

```typescript
const [profile, setProfile]     = useState<ProfileData | null>(null);
const [isUploading, setIsUploading] = useState(false);
const [error, setError]         = useState("");
const [isLoading, setIsLoading] = useState(true);
```

On mount, the page fetches the existing profile via `GET /profile/me`. If the user has no profile yet (404 response), it shows a prompt to upload a resume.

### 7.3 File Upload — `ResumeUpload.tsx`

The upload component performs **client-side validation** before sending the file:

1. **Type check**: Only `application/pdf` files are accepted
2. **Size check**: Files must be under 5 MB
3. **Immediate feedback**: `onUploadStart()` is called before the API request

The file is sent as `multipart/form-data` via the Axios client, which automatically attaches the JWT token from localStorage.

### 7.4 Profile Display — `ProfileDisplay.tsx`

The profile is rendered in four sections:

1. **Skills** — displayed as indigo badge chips in a flex-wrap row
2. **Interests** — displayed as emerald badge chips in a flex-wrap row
3. **Education** — one card per entry: degree as heading, institution + year as subtext
4. **Experience** — one card per entry: role as heading, company + duration as subtext, summary paragraph below

Each section gracefully handles empty data with a "No X parsed yet" placeholder message.

---

## 8. Input Validation & Error Handling

Input validation is performed at **three levels** to ensure defense in depth:

### Level 1 — Frontend (Client-side)

```typescript
if (file.type !== "application/pdf") return onError("Only PDF files are accepted.");
if (file.size > 5 * 1024 * 1024)    return onError("File size must be under 5MB.");
```

### Level 2 — Router (Presentation Layer)

```python
if file.content_type != "application/pdf":
    raise HTTPException(400, "Only PDF files are accepted")

pdf_bytes = await file.read()
if len(pdf_bytes) > 5 * 1024 * 1024:
    raise HTTPException(400, "File size must be under 5MB")

if not pdf_bytes.startswith(b"%PDF"):
    raise HTTPException(400, "Uploaded file is not a valid PDF")
```

The magic bytes check (`%PDF`) catches cases where a non-PDF file is uploaded with a spoofed `content_type` header.

### Level 3 — Adapter (Business Logic Layer)

```python
# PDFExtractor
if not cleaned:
    raise InvalidPDFError("Uploaded PDF appears to be empty")

# AIProfileAdapter
if not isinstance(data, dict):
    raise AIResponseParseError("AI response root must be a JSON object")
```

---

## 9. File Structure

The complete file structure for Task 5:

```
backend/app/
├── routers/
│   └── profile.py                    # Presentation layer — HTTP endpoints
├── services/
│   ├── resume_service.py             # Business logic — Pipe & Filter orchestrator
│   ├── errors.py                     # Custom exception hierarchy
│   ├── events.py                     # Pub-Sub — Redis event publisher
│   └── adapters/
│       ├── __init__.py               # Adapter exports
│       ├── pdf_extractor.py          # Filter 1 — PyMuPDF text extraction
│       └── ai_profile_adapter.py     # Filter 2 — AI structuring (Adapter pattern)
├── repositories/
│   └── profile_repository.py         # Data access layer — Repository pattern
├── models/
│   └── profile.py                    # SQLAlchemy Profile model
└── schemas/
    └── profile.py                    # Pydantic request/response schemas

frontend/src/app/profile/
├── page.tsx                          # Profile page — state management + layout
└── components/
    ├── ResumeUpload.tsx              # File upload with validation + loading states
    ├── ProfileDisplay.tsx            # Skills, education, experience renderer
    └── types.ts                      # Shared TypeScript interfaces
```

---

## 10. Dependencies

| Package | Purpose | Layer |
|---------|---------|-------|
| `pymupdf` (fitz) | PDF text extraction | Filter 1 |
| `google-generativeai` | Gemini API client | Filter 2 |
| `httpx` | Async HTTP client for Groq API | Filter 2 |
| `redis` | Pub-Sub event publishing | Events |
| `pydantic` / `pydantic-settings` | Data validation, schemas, config | All layers |
| `sqlalchemy` | ORM for PostgreSQL | Data Access |
| `pgvector` | Vector column type for future semantic matching | Data Access |
| `python-jose` | JWT encode/decode | Auth middleware |
| `python-multipart` | File upload handling | Presentation |

---

## 11. Prompt Engineering

Getting the AI to return **valid JSON consistently** is a critical challenge. The prompt was carefully designed with the following principles:

```
You are a resume parser.
Extract information from the resume text and return ONLY a valid JSON object.
Use exactly these keys:
- skills: list of strings
- education: list of objects with keys degree, institution, year
- experience: list of objects with keys role, company, duration, summary
- interests: list of strings
Do not return markdown, code fences, or explanation text.
```

**Key prompt engineering decisions:**

1. **Explicit key names and types**: The prompt specifies exact JSON keys and value types to minimize variation in responses.
2. **Negative instruction**: "Do not return markdown, code fences, or explanation text" prevents the model from wrapping JSON in markdown code blocks.
3. **Defensive parsing**: Despite the prompt, the adapter includes a fallback that strips markdown code fences (```` ``` ````) from the response before JSON parsing — handling cases where the model ignores the instruction.
4. **Text truncation**: The input is truncated to 20,000 characters to stay within token limits and reduce processing time.

---

## 12. Summary of Patterns and Tactics

| Category | Pattern/Tactic | Where Applied |
|----------|---------------|---------------|
| Architecture | Pipe and Filter | `PDFExtractor → AIProfileAdapter → PostgreSQL` pipeline |
| Architecture | Layered Architecture | Router → Service → Repository separation |
| Architecture | Publish-Subscribe | Redis `profile_updated` event after save |
| Design | Adapter | `AIProfileAdapter` wraps Groq + Gemini behind one interface |
| Design | Repository | `ProfileRepository` isolates all DB queries |
| Tactic | Modifiability | Intermediaries localize changes to one file |
| Tactic | Security | JWT auth + user-scoped queries on both endpoints |
| Tactic | Usability | Loading state + progress message during AI extraction |
| Tactic | Performance | 15-second `asyncio.timeout` on all AI calls |
| Tactic | Availability | Dual-provider failover (Groq → Gemini) |

---
