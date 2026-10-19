# Deploy cycle metadata alongside the existing InfluxDB waveforms

Prepared 2026-10-14 for `EUREPAISIKEI` (`172.20.48.28`). **These are deployment
instructions; no server changes have been executed by the coding agent.**
Deploy this server path before enabling MQTT in the updated desktop app.

## Confirmed environment

| Item | User-supplied observation |
| --- | --- |
| Host | Ubuntu 22.04.5 LTS, x86_64, kernel 5.15.0-177-generic |
| Capacity snapshot | 3.8 GiB RAM, 2.7 GiB available; root 43G total / 28G available |
| Docker Compose | v5.1.3 |
| PostgreSQL | Existing `postgres` container, **17.5**, port 5432; owner `postuser` |
| Existing databases | `postdb`, `postgres`, `template0`, `template1`; do not assume `postdb` is empty |
| Node-RED | `nodered`, custom `iotstack-nodered` image, v4.0.9 / Node.js v20.19.0, port 1880 |
| Influx waveform store | `influxdb`, image `influxdb:1.8`, port 8086, database `sensor_data` |
| Other services | `grafana`:3000, `mosquitto`:1883, `portainer-ce`:8000/9000/9443 |
| Separate Influx service | `influxdb2`, image `influxdb:latest`, host port 8087; not used by this workflow |
| Network | `postgres`, `nodered`, `grafana`, `influxdb` share `iotstack_default` |
| Retention | Influx `autogen`: duration 0s (unlimited), shard duration 168h, replicaN 1 |

IOTstack root is `/home/eduard.almar@local.eurecat.org/IOTstack`. Confirmed bind
mounts below are relative to that root:

| Container | Host path | Container path |
| --- | --- | --- |
| postgres | `volumes/postgres/data` | `/var/lib/postgresql/data` (confirmed live data_directory) |
| postgres | `volumes/postgres/db_backup` | `/backup` |
| nodered | `volumes/nodered/data` | `/data` |
| nodered | `volumes/nodered/ssh` | `/root/.ssh` |
| grafana | `volumes/grafana/data` | `/var/lib/grafana` |
| grafana | `volumes/grafana/log` | `/var/log/grafana` |
| influxdb | `volumes/influxdb/data` | `/var/lib/influxdb` |
| influxdb | `backups/influxdb/db` | `/var/lib/influxdb/backup` |

The backup mounts alone do not confirm a backup job or tested restore. The
empty `npm --prefix /data ls --depth=0` result only describes that package
directory; inspect the Node-RED palette before assuming a connector is absent.
No host PostgreSQL installation, container replacement, or image upgrade is needed.

## 1. Copy the deployment files and preserve the current setup

Pause acquisition/upload while changing the flow and backfilling the catalog.
Keep the previous desktop version available for rollback. Export the currently
deployed Node-RED flow and Grafana dashboard from their editors before importing
new versions. The previous flow must not run concurrently with the new subscription.

From the workstation (PowerShell, repository root):

```powershell
ssh -l 'eduard.almar@local.eurecat.org' 172.20.48.28 'mkdir -p ~/injection-monitoring-deploy'
scp -o 'User=eduard.almar@local.eurecat.org' -r iot scripts cycle_metadata.py 172.20.48.28:injection-monitoring-deploy/
ssh -l 'eduard.almar@local.eurecat.org' 172.20.48.28
```

All subsequent shell blocks in this guide run **on the Linux server**:

```bash
cd ~/injection-monitoring-deploy
umask 077
backup_stamp=$(date +%Y%m%d_%H%M%S)
iot_root="$HOME/IOTstack"
backup_dir="$iot_root/backups/metadata_upgrade_$backup_stamp"
mkdir -p "$backup_dir"
docker exec postgres pg_dumpall -U postuser > "$backup_dir/postgres-before.sql"
docker exec influxdb influxd backup -portable -database sensor_data "/var/lib/influxdb/backup/before_metadata_$backup_stamp"
tar -czf "$backup_dir/nodered-data.tgz" -C "$iot_root/volumes/nodered" data
```

Keep the Node-RED data backup private: it includes encrypted credentials and
their settings. Verify backup commands succeed and retain the files outside a
container's writable layer. Restore testing belongs in an isolated instance;
do not test a restore over these running databases.

## 2. Create a dedicated PostgreSQL database and schema

First check whether the proposed database already exists:

```bash
docker exec postgres psql -X -U postuser -d postgres -c "SELECT datname FROM pg_database WHERE datname='injection_monitoring'"
```

If it is absent, create it once. If it already exists, inspect its purpose before
reusing it. Do not drop or recreate existing databases.

```bash
docker exec postgres createdb -U postuser -O postuser injection_monitoring
```

Apply the versioned schema (safe to reapply this initial migration):

```bash
docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring < iot/001_cycle_metadata.sql
docker exec -it postgres psql -X -U postuser -d injection_monitoring
```

In that interactive `psql` session, set separate passwords without putting them
in a shell command or checked-in file:

```text
\password monitoring_ingest
\password monitoring_reader
\q
```

`monitoring_ingest` can execute only the ingestion functions; `monitoring_reader`
can read the cycle catalog. Both use the existing server at `postgres:5432` from
containers on `iotstack_default`. PostgreSQL stores one row per scoped cycle,
not samples or a database/table per cycle. Schema changes leave `postdb` alone.

## 3. Configure Node-RED

Check **Manage palette > Nodes** for `node-red-contrib-postgresql`. The flow
was prepared against **0.16.2**. If absent, install that version in `/data`:

```bash
docker exec -w /data nodered npm install --save-exact node-red-contrib-postgresql@0.16.2
docker restart nodered
```

If an older connector is already in use by other flows, review those flows
before upgrading it. Version 0.16 moved PostgreSQL credentials into Node-RED's
encrypted credential storage. [Connector documentation](https://flows.nodered.org/node/node-red-contrib-postgresql)

In the editor at `http://172.20.48.28:1880/`:

1. Import **the complete `iot/nodered_flows.json`**. Updating only the old
   `function 1` node is insufficient: the new function has three outputs.
2. Replace/update the previous `batch` flow, retaining its working MQTT and
   legacy Influx credentials. Ensure only one subscription/flow handles
   `+/sensors` using client ID `nodered-daq-ingest`.
3. Open **Cycle metadata** PostgreSQL configuration: host `postgres`, port
   `5432`, database `injection_monitoring`, username `monitoring_ingest`, its
   new password. Use the **credential** source in the Security tab.
4. The **Write Influx 1.8** HTTP node targets
   `http://influxdb:8086/write?db=sensor_data&rp=autogen&precision=ns`.
   If authentication is enabled on Influx, configure this node's Basic Auth
   with the existing Influx writer credentials. The old Influx config node's
   credentials are not automatically shared with this HTTP node.
5. Keep the existing `influxdb batch` node for legacy unversioned queued arrays.
   Confirm its database is `sensor_data`, version `1.x`, nanosecond precision.
6. Deploy. Check the error Debug node and server log before resuming uploads.

New captures are validated, registered in PostgreSQL, written to Influx using
exact nanosecond line protocol, then marked `stored` after HTTP 204. Identical
replays are idempotent; conflicting immutable captures are rejected. Editable
measurements use increasing revisions, so an older retry cannot reset newer
values. An edit arriving before its waveform creates an explicit `metadata_only`
row; normal charts exclude it until a capture has been stored.

The desktop's MQTT queue and failed-publish spool retain their existing broker-
ACK behavior. **This is not a new end-to-end delivery guarantee.** Backend errors
after PUBACK do not trigger an automatic desktop retry. Inspect Node-RED errors
and `pending`/`metadata_only` catalog rows; retain manually saved CSV/metadata
when a recording must be recoverable. No automatic local recording archive or
database-ACK protocol has been added.

## 4. Backfill the existing cycle catalog without moving waveforms

Keep acquisition paused for the diagnostic/backfill, or repeat with a new
diagnostic before resuming so the final catalog includes every old capture.
Run a fresh read-only diagnostic; an old report is not a current baseline:

```bash
diagnostic_dir="data/diagnostics/before_metadata_$backup_stamp"
python3 scripts/diagnose_influxdb.py --output "$diagnostic_dir"
python3 scripts/build_legacy_catalog.py "$diagnostic_dir/cycles.csv" --output legacy_catalog.sql --metadata-export legacy.metadata.json
```

Check the diagnostic completed without warnings, and review `legacy_catalog.sql`.
The builder rejects missing/reused scoped identities, multiple series per cycle,
duplicate sample timestamps, and unsupported measurements. It preserves exact
UTC nanoseconds and leaves unavailable settings/material/measurements and
session-relative cycle numbers unknown. It does not infer trigger times or
quality from observed sample bounds.

Apply the reviewed catalog:

```bash
docker exec -i postgres psql -X -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring < legacy_catalog.sql
docker exec postgres psql -X -U postuser -d injection_monitoring -c "SELECT count(*) AS cycles, sum(sample_count) AS samples, count(DISTINCT session_id) AS sessions FROM monitoring.cycle_catalog"
docker exec influxdb influx -database sensor_data -execute 'SELECT COUNT("t_ms") FROM "autogen"."sensor_data"'
```

For the unchanged supplied snapshot, expect **29 cycles, 45,447 samples, three
sessions**, all from the single August 4 test. Newer data requires its own fresh
baseline. Influx timestamps, fields, tags and retention remain unchanged by the
catalog import. Compare per-cycle counts/bounds with the diagnostic and use
the catalog's `influx_predicate` to check representative retrievals in Influx.

To load historical metadata into the desktop for editing, copy
`legacy.metadata.json` back to the PC and use the toolbar's **history icon >
Load…**. To retrieve the latest server measurement revisions later:

```bash
docker exec -i postgres psql -X -A -t -v ON_ERROR_STOP=1 -U postuser -d injection_monitoring < iot/export_metadata.sql > server.metadata.json
```

Load that file before editing a cycle that may already have newer server edits.
Weight and length updates do not resend the waveform.

## 5. Configure Grafana and import the dashboard

1. Keep the existing InfluxDB data source pointing at `influxdb:8086` /
   `sensor_data` using InfluxQL.
2. Add a **PostgreSQL** data source named **Cycle metadata**: host
   `postgres:5432`, database `injection_monitoring`, user `monitoring_reader`,
   its password, version 17; use the existing internal network's connection
   policy. Test the connection. No TimescaleDB extension is required.
3. Read the data source UID from its editor URL. The generated dashboard uses
   `cycle-metadata` by default. If Grafana generated a different UID, run this
   on the workstation, replacing the example UID with the actual one:

   ```powershell
   py -3.11 scripts/generate_grafana_dashboard.py --postgres-uid ACTUAL_DATASOURCE_UID
   ```

4. Import the regenerated `iot/grafana_dashboard.json` into the existing
   dashboard. The waveform source UID is retained from the checked-in template;
   map it to the existing Influx source if your live UID differs.
5. Set a time range containing the August test. The time picker filters
   **observed cycle start**, not individual waveform samples.

Machine, session, material, outcome and optional numeric ranges select cycles
in PostgreSQL. `n_cycles` selects the latest actual matches (maximum 100), even
with gaps in cycle numbers. The Cycles selector can narrow that set. A hidden
variable constructs one escaped Influx predicate per complete identity and
exact time range, joined with OR; independent lists of machines/sessions/cycle
numbers are never cross-matched. Traces partition by all three identifiers.
Continuous captures are an explicit mode, not manufactured parts. Blank numeric
filters include unknown values; an entered bound excludes unknown values.

Refresh remains 5 seconds. Query variables use time-range refresh and time
macros; **verify on the deployed Grafana version** that a newly stored cycle
and later metadata changes refresh the selectors as well as the panels. A
panel refresh alone is not proof that a query variable was recomputed. Until
that check passes, explicitly refresh/reload the dashboard after new records.

## 6. Verify before recording real parts

- Use isolated test databases/topics for synthetic publishing, not the live
  `+/sensors` subscription. Local regression tests do not contact this server.
- Confirm one new capture produces matching PostgreSQL bounds/count and Influx
  rows, with the original machine/session/cycle identity and all channel values.
- Edit weight/spiral length, clear a value, and replay an older capture/update.
  Confirm the latest measurements remain and samples are not duplicated.
- Test multiple sessions sharing a display cycle number, unknown old settings,
  interrupted recordings, continuous mode, and metadata-filtered overlays.
- Inspect `pending` catalog rows and Node-RED errors if either database is
  unavailable. Never interpret the GUI's **Queued (unconfirmed)** as stored.
- DAQ tests remain required when hardware returns, including >100-second runs,
  trigger wiring and physical sample accounting. Sampling parameters and the
  external DAQ driver were intentionally not changed in this work.

Useful read-only check:

```bash
docker exec postgres psql -X -U postuser -d injection_monitoring -c "SELECT machine_id, session_id, cycle_id, waveform_status, sample_count, weight_g, length_mm, metadata_revision FROM monitoring.cycles ORDER BY created_at DESC LIMIT 30"
```

## Retention, backups and rollback

Leave Influx `autogen` unlimited and do not add a PostgreSQL deletion job.
Include `injection_monitoring` in the existing PostgreSQL backup/restore plan;
waveform backups alone no longer include part measurements. After a restore,
reconcile catalog counts/bounds with Influx before relying on stored status.

To roll back, pause uploads, export the new server state, restore the previous
Node-RED flow/dashboard configuration and use the previous desktop version.
Keep the new PostgreSQL database and any new waveform data; do not delete them
as rollback. Preserve pending version-1 envelopes separately and replay them
only through the metadata-aware flow. The old flow cannot interpret new
envelopes, while the new flow intentionally accepts both old arrays and v1.

## Files and local validation

| File | Purpose |
| --- | --- |
| `001_cycle_metadata.sql` | Schema, constrained writes, replay/revision handling, read-only catalog view |
| `nodered_flows.json` | Complete ingestion flow, without credentials |
| `nodered_function.js`, `nodered_prepare_write.js`, `nodered_store_complete.js` | Sources embedded in that flow |
| `export_metadata.sql` | Export current catalog/measurements for the GUI |
| `grafana_dashboard.json` | Metadata selection, waveform overlays and exports |
| `../scripts/build_legacy_catalog.py` | Reviewable catalog SQL from a fresh diagnostic |

Regenerate Node-RED with `py -3.11 scripts/generate_nodered_flow.py` after
editing its functions. Reimporting the generated JSON is a separate deployment.

Local checks (no DAQ or production network):

```powershell
py -3.11 -m unittest discover -s tests -p 'test_*.py' -v
py -3.11 tests/check_metadata_gui.py
npm.cmd install --prefix data/validation --no-audit --no-fund --ignore-scripts @electric-sql/pglite@0.3.15
node tests/check_ingestion.mjs
```

The optional PGlite test dependency is isolated under ignored `data/`; it runs
PostgreSQL 17.5 locally to exercise SQL constraints, revisions, replay, failure
gating and reader permissions. It is not an application dependency or a substitute
for checking the actual Node-RED/Influx/Grafana deployment.
