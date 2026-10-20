#!/usr/bin/env bash
# Run on the existing Docker host. No container replacement or database deletion.
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exists=$(docker exec postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d postgres \
    -c "SELECT 1 FROM pg_database WHERE datname='injection_monitoring'")
if [[ "$exists" != 1 ]]; then
    docker exec postgres createdb -U postuser -O postuser injection_monitoring
fi
schema_exists=$(docker exec postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
    -c "SELECT to_regclass('monitoring.cycles') IS NOT NULL")
if [[ "$schema_exists" != t ]]; then
    docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
        < "$task_root/iot/postgres/001_cycle_metadata.sql"
fi
docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
    < "$task_root/iot/postgres/002_ingestion_recovery.sql"
docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
    < "$task_root/iot/postgres/003_history_reader.sql"
docker exec postgres psql -X -U postuser -d injection_monitoring \
    -c 'TABLE monitoring.schema_migrations'
