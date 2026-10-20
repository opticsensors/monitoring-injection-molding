#!/usr/bin/env bash
# Schedule during an idle recording window. No automatic backup deletion.
set -euo pipefail
umask 077
backup_root=${1:-"$HOME/IOTstack/backups/injection-monitoring"}
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="$backup_root/$backup_stamp"
mkdir -p -- "$backup_root"
mkdir -- "$backup_dir"
docker exec postgres pg_dump -U postuser -Fc injection_monitoring > "$backup_dir/metadata.dump.part"
test -s "$backup_dir/metadata.dump.part"
mv -- "$backup_dir/metadata.dump.part" "$backup_dir/metadata.dump"
docker exec postgres pg_dumpall -U postuser --roles-only > "$backup_dir/roles.sql.part"
test -s "$backup_dir/roles.sql.part"
mv -- "$backup_dir/roles.sql.part" "$backup_dir/roles.sql"
docker exec influxdb influxd backup -portable -database sensor_data "/var/lib/influxdb/backup/metadata_$backup_stamp"
printf '%s\n' "Influx backup: /var/lib/influxdb/backup/metadata_$backup_stamp" > "$backup_dir/influx-location.txt"
printf '%s\n' "Completed $backup_dir"
