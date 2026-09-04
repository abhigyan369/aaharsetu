# ==============================================================================
# MULTI-STAGE DOCKERFILE — FastAPI + React Food Waste Redistribution Platform
# ==============================================================================
# 1. Stage 1 (Frontend Builder): Node.js builds React SPA to frontend/dist
# 2. Stage 2 (Python Builder): Python 3.12 installs wheels/venv
# 3. Stage 3 (Production Runner): Minimal Python container running non-root user
# ==============================================================================

# ------------------------------------------------------------------------------
# STAGE 1: Frontend Builder (Build React SPA)
# ------------------------------------------------------------------------------
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# STAGE 2: Python Builder (Compile backend virtualenv)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS py-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# STAGE 3: Production Runner (Minimal secure runtime environment)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root group and user (UID 10001) for container security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

WORKDIR /app

# Copy virtualenv from Python builder stage
COPY --from=py-builder /opt/venv /opt/venv

# Copy backend application source code
COPY --chown=appuser:appgroup . /app

# Copy built React frontend static assets from Node builder stage
COPY --from=frontend-builder --chown=appuser:appgroup /frontend/dist /app/frontend/dist

# Ensure startup script is executable
RUN chmod +x /app/scripts/start.sh

USER appuser

EXPOSE 8000

CMD ["/app/scripts/start.sh"]
