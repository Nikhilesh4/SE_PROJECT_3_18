# Task 7 — Integration & Testing: Implementation Report

**Course**: Software Engineering (3-2)  
**Task**: 7 — Connect resume profiles with the discovery feed, verify caching, write README

---

## 1. What Task 7 Required

> "When a user has a profile, the feed should use their extracted skills/interests for relevance-based sorting. Test the full pipeline: user registers → uploads resume → profile extracted → browses feed → filters/sorts. Verify caching works correctly."

Before this task, these pieces existed but were **not connected**:
- Registration → redirected to `/login` (broken UX)
- Resume parsing extracted skills but feed **never used them**
- Cache key bug: `active_only` used Python `True`/`False` (inconsistent strings)
- No `skills` param on feed endpoint
- No "Sort by Relevance" in the UI

---

## 2. Changes Made — File by File

### 2.1 `backend/app/routers/auth.py`

**Problem**: After registering, the user had to manually log in again.

**Fix**: `POST /auth/register` now issues a JWT token in the same response.

```python
class RegisterResponse(UserResponse):
    access_token: str   # ← added

@router.post("/register", response_model=RegisterResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # ... create user ...
    access_token = create_access_token(data={"sub": str(new_user.id)})
    response = RegisterResponse.model_validate(new_user)
    response.access_token = access_token
    return response
```

**Pattern used**: Data Transfer Object (DTO) — `RegisterResponse` carries exactly what the client needs (user fields + token) without exposing internals.

---

### 2.2 `backend/app/routers/feeds.py`

This was the core backend change. Three things added:

**A) `skills` query parameter**

```python
skills: Optional[str] = Query(None,
    description="Comma-separated skills from resume profile")
```

**B) Relevance scoring function (Strategy Pattern)**

```python
def _relevance_score(item: NormalizedRssItem, skill_set: set[str]) -> int:
    tag_tokens   = {t.strip().lower() for t in item.tags}
    title_tokens = {w.strip().lower() for w in item.title.split()}
    return len(tag_tokens & skill_set) * 2 + len(title_tokens & skill_set)
```

- Tags count double (more specific match)
- Title words count once
- Items sorted descending by score, then by `published_at`

**C) Skills hash in cache key (Bug Fix)**

```python
# BEFORE (buggy):
cache_key = f"feed:{category}:{active_only}:{limit}:{offset}"
# active_only was Python True/False → inconsistent as string

# AFTER (fixed):
skills_hash = _build_skills_hash(skill_list)   # MD5[:8] of sorted skills
cache_key = f"feed:{category}:{str(active_only).lower()}:{limit}:{offset}:{skills_hash}"
```

Why this matters: without the skills hash, a generic fetch and a personalised fetch would overwrite each other in Redis. With the hash, they are stored as completely separate cache entries.

**Hash function**:
```python
def _build_skills_hash(skills: List[str]) -> str:
    normalised = sorted(s.strip().lower() for s in skills if s.strip())
    return hashlib.md5(",".join(normalised).encode()).hexdigest()[:8]
```

Sorted before hashing → `["python","ml"]` and `["ml","python"]` produce the same key, maximising cache reuse across users with identical skill sets.

---

### 2.3 `frontend/src/app/register/page.tsx`

**Before**: Called `POST /auth/register`, then did `router.push("/login?registered=true")`.

**After**:
```typescript
const { data } = await api.post("/auth/register", payload);

if (data.access_token) {
    persistToken(data.access_token);  // store JWT
    router.push("/profile?new=true"); // go straight to profile
}
```

Also added a **3-step progress indicator** so new users understand the flow:
`① Register → ② Upload Resume → ③ Explore Feed`

---

### 2.4 `frontend/src/lib/useProfile.ts` *(New File)*

A shared hook so any page can access the user's parsed profile without duplicate API calls.

**Key design**: module-level singleton cache

```typescript
let _cachedProfile: ProfileData | null = null;   // survives re-renders
let _fetchPromise: Promise<...> | null = null;    // deduplicates concurrent calls

async function fetchProfileOnce(): Promise<ProfileData | null> {
    if (_cachedProfile) return _cachedProfile;  // already loaded
    if (_fetchPromise)  return _fetchPromise;   // already loading
    _fetchPromise = api.get("/profile/me").then(...);
    return _fetchPromise;
}
```

Also exports `invalidateProfileCache(freshProfile?)` — called after resume upload so the next `useFeed` mount fetches updated skills.

---

### 2.5 `frontend/src/lib/useFeed.ts`

Added `skills?: string[]` option. When present, it:
1. Builds a stable, sorted comma-separated string
2. Adds it as `?skills=...` to the API call
3. Includes it in the `localStorage` cache discriminator

```typescript
interface UseFeedOptions {
    category?: string;
    limitPerFeed?: number;
    offset?: number;
    skills?: string[];   // ← new
}

// localStorage cache key now includes skillsKey
interface CachedFeed {
    data: RssAggregationResponse;
    category: string;
    offset: number;
    skillsKey: string;   // ← new — prevents generic/personalised collision
    timestamp: number;
}
```

---

### 2.6 `frontend/src/app/api/feeds/route.ts`

The Next.js proxy now forwards two new things to FastAPI:

```typescript
// Forward skills param
const skills = searchParams.get("skills");
if (skills) params.set("skills", skills);

// Forward Authorization header
const authHeader = request.headers.get("Authorization");
if (authHeader) headers["Authorization"] = authHeader;
```

**Pattern**: Facade — frontend always talks to `/api/feeds` (Next.js), never directly to FastAPI. This keeps the backend URL private.

---

### 2.7 `frontend/src/app/profile/page.tsx`

Three new features:

**A) Auth guard** using `useAuth()` — redirects to `/login` if not authenticated.

**B) New-user welcome hero** — shown when `?new=true` is in the URL (set by register page):
```tsx
{isNewUser && !profile && (
    <div className="rounded-2xl border border-indigo-200 bg-gradient-to-br ...">
        <h2>Welcome to UniCompass!</h2>
        <p>Upload your resume so AI can extract your skills...</p>
        {/* 3-step progress: ✓ Registered → ② Upload Resume → ③ Explore */}
    </div>
)}
```

**C) Post-upload success CTA**:
```tsx
{uploadDone && (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 ...">
        <p>✅ Profile created! Your feed now shows relevant opportunities.</p>
        <Link href="/feed?sort=relevant">Explore Your Feed →</Link>
    </div>
)}
```

After upload, calls `invalidateProfileCache(data)` so the feed hook picks up fresh skills on next mount.

---

### 2.8 `frontend/src/app/feed/page.tsx`

**New state**: `relevanceMode` boolean (defaults to `true` if `?sort=relevant` is in URL).

**Profile integration**:
```typescript
const { profile, hasProfile } = useProfile();

const userSkills = useMemo(() => {
    if (!relevanceMode || !profile) return [];
    return [...profile.skills, ...profile.interests];  // combined
}, [relevanceMode, profile]);

const { data } = useFeed({
    category: selectedCategory || undefined,
    limitPerFeed: ITEMS_PER_PAGE,
    offset,
    skills: userSkills.length > 0 ? userSkills : undefined,  // ← injected
});
```

**"Sort by Relevance" button**:
- Disabled (greyed out) if user has no profile
- Turns violet when active
- Shows skill chips below the header when active

**Skills panel in sidebar**: Shows user's extracted skills as small badges.

---

### 2.9 `frontend/src/app/feed/OpportunityCard.tsx`

Added `highlightSkills?: string[]` prop:

```typescript
const skillSet = new Set(highlightSkills.map(s => s.trim().toLowerCase()));
const hasMatch = item.tags.some(t => skillSet.has(t.trim().toLowerCase()));
```

Visual changes when `hasMatch` is true:
- Card gets a **violet border** + subtle ring
- **"🎯 Match" badge** appears next to category
- Individual matching tags get a **checkmark + violet background**

---

## 3. End-to-End Flow After Task 7

```
[1] User fills register form
         │
         ▼
[2] POST /auth/register → returns {user, access_token}
         │
         ▼  persistToken() → localStorage + cookie
[3] Redirect to /profile?new=true
         │
         ▼
[4] Profile page shows "Welcome!" hero + step indicator
         │
         ▼
[5] User uploads PDF → POST /profile/upload-resume
    → AI extracts skills/interests
    → Saves to DB
    → Redis DEL profile:{user_id}   ← cache invalidated
         │
         ▼
[6] "✅ Profile created! Explore Your Feed →" CTA
         │
         ▼
[7] User clicks → /feed?sort=relevant
         │
         ▼
[8] useProfile fetches GET /profile/me
    → Cache MISS → DB → Redis SET profile:{id} (1h TTL)
         │
         ▼
[9] useFeed called with skills=["Python","React",...]
    → GET /api/feeds?skills=python,react,...
         │
         ▼
[10] FastAPI checks Redis key: feed:None:true:50:0:a1b2c3d4
     → Cache MISS → DB query → relevance scoring → sort
     → Redis SET with 5min TTL
         │
         ▼
[11] Cards with matching tags show 🎯 Match badge
     Cache badge shows: 🗄️ PostgreSQL DB
         │
         ▼
[12] User refreshes → same key hit
     Cache badge shows: ⚡ Redis Cache
```

---

## 4. Caching Verification

### How to verify in the UI

| Action | Expected cache badge |
|--------|---------------------|
| First feed load | 🗄️ PostgreSQL DB |
| Second feed load (within 5 min) | ⚡ Redis Cache |
| Toggle "Sort by Relevance" | 🗄️ PostgreSQL DB (new key) |
| Second relevance load | ⚡ Redis Cache |
| Re-upload resume | Profile: 🗄️ PostgreSQL DB (invalidated) |
| First profile view after upload | 🗄️ PostgreSQL DB |
| Second profile view | ⚡ Redis Cache |

### How to verify in backend logs

```
# First feed request (cache miss)
INFO  unicompass.redis_cache - Redis SET key='feed:None:true:50:0:none' ttl=300s

# Second feed request (cache hit — no DB log)
DEBUG unicompass.redis_cache - Redis GET hit key='feed:None:true:50:0:none'

# After resume upload (invalidation)
INFO  unicompass.redis_cache - Redis DEL key='profile:3'

# Personalised feed (different key — no collision)
INFO  unicompass.redis_cache - Redis SET key='feed:None:true:50:0:a1b2c3d4' ttl=300s
```

---

## 5. Patterns & Tactics Summary

| Pattern / Tactic | Where Used in Task 7 |
|-----------------|---------------------|
| **Strategy Pattern** | `_relevance_score()` — swappable ranking algorithm in `feeds.py` |
| **Facade Pattern** | Next.js `/api/feeds` proxies all requests; frontend never calls FastAPI directly |
| **Singleton Pattern** | `redis_cache` (module-level instance); `_cachedProfile` in `useProfile.ts` |
| **DTO Pattern** | `RegisterResponse` extends `UserResponse` with `access_token` |
| **Cache-Aside Pattern** | Redis checked before every DB read in all endpoints |
| **Performance Tactic** | Redis caching, localStorage client-side cache, skills hash key |
| **Availability Tactic** | Redis failures silently fall back to DB (no 500 errors) |
| **Modifiability Tactic** | Skills hash in cache key — personalised/generic caches are independent |
| **Security Tactic** | Auth guard on profile + feed pages; JWT forwarded by proxy |

---

## 6. Files Changed / Created

| File | Type | Summary |
|------|------|---------|
| `backend/app/routers/auth.py` | Modified | Register returns JWT token |
| `backend/app/routers/feeds.py` | Modified | Skills param, relevance scoring, fixed cache key |
| `frontend/src/lib/useProfile.ts` | **New** | Shared profile hook with singleton cache |
| `frontend/src/lib/useFeed.ts` | Modified | Skills param, skills-aware localStorage key |
| `frontend/src/app/api/feeds/route.ts` | Modified | Forward skills + auth header |
| `frontend/src/app/register/page.tsx` | Modified | Auto-login, redirect to profile, 3-step indicator |
| `frontend/src/app/profile/page.tsx` | Modified | Auth guard, welcome hero, post-upload CTA |
| `frontend/src/app/feed/page.tsx` | Modified | Relevance toggle, profile integration, Suspense |
| `frontend/src/app/feed/OpportunityCard.tsx` | Modified | Skill-match highlight, 🎯 Match badge |
| `README.md` | Modified | Full SE architecture report |
