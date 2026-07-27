# Food Waste Redistribution Platform — Phase-wise Vibecoding Prompts

## Phase 0 — Project Setup & Structure

```
I'm building a Food Waste Redistribution Platform as a portfolio project.

Tech stack:
- Backend: FastAPI + SQLAlchemy (async) + PostgreSQL
- Frontend: Jinja2 templates + HTML/CSS (no JS framework, keep JS minimal/vanilla)
- Auth: JWT
- Deployment target: Docker, later deployed on Render/Railway

Set up the initial project structure with best practices for a FastAPI project meant to
scale to ~8-10 routers. Include:
- app/main.py (entrypoint)
- app/core/ (config.py using pydantic-settings, security.py for JWT/password hashing)
- app/db/ (database.py for async engine/session, base.py for declarative base)
- app/models/ (SQLAlchemy models, empty for now)
- app/schemas/ (Pydantic schemas, empty for now)
- app/routers/ (empty for now)
- app/templates/ and app/static/ for Jinja2 + CSS
- requirements.txt
- .env.example
- alembic setup for migrations
- A basic README explaining how to run the project locally

Explain briefly (in comments or README) what each folder is for, since I'm a fresher and
need to understand this well enough to explain it in interviews.
```

---

## Phase 1 — Database Models

```
Continuing the Food Waste Redistribution Platform (FastAPI + SQLAlchemy async + PostgreSQL,
project structure already set up as in Phase 0).

Create SQLAlchemy models for:

1. User
   - id, name, email (unique), hashed_password, role (enum: donor, receiver, admin),
     phone, is_verified, created_at

2. FoodListing
   - id, donor_id (FK to User), title, description, food_type (enum: cooked, packaged,
     raw, bakery, other), quantity, quantity_unit, latitude, longitude, address,
     pickup_window_start, pickup_window_end, expiry_time, image_url (nullable),
     status (enum: available, claimed, picked_up, expired, cancelled), created_at

3. Claim
   - id, listing_id (FK), receiver_id (FK to User), claimed_at, status
     (enum: pending, confirmed, completed, cancelled), notes

4. Notification (keep simple)
   - id, user_id (FK), message, is_read, created_at

Requirements:
- Use SQLAlchemy 2.0 style (Mapped, mapped_column)
- Proper relationships (User.listings, User.claims, FoodListing.claims etc.)
- Add appropriate indexes (email, status, expiry_time, lat/long)
- Generate an Alembic migration for these models
- Also generate matching Pydantic schemas in app/schemas/ (Base, Create, Update, Read
  variants for each model)

Explain the relationships briefly so I understand the FK structure.
```

---

## Phase 2 — Authentication (JWT + Role-based Access)

```
Continuing the Food Waste Redistribution Platform (FastAPI + SQLAlchemy async +
PostgreSQL, models from Phase 2 already exist: User, FoodListing, Claim, Notification).

Implement authentication:
- POST /auth/signup — creates a user with hashed password (bcrypt via passlib), role
  selectable (donor/receiver); admin accounts should not be self-signup-able (create
  a separate admin-seeding script instead)
- POST /auth/login — OAuth2PasswordRequestForm-based, returns JWT access token
  (and optionally refresh token)
- A get_current_user dependency that decodes JWT and fetches the user
- A role-checking dependency factory, e.g. require_role("donor") that I can use on routes
- GET /auth/me — returns current logged-in user's profile

Requirements:
- Use python-jose or pyjwt for token handling
- Store secret key and token expiry in config via pydantic-settings
- Passwords never returned in any response
- Add clear docstrings/comments since I need to explain JWT flow, password hashing,
  and dependency injection in interviews — comment on WHY each piece exists, not just what it does
```

---

## Phase 3 — Food Listing CRUD + Status Workflow

```
Continuing the Food Waste Redistribution Platform. Auth from Phase 3 exists
(get_current_user, require_role dependencies).

Implement FoodListing endpoints under /listings:
- POST /listings — donor-only, creates a listing (status defaults to "available")
- GET /listings — public/receiver, list all listings with filters: food_type, status,
  max_distance_km (using lat/long + haversine formula — NOT external routing APIs),
  and pagination (limit/offset)
- GET /listings/{id} — get single listing detail
- PUT /listings/{id} — donor-only, only the owning donor can edit, only if status is
  still "available"
- DELETE /listings/{id} — donor-only, soft delete (set status to "cancelled")
- POST /listings/{id}/claim — receiver-only, creates a Claim record, sets listing
  status to "claimed" (use a DB transaction so this is atomic — no double-claiming)
- POST /listings/{id}/complete — donor or receiver, marks Claim as "completed" and
  listing as "picked_up"

Also implement:
- A background task (FastAPI BackgroundTasks or a simple scheduled check) that marks
  listings as "expired" once expiry_time has passed and status is still "available"

Write the haversine distance function as a small utility in app/core/utils.py and
explain how it works in a comment (this is the "smart matching" feature I need to
be able to explain without invoking ML).
```

---

## Phase 4 — Notifications (Email)

```
Continuing the Food Waste Redistribution Platform. Listings + Claims from Phase 4 exist.

Implement basic notifications:
- When a listing is claimed, send an email to the donor (use FastAPI-Mail or a simple
  SMTP client with Gmail/Mailtrap for dev, and mention how to swap in SendGrid/Resend
  for production)
- When a listing is about to expire (e.g. within 1 hour of expiry_time), trigger a
  notification to the donor — implement this as a periodic background job (APScheduler
  is fine for this scale, explain why we're not using Celery here — keep it simple)
- Store notifications in the Notification table regardless of email success, so there's
  an in-app notification list too
- GET /notifications — current user's notifications, GET /notifications/{id}/read to
  mark as read

Keep the email templates very simple plain text for now. Add clear .env variables for
SMTP config with sensible defaults/comments for local dev.
```

---

## Phase 5 — Image Upload

```
Continuing the Food Waste Redistribution Platform.

Add image upload for FoodListing:
- Modify POST /listings to accept an optional image file (multipart/form-data)
- Store images using [Cloudinary free tier — preferred since local disk won't persist
  on Render/Railway]. Show me how to set up a Cloudinary account and where to put the
  API keys in .env
- Save the returned image_url on the FoodListing record
- Add basic validation: file type (jpg/png only), max size (e.g. 5MB)
- Add a fallback placeholder image if none is provided

Explain briefly why we shouldn't store images directly in Postgres or on local disk
in a deployed app — I want to be able to answer this if asked in an interview.
```

---

## Phase 6 — Analytics Dashboard (Admin)

```
Continuing the Food Waste Redistribution Platform.

Implement a simple analytics dashboard:
- GET /admin/stats (admin-only) — returns JSON with: total listings, active listings,
  completed pickups (proxy for "meals saved"), total registered donors/receivers,
  listings by food_type breakdown, and a simple time-series of listings-per-day for
  the last 30 days
- Use raw SQLAlchemy aggregate queries (func.count, func.sum, group_by) — no extra
  libraries needed
- Add a simple Jinja2 template page at /admin/dashboard that renders these stats as
  plain HTML with a couple of basic bar charts using Chart.js via CDN (vanilla JS,
  no build step needed since I don't know JS frameworks)

Keep the frontend minimal — table + 2 charts is enough. Explain the SQL aggregate
queries in comments since I'll need to explain the analytics logic.
```

---

## Phase 7 — Frontend Pages (Jinja2 + HTML/CSS)

```
Continuing the Food Waste Redistribution Platform. All backend APIs from Phases 3-7 exist.

Build server-rendered Jinja2 pages (since I only know HTML/CSS, keep JS minimal —
just enough for form submission via fetch() and simple dynamic bits):
1. Landing page — explains the platform, CTA to sign up as donor/receiver
2. Signup/Login pages
3. Donor dashboard — list their own listings, form to create new listing, status badges
4. Receiver/browse page — list of available listings with filters (food type, distance,
   sort by expiry), claim button
5. Listing detail page
6. Admin dashboard (from Phase 7)

Requirements:
- Clean, simple CSS (no framework needed, but feel free to use a minimal reset).
  Consistent color scheme suggesting sustainability (greens/earth tones)
- Mobile-responsive using basic CSS flexbox/grid, no JS frameworks
- Forms should submit via fetch() to the JSON APIs and handle success/error states
  simply (show a message, no fancy state management)
- Store JWT in an httpOnly-safe way appropriate for a server-rendered app — explain
  the tradeoff of storing JWT in localStorage vs cookie here, and pick the safer option

Keep this simple and functional over pretty — I'll polish CSS later if I have time.
```

---

## Phase 8 — Testing

```
Continuing the Food Waste Redistribution Platform.

Add a test suite using pytest + httpx (FastAPI's async test client) + pytest-asyncio:
- Use a separate test database (SQLite in-memory or a test Postgres schema — recommend
  which is simpler for my case and explain why)
- Write tests for:
  - Auth: signup, login, invalid credentials, protected route without token
  - Listings: create (donor only, rejects receiver), list with filters, claim flow
    (including preventing double-claim), status transitions
  - Basic permission checks (donor can't edit another donor's listing, etc.)
- Add a pytest.ini or pyproject.toml config
- Add a GitHub Actions workflow (.github/workflows/tests.yml) that runs these tests
  on every push/PR

I don't need 100% coverage — aim for the critical paths (auth + claim flow) since
that's what I'll most likely be asked about.
```

---

## Phase 9 — Dockerize the App

```
Continuing the Food Waste Redistribution Platform.

Containerize the app:
- Write a multi-stage Dockerfile for the FastAPI app (production-ready, non-root user,
  small final image using python:3.12-slim)
- Write a docker-compose.yml for local dev with two services: the FastAPI app and a
  Postgres container, with a named volume for Postgres data and proper env var wiring
- Add a .dockerignore
- Update README with docker-compose up instructions for local dev

Explain briefly in comments why multi-stage builds and non-root users matter — I want
to be able to talk about this in interviews as "I understand basic container security
and image size best practices," not just "I copy-pasted a Dockerfile."
```

---

## Phase 10 — Deployment (Render/Railway) + CI/CD

```
Continuing the Food Waste Redistribution Platform. Docker setup from Phase 10 exists.

Help me deploy this:
1. Walk me through deploying the Dockerized FastAPI app + a managed Postgres instance
   on Render (free tier) OR Railway — recommend which is easier/more reliable for a
   fresher's first deployment right now, and explain why
2. Show me how to run Alembic migrations automatically on deploy (release command / start
   script)
3. Set up environment variables securely on the platform (not committed to git)
4. Extend the GitHub Actions workflow from Phase 9 so that on push to main, after tests
   pass, it triggers a deploy (via Render/Railway's deploy hook or CLI)
5. Add a /health endpoint for uptime checks

Give me a step-by-step checklist I can follow manually in the platform's dashboard,
plus the code/config changes needed in the repo.
```

---

## Optional Polish Prompts (only if time allows)

```
Add a simple rating/feedback endpoint: after a claim is marked "completed", receiver
can rate the donor 1-5 stars with an optional comment. Show average rating on donor
profile.
```

```
Add rate limiting to auth endpoints (slowapi) to prevent brute-force login attempts,
and explain why this matters for a resume project.
```

---

## Interview Prep Checklist (do this after building)

For each phase, be ready to answer:
- **Auth (Phase 3):** Why JWT over sessions? What's in the token payload? How do you
  handle token expiry/refresh? Where's the password hashed and why bcrypt?
- **Listings (Phase 4):** How do you prevent two receivers from claiming the same
  listing at once (race condition)? What does the haversine formula actually compute?
- **Notifications (Phase 5):** Why APScheduler instead of Celery? What's the tradeoff?
- **Images (Phase 6):** Why not store images in the database or local disk?
- **Deployment (Phase 10-11):** What's in your Dockerfile and why multi-stage? How do
  migrations run in production? What happens if the deploy fails mid-migration?

If you can answer these in plain language without re-reading the code, you're in
good shape for interviews.