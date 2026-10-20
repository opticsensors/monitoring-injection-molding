# Deploy cycle metadata and recoverable ingestion

This is the detailed maintenance/reference path. Normal deployment now uses
`bash iot/deploy.sh` or `scripts/deploy.ps1`; see [the short guide](../SERVER_SETUP.md).
Do not execute both paths at the same time. All commands below still run from
the deployment root, not from this maintenance directory.

Updated 2026-10-19 for `EUREPAISIKEI` / `172.20.48.28`. **Production has not
been changed by the coding agent.** Pause recording for the production cutover.
InfluxDB 1.8 keeps waveforms; PostgreSQL keeps the catalog, measurements and
rejected edits. Manual Save, optional MQTT, client broker-ACK cleanup, sampling
settings and the external DAQ driver retain their existing behaviour.

## 1. Copy files and inspect the existing server

From the Windows workstation, in the repository:

```powershell
ssh -l 'eduard.almar@local.eurecat.org' 172.20.48.28 'mkdir -p ~/injection-monitoring-deploy'
scp -o 'User=eduard.almar@local.eurecat.org' -r iot scripts tests cycle_metadata.py sensor_types.py 172.20.48.28:injection-monitoring-deploy/
ssh -l 'eduard.almar@local.eurecat.org' 172.20.48.28
```

Subsequent commands run in **Bash on the Linux server**, unless labelled otherwise:

```bash
set -euo pipefail
umask 077
cd "$HOME/injection-monitoring-deploy"
deploy_root="$PWD"
iot_root="$HOME/IOTstack"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
docker exec postgres psql -X -U postuser -d postgres -c 'SELECT version()' -c '\l'
docker exec nodered node --version
docker exec nodered sh -c 'cd /data && npm ls node-red-contrib-postgresql --depth=0' || true
docker inspect nodered --format '{{json .Mounts}}'
docker inspect influxdb --format '{{json .Mounts}}'
```

Known inventory: PostgreSQL 17.5 (`postgres`, owner `postuser`), Node-RED 4.0.9 /
Node 20.19 (`nodered`), InfluxDB 1.8.10 (`influxdb`, database `sensor_data`),
`mosquitto`, and `grafana`. Shared network: `iotstack_default`. The separate
`influxdb2` service is unused by this application; leave it alone.
The observed IOTstack root is `/home/eduard.almar@local.eurecat.org/IOTstack`.

| Host path below IOTstack | Container path |
| --- | --- |
| `volumes/postgres/data` | `/var/lib/postgresql/data` |
| `volumes/postgres/db_backup` | `/backup` |
| `volumes/nodered/data` | `/data` |
| `volumes/grafana/data` | `/var/lib/grafana` |
| `volumes/influxdb/data` | `/var/lib/influxdb` |
| `backups/influxdb/db` | `/var/lib/influxdb/backup` |

Inspect the IOTstack Compose definition. Pin the intended PostgreSQL 17 image
(the existing Debian build is bookworm) and the tested Grafana version. This
feature needs no image upgrade. Avoid an unreviewed whole-stack pull. Verify
existing external database clients before changing published ports.

Inspect Mosquitto's actual version, persistence mount and configuration:
`persistence`, `max_packet_size`, `message_size_limit`, `max_queued_bytes` and
`max_queued_messages`. Each capture is still one MQTT JSON message; HTTP chunking
happens only after Node-RED receives it. Size limits must accommodate the largest
expected JSON capture, which can exceed its line-protocol size. Keep the stable
subscriber ID, QoS 1 and persistent session. Do not copy the anonymous validation
broker configuration into production.

## 2. Preserve the deployment and drain old uploads

Export the deployed Node-RED flow and Grafana dashboard from their editors.
Preserve Compose/settings and the lab PC's `data/pending/`. With the **old flow
still running**, drain old uploads and verify their arrival in Influx. An empty
PC spool proves broker acknowledgement only. Then stop recording/close the app.

```bash
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="$iot_root/backups/metadata_upgrade_$backup_stamp"
mkdir -p "$backup_dir"
docker exec postgres pg_dumpall -U postuser > "$backup_dir/postgres-before.sql"
test -s "$backup_dir/postgres-before.sql"
docker exec influxdb influxd backup -portable -database sensor_data "/var/lib/influxdb/backup/before_metadata_$backup_stamp"
tar -czf "$backup_dir/nodered-data.tgz" -C "$iot_root/volumes/nodered" data
cp -p "$iot_root/volumes/nodered/data/settings.js" "$backup_dir/settings.js"
printf '%s\n' "$backup_dir"
```

Keep these private: Node-RED settings/credential files and role dumps contain
sensitive material. Keep an off-server copy and verify restoration in an isolated
instance; never restore over production to test a backup.

## 3. Validate in the isolated Docker stack

This project has its own broker, databases, network and named volumes. Only test
Grafana is published, at `127.0.0.1:13000`. Passwords under `iot/validation/` are
test-only. The stack does not join `iotstack_default`.

```bash
cd "$deploy_root"
python3 scripts/prepare_stack_test.py
docker compose -p monitoring-metadata-test -f iot/validation/compose.yaml config --quiet
docker compose -p monitoring-metadata-test -f iot/validation/compose.yaml up -d --build
python3 tests/check_stack.py
```

The test publishes synthetic multi-chunk captures, verifies real Influx retrieval
and duplicate replay, and stops/restarts **only this test project's** databases
and Node-RED. It leaves data for inspection. A larger case is available with
`python3 tests/check_stack.py --samples 200000`.

For the Grafana browser check, use a **second workstation terminal**:

```powershell
ssh -N -L 13000:127.0.0.1:13000 -l 'eduard.almar@local.eurecat.org' 172.20.48.28
```

Visit `http://localhost:13000`, login `validation` / `test-only-grafana`. Open the
provisioned dashboard: latest 1, latest 10 and numeric cycle legends. The automated
test uses both 55t and 160t in isolated storage and creates CH0
only; other channel panels are empty by design. Verify latest-cycle refresh after
new captures. A panel
refresh does not prove a query variable refreshed; reload if necessary. Also
check the deployed Grafana version if different from the validation image.

Stop this isolated stack when done (volumes remain for inspection):

```bash
docker compose -p monitoring-metadata-test -f iot/validation/compose.yaml down
```

Only to reset its disposable data, use `down --volumes` with the **same** project
name and file. Never use production's Compose project for these tests.

## 4. Apply production schema and roles

Confirm `injection_monitoring` is absent or belongs to this app. The helper
creates it if absent, applies 001 only to a fresh schema, then applies additive
migration 002. It leaves `postdb`, passwords and waveform data alone.

```bash
cd "$deploy_root"
bash scripts/apply_server_migrations.sh
docker exec -it postgres psql -X -U postuser -d injection_monitoring
```

In interactive `psql`, set distinct passwords if these logins are new; retain
existing passwords if already configured:

```text
\password monitoring_ingest
\password monitoring_reader
\q
```

`monitoring_owner` owns the application objects and cannot login or act as a
superuser. `monitoring_ingest` calls ingestion functions. `monitoring_reader`
reads the catalog and conflict records. Run migrations as `postuser`.

## 5. Install the queue and updated Node-RED flow

Check Manage palette first. The flow targets `node-red-contrib-postgresql@0.16.2`.
Review other flows before changing a shared connector version. Install if absent:

```bash
docker exec -w /data nodered npm install --save-exact node-red-contrib-postgresql@0.16.2
docker exec nodered mkdir -p /data/lib
docker cp iot/nodered/capture_queue.cjs nodered:/data/lib/capture_queue.cjs
nano "$iot_root/volumes/nodered/data/settings.js"
```

Add this entry to the **existing** `functionGlobalContext` object. If commented
out, enable it inside `module.exports`. Retain all other settings, especially
credential encryption and authentication:

```javascript
functionGlobalContext: {
    // retain other existing entries
    captureQueue: require("/data/lib/capture_queue.cjs")
},
```

```bash
docker exec nodered node --check /data/settings.js
docker restart nodered
```

In `http://172.20.48.28:1880/`:

1. Disable/remove the old ingestion tab. Import the complete
   `iot/nodered_flows.json`; updating one Function node is insufficient. Preserve
   or re-enter the working MQTT credentials. Never leave both subscribers running.
2. Set PostgreSQL **Cycle metadata**: `postgres:5432`, database
   `injection_monitoring`, user `monitoring_ingest`, password in **credentials**.
3. **Write Influx 1.8** uses
   `http://influxdb:8086/write?db=sensor_data&rp=autogen&precision=ns`.
   If Influx auth is enabled, configure this HTTP node's Basic Auth using the
   existing writer credentials. Old Influx-node credentials are not inherited.
4. Deploy. Keep one `+/sensors` subscriber with client ID `nodered-daq-ingest`,
   QoS 1, persistent session. The old Influx batch node is no longer required.

```bash
docker logs --tail 100 nodered
docker exec nodered node /data/lib/capture_queue.cjs status
```

Original messages are stored under `/data/capture-queue/` before DB processing.
This uses the existing persistent `/data` mount, one active job and a five-minute
durable lease; an abandoned in-flight job may take five minutes to resume.
Temporary failures retry after 5 seconds, doubling to a five-minute cap.
Validation errors, legacy arrays, rejected measurement updates and non-retryable
HTTP failures go to `quarantine/`. Jobs are removed only after a DB completion
receipt. No periodic Node-RED context flush is used for durability.

Influx writes contain at most 5,000 points / 4,000,000 bytes. All chunks must
succeed before `stored`; retries keep exact identities, timestamps, values and
the whole-capture hash. PostgreSQL registration continues to reject overlaps
and conflicting immutable waveforms before they can overwrite Influx data.

**Delivery boundary:** standard MQTT input may acknowledge before the disk queue
write. A crash/disk failure in that gap is not covered. Broker retention, disk
capacity and queue limits also matter. The desktop still reports queued /
unconfirmed; retain manual exports when a recording must be recoverable.

## 6. Reconcile history and import Grafana

Keep acquisition paused. Export the current catalog and run a fresh diagnostic:

```bash
docker exec -i postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
  < iot/postgres/export_metadata.sql > server.metadata.json
diagnostic_dir="data/diagnostics/before_metadata_$(date -u +%Y%m%dT%H%M%SZ)"
python3 scripts/diagnose_influxdb.py --output "$diagnostic_dir"
python3 scripts/build_legacy_catalog.py "$diagnostic_dir/cycles.csv" \
  --catalog server.metadata.json --output legacy_catalog.sql
```

Review diagnostic warnings and the generated SQL. The builder skips matching
catalog entries and rejects changed counts/bounds, resets, duplicate timestamps,
mixed formats and native captures without matching catalog entries. Reconcile
or replay those records; do not invent legacy manifests for native captures.

```bash
docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring < legacy_catalog.sql
docker exec postgres psql -X -U postuser -d injection_monitoring -c \
  'SELECT count(*) AS cycles, sum(sample_count) AS samples, count(DISTINCT session_id) AS sessions FROM monitoring.cycle_catalog'
docker exec influxdb influx -database sensor_data -execute 'SELECT count("t_ms") FROM "autogen"."sensor_data"'
docker exec -i postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring \
  < iot/postgres/export_metadata.sql > server.metadata.json
```

The old supplied snapshot had **29 cycles / 45,447 samples / 3 sessions**; the
fresh diagnostic is the actual baseline. Backfill copies no waveforms, preserves
existing measurements and native status, and leaves unknown old settings null.

In Grafana (`http://172.20.48.28:3000`):

1. Retain the InfluxQL source at `influxdb:8086` / `sensor_data`.
2. Add/configure PostgreSQL source **Cycle metadata**, UID `cycle-metadata`, host
   `postgres:5432`, database `injection_monitoring`, user `monitoring_reader`.
   Test the connection. For a different UID, regenerate on the workstation:
   `py -3.11 scripts/generate_grafana_dashboard.py --postgres-uid ACTUAL_UID`.
3. Import `iot/grafana_dashboard.json`, mapping its Influx UID to the existing
   source if needed. The dashboard UID is unchanged.
4. Set Latest cycles to 1, then 10. Verify numeric legends, relative-time axes,
   historical curves without a date filter, and refresh after a new capture.

The catalog now supplies identity-only predicates. The dashboard adds one outer
time range. Deploy migration 002 and the new dashboard together. Upgrade the lab
PC, verify Windows clock synchronization (`w32tm /query /status`), then resume
recording. Hardware trigger/rate/sample accounting checks remain necessary when
the DAQ returns; this release does not fix the separate driver/rate issue.

## 7. Recovery and measurement reconciliation

```bash
docker exec nodered node /data/lib/capture_queue.cjs status
bash scripts/check_server_ingestion.sh
docker exec postgres psql -X -U postuser -d injection_monitoring -c \
  "SELECT id,machine_id,session_id,cycle_id,reason,proposed,current_values FROM monitoring.measurement_conflicts WHERE resolved_at IS NULL ORDER BY observed_at"
```

Temporary failures retry automatically after the service recovers. For a
quarantined job, inspect/fix its error before replaying its ID from `status`:

```bash
docker exec nodered node /data/lib/capture_queue.cjs requeue QUEUE_ID_FROM_STATUS
```

Legacy arrays need explicit reconciliation. Export the original for review,
retaining its quarantine copy. Use the preserved old uploader/flow during a
controlled maintenance window, then diagnose/backfill again. Requeueing an
unchanged legacy array into the new validator only quarantines it again.

```bash
docker exec nodered node /data/lib/capture_queue.cjs export QUEUE_ID_FROM_STATUS /data/legacy-review.json
docker cp nodered:/data/legacy-review.json ./legacy-review.json
```

Export refuses to overwrite an existing file. For measurement conflicts, export
fresh `server.metadata.json` (section 6), copy it to the PC and Load it in Cycle
history. The GUI asks before replacing divergent local edits with server values;
Save the local metadata first if needed. Edit from the fresh server revision,
send, verify the server values, then mark the specific conflict resolved in psql:

```sql
UPDATE monitoring.measurement_conflicts SET resolved_at=clock_timestamp()
WHERE id=THE_REVIEWED_NUMERIC_ID AND resolved_at IS NULL;
```

Do not replay superseded measurement proposals. Client timestamps are provenance,
not overwrite priority. Capture-side conflicts remain in PostgreSQL while their
valid waveform proceeds. After verifying resolution, archive the specific queue
job with a note; this preserves its original file and removes it from active alerts:

```bash
docker exec nodered node /data/lib/capture_queue.cjs archive QUEUE_ID_FROM_STATUS 'Verified resolution; describe action here'
```

## 8. Ongoing backups, checks, restore and rollback

```bash
bash "$deploy_root/scripts/backup_server_metadata.sh"
bash "$deploy_root/scripts/check_server_ingestion.sh"
```

The backup helper writes a custom-format DB dump, role SQL and portable Influx
backup using the persistent backup mount. It deletes no backups. Schedule during
an idle recording window, copy off-server and monitor capacity. Example entry
for `crontab -e` (only if 02:00 is an idle window):

```cron
0 2 * * * /bin/bash /home/eduard.almar@local.eurecat.org/injection-monitoring-deploy/scripts/backup_server_metadata.sh >> /home/eduard.almar@local.eurecat.org/IOTstack/backups/metadata-backup.log 2>&1
```

Connect `check_server_ingestion.sh` to site monitoring/alerting. Its nonzero exit
reports old pending work, quarantine, unresolved conflicts or unavailable
services. Cron alone without monitored output does not create an alert. Monitor
`/data` disk space too. Back up the queue's `archive/` and `state/` directories
for reviewed evidence; never delete unreviewed original messages.

Test a PostgreSQL restore in a **new disposable container**, with no ports or
network. Do not reuse an existing `metadata-restorecheck` container:

```bash
restore_dir=/absolute/path/to/the/completed/backup
docker run -d --name metadata-restorecheck --network none \
  -e POSTGRES_USER=restore_validation_admin -e POSTGRES_DB=postgres \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17-bookworm
# Wait for success before the following restore commands:
docker exec metadata-restorecheck pg_isready -U restore_validation_admin
docker exec -i metadata-restorecheck psql -X -v ON_ERROR_STOP=1 -U restore_validation_admin -d postgres < "$restore_dir/roles.sql"
docker exec metadata-restorecheck createdb -U restore_validation_admin -O postuser injection_monitoring
docker exec -i metadata-restorecheck pg_restore -U restore_validation_admin -d injection_monitoring --exit-on-error < "$restore_dir/metadata.dump"
docker exec metadata-restorecheck psql -X -U restore_validation_admin -d injection_monitoring -c 'TABLE monitoring.schema_migrations' -c 'SELECT count(*) FROM monitoring.cycle_catalog'
```

Test the portable Influx backup in a separate Influx 1.8 instance with
`influxd restore -portable`. Compare per-cycle counts/bounds after restoring both
stores. Their backups are not a distributed atomic snapshot; preserve the idle
window and reconcile data before resuming recording.

Rollback: pause acquisition, preserve the new queue and server metadata export,
restore previous Node-RED settings/flow and Grafana dashboard, then use the
previous desktop app. Keep the new database and waveform data. The legacy flow
cannot process v1 envelopes; retain those jobs for the updated flow. Influx
retention remains unlimited.

## Local validation and limits

```powershell
py -3.11 -B scripts/generate_nodered_flow.py
py -3.11 -B scripts/generate_grafana_dashboard.py
py -3.11 -B -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 -B tests/check_metadata_gui.py
npm.cmd install --prefix data/validation --no-audit --no-fund --ignore-scripts @electric-sql/pglite@0.3.15
node tests/check_ingestion.mjs
node tests/check_recovery.mjs
```

PGlite exercises actual PostgreSQL SQL locally. Recovery checks use the actual
flow functions and filesystem, with simulated HTTP responses. The Docker stack
test exercises real Node-RED/MQTT/PostgreSQL/Influx. Grafana browser behaviour and
physical DAQ acquisition need the explicit checks above. The implementation
workstation's Docker engine was unavailable; container integration and
production deployment have **not** been verified here.
