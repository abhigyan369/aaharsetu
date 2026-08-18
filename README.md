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

### 🐳 Option B: Running with Docker Compose (Recommended)

You can spin up both the FastAPI application and PostgreSQL with a single command without needing local Python or Postgres installations.

#### 1. Start services with Docker Compose

```bash
docker compose up --build
```

This will:
- Build the FastAPI container using a multi-stage `Dockerfile`.
- Launch a PostgreSQL 16 container (`postgres:16-alpine`).
- Wait for PostgreSQL to pass its health check (`pg_isready`).
- Automatically run Alembic database migrations (`alembic upgrade head`).
- Start the Uvicorn ASGI web server at `http://localhost:8000`.

#### 2. Stopping services

```bash
# Stop containers but preserve database data volume:
docker compose down

# Stop containers AND delete database volume (fresh reset):
docker compose down -v
```

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

### Multi-Stage Builds (Phase 10)
- **Image Size Reduction:** Compilers (`gcc`) and header files are needed during `pip install` for C extensions (e.g. `asyncpg`, `bcrypt`, `cryptography`), but discarded in the final stage. Only the compiled `/opt/venv` is copied into `python:3.12-slim`.
- **Attack Surface Reduction:** Dropping build tools from the final runtime image prevents potential attackers from using internal tools in case of container execution exploits.
- **Layer Caching:** Isolating dependency installation from source code speeds up rebuilds when application code changes.

### Container Security & Non-Root User (Phase 10)
- **Least Privilege Execution:** By default, Docker containers run processes as root (UID 0). Running as a dedicated non-root user (`appuser`, UID 10001) ensures that an application compromise doesn't grant root control inside the container.
- **Preventing Container Breakout:** If an RCE occurs, a non-root process cannot easily interact with host resources or exploit container escape vulnerabilities requiring root permissions.
- **Production / Kubernetes Compliance:** Enterprise container environments mandate non-root execution (`securityContext.runAsNonRoot`).

---

## 🌐 Production Deployment & CI/CD (Phase 11)

### Deploying on Render (Recommended)
1. **Provision PostgreSQL Database:** Create a Managed PostgreSQL instance on Render. Copy the **Internal Database URL**.
2. **Deploy Web Service:** Create a new Web Service from your GitHub repository choosing **Docker** runtime.
3. **Environment Variables:** In Render dashboard, configure:
   - `DATABASE_URL`: Internal Postgres connection string (`postgres://...` is automatically normalized to `postgresql+asyncpg://`).
   - `SECRET_KEY`: Random 32-byte hex key.
   - `APP_ENV`: `production`
   - `DEBUG`: `false`
4. **Automated Migrations:** Alembic migrations run automatically on container startup via `scripts/start.sh` (`alembic upgrade head`).
5. **CI/CD Integration:** Copy your Render Web Service **Deploy Hook URL** and store it as `RENDER_DEPLOY_HOOK_URL` in GitHub Repository Secrets (`Settings > Secrets and variables > Actions`). On every push to `main`, GitHub Actions runs tests and triggers a deploy automatically.

---

## 🗺️ Build Phases

| Phase | Feature |
|-------|---------|
| **0** | ✅ Project structure |
| **2** | ✅ SQLAlchemy models + Pydantic schemas |
| **3** | ✅ JWT authentication + role-based access |
| **4** | ✅ Food listing CRUD + claim workflow |
| **5** | ✅ Email notifications + APScheduler |
| **6** | ✅ Image upload via Cloudinary |
| **7** | ✅ Admin analytics dashboard |
| **8** | ✅ Jinja2 frontend pages |
| **9** | ✅ Test suite (pytest + httpx) |
| **10** | ✅ Docker + docker-compose |
| **11** | ✅ Deploy to Render/Railway + CI/CD |

---

## 🤝 Contributing

This is a portfolio/learning project. Feel free to fork it and build your own version!

