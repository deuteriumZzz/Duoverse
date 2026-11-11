#!/bin/sh
# Runs before the web process (and the worker). Migrations are idempotent; the knowledge-base seed
# only touches blocks nobody has reviewed in the admin, so edits made by people are never overwritten.
set -e
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py kb_seed
  # birthplaces (GeoNames, ~14 MB download) once; without network the app still works with the short city list
  python manage.py places_load --if-empty || echo "places_load failed: birthplaces stay limited until it runs" >&2
fi
exec "$@"
