# Multi-stage Dockerfile for Django backend

# Stage 1: Base — installs all dependencies
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Stage 2: Development
FROM base AS development

ENV DJANGO_ENV=development

COPY . .

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

# Stage 3: Production
FROM base AS production

ENV DJANGO_ENV=production

COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
