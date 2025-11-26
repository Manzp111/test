#!/bin/sh
set -e

# Wait for Postgres (remote or local)
# Change "db" to your actual remote host if needed
./wait-for-it.sh db:5432 -- echo "Postgres is up"

# Wait for Redis
./wait-for-it.sh redis:6379 -- echo "Redis is up"

# Do NOT run migrations for a remote production DB
echo "Skipping migrations because remote DB already has schema."

# Start gunicorn / django server
exec "$@"
