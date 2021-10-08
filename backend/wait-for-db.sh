#!/bin/sh
# Wait for Postgres to be ready before starting the API.
set -e

host="$1"
shift
cmd="$@"

PGUSER="${POSTGRES_USER:-postgres}"
PGDATABASE="${POSTGRES_DB:-postgres}"

echo "Waiting for Postgres at $host:5432 (user=$PGUSER, db=$PGDATABASE)..."

until pg_isready -h "$host" -p 5432 -U "$PGUSER" -d "$PGDATABASE"; do
  sleep 1
done

echo "Postgres is ready - executing command"
exec $cmd
