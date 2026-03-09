#!/bin/sh
set -e

# Wait for PostgreSQL to be ready (only in production with DATABASE_URL)
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL..."
    until python -c "
import psycopg2
import os
from urllib.parse import urlparse
u = urlparse(os.environ['DATABASE_URL'])
try:
    psycopg2.connect(
        host=u.hostname,
        port=u.port or 5432,
        dbname=u.path[1:],
        user=u.username,
        password=u.password
    )
    exit(0)
except Exception as e:
    exit(1)
" 2>/dev/null; do
        echo "PostgreSQL not ready yet, retrying in 2s..."
        sleep 2
    done
    echo "PostgreSQL is ready."
else
    # SQLite: ensure data directory exists
    DB_DIR=$(dirname "${DATABASE_PATH:-/app/db.sqlite3}")
    mkdir -p "$DB_DIR"
fi

echo "Running migrations..."
python manage.py migrate --noinput

if [ "$DJANGO_ENV" = "production" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    echo "Starting Gunicorn..."
    exec gunicorn backend.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --timeout 60 \
        --access-logfile - \
        --error-logfile -
else
    echo "Starting Django development server..."
    exec python manage.py runserver 0.0.0.0:8000
fi
