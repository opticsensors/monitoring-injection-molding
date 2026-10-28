# Server setup: one command

Stop recording and finish sending old queued uploads first. Keep manual CSV
exports. Run this in **PowerShell from the repository**:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1
```

It copies only the deployment files into a fresh directory under
`~/injection-monitoring-releases/`, opens SSH and runs the installer. Enter
your SSH password and Grafana login when prompted; Node-RED login is requested
only if its editor requires one. New database passwords are generated and
configured automatically. Existing database passwords are requested if needed.
No Grafana or Node-RED GUI import is needed.

Already connected to the server? Upload from PowerShell without opening another
deployment session:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -UploadOnly
```

Then copy the `cd '...' && bash iot/deploy.sh` command printed by the upload
into your existing **server terminal**. It points to the files just uploaded.

For an inspection without deploying, add `--check` to the Bash command, or
`-Check` to the PowerShell command. The installer is intended for this project's
existing IOTstack server, not an arbitrary Docker installation.

## What it does

1. Checks services, versions, persistent mounts, database access, installed
   connector, existing flow and dashboard. Stops on ambiguous configurations.
   On the first run of each release, automatically tests ingestion and recovery
   in separate temporary Docker containers before changing production. Test
   containers are removed afterward; their volumes remain for inspection.
2. Backs up PostgreSQL, Influx, Node-RED and Grafana. Grafana briefly stops for a
   consistent backup; Node-RED restarts only when its runtime setup changes.
3. Creates/migrates the metadata database through **005_machine_correction.sql** and configures its two login roles.
4. Diagnoses existing history and backfills matching legacy cycles. Anomalies
   stop the installer for review; it never relabels native captures as legacy.
5. Installs missing Node-RED components, sets up the queue and deploys the flow,
   preserving the existing MQTT connection/credentials and other flow tabs.
6. Configures the Grafana PostgreSQL datasource and updates this dashboard,
   using the existing Influx datasource and retaining its folder.
7. Checks both database connections, migration 005/catalog columns, History corrections,
   queue health and unchanged waveform counts.
8. If cron is available, installs daily backups at 02:00 server time and a
   five-minute health log, preserving unrelated cron jobs.

Rerun the same command after correcting an error. It reuses generated passwords,
checks existing state and repeats safe migrations/backfill. It does not upgrade
container images, delete waveform history or reset existing admin passwords.
Old upload directories are left untouched; each upload uses a fresh directory
and fixes Windows archive permissions before starting the installer.

Backups and installer state are private under
`~/.local/state/injection-monitoring/`. Influx backups use the existing persistent
backup mount. Keep an off-server backup and periodically verify a restore.
`health.log` is a local report, not an email/notification service. Backups are
retained, so monitor available disk space.

A supervised machine trial can precede restore testing and external alerting.
Keep manual session exports and an independent copy, check disk space and verify
server arrival. Follow [the machine-test checklist](../MACHINE_TEST.md); restore
verification and monitored failures remain follow-ups before relying on the
server as the sole recording store.

After success, open Grafana, set Latest cycles (max 100) and check the curves.
Record one real cycle and confirm it appears before returning to normal work.
The installer cannot prove hardware behaviour, drain a disconnected PC's spool,
or inspect the visual appearance of a chart. MQTT acknowledgement still does
not guarantee database storage.

The current dashboard requires migration 004 because its selector filters excluded
cycles. Deploy the database, Node-RED and dashboard together with the command above.
The dashboard still has one visible count control, numeric cycle legends and the
collapsed raw Export row. It combines 55t and 160t (100 total), omits continuous
and excluded cycles, and retains the existing datasource/dashboard identity.

## Where the supporting files live

The two JSON files remain at the top of `iot/`. `nodered/` contains runtime
JavaScript, `postgres/` contains migrations, `validation/` is the installer's
isolated test stack, and `maintenance/` contains the detailed manual recovery guide.
You normally use only `deploy.sh`; these files are managed by it.

## Desktop history

The GUI preview works offline. Run `scripts/deploy.ps1` for this release: it applies
missing migrations 003/004/005, the read-only History endpoints, MQTT correction
handling and Grafana's exclusion filter. Existing capture JSON and waveforms are
preserved. The migration runner skips older view definitions on a newer database;
rerunning 005 preserves corrections. The isolated stack checks the actual migration
runner twice and exercises correction/exclude/restore messages before production.

Machine corrections are stored in the existing revisioned review JSON. Migration
005 adds validation and `cycle_catalog.effective_machine_id`; capture keys and
Influx waveform routing retain the original machine ID. The installer includes
this migration automatically. This change has not been deployed to the live server.

After deployment, print the history key **in your server terminal**:

```bash
python3 -c 'import json,pathlib; print(json.loads((pathlib.Path.home()/".local/state/injection-monitoring/history-api-access.json").read_text())["token"])'
```

Add the following to the **same local `.env` as MQTT** on each PC:

```dotenv
HISTORY_URL=http://172.20.48.28:1880
HISTORY_TOKEN=the-key-from-your-server-terminal
```

The URL is an installation setting, not a hard-coded desktop default. For a
OneDrive checkout, use `%LOCALAPPDATA%\InjectionMonitoring\.env`; move an existing
repository `.env` there, preserving its MQTT settings. Outside OneDrive the
default remains the repository `.env`. `MONITORING_ENV_FILE` can specify another
local path. The shared file format is [.env.example](../.env.example); keep actual
credentials outside Git and OneDrive. Missing/rejected settings produce a short
error pointing to the file. Database passwords remain on the server.
The agreed deployment is internal-network use; this update adds no TLS or
Windows Credential Manager setup.

**Load server** fetches the latest 10 summaries; **Load more** fetches the next 10.
Load server also refreshes already loaded identities, including exclusions made
on other PCs. Already loaded/local rows and pending edits are kept. **Plot** downloads only selected curves, kept
in RAM for reuse. No CSV files are created automatically. Legacy settings remain
blank when unknown. T/P maxima come from the stored channels; Time is the recorded
sample span.

History uses Exclude/Restore rather than physical deletion. The database stores
the original capture and the latest revisioned correction (`kind=review`), not a
full audit trail of every accepted edit. The catalog/API/export return effective
Material/Mold/Melt/Speed values. Older captures have blank Melt until corrected.
Rejected competing review proposals are available in `monitoring.review_conflicts`.

Pending settings, exclusion and part-measurement edits are written to the PC's
`data/pending_edits.json` before success is shown. They survive restarts and respect
automatic upload being off. Send edits explicitly queues selected proposals;
manual session Send also sends that session's pending corrections. Connectivity
loss leaves work pending. Server readback of the same/newer revision and values
confirms synchronization; broker acknowledgement alone does not. A concurrent
server correction is retained alongside the local proposal for explicit resolution.
This journal contains edited metadata only, never waveform samples: normal Save
is still needed for an offline recording. Exports retain excluded waveforms and
mark them, and keep original capture settings in `.metadata.json`.

For unusual authentication, restore/rollback commands or the isolated integration
test, see [the manual guide](maintenance/MANUAL_SETUP.md). The installer supports
`NODERED_TOKEN`/`GRAFANA_TOKEN` for existing admin/service tokens, and
`--nodered-url`/`--grafana-url` for custom localhost or HTTPS admin URLs.

Local automated tests cover flow merging, credential reuse, API requests and
failure handling, including connections dropped while Node-RED restarts.
User output on 2026-10-19 confirms release.oqzIvlaQ completed all installer stages:
isolated Docker tests, backups, PostgreSQL setup, 29 matching historical cycles,
Node-RED/Grafana deployment, production verification and scheduled maintenance.
The user confirmed Grafana works. Hardware and backup restore checks remain;
see [current status](../TODO.md). The History/correction update through migration
004/005 have not been applied to the live server during this implementation.
The first run can take several minutes to download/build the isolated test stack.
These are deployment tests using separate containers and synthetic data; no DAQ
or active recording is needed. They are not a runtime dependency of the app.
If they fail, read the displayed cause and `~/.local/state/injection-monitoring/validation.log`
before rerunning. A test-environment failure does not by itself prove that the
production services are broken.
The test Grafana uses localhost port 13000 on its own project bridge; test databases
remain on the internal network. On failure, the log includes container status and
service output collected before cleanup. Production Grafana uses port 3000.
