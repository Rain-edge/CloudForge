# --- builder stage ---
FROM python:3.11-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev postgresql-dev

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
    pydantic pydantic-settings python-jose[cryptography] passlib[bcrypt] structlog redis \
    opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi \
    opentelemetry-instrumentation-sqlalchemy opentelemetry-exporter-otlp-proto-grpc \
    prometheus-fastapi-instrumentator \
    --target=/app/deps

# --- runtime stage ---
FROM python:3.11-alpine AS runtime

RUN addgroup -S cloudforge && adduser -S cloudforge -G cloudforge

# libpq is the runtime library needed by asyncpg (psycopg2 equivalent for PostgreSQL)
RUN apk add --no-cache libpq

COPY --from=builder /app/deps /usr/local/lib/python3.11/site-packages/

COPY app/ /app/app/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER cloudforge
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
