# Implementation status and remaining deployment work

Updated 2026-10-27 after implementing the agreed desktop/server changes. Checked items are
implemented/locally verified unless server evidence is stated below. The server
installer completed and the user confirms Grafana works. Hardware and backup
restore checks remain open. Desktop online history is new and needs deployment;
the GUI/demo can be reviewed locally first.
The earlier full migration, acquisition-rate conversion and automatic local
journal plans are superseded by the user's later decisions.
The October 27 changes are implemented locally below. The live server still needs
the coordinated 003/004/005 migration, Node-RED and Grafana deployment. Pending edits
are durable metadata proposals; this adds no automatic waveform archive.

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

- [x] Sidebar icon, scrollable panel and equal-width inputs. Session settings apply
  on Start; Part measurements autosave. Old pressure settings retain their meaning.
- [x] History tab adds cycles automatically, with date/settings/duration/peak T/P.
  Check rows to open independent comparison tabs using the Live plot components.
- [x] Background server history loader, on-demand waveforms, and bounded RAM cache.
  Pending edits survive server refreshes; explicit Save/Send reconciles conflicts.
- [x] One load icon fetches 10 summaries per click, then refreshes loaded identities
  and the newest page. Retry/cancel retains the cursor; local edits survive reload.
- [x] Compact History actions, balanced columns and no idle helper text.
- [x] One fixed top plot toolbar/readout for Live and comparison tabs, with independent
  state and selected-cycle calculations. Compact cycle selector and 72 px sidebar inputs;
  comparison explanation moved to the GUI log.
- [x] Offline simulated preview: `py -3.11 scripts/preview_gui.py`.
  Add `--history-demo` to exercise 10/20/25 summaries and selected-only curve loading.
- [x] User approved the Full inspector layout; adopted in the main application.
- [x] October 28: revise `py -3.11 scripts/preview_layouts.py` around Full inspector.
  Embedded Setup tabs (DAQ / Mold sensors / Machine data / Display), inline
  History edits, balanced columns, one paginated load action, icon tooltips and
  independent closable plot tabs. Removed Session strip and configuration popup.
  Simulated acquisition and a 25-cycle in-memory server use disposable state.
  The production window now shares this layout and editing behavior; only the demo replaces I/O.
- [x] Refine the preview: native connected tab panes, Monitor-only acquisition
  controls, one action row per view, consistent Lucide icons and a single DAQ
  connection toggle. Remove the title, cycle-count banner and verbose status strip.
- [x] Full inspector integrated into `main.py` with real DAQ connection and staged configuration.
- [x] Fit analog/digital channel tables to their contents, remove reserved scrollbar
  space below the rows, and center numeric machine conversion cells.
- [x] Missing DAQ ends Connect with a clear bottom-log message and permits retry.
  The app overrides the shared driver's infinite discovery wait; partial serial
  connections are released on failure. Real-driver/Qt failure-path checks pass.
- [x] Preview: replace the plug icon with a named Connect/Disconnect action for
  the single DAQ, without a device selector. Stack and fit Trigger; keep Machine
  variables full width with a fitted height, and Session settings/Next in Monitor.
- [x] Preview: narrow the inspector to 250 px, autosave Weight/Spiral and follow
  trigger starts. Keep live measurements in a local draft until capture finishes;
  defer automatic selection while typing so measurements cannot cross cycles.
- [x] Machine corrections use revisioned metadata in both main and preview. Migration
  005 validates machine edits; immutable identity and waveform routing remain intact.
- [x] Main-window checks cover real controller Start/Stop/Next/restart with a fake
  serial device, changed scan lists, autosave during acquisition, focus-safe cycle
  following, discarded-number reuse and frozen stopped-session exports.
- [ ] Deploy migrations through 005 and authenticated read-only history routes;
  configure the shared local `.env`, then check actual historical cycles in the desktop.
  Local API/PGlite/GUI checks pass; the new full Docker test awaits the server.
- [x] Apply operator settings on Start; freeze a deep snapshot at the
  trigger boundary, including channel names/units/order, actual DAQ command
  parameters, conversion settings, trigger settings and rheology geometry.
- [x] Lock all session settings during acquisition. New session IDs combine a
  readable timestamp and UUID; retain the tested installation-wide cycle counter.
- [x] Native Setup/Monitor/History and closable Plot tabs; File provides Save/Send/Close.
  Acquisition controls stay in Monitor, with autosaved part measurements.
- [x] Keep metadata across Next in RAM. Pending metadata edits survive restart in
  a small local journal; waveforms still require explicit Save or server storage.
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
  on session/cycle IDs. Export uses effective corrected settings and latest measurements;
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
- [x] Server metadata export retains original captures and latest corrections/measurements.
  Desktop History loads current server values directly.
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
  gaps and date windows. Continuous and excluded cycles are omitted from this viewer.
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

## Implemented October 27: melt, History corrections/exclusion and session sidebar

- [x] Melt (°C) is directly below Mold: a manual setpoint with the same -273.15 °C
  lower bound, saved on Start, retained across sessions/restarts and frozen
  in each capture. History, cycle CSV, demo, Node-RED validation, migration 004
  and the server export include it; old captures read as blank.
- [x] History distinguishes This PC / Upload queued / On server / Server processing.
  Interrupted records show orange **Incomplete**. Weight and Spiral have columns.
  Measurement editing stays in the Part box; optional inline editing was omitted.
- [x] Check/select multiple rows for **Edit settings**, **Exclude**, **Restore** or
  **Send edits**. A correction changes effective Material/Mold/Melt/Speed while
  preserving the original capture; cells show the original value in a tooltip.
  The batch dialog changes only ticked fields; a blank ticked field clears it.
- [x] Exclusion is reversible and hides the row in normal History/Grafana. Show
  excluded makes it available for Restore. Save keeps the underlying samples and
  flags excluded rows in waveform/cycle CSVs; full metadata keeps the original.
- [x] The server stores only the latest correction/exclusion object and revision,
  not a complete history of accepted edits. `kind=review` uses the existing MQTT
  ingestion path. Older revisions never replace newer ones. Rejected competing
  proposals remain in `monitoring.review_conflicts` for diagnosis.
- [x] Pending settings/exclusion/Weight/Spiral edits are written atomically to
  `data/pending_edits.json` before success is shown and restored after restart.
  Offline or automatic-upload-off means **Pending sync**. Automatic sending respects
  the switch; explicit Send edits permits sending selected edits with the switch
  off. Manual session Send also sends that session's pending corrections.
  Server readback confirms synchronization; broker enqueue/ACK is not sufficient.
- [x] History reload refreshes all already-loaded identities before its newest
  10-row page, so exclusions/corrections made on another PC update older loaded rows.
  Local pending proposals survive refresh. A competing server revision is shown as
  a conflict; explicit Save/Send rebases the proposal and preserves untouched fields.
- [x] Remove the File menu. Save keeps its metadata companion. The optional offline
  Open saved session replacement and inline measurement editing are not included.
- [x] MQTT and History share `.env`: `HISTORY_URL` / `HISTORY_TOKEN`, no hard-coded
  desktop server IP or credential prompts. Missing/rejected settings point to the
  file. Upload connection and History server state changes appear in the bottom
  message log (updated October 28), without repeated polling messages or separate
  status-bar labels. Uploads off and not checked are ordinary informational states.
  OneDrive checkouts default to `%LOCALAPPDATA%\InjectionMonitoring\.env`;
  `MONITORING_ENV_FILE` overrides both services. The existing local `.env` was
  moved out of this OneDrive checkout with its contents verified unchanged.
- [x] Lock Machine/Material/Mold/Melt/Speed while recording; unlock after final Stop
  data. Apply only on Start. Applying DAQ configuration preserves typed fields.
  Part measurements autosave while recording. Focused input retains its cycle;
  invalid values stay highlighted and prevent leaving the measurement unsaved.
- [x] Migration 004 adds the melt column and latest review/exclusion state, updates
  effective catalog/history values, and preserves immutable captures/waveforms.
  The installer applies missing migrations in order, verifies schema 005/History,
  and packages the matching flow, reader API and Grafana exclusion selector.
  Its isolated test now exercises the actual migration runner twice and sends
  corrections/exclude/restore through real MQTT/Node-RED before production changes.
- [x] Updated unit, offscreen GUI, PGlite and deployment checks; rendered and inspected
  the revised History/sidebar. See the tracked server guide for the rollout command.
- [ ] Run the coordinated deployment on the live server, add its History URL/key to
  each PC's local `.env`, and verify two-PC refresh, exclusion/restore and Grafana.
- [ ] Review the revised UI with the user and perform the supervised hardware checks.

Local validation: 70 Python unit tests passed (one additional WSL extraction check
skipped because local Ubuntu was unavailable), four offscreen GUI scenarios passed,
and PGlite ingestion/history/review/recovery checks passed. The Windows deployment
package was built and checked for migration/API/runner contents and absence of secrets.
Live DAQ, production deployment and the full Docker stack remain separate checks;
the local Docker engine is unavailable. No production commands were run.

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
