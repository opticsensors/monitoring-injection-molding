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
3. Creates/migrates the metadata database and configures its two login roles.
4. Diagnoses existing history and backfills matching legacy cycles. Anomalies
   stop the installer for review; it never relabels native captures as legacy.
5. Installs missing Node-RED components, sets up the queue and deploys the flow,
   preserving the existing MQTT connection/credentials and other flow tabs.
6. Configures the Grafana PostgreSQL datasource and updates this dashboard,
   using the existing Influx datasource and retaining its folder.
7. Checks both database connections, queue health and unchanged waveform counts.
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

After success, open Grafana, set Latest cycles (max 100) and check the curves.
Record one real cycle and confirm it appears before returning to normal work.
The installer cannot prove hardware behaviour, drain a disconnected PC's spool,
or inspect the visual appearance of a chart. MQTT acknowledgement still does
not guarantee database storage.

For the dashboard-only simplification prepared on 2026-10-20, use Grafana's
**Dashboards -> New -> Import**, upload `iot/grafana_dashboard.json`, and replace
the existing dashboard with the same UID. Its existing datasources are retained.
No server installation, database migration or Node-RED deployment is needed.
The dashboard has one visible count control, numeric cycle legends and the
existing collapsed raw Export row. It combines 55t and 160t in one latest-cycle
selection (100 total), across recording dates, and
omits continuous captures and metadata filters/tables.

## Where the supporting files live

The two JSON files remain at the top of `iot/`. `nodered/` contains runtime
JavaScript, `postgres/` contains migrations, `validation/` is the installer's
isolated test stack, and `maintenance/` contains the detailed manual recovery guide.
You normally use only `deploy.sh`; these files are managed by it.

## Desktop history

The GUI preview works offline. To enable **History → Refresh** (load from server), rerun
`scripts/deploy.ps1`; it installs migration 003 and the read-only Node-RED endpoints.
Grafana stays the same.

After deployment, print the history key **in your server terminal**:

```bash
python3 -c 'import json,pathlib; print(json.loads((pathlib.Path.home()/".local/state/injection-monitoring/history-api-access.json").read_text())["token"])'
```

In the app, **File → Server connection**: server `http://172.20.48.28:1880`,
paste that key. It is kept for this app run; `MONITORING_HISTORY_TOKEN` can supply
it at startup. Database passwords stay on the server. Use HTTPS if accessing it
outside the lab's trusted network.

Metadata loads in pages in the background; waveforms load only for selected
cycles. Legacy settings remain blank when unknown. T/P maxima come from the
stored channels; Time is the recorded sample span.

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
see [current status](../TODO.md). The new desktop history endpoints need the
update described above; they have not been applied to the live server.
The first run can take several minutes to download/build the isolated test stack.
These are deployment tests using separate containers and synthetic data; no DAQ
or active recording is needed. They are not a runtime dependency of the app.
If they fail, read the displayed cause and `~/.local/state/injection-monitoring/validation.log`
before rerunning. A test-environment failure does not by itself prove that the
production services are broken.
The test Grafana uses localhost port 13000 on its own project bridge; test databases
remain on the internal network. On failure, the log includes container status and
service output collected before cleanup. Production Grafana uses port 3000.
