#!/usr/bin/env bash
# Exit nonzero for work needing attention; attach this to the site's alerting.
set -euo pipefail
queue_status=0
docker exec nodered node /data/lib/capture_queue.cjs health || queue_status=$?
issues=$(docker exec postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring -c \
    "SELECT (SELECT count(*) FROM monitoring.cycles WHERE waveform_status='pending' AND created_at < now()-interval '5 minutes') + (SELECT count(*) FROM monitoring.measurement_conflicts WHERE resolved_at IS NULL)")
if [[ "$queue_status" != 0 || "$issues" != 0 ]]; then
    printf '%s\n' "Ingestion needs attention: queue exit=$queue_status, database issues=$issues" >&2
    exit 1
fi
printf '%s\n' 'Ingestion checks passed'
