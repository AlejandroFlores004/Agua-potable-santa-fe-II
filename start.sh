#!/bin/sh
set -e

# Apply pending database migrations
python manage.py migrate --noinput

# Collect static files so WhiteNoise can serve them
python manage.py collectstatic --noinput

# Start the production server (Railway injects $PORT)
exec gunicorn agua_potable_santa_fe_II.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-3} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
