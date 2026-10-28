#!/usr/bin/env bash
# Run on the existing Docker host. No container replacement or database deletion.
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task_container=${MONITORING_POSTGRES_CONTAINER:-postgres}
exists=$(docker exec "$task_container" psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname='injection_monitoring'")
if [[ "$exists" != 1 ]]; then
    docker exec "$task_container" createdb -U postuser -O postuser injection_monitoring
fi
schema_exists=$(docker exec "$task_container" psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
    -c "SELECT to_regclass('monitoring.cycles') IS NOT NULL")
if [[ "$schema_exists" != t ]]; then
    docker exec -i "$task_container" psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
        < "$task_root/iot/postgres/001_cycle_metadata.sql"
fi
versions_exist=$(docker exec "$task_container" psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
    -c "SELECT to_regclass('monitoring.schema_migrations') IS NOT NULL")
current_version=1
if [[ "$versions_exist" == t ]]; then
    current_version=$(docker exec "$task_container" psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
        -c "SELECT COALESCE(max(version),1) FROM monitoring.schema_migrations")
fi
# Old view definitions cannot replace newer views with appended columns. Apply
# missing versions in order, and allow the current migration to be reapplied.
for migration in 002_ingestion_recovery.sql 003_history_reader.sql 004_cycle_review.sql 005_machine_correction.sql; do
    number=${migration%%_*}
    version=$((10#$number))
    if (( version >= current_version )); then
        docker exec -i "$task_container" psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
            < "$task_root/iot/postgres/$migration"
        current_version=$version
    fi
done
docker exec "$task_container" psql -X -U postuser -d injection_monitoring \
    -c 'TABLE monitoring.schema_migrations'
