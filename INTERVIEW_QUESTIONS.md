# 🎯 Comprehensive Interview Preparation Guide: Food Waste Redistribution Platform

> **Target Repository:** `food_waste_redistribution`  
> **Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (Async) · PostgreSQL (`asyncpg`) · Alembic · Jinja2 · JWT · APScheduler · Cloudinary · Docker & Multi-Stage Builds  
> **Purpose:** Designed for technical screening, system architecture rounds, and deep-dive coding interviews. This document identifies both your system's strengths and the hidden trade-offs/flaws that senior interviewers will test to see if you truly understand your codebase or if it was generated via AI / vibecoding.

---

## 📁 Executive Summary & Codebase Architecture Map

| Subsystem | File Reference | Primary Responsibility & Implementation Details |
| :--- | :--- | :--- |
| **Application Assembly & Lifespan** | [`app/main.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/main.py) | ASGI entrypoint, CORS configuration, static mounting, router registration, and `lifespan` context manager initializing `APScheduler`. |
| **Configuration & Environment** | [`app/core/config.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/config.py) | Pydantic `BaseSettings` reading `.env`. Enforces 12-factor app principles and normalizes DB URLs (`postgres://` → `postgresql+asyncpg://`). |
| **Security & JWT Cryptography** | [`app/core/security.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/security.py) | `passlib` with `bcrypt` password hashing, token creation (`create_access_token`, `create_refresh_token`), and decoding (`decode_access_token`). |
| **Dependency Injection & Auth Guards** | [`app/core/dependencies.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/dependencies.py) | `get_current_user` (header + cookie extraction) and `require_role(*roles)` higher-order dependency factory. |
| **Async Background Scheduler** | [`app/core/scheduler.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py) | `AsyncIOScheduler` executing `check_expiring_listings()` every 15 minutes inside FastAPI's existing asyncio event loop. |
| **Email Delivery Engine** | [`app/core/email_service.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/email_service.py) | Non-blocking SMTP delivery using `aiosmtplib`. Implements store-then-send best-effort email delivery. |
| **Cloudinary Media Pipeline** | [`app/core/cloudinary_service.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/cloudinary_service.py) | Validates MIME/extensions & file size (5MB limit). Wraps Cloudinary's synchronous SDK in `loop.run_in_executor(None, ...)`. |
| **Spatial Calculation Utilities** | [`app/core/utils.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/utils.py) | Great-circle distance calculations via the Haversine formula (`R = 6371.0 km`) with floating-point clamping. |
| **Database Connection Pool** | [`app/db/database.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/db/database.py) | Async engine (`create_async_engine`) with `async_sessionmaker` and `get_db()` yield dependency for request session lifecycle. |
| **Data Models (ORM)** | [`app/models/`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/) | [`user.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/user.py), [`food_listing.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/food_listing.py), [`claim.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/claim.py), [`notification.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/notification.py). Enforces foreign keys, composite indexes, and SQLAlchemy relationships. |
| **API Routers** | [`app/routers/`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/) | [`auth.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py), [`listings.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py), [`notifications.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/notifications.py), [`admin.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/admin.py), [`pages.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/pages.py). |
| **Container & Startup Scripts** | [`Dockerfile`](file:///Users/abhigyankumar/food_waste_redistribution/Dockerfile), [`scripts/start.sh`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/start.sh) | Multi-stage docker build (`builder` → `runner`), non-root execution (`appuser:10001`), database health polling, auto-migrations via Alembic. |

---

## 🗂️ Section 1: Core Technical Deep Dives (Basic → Advanced → Deep Technical)

### 1. Project Background, Motivation & Problem Solved
* **What problem does it solve?** It bridges the communication and logistics gap between commercial/household food donors (restaurants, bakeries, events, individuals) and receivers (NGOs, shelters, community members). It turns short-shelf-life food surplus into zero-waste distributions before food spoils.
* **Why did you build it?** To demonstrate a production-grade, asynchronous Python web architecture handling real-time inventory claim workflows, concurrency control, background job processing, and containerized deployment.
* **What features are implemented?**
  * Multi-role JWT authentication (`donor`, `receiver`, `admin`).
  * Multipart image uploads with Cloudinary CDN integration and fallback placeholders.
  * Spatial listing discovery via client-side/server-side Haversine distance calculations.
  * Concurrency-safe atomic listing claiming using PostgreSQL row-level locks (`SELECT ... FOR UPDATE`).
  * Background stale listing expiration via FastAPI `BackgroundTasks`.
  * Near-expiry automated notifications using in-process `APScheduler` cron jobs.
  * Store-then-send asynchronous email notification system via `aiosmtplib`.
  * Administrative analytics dashboard featuring Chart.js visualisations and aggregate SQL queries.
  * Dual-mode frontend (REST JSON endpoints + Jinja2 server-rendered pages using `httpOnly` cookies).

---

### 2. Architecture & Data Flow

```
[ Browser / Frontend Client ]
        │
        ├── HTTP Request (Bearer JWT Header OR httpOnly Cookie)
        ▼
[ Uvicorn ASGI Server ]
        │
        ▼
[ FastAPI Application (app/main.py) ]
        │
        ├── CORS & Static File Routing
        ├── Lifespan Event Loop Context Manager ──▶ [ APScheduler Cron (15-min interval) ]
        │                                                    │
        ▼                                                    ▼
[ Auth Dependencies (app/core/dependencies.py) ]    [ Expiry Warning Task ]
        │ (Decodes JWT, checks DB user state, validates role) │
        ▼                                                    │
[ Feature Routers (app/routers/*.py) ]                       │
        │                                                    │
        ├──▶ Listings Router: [ SELECT FOR UPDATE ] ─────────┤
        │                                                    │
        ▼                                                    ▼
[ SQLAlchemy 2.0 Async Session (AsyncSessionLocal) ] ◀───────┘
        │
        ▼
[ PostgreSQL Database (food_waste_db) ]
```

---

### 3. Tech-Stack Choices & Trade-Offs

#### Q: Why FastAPI over Django or Flask?
* **FastAPI:** Built natively on `ASGI` and `asyncio`. Allows non-blocking DB calls and background tasks while maintaining low memory footprint and high throughput. Automatic OpenAPI/Swagger generation via Pydantic type annotations.
* **Django:** Includes "batteries included" ORM and admin panel, but its standard ORM is synchronous by default. Running synchronous DB operations in an async ASGI wrapper often leads to context switching overhead or thread blocking.
* **Flask:** Simple, but WSGI-based (synchronous). Handling concurrent HTTP connections during slow tasks (like image uploads or emails) requires gunicorn worker scaling, consuming significantly more memory.

#### Q: Why SQLAlchemy 2.0 Async (`asyncpg`) over sync SQLAlchemy or Django ORM?
* In an async framework like FastAPI, using a synchronous DB driver (like `psycopg2`) blocks the main event loop while waiting for database network I/O. Every other concurrent request hangs until that query finishes. `asyncpg` combined with SQLAlchemy's `AsyncSession` yields execution back to the asyncio event loop during DB waits.

#### Q: Why APScheduler over Celery + Redis?
* **Celery:** Requires a message broker (Redis/RabbitMQ), a dedicated Celery worker process, and optionally Celery Beat for cron scheduling. That adds 2 to 3 extra infrastructure containers.
* **APScheduler:** Runs in-process inside FastAPI's existing asyncio event loop using `AsyncIOScheduler`. It has zero external dependencies or infrastructure overhead.
* **Trade-off:** If the FastAPI container scales horizontally to multiple instances, APScheduler will run duplicate jobs on every container. Celery is required once distributed task deduplication and worker queues are required.

---

### 4. Code & Implementation Details

#### Q: How does double-claiming prevention work in [`app/routers/listings.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L494-L565)?
Double-claiming is prevented at the database layer using pessimistic row locking. When a receiver calls `POST /listings/{id}/claim`:
```python
result = await db.execute(
    select(FoodListing)
    .where(FoodListing.id == listing_id)
    .with_for_update()  # Acquires PostgreSQL row-level lock (FOR UPDATE)
)
listing = result.scalar_one_or_none()
```
1. `with_for_update()` emits SQL `SELECT ... FOR UPDATE`.
2. If two receivers request the same listing simultaneously, the DB locks the row for transaction 1. Transaction 2 is forced to wait at the DB level.
3. Transaction 1 checks `listing.status == ListingStatus.AVAILABLE`, creates the `Claim` row, updates `listing.status = ListingStatus.CLAIMED`, and commits.
4. Transaction 2 unblocks, reads the updated status (`CLAIMED`), fails the guard condition, and returns `HTTP 409 Conflict`.

#### Q: How is non-blocking image upload implemented in [`app/core/cloudinary_service.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/cloudinary_service.py#L201-L218)?
The Cloudinary Python SDK is synchronous (uses `requests` under the hood). Calling `cloudinary.uploader.upload()` directly in an `async def` route would block the asyncio event loop.  
To solve this, the synchronous SDK call is offloaded to a thread pool executor:
```python
loop = asyncio.get_event_loop()
upload_fn = partial(
    cloudinary.uploader.upload,
    io.BytesIO(data),
    folder=settings.CLOUDINARY_UPLOAD_FOLDER,
)
result = await loop.run_in_executor(None, upload_fn)
```

#### Q: How does spatial Haversine distance filtering work in [`app/core/utils.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/utils.py#L24-L111)?
Instead of external API calls to Google Maps or PostGIS extension requirements, the app uses the Haversine formula on spherical coordinates ($R = 6371.0\text{ km}$):
$$a = \sin^2\left(\frac{\Delta \text{lat}}{2}\right) + \cos(\text{lat}_1) \cdot \cos(\text{lat}_2) \cdot \sin^2\left(\frac{\Delta \text{lon}}{2}\right)$$
$$c = 2 \cdot \arcsin(\sqrt{a}), \quad d = R \cdot c$$
To prevent floating-point rounding errors causing `math.sqrt()` domain errors (e.g. $a = 1.0000000000000002$), the intermediate value $a$ is clamped:
```python
a = max(0.0, min(1.0, a))
```

---

### 5. Authentication & Security Architecture

#### Q: What is the authentication flow and key security primitives?
1. **Password Hashing:** Passwords are hashed with `bcrypt` (cost factor 12) via `passlib.context.CryptContext` ([`app/core/security.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/security.py#L31)). Plaintext passwords never enter the DB or logs.
2. **Timing Attack Protection:** On login ([`app/routers/auth.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py#L168-L173)), if a user is not found, `verify_password` is still executed against a `DUMMY_HASH` string. This ensures the execution time is identical whether the user exists or not, preventing username enumeration via timing attacks.
3. **Role Guards:** Higher-order dependency factory `require_role(*roles)` ([`app/core/dependencies.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/dependencies.py#L140)) creates closures checking user roles before handler execution.
4. **Dual Auth Mechanism:** JSON API endpoints accept `Authorization: Bearer <token>` headers. Jinja2 page endpoints read from `httpOnly`, `SameSite=Lax` cookies ([`app/routers/pages.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/pages.py#L77-L90)) to protect HTML clients against Cross-Site Scripting (XSS) token extraction.
5. **Admin Self-Signup Prevention:** [`POST /auth/signup`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py#L80) explicitly rejects `role = "admin"`. Admin accounts can only be created via the CLI script [`scripts/seed_admin.py`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/seed_admin.py).

---

### 6. AI/LLM Usage Verification
* **Is there any AI / LLM integration in this codebase?**
  * **Verified Fact:** **No.** There are no OpenAI, Anthropic, LangChain, or LLM bindings in `requirements.txt` or the codebase.
  * **Interview Tip:** If an interviewer asks "How did you use AI in this project?", clarify: *"The core platform logic uses deterministic algorithms (Haversine for spatial search, SQL row locks for concurrency, APScheduler for cron). I did not integrate LLMs into the application runtime, though AI assistants were used as pair-programming tools during development."*

---

### 7. Bugs, Weaknesses, Technical Debt & Anti-Patterns

Senior interviewers look for technical debt to verify if you can critically evaluate your own code. Here are the genuine vulnerabilities and architectural limitations in this project:

#### 🚨 1. Spatial Search Does Not Scale in SQL ([`app/routers/listings.py:331-362`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L331-L362))
* **The Flaw:** When `max_distance_km` is supplied to `GET /listings`, the API fetches **ALL** matching listings from Postgres into Python memory, then runs `is_within_distance()` in a Python loop before applying `offset` and `limit`.
* **Why it breaks:** If there are 500,000 active listings, fetching 500,000 ORM objects into Python RAM will cause MemoryError / High Latency.
* **The Fix:** Implement a Bounding-Box pre-filter in SQL before the Haversine calculation:
  $$\Delta \text{lat} \approx \frac{\text{max\_km}}{111}, \quad \Delta \text{lon} \approx \frac{\text{max\_km}}{111 \cdot \cos(\text{lat})}$$
  Add `WHERE latitude BETWEEN (lat - delta_lat) AND (lat + delta_lat)` to let Postgres index `ix_food_listings_lat_lon` filter down the row count in SQL first. Alternatively, migrate to PostgreSQL `PostGIS` (`ST_DWithin`).

#### 🚨 2. Non-Standard REST Mutation via GET ([`app/routers/notifications.py:99`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/notifications.py#L99))
* **The Flaw:** Marking a notification as read is implemented as `GET /notifications/{id}/read`.
* **Why it breaks:** According to RFC 7231, HTTP `GET` must be safe and idempotent (no state mutation). Caching proxies, browser pre-fetchers, or CDN edge nodes might pre-fetch `GET` links, accidentally marking notifications as read without user interaction.
* **The Fix:** Refactor to `PATCH /notifications/{id}` or `POST /notifications/{id}/read`.

#### 🚨 3. In-Process Scheduler Duplicate Job Vulnerability ([`app/core/scheduler.py:64`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py#L64))
* **The Flaw:** `APScheduler` is initialized inside the FastAPI web process.
* **Why it breaks:** If the web app is deployed across 4 horizontal instances (e.g., behind a load balancer or Kubernetes HPA with `replicas: 4`), all 4 instances will execute `check_expiring_listings()` simultaneously every 15 minutes, causing duplicate database queries and notification processing.
* **The Fix:** Decouple scheduler execution from the web container into a single-instance worker container, or use a distributed lock (e.g., `redis-lock` / Postgres advisory lock `pg_try_advisory_lock`).

#### 🚨 4. Fragile Notification Deduplication ([`app/core/scheduler.py:142`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py#L142))
* **The Flaw:** Deduplication checks if a notification was already sent by matching a string pattern in text: `Notification.message.contains(f"[expiry-warn:{listing.id}]")`.
* **Why it breaks:** Doing full-text substring matching on an un-indexed text column in the `notifications` table degrades as notification history grows.
* **The Fix:** Add a dedicated timestamp column `expiry_warned_at: Mapped[datetime | None]` directly on the `FoodListing` table.

#### 🚨 5. In-Memory SQLite vs. Production PostgreSQL Test Discrepancy ([`tests/conftest.py:44`](file:///Users/abhigyankumar/food_waste_redistribution/tests/conftest.py#L44))
* **The Flaw:** Tests use `sqlite+aiosqlite:///:memory:` while production uses PostgreSQL `asyncpg`.
* **Why it breaks:** SQLite does not support native ENUMs, `SELECT ... FOR UPDATE` row locks, or PostgreSQL specific features. Race condition tests for row locking cannot truly execute against SQLite's single-writer architecture.
* **The Fix:** Use `testcontainers-python` to spin up an ephemeral PostgreSQL Docker container during integration tests.

---

## 🎭 Section 2: Behavioral & Project-Experience Questions

#### Q1: What was the single biggest engineering challenge you faced in this project?
* **Answer:** *"Designing the claim workflow so that two users pressing 'Claim' at the exact same millisecond could never double-claim the same item. Initially, I considered application-level locks using Python's `asyncio.Lock()`, but realized that wouldn't work once deployed across multiple container instances. I solved it by delegating atomicity to PostgreSQL using `SELECT ... FOR UPDATE` row locks inside an explicit transaction block."*

#### Q2: Tell me about a difficult bug you encountered and how you debugged it.
* **Answer:** *"When implementing background email notifications using `aiosmtplib`, the app was throwing `RuntimeError: Task attached to a different loop`. I discovered that starting `APScheduler` at module import time captured the loop before FastAPI initialized Uvicorn's event loop. I resolved it by moving `scheduler.start()` inside FastAPI's async `lifespan` context manager, ensuring the scheduler inherits the active running event loop."*

#### Q3: What design decision are you most proud of?
* **Answer:** *"The store-then-send notification pattern. Instead of making the HTTP request block on third-party SMTP server availability, the route writes the `Notification` record to PostgreSQL within the database transaction, then delegates the email send to a non-blocking `BackgroundTask`. If SMTP fails or times out, the user still sees their in-app notification and the HTTP request returns instantly."*

#### Q4: What mistake did you make during development, and what did you learn?
* **Answer:** *"I initially accepted JSON bodies for listing creation, but when adding image uploads, I realized standard HTTP doesn't allow mixing binary file streams and raw JSON payloads in a single request. I had to refactor `POST /listings` to accept `multipart/form-data` with individual `Form(...)` parameters. I learned to design API contracts with media attachments in mind from day one."*

#### Q5: If you had one more month to work on this project, what would you improve?
* **Answer:**
  1. Migrate spatial search to PostgreSQL `PostGIS` to perform real spatial indexing instead of loading rows into Python memory.
  2. Extract `APScheduler` out of the web container into a dedicated background worker container.
  3. Replace the SQLite test database with ephemeral PostgreSQL instances via `testcontainers`.
  4. Add token revocation (JWT blacklist) via Redis.

---

## 🏆 Section 3: Top 50 Questions You MUST Know

### 🔹 Architecture & General Design (1–10)
1. **Q: What is the main entry point of the application and how is it assembled?**  
   *A:* [`app/main.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/main.py) instantiates `FastAPI()`, mounts CORS middleware, static files at `/static`, registers 5 feature routers, and manages startup/shutdown via the async `lifespan` context manager.
2. **Q: How does the application implement the 12-Factor App methodology for configuration?**  
   *A:* Via `pydantic-settings` in [`app/core/config.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/config.py). Variables are loaded from environment/`.env` files without hardcoding sensitive defaults into source control.
3. **Q: What is the difference between WSGI and ASGI?**  
   *A:* WSGI (e.g. Flask/Django) is synchronous and handles one request per worker thread/process. ASGI (e.g. FastAPI/Uvicorn) is asynchronous, handling thousands of concurrent connections on a single event loop via non-blocking I/O.
4. **Q: Why are database migrations necessary and how are they managed here?**  
   *A:* Alembic tracks ORM schema changes version by version in [`migrations/versions/`](file:///Users/abhigyankumar/food_waste_redistribution/migrations/versions/). `alembic upgrade head` is executed on container startup by [`scripts/start.sh`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/start.sh).
5. **Q: What is the benefit of using SQLAlchemy 2.0 style queries over legacy 1.x query objects?**  
   *A:* SQLAlchemy 2.0 uses explicit `select()`, `update()`, and `delete()` statements with `session.execute()`, harmonizing type hints and fully supporting async execution.
6. **Q: How are static files and HTML templates served?**  
   *A:* `StaticFiles` mounts `app/static` at `/static`. `Jinja2Templates` in [`app/routers/pages.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/pages.py) renders server-side HTML pages.
7. **Q: How is the database connection string normalized for Render/Railway?**  
   *A:* A Pydantic `@field_validator` in [`app/core/config.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/config.py#L40) automatically converts `postgres://` or `postgresql://` prefixes to `postgresql+asyncpg://`.
8. **Q: How is the admin analytics dashboard populated?**  
   *A:* `_gather_stats()` in [`app/routers/admin.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/admin.py#L56) executes aggregate SQL queries (`func.count()`, `group_by`, date casting) and passes the data to Chart.js via Jinja2 templates.
9. **Q: Why is there a custom Jinja2 filter added in main.py?**  
   *A:* `admin.templates.env.filters["zip"] = zip` registers Python's native `zip()` function so templates can iterate over two parallel arrays simultaneously.
10. **Q: How does the application handle graceful shutdown?**  
    *A:* `lifespan` in `app/main.py` yields control while running, and on shutdown calls `scheduler.shutdown(wait=True)` to wait for running jobs to finish before terminating.

---

### 🔹 Authentication & Security (11–20)
11. **Q: Which hashing algorithm is used for passwords and why?**  
    *A:* `bcrypt` via `passlib` ([`app/core/security.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/security.py)). It includes automatic salt generation and a configurable cost factor (work factor) to resist hardware brute-forcing.
12. **Q: What claims are stored inside the JWT access token?**  
    *A:* `sub` (subject: the stringified user ID) and `exp` (expiration Unix timestamp).
13. **Q: How does access token expiration work?**  
    *A:* The server checks `exp` on every request inside `decode_access_token()`. If the current time exceeds `exp`, `jose.JWTError` is raised and the user receives HTTP 401.
14. **Q: What is the purpose of the custom `type: refresh` claim in refresh tokens?**  
    *A:* It prevents clients from using long-lived refresh tokens in the `Authorization: Bearer` header of standard API endpoints.
15. **Q: How does FastAPI's `OAuth2PasswordBearer` dependency work?**  
    *A:* It extracts the token from the `Authorization: Bearer <token>` HTTP header and powers the OpenAPI Swagger UI "Authorize" modal.
16. **Q: Why does `get_current_user` query the DB if the JWT is already cryptographically valid?**  
    *A:* JWTs are stateless. A user might have been deleted, banned, or had their role revoked after token issuance. The DB check enforces active user status ([`app/core/dependencies.py:129`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/dependencies.py#L129)).
17. **Q: How are non-API HTML pages authenticated?**  
    *A:* Through `httpOnly`, `SameSite=Lax` cookies named `access_token` read by `_get_current_user_from_cookie()` in [`app/routers/pages.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/pages.py#L93).
18. **Q: Why is `httpOnly` important for cookies?**  
    *A:* It prevents client-side JavaScript (`document.cookie`) from accessing the token, protecting against XSS token theft.
19. **Q: How does the login route protect against user enumeration via timing attacks?**  
    *A:* If a user email is not found in the DB, `verify_password()` is executed against a constant `DUMMY_HASH` so the operation always consumes ~100ms of CPU time ([`app/routers/auth.py:169`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py#L169)).
20. **Q: Why is self-signup for the Admin role blocked in the signup API?**  
    *A:* Allowing public signups to grant `admin` privileges is a critical security vulnerability. Admins must be provisioned out-of-band via [`scripts/seed_admin.py`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/seed_admin.py).

---

### 🔹 Database & Concurrency (21–30)
21. **Q: What database engine is used in production versus testing?**  
    *A:* PostgreSQL (`asyncpg`) in production; in-memory SQLite (`aiosqlite`) in tests.
22. **Q: How does `get_db()` prevent connection leaks?**  
    *A:* It uses an async generator (`yield`). FastAPI guarantees execution enters the `finally:` block after request completion, executing `await session.close()` ([`app/db/database.py:74`](file:///Users/abhigyankumar/food_waste_redistribution/app/db/database.py#L74)).
23. **Q: What does `expire_on_commit=False` do in session configuration?**  
    *A:* It allows ORM object attributes to be read after `await session.commit()` without triggering implicit, synchronous I/O DB re-fetches.
24. **Q: How is pessimistic locking used in the claim workflow?**  
    *A:* `select(FoodListing).with_for_update()` issues a row lock in PostgreSQL, ensuring concurrent claim operations process sequentially ([`app/routers/listings.py:530`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L530)).
25. **Q: What is the difference between pessimistic and optimistic locking?**  
    *A:* Pessimistic locking (`FOR UPDATE`) locks the row on read until commit. Optimistic locking uses a version column and checks if the version changed on write, failing if a conflict occurred.
26. **Q: What is `selectinload` and why is it used?**  
    *A:* `selectinload(FoodListing.donor)` pre-fetches related objects using a secondary `SELECT ... WHERE id IN (...)` query, preventing N+1 lazy loading errors in async SQLAlchemy.
27. **Q: What table indexes are defined in `FoodListing`?**  
    *A:* `ix_food_listings_status_expiry` (status + expiry), `ix_food_listings_lat_lon` (latitude + longitude), and `ix_food_listings_donor_status` (donor_id + status) ([`app/models/food_listing.py:136`](file:///Users/abhigyankumar/food_waste_redistribution/app/models/food_listing.py#L136)).
28. **Q: How is soft-deletion implemented for listings?**  
    *A:* `DELETE /listings/{id}` sets `status = ListingStatus.CANCELLED` instead of issuing a SQL `DELETE` statement, preserving historical audit data ([`app/routers/listings.py:486`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L486)).
29. **Q: What happens if a User row is deleted in PostgreSQL?**  
    *A:* Foreign keys use `ondelete="CASCADE"`, so deleting a user automatically cascades and deletes their associated listings, claims, and notifications.
30. **Q: How does `expire_stale_listings()` work as a background task?**  
    *A:* It runs a bulk SQL `UPDATE food_listings SET status='expired' WHERE status='available' AND expiry_time < NOW()` using a fresh `AsyncSessionLocal()` session ([`app/routers/listings.py:97`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L97)).

---

### 🔹 Background Jobs, Email & External Services (31–40)
31. **Q: How often does the scheduler run and what job does it execute?**  
    *A:* Every 15 minutes, executing `check_expiring_listings()`, which finds listings expiring within 1 hour and notifies donors ([`app/core/scheduler.py:60`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py#L60)).
32. **Q: Why does the scheduler create a new session instead of reusing a request session?**  
    *A:* Scheduler jobs run independently on a timer when no HTTP request is active, requiring their own session lifecycle via `AsyncSessionLocal()`.
33. **Q: What is the "store-then-send" pattern in notifications?**  
    *A:* The `Notification` row is committed to the database first. The email is sent second via a non-blocking background task. Email failure does not roll back the database notification ([`app/core/notification_service.py:20`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/notification_service.py#L20)).
34. **Q: Why is `aiosmtplib` used instead of Python's standard `smtplib`?**  
    *A:* `smtplib` is synchronous and blocks the asyncio event loop during network handshakes. `aiosmtplib` is fully asynchronous.
35. **Q: What happens if `EMAILS_ENABLED=False` in `.env`?**  
    *A:* `send_email()` logs a message and returns `False` without raising errors or attempting an SMTP connection ([`app/core/email_service.py:145`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/email_service.py#L145)).
36. **Q: How are image upload types and sizes validated?**  
    *A:* [`app/core/cloudinary_service.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/cloudinary_service.py#L107) validates both the file extension (`.jpg`, `.jpeg`, `.png`) and the `content_type` header, enforcing a `MAX_FILE_SIZE_BYTES` limit of 5 MB (`413 Payload Too Large`).
37. **Q: Why are images uploaded to Cloudinary instead of saved to local disk?**  
    *A:* Ephemeral filesystems on container platforms (Render/Railway/Kubernetes) wipe local disk files on redeployment. Cloudinary provides persistent storage served via a global CDN.
38. **Q: What happens if a user submits a listing without an image?**  
    *A:* `upload_image(None)` returns a stable `PLACEHOLDER_IMAGE_URL` string so `image_url` is never `NULL` ([`app/core/cloudinary_service.py:75`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/cloudinary_service.py#L75)).
39. **Q: Why is `run_in_executor` needed for Cloudinary uploads?**  
    *A:* The Cloudinary SDK is synchronous. `loop.run_in_executor(None, upload_fn)` offloads the blocking I/O call to a background thread pool.
40. **Q: How are background tasks registered in FastAPI route responses?**  
    *A:* By injecting `background_tasks: BackgroundTasks` into the route handler and calling `background_tasks.add_task(func, *args)`.

---

### 🔹 Testing, Docker & Deployment (41–50)
41. **Q: How does the test suite achieve test isolation?**  
    *A:* An `autouse=True` fixture in [`tests/conftest.py`](file:///Users/abhigyankumar/food_waste_redistribution/tests/conftest.py#L60) executes `Base.metadata.create_all` before every test and `Base.metadata.drop_all` after every test using a `StaticPool` in-memory SQLite database.
42. **Q: How are external network calls prevented during testing?**  
    *A:* `mock_external_services` in `conftest.py` uses `unittest.mock.patch` to mock `upload_image`, `send_email`, and `scheduler.start/shutdown`.
43. **Q: What library is used to issue test HTTP requests against FastAPI?**  
    *A:* `httpx.AsyncClient` wrapped around `httpx.ASGITransport(app=app)`.
44. **Q: Why does the `Dockerfile` use a multi-stage build?**  
    *A:* Stage 1 (`builder`) installs gcc and compiles binary wheels. Stage 2 (`runner`) copies only the compiled `/opt/venv` into a slim runtime image, reducing image size and attack surface ([`Dockerfile`](file:///Users/abhigyankumar/food_waste_redistribution/Dockerfile)).
45. **Q: Why is the container run under user `appuser` (UID 10001) instead of `root`?**  
    *A:* Principle of Least Privilege. Running as non-root prevents container breakout exploits from obtaining root privileges on the host OS.
46. **Q: What does `scripts/start.sh` do during container startup?**  
    *A:* It polls the database connection until healthy, executes `alembic upgrade head`, and uses `exec uvicorn` to replace the shell process as PID 1 ([`scripts/start.sh`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/start.sh)).
47. **Q: Why is `exec` used before `uvicorn` in `start.sh`?**  
    *A:* `exec` replaces the shell process so Uvicorn receives process signals (like `SIGTERM`) directly from Docker/Kubernetes for graceful shutdowns.
48. **Q: How does `docker-compose.yml` verify Postgres is ready before starting the app?**  
    *A:* Using a `healthcheck` running `pg_isready -U postgres` and setting `depends_on.db.condition: service_healthy` ([`docker-compose.yml:59`](file:///Users/abhigyankumar/food_waste_redistribution/docker-compose.yml#L59)).
49. **Q: How does CI/CD integration work for this project?**  
    *A:* Pushing to `main` triggers GitHub Actions to run pytest. Upon success, it calls the Render deploy hook URL stored in repository secrets.
50. **Q: What is the main operational limitation of the current spatial search implementation?**  
    *A:* It performs Haversine distance filtering in Python memory rather than filtering at the database layer using spatial SQL indexes (PostGIS).

---

## 🎙️ Section 4: 20-Question Realistic Mock Interview

> **Format:** Senior Technical Interviewer (**Interviewer**) vs. Candidate (**You**).

### Question 1: "Tell me about your project."
* **Interviewer:** "Can you start by giving me an overview of what you built, the stack you chose, and the core problems it addresses?"
* **You:** "I built a Food Waste Redistribution Platform designed to connect food donors like restaurants and households with receivers like NGOs and individuals. The backend is built with Python 3.12 and FastAPI running asynchronously with SQLAlchemy 2.0 and PostgreSQL via `asyncpg`. It features role-based JWT authentication, real-time spatial filtering via the Haversine formula, Cloudinary CDN image uploads, and background job scheduling via APScheduler for expiring listing notifications. I containerized it using a multi-stage Docker build running as a non-root user with automated Alembic database migrations."

---

### Question 2: "Why did you choose FastAPI over traditional frameworks like Django or Flask?"
* **Interviewer:** "Django has a built-in admin panel and ORM, while Flask is very simple. Why FastAPI?"
* **You:** "FastAPI is built natively on ASGI and Python's `asyncio` event loop. In a food redistribution system where endpoints handle concurrent database reads, background tasks, and external image uploads, asynchronous non-blocking I/O allows a single server process to handle high connection concurrency without thread pool starvation. Additionally, FastAPI uses Pydantic for request validation and auto-generates OpenAPI documentation directly from type hints."

---

### Question 3: "Walk me through how you prevent two receivers from claiming the exact same listing at the same time."
* **Interviewer:** "Suppose two users click 'Claim' simultaneously on the last available listing. How does your backend guarantee only one succeeds?"
* **You:** "I enforce atomicity at the database level using pessimistic row locking in PostgreSQL. In [`app/routers/listings.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/listings.py#L530), when a claim request arrives, I execute `select(FoodListing).where(FoodListing.id == listing_id).with_for_update()`. This issues a SQL `SELECT ... FOR UPDATE` statement. PostgreSQL locks that specific row. The second concurrent request is forced to block at the database level until the first transaction commits. When the first transaction commits, the listing's status changes to `claimed`. When the second transaction unblocks and executes its status check, it sees status is no longer `available` and fails with HTTP 409 Conflict."

---

### Question 4: "Why use database row locking instead of an in-memory lock in Python using `asyncio.Lock()`?"
* **Interviewer:** "Wouldn't an `asyncio.Lock()` be faster than hitting the database?"
* **You:** "An `asyncio.Lock()` only works inside a single Python process. If the application scales horizontally to 2 or more container instances behind a load balancer, each instance would have its own isolated memory space. Two requests hitting two separate containers would both acquire their local `asyncio.Lock()` and cause a double-claim. The PostgreSQL database is the single source of truth across all application nodes."

---

### Question 5: "I noticed you use Cloudinary for image uploads. The Cloudinary Python SDK is synchronous. Did that cause any issues in your async routes?"
* **Interviewer:** "If you call a synchronous library inside an `async def` FastAPI route, what happens?"
* **You:** "Calling a synchronous blocking function directly inside an `async def` route blocks the main asyncio event loop, pausing all other concurrent request handling until the upload completes. In [`app/core/cloudinary_service.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/cloudinary_service.py#L217), I solved this by wrapping the synchronous `cloudinary.uploader.upload()` call in `await loop.run_in_executor(None, upload_fn)`. This offloads the network transfer to a background thread pool executor, keeping the main event loop responsive."

---

### Question 6: "How do you calculate distance for nearby food listings, and what are the limitations of your approach?"
* **Interviewer:** "How does your proximity search work in `GET /listings`?"
* **You:** "I calculate great-circle distance using the Haversine formula in [`app/core/utils.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/utils.py). It takes user coordinates and listing coordinates and computes distance in kilometers. The major limitation of my current implementation is that filtering happens in Python memory. In `list_listings()`, if `max_distance_km` is provided, all matching rows are fetched into memory first before applying Haversine and paginating. At scale, this should be refactored to use a bounding-box SQL query or PostgreSQL's `PostGIS` extension (`ST_DWithin`) to filter rows directly on indexed spatial columns in SQL."

---

### Question 7: "How does your background scheduler work, and how did you integrate it with FastAPI?"
* **Interviewer:** "Where does your scheduler run, and why did you choose APScheduler over Celery?"
* **You:** "I use `APScheduler`'s `AsyncIOScheduler` configured in [`app/core/scheduler.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py). I chose it over Celery because Celery requires a separate Redis/RabbitMQ broker and a worker process. For a single periodic job checking expiring listings every 15 minutes, APScheduler runs directly inside FastAPI's event loop with zero additional infrastructure. I start it inside FastAPI's async `lifespan` context manager in `main.py` so it initializes after the event loop is active and shuts down cleanly on SIGTERM."

---

### Question 8: "What happens to email delivery if the SMTP server goes down or times out?"
* **Interviewer:** "If Mailtrap or SendGrid is unresponsive, does the user's claim fail?"
* **You:** "No. I implemented a 'store-then-send' architecture. When a listing is claimed, the route handler creates and commits the `Notification` record to PostgreSQL within the primary database transaction. The email sending function `send_email` is passed to FastAPI's `BackgroundTasks`. The HTTP response returns `201 Created` immediately. If `aiosmtplib` encounters an SMTP or network timeout, the exception is caught, logged, and suppressed ([`app/core/email_service.py:188`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/email_service.py#L188)). The in-app notification remains safely stored in the database."

---

### Question 9: "How does authentication work for both API clients and browser clients in your app?"
* **Interviewer:** "You have JSON endpoints and Jinja2 HTML endpoints. How do their auth mechanisms differ?"
* **You:** "API endpoints accept an `Authorization: Bearer <JWT>` header processed by `get_current_user` in `dependencies.py`. For Jinja2 HTML pages in `pages.py`, browser forms submit to `/login`, which sets an `httpOnly`, `SameSite=Lax` cookie containing the JWT. `_get_current_user_from_cookie()` inspects this cookie on page navigation. Using `httpOnly` cookies for HTML pages prevents client-side JavaScript from accessing the token via XSS."

---

### Question 10: "How do you protect your login endpoint against timing attacks?"
* **Interviewer:** "How could an attacker figure out if an email exists in your database just by analyzing HTTP response times?"
* **You:** "Comparing a password using `bcrypt` takes ~100ms. If an attacker submits a non-existent email, and the server returns immediately without running `bcrypt`, that request returns in 5ms versus 100ms for an existing user. I mitigated this in [`app/routers/auth.py:169`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py#L169): if `user` is `None`, the route still executes `verify_password(form_data.password, DUMMY_HASH)`. Running `bcrypt` against a dummy hash ensures every login attempt takes identical execution time."

---

### Question 11: "Explain how user roles are enforced across different API endpoints."
* **Interviewer:** "How do you restrict `POST /listings` to donors only?"
* **You:** "I created a higher-order dependency factory function `require_role(*roles)` in [`app/core/dependencies.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/dependencies.py#L140). It takes allowed roles and returns a closure dependency that inspects `current_user.role`. I defined type aliases like `DonorUser = Annotated[User, Depends(require_role(UserRole.DONOR))]`. In route handlers, declaring `current_user: DonorUser` automatically enforces that `get_current_user` runs first, followed by the role check. If unauthorized, it raises HTTP 403 Forbidden before the route body executes."

---

### Question 12: "Why do you create Admin accounts via a CLI script instead of an API route?"
* **Interviewer:** "Why isn't there an option to sign up as an admin on `/auth/signup`?"
* **You:** "Self-signup for administrative roles creates a critical security vulnerability. [`POST /auth/signup`](file:///Users/abhigyankumar/food_waste_redistribution/app/routers/auth.py#L80) explicitly blocks `role == UserRole.ADMIN`. Admins must be provisioned via a dedicated CLI script [`scripts/seed_admin.py`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/seed_admin.py) executed directly on the host or inside a secure deployment pipeline using environment variables. This limits admin creation access strictly to system operators."

---

### Question 13: "Tell me about your test setup. Why do you mock external services?"
* **Interviewer:** "How do your unit/integration tests run without calling Cloudinary or sending real emails?"
* **You:** "In [`tests/conftest.py`](file:///Users/abhigyankumar/food_waste_redistribution/tests/conftest.py), I configured an `autouse=True` fixture `mock_external_services` using `unittest.mock.patch`. It replaces `upload_image` with a mock function returning a deterministic placeholder URL, mocks `send_email` with an `AsyncMock`, and neutralizes `scheduler.start/shutdown`. This makes the test suite completely offline, deterministic, and fast."

---

### Question 14: "I noticed your test setup uses SQLite in-memory, but production uses PostgreSQL. What problems can that cause?"
* **Interviewer:** "Is testing against SQLite while running Postgres in production a good practice?"
* **You:** "It is a trade-off. SQLite in-memory allows tests to run extremely fast without local Postgres dependencies. However, it introduces architectural drift: SQLite doesn't enforce PostgreSQL native ENUMs, handle timezone-aware datetimes the same way, or support row-level locking (`SELECT ... FOR UPDATE`). A better production approach would be using `testcontainers-python` to launch an ephemeral PostgreSQL Docker container during pytest runs."

---

### Question 15: "Why did you build a multi-stage Dockerfile?"
* **Interviewer:** "What advantages does a multi-stage Docker build offer over a single-stage build?"
* **You:** "My [`Dockerfile`](file:///Users/abhigyankumar/food_waste_redistribution/Dockerfile) uses two stages: `builder` and `runner`. The `builder` stage uses `python:3.12-slim` to install gcc, build headers, and compile binary wheels into `/opt/venv`. The `runner` stage copies *only* the compiled `/opt/venv` and application code into a fresh slim base image. This dramatically reduces final container image size and strips out build tools like compilers, minimizing the security attack surface."

---

### Question 16: "Why do you run the Docker container under a non-root user?"
* **Interviewer:** "In your Dockerfile, you create `appuser` with UID 10001. Why is this necessary?"
* **You:** "By default, Docker containers run as root (UID 0). If a Remote Code Execution (RCE) vulnerability occurs inside a root container, the attacker has root access within the container namespace, increasing the risk of container breakout. Running as a dedicated non-root user (`appuser:10001`) adheres to the Principle of Least Privilege and satisfies enterprise security constraints."

---

### Question 17: "How does `scripts/start.sh` handle startup orchestration in production?"
* **Interviewer:** "What happens when your container boots up on Render or Railway?"
* **You:** "[`scripts/start.sh`](file:///Users/abhigyankumar/food_waste_redistribution/scripts/start.sh) first executes a Python inline script that loops up to 30 times pinging `SELECT 1` against the database to wait for connection readiness. Once ready, it runs `alembic upgrade head` to automatically apply pending database migrations. Finally, it uses `exec uvicorn` to launch the web server. `exec` ensures Uvicorn replaces the shell as PID 1 to receive process termination signals directly."

---

### Question 18: "What is a flaw in your notification code that you would refactor if you had more time?"
* **Interviewer:** "If you had to critique your notification deduplication logic, what would you change?"
* **You:** "In [`app/core/scheduler.py:142`](file:///Users/abhigyankumar/food_waste_redistribution/app/core/scheduler.py#L142), deduplication checks if a notification was sent by querying `Notification.message.contains(f'[expiry-warn:{listing.id}]')`. Parsing substring markers in a text column is brittle and slow at scale. I would refactor this by adding a dedicated `expiry_warned_at: Mapped[datetime | None]` column directly to the `food_listings` table."

---

### Question 19: "How does your application handle database session scoping per request?"
* **Interviewer:** "How do you ensure requests don't leak database connections or share state?"
* **You:** "I use FastAPI's dependency injection system with `get_db()` in [`app/db/database.py`](file:///Users/abhigyankumar/food_waste_redistribution/app/db/database.py). `get_db()` instantiates `AsyncSessionLocal()` inside an `async with` block and `yield`s the session to the route. When the request completes or raises an exception, FastAPI resumes execution after `yield` and enters the `finally:` block to close the session."

---

### Question 20: "If this application experienced 100x traffic tomorrow, what parts of the system would break first and how would you fix them?"
* **Interviewer:** "Walk me through your scaling bottleneck analysis."
* **You:**
  1. **Spatial Search:** Python-side Haversine distance filtering will cause CPU and RAM exhaustion. *Fix:* Replace with PostGIS spatial indexes.
  2. **In-Process Scheduler:** Multiple container instances will execute duplicate background jobs. *Fix:* Extract APScheduler to a single worker process or use Redis distributed locks.
  3. **Database Connection Limits:** High request concurrency will exhaust PostgreSQL connection pools. *Fix:* Introduce `PgBouncer` for connection pooling.
  4. **Token Revocation:** Short-lived access tokens cannot be revoked before 30 minutes. *Fix:* Introduce a Redis-backed token blacklist.

---
