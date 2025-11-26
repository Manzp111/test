#!/bin/sh
set -e

# Wait for Postgres
./wait-for-it.sh db:5432 -- echo "Postgres is up"

# Wait for Redis (optional, if using Celery)
./wait-for-it.sh redis:6379 -- echo "Redis is up"

# Make migrations (safe if nothing changed)
echo "Making migrations..."
python manage.py makemigrations || echo "No changes to migrations"

# Apply migrations
echo "Applying migrations..."
python manage.py migrate

# Start the server
exec "$@"
