# Implementation status and remaining deployment work

Updated 2026-10-26 after the acquisition-readiness discussion. Checked items are
implemented/locally verified unless server evidence is stated below. The server
installer completed and the user confirms Grafana works. Hardware and backup
restore checks remain open. Desktop online history is new and needs deployment;
the GUI/demo can be reviewed locally first.
The earlier full migration, acquisition-rate conversion and automatic local
journal plans are superseded by the user's later decisions.
Work agreed on 2026-10-27 (melt temperature, History edits/deletion, File menu,
server connection, per-session sidebar settings) is listed under "Planned" below
and is not implemented yet.

## Next supervised machine test

Follow [MACHINE_TEST.md](MACHINE_TEST.md). Hardware repair, backup-restore testing
and external alerting are not prerequisites for this supervised trial. Retain
manual exports and an independent copy; keep those operational follow-ups open.

- [x] Document Machine mold position as an accepted hardware limitation; use
  other known-working trigger methods. Repair is deferred, not a general blocker.
- [x] Fix this app's analog inputs at ±10 V in the GUI and application config.
  Shared `daq_connectivity` range support remains unchanged.
- [x] Clarify the sampling-divisor label without changing values or commands.
- [x] Add `scripts/validate_acquisition.py`: launches the normal GUI and reports
  consumed/returned scans per session using process-local observation only.
- [ ] Run that diagnostic with the actual machine and inspect discards after
  the initial buffered read, host timing, physical traces and saved results.
- [ ] Compare saved cycle identities/counts/timestamps/values with server storage
  and confirm Grafana refresh. Desktop online history remains a separate rollout.

Local verification on 2026-10-26: all 65 Python unit tests passed, including the
new observer tests using synthetic bytes through the installed driver without
opening a port. Offscreen checks passed for fixed ranges, unchanged sampling
commands, metadata/export behavior and the full diagnostic launcher. Hardware
acquisition and live-server results remain unverified by these checks.

## Agreed scope

- Keep InfluxDB 1.8 for waveforms and PostgreSQL for one metadata row per cycle.
  Keep `(machine_id, session_id, cycle_id)`; Influx retains its numeric
  `cycle_num` field and existing machine/session tags. No waveform migration.
- GUI: machine ID, material/grade, manual mold-temperature setpoint in degrees C,
  injection speed in mm/s; one part per cycle, weight in g, spiral length in mm.
  Unknown values are null, never fabricated zeros. Additional pressures can be
  added through the pressure-settings registry and captured JSON settings.
- Preserve all selectable trigger modes and the existing sampling settings,
  rate commands and external DAQ driver. One PC records one machine at a time.
- Preserve manual Save, optional automatic MQTT, explicit manual Send, and
  failed-MQTT spool/cleanup behavior. No automatic local recording archive,
  capture journal, new client database acknowledgements, or retention redesign.
- Uploaded server data stays indefinitely. August 4 was the only historical
  test; absence of later history is expected. DAQ hardware is unavailable now.

## Implemented in the repository

### GUI and capture metadata

- [x] Sidebar icon, one scrollable panel, compact equal-width inputs and one Apply
  for future settings/selected-part measurements. Old pressure settings retain their meaning.
- [x] History tab adds cycles automatically, with date/settings/duration/peak T/P.
  Check rows to open independent comparison tabs using the Live plot components.
- [x] Background server history loader, on-demand waveforms, and bounded RAM cache.
  Unsent measurement edits survive server refreshes; Apply reconciles edited values.
- [x] Load server fetches only the latest 10 summaries; Load more fetches one older
  page per click. Retry/cancel retains the next-page position; local rows/edits survive reload.
- [x] Compact Load server/Load more/Plot actions; balanced Material column, no idle helper text.
- [x] One fixed top plot toolbar/readout for Live and comparison tabs, with independent
  state and selected-cycle calculations. Compact cycle selector and 72 px sidebar inputs;
  comparison explanation moved to the GUI log.
- [x] Offline simulated preview: `py -3.11 scripts/preview_gui.py`.
  Add `--history-demo` to exercise 10/20/25 summaries and selected-only curve loading.
- [ ] Review the revised layout with the user.
- [ ] Deploy migration 003 and authenticated read-only history routes; configure
  File → Server connection, then check the actual historical cycles in the desktop.
  Local API/PGlite/GUI checks pass; the new full Docker test awaits the server.
- [x] Apply operator settings to future cycles; freeze a deep snapshot at the
  trigger boundary, including channel names/units/order, actual DAQ command
  parameters, conversion settings, trigger settings and rheology geometry.
- [x] Lock machine selection during acquisition. New session IDs combine a
  readable timestamp and UUID; retain the tested installation-wide cycle counter.
- [x] Toolbar history icon toggles History/Live; its checked state follows the active tab. Metadata import/export
  remain under File; history has no local Load/Save buttons.
- [x] Keep metadata across Next in RAM; explicitly save/load metadata for earlier
  sessions after restart. No automatic waveform or measurement archive added.
- [x] Independent measurement revisions; original queued capture messages do not
  mutate when later measurements change. GUI states say queued/unconfirmed.
- [x] Reopen DAQ configuration with active values, not startup defaults. Move
  machine editing to the sidebar. Sampling values and hardware commands unchanged.
- [x] Continuous capture has cycle_id=0 and its own frozen snapshot; it is not
  treated as a single part for weight/length entry.

### Lifecycle and export changes needed for complete metadata

- [x] Finalize partial active cycles as interrupted with retained identity.
- [x] Gate Save/Next on final worker data rather than the old fixed Stop delay.
- [x] Finalize acquisition before stopping MQTT on application close.
- [x] Process queued scans without relying on the lossy notification flag;
  handle queue.Empty separately and log processing errors.
- [x] Use session elapsed time for the monitoring-duration limit and copy plot
  payload lists before emitting them across threads.
- [x] Manual Save writes waveform CSV, one-row-per-cycle `.cycles.csv`, and full
  `.metadata.json`. Waveforms retain session/both cycle numbers, exact timestamp,
  relative time and channels; machine ID is in the cycle summary. Both CSVs join
  on session/cycle IDs. Export uses captured settings and latest measurements;
  blank/zero values, interrupted/continuous captures and staged writes are checked.

### Ingestion, schema and history

- [x] Version-1 capture and measurements messages, with decimal-string exact
  nanoseconds. Per-cycle metadata is outside numeric waveform samples.
- [x] Preserve desktop failed-publish spool semantics. Retain late legacy arrays
  in the server quarantine for explicit reconciliation after the controlled cutover.
- [x] PostgreSQL schema with scoped primary key, metadata constraints, typed
  searchable fields, frozen JSON snapshot, revisions and catalog indexes.
- [x] Parameterized Node-RED SQL; deterministic replay hashes and immutable
  capture conflict rejection; later edits survive old capture retries.
- [x] Reject overlapping time ranges within a machine/session, since Influx
  point identity does not include numeric cycle_id.
- [x] Record metadata-only/pending/stored states separately from acquisition
  outcome; mark stored only after a successful Influx HTTP 204 response.
- [x] Separate ingestion and read-only Grafana roles, with no credentials in
  the flow/schema files. Do not infer client delivery from server status.
- [x] Exact nanosecond line-protocol writer with sequential 5,000-point / 4 MB
  chunks; mark stored only after all HTTP writes. No Influx field rename/cycle tag.
- [x] Historical catalog builder from a fresh diagnostic cycles.csv, with
  anomaly checks, exact bounds and unknown old metadata. No waveform copies.
- [x] Server metadata export for importing the latest measurement revisions
  into the desktop before editing earlier recordings.
- [x] Reproducible flow generator keeps standalone JavaScript and JSON in sync.
- [x] Persistent server queue with atomic files, fsync on Linux, leases, backoff,
  quarantine/requeue and reviewed archive. Client ACK gap remains documented.
- [x] Migration 002 records rejected measurements separately from waveform
  acceptance, tracks schema versions, uses a non-login owner and explicit pg_temp.
- [x] Repeatable catalog reconciliation rejects resets/mixed formats and checks
  existing native counts/bounds rather than relabelling them legacy.
- [x] Manual Send uses frozen session mode; wall/elapsed time zero is paired
  after plot setup. Server exports can reconcile conflicting local measurements.

### Grafana and handoff

- [x] One visible control: Latest cycles (max 100), default 10, combining 55t and
  160t with one total limit. Select latest recorded cycles by time, independent of number
  gaps and date windows. Continuous captures are excluded from this viewer.
- [x] Complete machine/session/cycle predicates share one outer Influx time
  range. The hidden predicate variable skips URL sync; there is no machine variable.
  Empty selection yields no samples; overlays partition on all three identifiers.
- [x] Retain relative-time plots, channel labels and the collapsed raw Export row.
  Remove metadata filters/table and capture-mode controls; use numeric cycle
  legends. Stored metadata and acquisition modes remain available in the app/DB.
- [x] Retain 5-second panel refresh and time-range query-variable refresh;
  deployed selector refresh behavior remains a server verification item.
- [x] One-command Windows upload/server installer: preflight, backups, migration,
  password reuse, catalog reconciliation, API deployment of Node-RED/Grafana,
  connection/queue checks and scheduled backups. Preserve unrelated flow/cron
  entries; stop on uncertain mappings or concurrent flow/dashboard edits.
- [x] Short iot/SERVER_SETUP.md; detailed manual guide under maintenance/.
  Group runtime JavaScript and SQL into nodered/ and postgres/ subfolders.
- [x] Update README/CLAUDE and local engineering notes; remove no-loss claims.

## Local validation

- [x] Unit checks for exact timestamps, snapshot immutability, nullable values,
  scoped identity, independent revisions, metadata exports, diagnostic timestamp
  parsing, safe SQL literals, dashboard filters and existing MQTT spool behavior.
- [x] One offscreen Qt process exercises all four triggered modes, setting edits
  during a cycle, interrupted finalization, history, and manual CSV/JSON export.
- [x] Node-RED function logic and SQL exercised with isolated PostgreSQL 17.5
  (PGlite 0.3.15 under ignored data/validation). Includes old/new messages,
  edit-before-capture, duplicate/conflicting replay, out-of-order revisions,
  null clearing, exact bounds, failed Influx response gating and reader rights.
- [x] Generated Grafana SQL exercised with actual latest-cycle selection,
  105 captures with number gaps, the 100-cycle cap, invalid/huge textbox input,
  continuous/pending/other-machine exclusions and empty history.
- [x] Filesystem/flow recovery tests cover leases/restarts, duplicate replay,
  partial writes, failed final DB receipts, byte limits and quarantine.
- [x] Isolated Docker stack, real-service integration test and server backup/
  health helpers prepared. Compose configuration validates; engine unavailable
  locally. The user-run isolated integration test passed on the server on 2026-10-19.
- [x] Supplied historical report builds 29 catalog rows / 45,447 samples / three
  sessions; validated in an isolated database, without contacting the server.

Commands are in iot/SERVER_SETUP.md. Local SQL/function tests do not replace a
live Node-RED/Influx/Grafana integration test or a physical DAQ run.

Deployment tests cover preserving shared configuration, collisions, API bodies,
password recovery after interruption, backup failure gates, check-only mode and
health-failure reporting. They do not certify deployment on the live server.

## Server rollout complete; browser and hardware verification pending

User-provided output on 2026-10-19 for release.oqzIvlaQ confirms all eight stages
completed and the installer printed "Deployment complete." The corrected isolated
container tests passed, including repeated Grafana datasource updates, the real
Node-RED PostgreSQL probe, multi-cycle queries and outage/replay recovery.
Production Node-RED and Grafana were applied and verified, all 29 historical
cycles matched, database access and queue health passed, and waveform counts were
unchanged. Daily backups and five-minute health checks were scheduled. No direct
production commands were run by the assistant; this status records the user's log.

- [x] Back up PostgreSQL/Influx and deployed Node-RED/Grafana configuration.
  Latest backup: `20261019T142821Z-bc4f36` under the installer's private backup directory.
- [x] Schedule daily backups at 02:00 server time and health.log every five minutes.
- [ ] Verify backup restores in an isolated instance and retain an off-server copy.
- [x] Create injection_monitoring in the existing PostgreSQL 17.5 instance,
  apply schema and set role passwords.
- [x] Complete production cross-container authentication checks.
- [x] PostgreSQL connector 0.16.2 installed and Node-RED flow deployed;
  existing MQTT credentials and other tabs retained per installer output.
- [x] User-run isolated container integration passed multi-cycle queries,
  chunked writes, replay and outage/restart recovery.
- [x] Fresh diagnostic/catalog reconciliation imported 29 historical cycles.
- [x] Finish the final production check that Influx history counts are unchanged.
- [x] Pass production queue/quarantine and metadata status checks during deployment.
- [x] Grafana works, confirmed by the user.
- [ ] Confirm one real newly recorded cycle reaches the database and charts.
- [x] Grafana PostgreSQL reader and dashboard applied; both datasource health
  checks passed during the completed deployment.
- [x] The user reports the simplified 2026-10-20 Grafana dashboard works.
- [ ] Verify BOTH selector queries and waveform panels update after a new cycle
  at the deployed refresh interval; otherwise explicitly refresh the dashboard
  pending a version-specific refresh adjustment.
- [ ] Verify DAQ counts/timing, the working physical trigger sources, calibration,
  repeated Start/Stop/Next/close and long cycles when the DAQ is available.
  Machine mold position amplifier wiring remains an accepted, deferred issue.
  No physical signal or end-to-end storage guarantee is claimed.

## Planned: melt temperature, History tab and server connection (not implemented)

Agreed with the user on 2026-10-27 and only written down for now. Each item
records what was found in the code so the work can start from it.

### 1. Melt temperature: REQUIRED

- [ ] **Add `Melt (°C)` directly below `Mold (°C)` in the run setup.** Melt
  temperature is a process parameter that must be recorded with every cycle,
  and it must also appear as a History column.
  - Same behaviour as Material/Mold/Speed (checked 2026-10-27): manual entry,
    written to `data/run_setup.json` on Apply/Start/Next, kept across cycles,
    sessions and restarts, frozen into each capture at the trigger edge.
  - Desktop: `melt_temperature_c` in `operator_settings()` (lower bound
    -273.15, as for mold), a `RunSetup` field, a History column next to
    Mold (°C), the `.cycles.csv` field list in `export_cycle_summary()`, and the
    preview/demo data.
  - Server: settings travel inside `capture`, and the server stores the whole
    capture JSON, so the value already reaches PostgreSQL and the history API;
    older cycles read as blank. Still add validation in
    `iot/nodered/nodered_function.js`, a generated column plus `cycle_catalog`
    entry in a new migration, and the server metadata export. Grafana only if wanted.
  - Must also be correctable through the settings-correction layer (2.3).
  - **It is a setpoint, like the mold temperature** (confirmed by the user on
    2026-10-27), not a measured value. Tooltip: "Manual melt-temperature
    setpoint."; validation message "Melt setpoint", matching "Mold setpoint".

### 2. History tab

Current behaviour, for reference:

- **Load server**: asks for URL and access key when none is set, then
  `GET /monitoring/history` returns the 10 newest cycle summaries of all
  machines, without waveforms. Existing rows and unsent local Weight/Spiral
  edits are kept. Clicking again restarts from the newest page.
- **Load more**: the next 10 older summaries via the page cursor. Disabled while
  a request runs and at the end ("No older cycles"); failure/cancel keeps the position.
- Waveforms download only on **Plot**, into the 128 MB RAM cache.

#### 2.1 State column: clearer wording (desktop only)

The column combines two things (`metadata_widgets.py:283-285`):

1. Where the row came from / waveform status (`waveform_status`):
   - **Local**: recorded by this app in this run, only in this PC's memory. It
     stays "Local" even after it was sent over MQTT; the tooltip shows the
     delivery state (e.g. "Queued (unconfirmed)").
   - **Stored**: loaded from the server; the waveform is in InfluxDB and can be plotted.
   - **Legacy**: old data from before the metadata system; can be plotted.
   - **Pending**: the server has the metadata, but the waveform is not confirmed
     as written yet. Plot fails with "waveform unavailable".
   - **Metadata_only**: the server got Weight/Spiral but never the capture.
2. **"· partial"**: capture status `interrupted`. The cycle was still running
   when acquisition stopped (Stop mid-cycle, monitoring-time limit, device
   error); the trigger never went low, so the waveform is cut off and its
   Time, T max and P max may be wrong.

Keep the column, but:

- [ ] Show partial as **"Incomplete"**, highlighted (e.g. orange): it tells the
  operator not to trust that cycle.
- [ ] Rename the delivery labels, e.g. "This PC · not sent", "Sent (unconfirmed)",
  "On server", "Server processing". Local → Stored after Load server is currently
  the only GUI confirmation that the server received a cycle, and "Local" is
  misleading for a cycle that was already sent.

#### 2.2 Weight and Spiral columns (desktop only, low risk)

- [ ] Add Weight (g) and Spiral (mm) columns from each row's `measurements`.
- [ ] Optionally make them editable in the table through the same revisioned
  path as the sidebar (`update_measurements()` → MQTT measurements message), so
  the sidebar, the table and the server stay in sync.

#### 2.3 Row deletion and row editing: IMPORTANT, every change must reach the server

The operator must be able to remove a wrong cycle and correct wrongly entered
settings from the History tab, and **every such change must be sent to the
cloud/server** (PostgreSQL catalog, History on other PCs, Grafana). A change
that exists only on this PC is not acceptable.

Deletion:

- [ ] **Soft delete ("Exclude / bad cycle")**, not real deletion. Sent like
  Weight/Spiral, with a revision, so it can be undone. Grafana and History hide
  excluded cycles (optionally a "show excluded" toggle). Real deletion is ruled
  out: it contradicts "never delete waveform history", and the history API is
  read-only by design (`iot/nodered/history_api.cjs:102`).
- [ ] Removing a row only from the local list is not enough: a server row comes
  back on the next Load server.
- [ ] Current-session trap: Save writes every sample and looks up its cycle in
  `cycle_history` (`metadata_controller.py:411`). Deleting the entry there makes
  Save crash with a KeyError, so excluded cycles must be skipped explicitly in
  the waveform/cycle export (or exported with an `excluded` flag), never just
  removed from `cycle_history`.

Editing Material / Mold / Melt / Speed:

- [ ] **Correction layer, not overwriting the recorded values.** Captured
  settings are immutable on purpose: the server rejects a conflicting capture
  replay, the desktop requires local and server capture to match exactly
  (`history_controller.py:155`), and metadata import does the same
  (`metadata_controller.py:362`). Keep the recorded values and add revisioned
  corrections, like Weight/Spiral. Table, Grafana and `.cycles.csv` show the
  corrected value, with a tooltip such as "recorded as X".
- [ ] **Multi-row editing.** Settings carry over between cycles, so one typo is
  usually repeated on many consecutive cycles: select the rows, then
  "Edit settings for N cycles". Cell-by-cell editing would be tedious.

Server work shared by deletion and correction (one deployment):

- [ ] One new revisioned message (or an additive extension of measurements v1)
  carrying `excluded` and the setting corrections, with the same rule that an
  older revision never overwrites a newer one.
- [ ] New PostgreSQL migration (correction/excluded columns; catalog and history
  views return the effective values), Node-RED validation, Grafana selector
  filter, server metadata export, desktop merge/conflict handling, redeploy.

Suggested order: (1) desktop only: State wording, Incomplete highlight,
Weight/Spiral columns; (2) desktop + server in one deployment: Exclude cycle
and multi-row settings correction, including Melt.

### 3. Remove the File menu

The top-left `File` menu holds Import metadata…, Export metadata… and Server
connection… (`metadata_controller.py:105-109`). The user would prefer not to
have it. They are only partly covered by GUI buttons:

- Export metadata: mostly duplicated by **Save**, which already writes
  `.metadata.json`. Difference: Save exports only the current session; File →
  Export writes every cycle in memory (all sessions since start plus loaded
  server rows).
- Import metadata: no button equivalent. Restores metadata of earlier sessions
  after a restart and reconciles server metadata exports. Imported local-only
  cycles have no waveform in RAM, so Plot tries the server. Mostly redundant
  once server history is used.
- Server connection: no button; it also opens automatically on the first
  Load server without a key. Unnecessary once item 4 is done.
- [ ] Remove the menu: Save keeps the metadata export; drop Import (or replace it
  with a History-tab "Open saved session…" that reads the CSV + metadata, so
  offline sessions can also be plotted); replace Server connection with item 4
  plus a status indicator.

### 4. Server connection without prompts

Now: `history_controller.py` keeps the URL in QSettings (default hard-coded
`http://172.20.48.28:1880`) and the access key only in memory, or from the
`MONITORING_HISTORY_TOKEN` process environment variable, which is not read from
`.env`. So the dialog appears on the first Load server of every app run. MQTT is
already configured from `.env` (`BROKER`, `PORT`, `user`, `password`, read
directly by `mqtt_publisher.load_settings()`).

Usual practice in plant-floor software: connection details are set once at
commissioning by an engineer/administrator, in a machine-level configuration
file or an admin-protected settings page; operators never type server addresses
or passwords. Secrets live in the OS credential store (Windows Credential
Manager / DPAPI) or an encrypted configuration, or are replaced by Windows/AD
integrated login or certificates (e.g. PI System clients, OPC UA). Operators
only see a connection-status indicator; user logins exist for auditing who
changed what, not for connecting.

**Decision (user, 2026-10-27): internal use only, so `.env` is enough.** No
Windows Credential Manager, certificates or TLS for now.

- [ ] Read `HISTORY_URL` and `HISTORY_TOKEN` from the same git-ignored `.env` as
  MQTT; no prompt when they are present, and a short error pointing to `.env`
  when they are missing or rejected. Remove the hard-coded IP.
- [ ] The key already exists on the server: the installer generates it and keeps
  it in `~/.local/state/injection-monitoring/history-api-access.json`
  (`scripts/deploy_server.py:785`). Copy it into each PC's `.env` once. Update
  that installer message and `iot/SERVER_SETUP.md:104`, which still point to
  File → Server connection.
- [ ] Keep `.env` out of Git (already ignored) and out of OneDrive sync.
- [ ] Show broker/server status (green/red) in the GUI instead of a connection dialog.

### 5. Sidebar: settings fixed per session, separate Part box

Current behaviour (checked 2026-10-27):

- Material/Mold/Speed can be edited at any time, also during a running cycle;
  only Machine is locked while a session records (`begin_metadata_session()`,
  unlocked in `receiveXYData()`).
- Typing alone does nothing. A change takes effect on Apply, or automatically on
  Start/Next (`prepare_run_setup()`), from the next trigger edge; the running
  cycle keeps the snapshot it started with.
- Risk: a value typed but not applied stays visible in the box while cycles keep
  recording the old value, with no warning.
- One Apply serves two targets: settings go to *future* cycles, Weight/Spiral go
  to the *already finished* cycle shown as "Cycle 339 · 55t"
  (`metadata_controller.py:72-76`). Confusing for the operator.

**Decision (user, 2026-10-27):**

- [ ] **Settings fixed per session.** Machine/Material/Mold/Melt/Speed are locked
  while a session records, like Machine today; editable after Stop; applied on
  Start/Next through the existing `prepare_run_setup()`. Remove the settings part
  of Apply. Short hint while locked: "Stop to change; applies from Next".
  - Matches the workflow: one setpoint set per session (on 2026-10-27, sessions
    of 5 cycles with cycle times 18.96 → 18.01 → 17.55 → 17.39 → 17.32 s).
  - Rejected alternative, locking only during a running cycle: cycles take
    ~17-21 s with ~4-11 s gaps, so the fields would be disabled most of the time.
  - Changing a setpoint means Stop, then Next. Press Stop between cycles,
    otherwise the running cycle is saved as partial. Wrong entries are fixed
    afterwards with the correction layer (2.3).
  - While stopped, applying the DAQ configuration window must not reset typed
    values (`main.py:975-976` currently restores the last applied ones).
    Optionally save edits to `data/run_setup.json` as they are made, so closing
    the app without starting keeps them.
- [ ] **Separate Part box**, titled "Part · Cycle N · machine", with Weight/Spiral
  and its own Save button (enabled only after an edit). It stays editable during
  cycles: part N is weighed while part N+1 is moulded. Keep the
  Apply/Discard/Cancel prompt when the selection would change with unsaved
  values (`PartEditor.can_leave()`).
- [ ] Update the tests that encode the current behaviour:
  `tests/check_metadata_gui.py:95` applies settings mid-session from
  `cycleStartedSig`, and `tests/check_history_gui.py:87-99` relies on the shared
  Apply. Keep their checks that recorded captures never change.

## Separate follow-ups, not silently bundled into this rollout

- Hz-to-divisor conversion and acquisition-rate changes remain deferred. Only
  the misleading Hz label was corrected; existing command values are preserved.
- Automatic desktop capture journaling, disk-retention policies, client chunk receipts and
  client database-ACK delivery: explicitly deferred to preserve tested behavior.
- External driver all-scan/batching contract, cancellable discovery and hardware
  alignment changes: require a separate driver/hardware validation pass. The
  current driver can discard buffered scans; metadata work does not fix that.
- Rendering/memory bounds for very long runs and trigger-boundary inclusion
  remain separate acquisition follow-ups. Other input ranges are outside this
  app's scope; the shared driver retains them. Machine mold position wiring
  repair is deferred. No claim that the old broad reliability wishlist is complete.
- Multi-PC allocation/conflict resolution, per-machine counter migration,
  recipe/MES/material catalogs, automatic historical downloads and other
  metadata kinds remain outside the confirmed single-PC workflow.
