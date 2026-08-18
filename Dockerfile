# ==============================================================================
# MULTI-STAGE DOCKERFILE — FastAPI Food Waste Redistribution Platform
# ==============================================================================
#
# 💡 INTERVIEW PREP: WHY MULTI-STAGE BUILDS MATTER
# ------------------------------------------------------------------------------
# 1. Smaller Image Size: In the build stage, compilers (gcc), header files, and
#    temporary build tools/caches are required to compile C extensions (e.g.,
#    asyncpg, bcrypt, cryptography). By copying ONLY the compiled virtualenv
#    into a clean runtime stage, we drop hundreds of megabytes of unnecessary
#    build bloat.
# 2. Security & Reduced Attack Surface: Build tools like compilers, git, or header
#    files inside a running production container can be exploited by an attacker
#    if a vulnerability is found. Omitting them shrinks the attack surface.
# 3. Layer Caching Efficiency: Copying requirements.txt and installing dependencies
#    in a separate step before copying application code ensures that Docker's layer
#    cache is reused unless dependencies change.
# ==============================================================================

# ------------------------------------------------------------------------------
# STAGE 1: Builder (Compile dependencies and build wheels)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files and force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Create a virtual environment in /opt/venv
# Using a dedicated venv makes copying all installed packages to Stage 2 trivial.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependencies list first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies into the virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# STAGE 2: Runner / Production (Minimal runtime environment)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

# 💡 INTERVIEW PREP: WHY NON-ROOT USERS MATTER
# ------------------------------------------------------------------------------
# By default, Docker containers run processes as root (UID 0).
# If an application running as root inside a container suffers a Remote Code
# Execution (RCE) vulnerability, the attacker gains root privilege inside the
# container. Combined with any kernel or container runtime vulnerability, this
# could allow container breakout and root access on the underlying host OS.
#
# Running as a dedicated non-root user (e.g., appuser: 10001):
# - Enforces Principle of Least Privilege: The process can only read/write files
#   explicitly owned by or permitted for appuser.
# - Complies with Security Benchmarks: Kubernetes (securityContext.runAsNonRoot)
#   and enterprise container registries prohibit root execution.
# ------------------------------------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create a non-root group and user with explicit GID/UID (10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code and grant ownership to non-root user
COPY --chown=appuser:appgroup . /app

# Ensure start script is executable
RUN chmod +x /app/scripts/start.sh

# Switch to non-root user for execution
USER appuser

# Expose FastAPI application port
EXPOSE 8000

# Entrypoint script runs Alembic migrations automatically before starting Uvicorn
CMD ["/app/scripts/start.sh"]
