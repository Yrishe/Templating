# ---------------------------------------------------------------------------
# Stage 1: Builder — install Python dependencies into /install
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to leverage Docker layer caching
COPY requirements/production.txt requirements/production.txt
COPY requirements/base.txt requirements/base.txt

RUN pip install --prefix=/install -r requirements/production.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime image — lean, non-root
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    PORT=8000

# Runtime system libraries only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser

WORKDIR /app

# Copy source code
COPY . .

# Ensure manage.py is executable
RUN chmod +x manage.py

# Collect static files (requires SECRET_KEY at build time for some setups)
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY=build-placeholder \
    DB_HOST=localhost \
    python manage.py collectstatic --noinput || true

# Change ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Use daphne to serve both HTTP and WebSocket traffic
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
