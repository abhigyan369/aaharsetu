# 🌱 Food Waste Redistribution Platform

A portfolio project that connects food donors (restaurants, households, stores) with
receivers (NGOs, food banks, individuals) to reduce food waste.

**Tech stack:** FastAPI · SQLAlchemy (async) · PostgreSQL · Jinja2 · JWT Auth · Alembic · Docker

---

## 📁 Project Structure

```
food_waste_redistribution/
│
├── app/                        ← All application source code lives here
│   ├── __init__.py
│   ├── main.py                 ← FastAPI app creation, router registration, startup events
│   │
│   ├── core/                   ← Cross-cutting concerns (config, security)
│   │   ├── config.py           ← Reads .env into typed Settings object (pydantic-settings)
│   │   └── security.py         ← Password hashing (bcrypt) + JWT creation/verification
│   │
│   ├── db/                     ← Database connection layer
│   │   ├── database.py         ← Async engine, session factory, get_db() dependency
│   │   └── base.py             ← SQLAlchemy DeclarativeBase (all models inherit from this)
│   │
│   ├── models/                 ← SQLAlchemy ORM models (one file per table)
│   │   └── __init__.py         ← (Phase 2: User, FoodListing, Claim, Notification)
│   │
│   ├── schemas/                ← Pydantic schemas for request/response validation
│   │   └── __init__.py         ← (Phase 2: UserRead, FoodListingCreate, etc.)
│   │
│   ├── routers/                ← FastAPI route handlers (one file per feature)
│   │   └── __init__.py         ← (Phase 3+: auth, listings, notifications, admin, pages)
│   │
│   ├── templates/              ← Jinja2 HTML templates
│   │   ├── base.html           ← Master layout (navbar, footer, shared CSS)
│   │   └── errors/
│   │       └── 404.html
│   │
│   └── static/                 ← CSS, images, JavaScript files served directly
│       └── css/
│           └── main.css        ← Global stylesheet (design tokens, components)
│
├── migrations/                 ← Alembic migration files (commit these to git!)
│   ├── env.py                  ← Alembic config — reads DB URL from .env, imports models
│   └── versions/               ← Auto-generated migration scripts live here
│
├── alembic.ini                 ← Alembic settings (script_location, logging)
├── requirements.txt            ← Python dependencies (pin versions for reproducibility)
├── .env.example                ← Template for env vars — copy to .env and fill in values
├── .gitignore
└── README.md                   ← You are here
```

---

## 🚀 Running Locally

### Prerequisites

- Python 3.12+
- PostgreSQL running locally (or use Docker)

### 1. Clone and create a virtual environment

```bash
git clone <your-repo-url>
cd food_waste_redistribution

python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Now open .env and fill in your DATABASE_URL, SECRET_KEY, etc.
```

Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Create the database

```bash
# In psql or pgAdmin, create the database:
createdb food_waste_db

# Or via psql:
psql -U postgres -c "CREATE DATABASE food_waste_db;"
```

### 5. Run Alembic migrations

```bash
# Apply all migrations to the database (creates tables):
alembic upgrade head

# When you add/change a model, generate a new migration:
alembic revision --autogenerate -m "describe what changed"
```

### 6. Start the development server

```bash
uvicorn app.main:app --reload
```

The app will be at: **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

---

## 🔑 Key Concepts (Interview Reference)

### Why FastAPI?
- Async-native (handles many requests concurrently without blocking)
- Auto-generates OpenAPI docs from type hints (no extra work)
- Dependency injection makes auth, DB sessions, and permissions clean

### Why SQLAlchemy Async?
- Mixing sync DB calls in an async app blocks the event loop — every request
  waits for every DB query to finish before doing anything else
- Async sessions let the server handle other requests while waiting for DB

### Why Alembic?
- Raw `CREATE TABLE` SQL is brittle — someone applies it, someone else
  doesn't, and schemas diverge
- Alembic generates versioned migration files that you commit to git.
  Everyone (and the production server) runs the same migrations in order

### Why pydantic-settings?
- Config values validated at startup — app fails fast with a clear error if
  `DATABASE_URL` is missing, rather than crashing at the first DB call
- Follows the 12-factor app principle: config separated from code

### JWT Auth Flow (Phase 3)
1. User logs in → server verifies password with bcrypt
2. Server creates a signed JWT with user ID + expiry
3. Client stores token and sends it in `Authorization: Bearer <token>` header
4. Server verifies signature + expiry on every protected request — no DB lookup needed

---

## 🗺️ Build Phases

| Phase | Feature |
|-------|---------|
| **0** | ✅ Project structure (this phase) |
| **2** | SQLAlchemy models + Pydantic schemas |
| **3** | JWT authentication + role-based access |
| **4** | Food listing CRUD + claim workflow |
| **5** | Email notifications + APScheduler |
| **6** | Image upload via Cloudinary |
| **7** | Admin analytics dashboard |
| **8** | Jinja2 frontend pages |
| **9** | Test suite (pytest + httpx) |
| **10** | Docker + docker-compose |
| **11** | Deploy to Render/Railway + CI/CD |

---

## 🤝 Contributing

This is a portfolio/learning project. Feel free to fork it and build your own version!
