# Implementation status and remaining deployment work

Updated 2026-10-19 after the paired local CSV export change. Checked items are
implemented/locally verified; server and hardware checks remain explicitly open.
The earlier full migration, acquisition-rate conversion and automatic local
journal plans are superseded by the user's later decisions.

## Agreed scope

- Keep InfluxDB 1.8 for waveforms and PostgreSQL for one metadata row per cycle.
  Keep `(machine_id, session_id, cycle_id)`; Influx retains its numeric
  `cycle_num` field and existing machine/session tags. No waveform migration.
- GUI: machine ID, material/grade, manual mold-temperature setpoint in degrees C,
  limit pressure in bar; one part per cycle, weight in g, spiral length in mm.
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

- [x] Compact settings row with editable machine ID, material, nullable mold
  setpoint and limit pressure; reusable preferences in ignored data/run_setup.json.
- [x] Apply operator settings to future cycles; freeze a deep snapshot at the
  trigger boundary, including channel names/units/order, actual DAQ command
  parameters, conversion settings, trigger settings and rheology geometry.
- [x] Lock machine selection during acquisition. New session IDs combine a
  readable timestamp and UUID; retain the tested installation-wide cycle counter.
- [x] Toolbar history icon opens cycle history with machine/session/both cycle numbers, outcomes,
  settings, weight/spiral length editing, clearing and independent metadata send.
- [x] Keep metadata across Next in RAM; explicitly save/load metadata for earlier
  sessions after restart. No automatic waveform or measurement archive added.
- [x] Independent measurement revisions; original queued capture messages do not
  mutate when later measurements change. GUI states say queued/unconfirmed.
- [x] Reopen DAQ configuration with active values, not startup defaults. Move
  machine editing to Run setup. Sampling values and hardware commands unchanged.
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
- [x] Preserve legacy array replay and existing failed-publish spool semantics.
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
- [x] Exact nanosecond line-protocol writer for new captures; original Influx
  writer remains for old queued arrays. No Influx field rename or cycle tag.
- [x] Historical catalog builder from a fresh diagnostic cycles.csv, with
  anomaly checks, exact bounds and unknown old metadata. No waveform copies.
- [x] Server metadata export for importing the latest measurement revisions
  into the desktop before editing earlier recordings.
- [x] Reproducible flow generator keeps standalone JavaScript and JSON in sync.

### Grafana and handoff

- [x] PostgreSQL machine/session/material/outcome/numeric metadata filters and
  latest-N actual cycle selection, independent of gaps in cycle numbering.
- [x] Bounded Influx predicates keep each machine/session/cycle/time tuple
  together; overlays partition on all three identifiers. Empty selection yields
  no samples. SQL variables use quoting; numeric filters are cast at the database.
- [x] Retain relative-time plots, channel labels and raw export table; add a
  metadata table and explicit continuous/legacy/interrupted access.
- [x] Retain 5-second panel refresh and time-range query-variable refresh;
  deployed selector refresh behavior remains a server verification item.
- [x] Add tracked iot/SERVER_SETUP.md with observed environment, ordered backup,
  schema/roles, Node-RED, catalog, Grafana, verification and rollback steps.
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
- [x] Generated Grafana SQL executed with representative variable interpolation,
  including empty numeric filters and an SQL-like material value.
- [x] Supplied historical report builds 29 catalog rows / 45,447 samples / three
  sessions; validated in an isolated database, without contacting the server.

Commands are in iot/SERVER_SETUP.md. Local SQL/function tests do not replace a
live Node-RED/Influx/Grafana integration test or a physical DAQ run.

## Server rollout and hardware verification (not executed)

- [ ] Back up PostgreSQL/Influx and deployed Node-RED/Grafana configuration;
  verify restores in an isolated instance. Existing backup mounts alone are
  not evidence of scheduled or recoverable backups.
- [ ] Create injection_monitoring in the existing PostgreSQL 17.5 instance,
  apply schema, set role passwords, verify cross-container authentication.
- [ ] Check the custom Node-RED image's installed modules. Its empty /data npm
  listing is not an inventory of globally/bundled modules. Install/configure
  the PostgreSQL connector, import the complete flow, preserve existing creds.
- [ ] Confirm new exact-ns HTTP writes and legacy replay against InfluxDB 1.8;
  inspect backend failures separately from MQTT broker acknowledgement.
- [ ] With uploads paused, collect a fresh diagnostic, review/apply catalog SQL,
  compare counts/bounds/identities, and verify Influx history is unchanged.
- [ ] Configure Grafana's PostgreSQL reader, set its UID in the generator and
  import the new dashboard. Verify exact filters, last-N, gaps/reused IDs,
  interrupted/continuous/legacy data, unknown values, later edits and exports.
- [ ] Verify BOTH selector queries and waveform panels update after a new cycle
  at the deployed refresh interval; otherwise explicitly refresh the dashboard
  pending a version-specific refresh adjustment.
- [ ] Verify DAQ counts/timing, all physical trigger sources, calibration,
  repeated Start/Stop/Next/close, long cycles and amplifier wiring when the DAQ
  is available. No physical signal or end-to-end storage guarantee is claimed.

## Separate follow-ups, not silently bundled into this rollout

- Sampling-rate label/Hz-to-divisor conversion: explicitly deferred by the user.
- Automatic capture journaling, disk-retention policies, chunk receipts and
  client database-ACK delivery: explicitly deferred to preserve tested behavior.
- External driver all-scan/batching contract, cancellable discovery and hardware
  alignment changes: require a separate driver/hardware validation pass. The
  current driver can discard buffered scans; metadata work does not fix that.
- Rendering/memory bounds for very long runs, range-aware calibration outside
  the tested +/-10 V setup, and trigger-boundary inclusion/wiring checks remain
  separate acquisition follow-ups. No claim that the old broad reliability
  wishlist is fully completed.
- Multi-PC allocation/conflict resolution, per-machine counter migration,
  recipe/MES/material catalogs, automatic historical downloads and other
  metadata kinds remain outside the confirmed single-PC workflow.
