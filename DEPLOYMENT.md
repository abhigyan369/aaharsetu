# Render Deployment Guide - AaharSetu (Food Waste Redistribution Platform)

This repository is optimized for one-click deployment on [Render](https://render.com) using Docker and PostgreSQL.

---

## Deployment Option 1: Render Blueprint (Recommended)

Render Blueprints automatically set up both the **Web Service** and the **PostgreSQL Database** using `render.yaml`.

### Steps:
1. **Push your code to GitHub / GitLab**.
2. **Log into Render**: Go to [dashboard.render.com](https://dashboard.render.com).
3. **Click `New +`** $\rightarrow$ **`Blueprint`**.
4. **Connect your repository**: Select your `food_waste_redistribution` repository.
5. Render will automatically read `render.yaml` and prompt you to create:
   - **Database**: `food-waste-db` (PostgreSQL)
   - **Web Service**: `food-waste-redistribution` (Multi-stage Docker container)
6. Click **Apply**.
7. Render will build the container, run database migrations automatically via `alembic upgrade head`, and start the application

---

## Deployment Option 2: Manual Web Service & Database Setup

If you prefer to configure services manually in the Render dashboard:

### 1. Create a PostgreSQL Database
- In Render Dashboard, click **New +** $\rightarrow$ **PostgreSQL**.
- **Name**: `food-waste-db`
- **Database**: `foodwastedb`
- **User**: `foodwasteuser`
- **Plan**: Free (or chosen plan)
- Copy the **Internal Database URL** once created.

### 2. Create a Web Service
- Click **New +** $\rightarrow$ **Web Service**.
- Connect your GitHub repository.
- **Runtime**: Docker
- **Dockerfile Path**: `Dockerfile`
- Add the following **Environment Variables**:
  - `APP_ENV`: `production`
  - `DEBUG`: `false`
  - `DATABASE_URL`: *(Select "Add from Database" and choose `food-waste-db` Internal Connection String)*
  - `SECRET_KEY`: *(Generate a 32-byte hex string using `openssl rand -hex 32`)*
  - `CORS_ORIGINS`: `*`
  - `EMAILS_ENABLED`: `false` (or `true` if SMTP credentials are provided)
- Click **Create Web Service**.

---

## Environment Variables Reference

| Variable | Recommended Production Value | Description |
|---|---|---|
| `APP_ENV` | `production` | Enables production mode & secure cookies |
| `DEBUG` | `false` | Disables verbose debug outputs & interactive `/docs` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string (auto-normalized) |
| `SECRET_KEY` | Long random hex string | Signs JWT authentication tokens |
| `CORS_ORIGINS` | `*` or `https://<your-app>.onrender.com` | Allowed CORS origins for API requests |
| `EMAILS_ENABLED` | `false` | Master toggle for email notifications |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary name | Optional for image uploads |
| `CLOUDINARY_API_KEY` | Cloudinary API Key | Optional for image uploads |
| `CLOUDINARY_API_SECRET` | Cloudinary API Secret | Optional for image uploads |

---

## Architecture Summary
- **FastAPI Backend**: Serves machine-to-machine JSON APIs, WebSockets (`/chat/ws`), and health checks (`/health`).
- **Jinja2 Server Pages**: Served at `/` (landing page, donor dashboard, receiver browse, etc.).
- **React SPA**: Built into `frontend/dist` by Docker multi-stage build, served automatically at `/app`.
- **Database Migrations**: Automatically executed on container startup via `scripts/start.sh` using Alembic.
