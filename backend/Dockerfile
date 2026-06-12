# Dockerfile multietapa para el backend de Django

# Etapa 1: base — instala todas las dependencias
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

# Etapa 2: desarrollo
FROM base AS development

ENV DJANGO_ENV=development

# El código fuente se montará como volumen para recarga en caliente
# Copia únicamente el script de entrada, que ya está en la etapa base
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

# Etapa 3: producción
FROM base AS production

ENV DJANGO_ENV=production

COPY . .

RUN test -f /app/manage.py

# Crea un usuario sin privilegios de root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
