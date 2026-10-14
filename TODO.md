# Implementation TODO

Updated 2026-10-13. This is the handoff for the next implementation session.
Unchecked items are planned work, not changes already made. Complete each stage
and its relevant checks before moving to server cutover.

## Agreed direction

- Use **one PostgreSQL database for both cycle metadata and sensor samples**.
  Separate linked tables within that database; no permanent PostgreSQL/InfluxDB
  split. The reason to migrate is relational querying and traceability, not a
  demonstrated performance problem with the present database.
- Keep Grafana for plots after cycles finish. Keep the existing PyQt application
  and MQTT transport. Start by adapting Node-RED ingestion; only introduce a
  separate ingestion service if the required transaction/acknowledgement behavior
  cannot be implemented cleanly there.
- Standardize the persistent numeric cycle number as `cycle_id`. Keep
  `session_id` for the acquisition session and `session_cycle` for its relative
  cycle number. Numeric `cycle_id` alone is not a globally unique database key.
- Capture a settings/context snapshot for every cycle, reused from operator
  inputs until they change. Historical snapshots must not change when defaults
  or the current settings change.
- Start with plain PostgreSQL. TimescaleDB/partitioning, a custom analysis UI,
  recipe management and production-order management are deferred until an actual
  requirement justifies them. A TimescaleDB extension would still use PostgreSQL,
  but is not needed to establish these relationships.
- Keep InfluxDB running during preparation and migration verification. Retire it
  as an active data store after a verified cutover and retained backup. Temporary
  overlap is a migration measure, not the final architecture.

## Evidence and limits to remember

The supplied diagnostic was collected on 2026-10-13 from InfluxDB 1.8.10,
database `sensor_data`, measurement `autogen.sensor_data`:

| Observation | Result |
| --- | --- |
| Stored samples / sensor values | 45,447 / 318,129 across seven sensor channels |
| Machines / sessions / cycles | One (`55t`) / three / 29 (cycle numbers 3-31) |
| Stored date range | 2026-08-04 10:22:49.691369500 to 13:06:51.233424000 UTC |
| Series / tags | Three / `machine_id`, `session_id` |
| Current cycle field | `cycle_num`, declared float; observed values are integral |
| Completeness checks | No missing fields, nonfinite values, duplicate timestamps or reused cycle IDs in this snapshot |
| Observed storage | About 2.08 MiB of data; unlimited retention |
| Stored effective rate per cycle | Median 219.947 Hz; range 58.457-244.457 Hz |
| Long-cycle concern | Cycle 5: 122.740 s, 7,176 samples, 58.457 Hz, maximum interval 119.0024 ms |

Stored rates are not measured hardware sampling rates. These checks cannot detect
all samples lost before storage. Historical acquisition settings and software
versions are unknown; today's defaults must not be assigned to August's records.
The diagnostic contains summaries and small example rows, not a full raw backup.

Local evidence: `data/diagnostics/{report.json,summary.txt,cycles.csv,sessions.csv,
fields.csv,daily.csv,reused_cycle_ids.csv}`. Detailed local analysis:
`docs/database-assessment-2026-10-13.md`, `docs/review-findings.md` and
`docs/INDEX.md`. Both directories are ignored and may be absent in another clone;
this TODO carries the implementation essentials independently.

## 0. Establish the baseline before implementation

- [ ] Inspect `git status` and preserve unrelated working-tree changes. Read the
  affected source before editing; local reference notes describe a reviewed
  snapshot, not a guarantee about later code. If available, run
  `py -3.11 docs/reference_index.py --check` and inspect reported differences.
- [ ] Confirm whether August-only data is expected. If newer captures should be
  present, investigate the acquisition-to-database path first; missing later data
  is more urgent than schema migration. Do not infer that cycles 1-2 were lost.
- [ ] Establish the intended workload: machines, actual desired samples/second
  per channel, typical/maximum cycle length, duty cycle and raw-data retention.
  Measure ingestion/query behavior for that workload before committing capacity
  settings. The small diagnostic is not a production benchmark.
- [ ] Confirm the deployed Node-RED flow, Grafana data source/dashboard and DAQ
  driver revision. Repository configuration is not proof of server configuration.
  The dashboard checked into Git refreshes every 5 seconds.
- [ ] If `Machine mold position` triggering is used, verify the actual amplifier
  reset/operate wiring during injection. Existing project notes flag inverted
  coil behavior; software trigger inversion cannot correct amplifier reset at
  the wrong physical time. Resolve this before trusting those pressure curves.

## 1. Highest priority: acquisition fidelity and timing

Files: `config.py`, `config/daq_config_defaults.json`, `config_window.py`,
`main.py` (`DaqThread`, `GraphThread`), and the separate editable package
`../daq_connectivity/daq_connectivity/daq_serial.py`.

- [ ] Correct the sample-rate contract. The UI says Hz, but the app currently
  forwards `sample_rate_hz` directly as the DATAQ `srate` divisor. For DI-4108,
  the documented nominal per-channel rate is
  `60,000,000 / (srate * dec * deca)`. Current defaults `6000 / 100 / 1`
  therefore correspond to 100 Hz, not 6,000 Hz. Check permitted parameters against
  the [DATAQ protocol, p.47](https://www.dataq.com/resources/pdfs/misc/Dataq-Instruments-Protocol.pdf).
- [ ] Accept desired Hz, compute supported protocol parameters, and display the
  achieved nominal rate. Version/migrate existing configuration without changing
  its nominal hardware behavior. Do not merely replace `6000` with `100` while
  leaving the current driver call unchanged. Record requested Hz, achieved
  nominal Hz and the actual `srate`, `dec`, `deca` values.
- [ ] Change the reader/application contract to return and process every complete
  scan in order, preferably in batches. Current `collect_data_binary1` drains
  buffered scans and returns only the newest. `binary2` returns a flat multi-scan
  tuple and is not a drop-in fix. Preserve channel/digital-word alignment and
  handle partial scans explicitly; never fabricate valid samples by zero-padding
  malformed reads.
- [ ] Define a sample sequence and timing contract. Separate host arrival time
  from acquisition time; determine hardware timing support. If times are
  reconstructed from nominal rate and scan index, label that provenance and
  expose discontinuities rather than presenting them as measured hardware times.
  Anchor UTC and monotonic elapsed time consistently.
- [ ] Fix queue processing so queued data does not depend on a lossy notification
  flag. The current loop processes at most 20 entries then clears `readQSigRec`.
  Reproduce backlog/race behavior, replace broad exception swallowing with
  `queue.Empty` handling plus logged processing failures, and record backlog,
  processed scans and any known loss/overflow.
- [ ] Separate acquisition/storage from display refresh. Bound display history
  and ghost curves, downsample only for rendering, and avoid repeatedly copying
  an entire long capture into every plot update. Keep full-resolution persisted
  measurements and avoid unbounded session/raw/completed-cycle copies in RAM.
- [ ] Verify with synthetic multi-scan input and representative hardware runs,
  including >100-second cycles. Check scan order/counts, channel alignment,
  trigger edges, timing provenance, queue depth and UI responsiveness. The
  historical cycle-5 slowdown is a reason to investigate, not a proven root cause.

## 2. Highest priority: durable capture and correct lifecycle

Files: `main.py` (`GraphThread.run`, `stopReading`, `onCycleEnded`,
`receiveXYData`, `closeEvent`), `mqtt_publisher.py`, and ingestion changes below.

- [ ] Persist recoverable data locally during acquisition, independently of the
  optional Save action and cloud enablement. Use bounded durable chunks/a journal
  plus a final cycle manifest, so a long in-progress cycle can be recovered after
  interruption. Specify flush frequency and any remaining crash-loss window.
  Atomic replacement alone does not guarantee power-loss durability.
- [ ] Persist completed upload envelopes before queueing network delivery. Write
  spool files atomically, retain schema version, original identity, frozen
  metadata and original destination/topic. `_drain_pending` currently uses the
  active publisher's topic even for older records belonging to another machine.
- [ ] Make Stop, duration expiry, device failure and application close finalize
  an active cycle exactly once with a reason/status. Preserve partial samples as
  interrupted/aborted captures. Keep completion state separate from part quality
  and whether a part was produced. Define the trigger-blip rejection policy.
- [ ] Prevent identifier reuse for any persisted interrupted/aborted cycle. Tiny
  rejected triggers may reuse a display number only if no retained cycle record
  owns it; their rejection can be logged separately.
- [ ] Enforce monitoring duration with session monotonic elapsed time. The current
  test uses cycle-relative X, so repeated short cycles can exceed the configured
  session duration.
- [ ] Replace the fixed Stop delay with explicit worker completion/drain gating
  before Save/Next/reset. Stop and finalize acquisition before stopping the
  publisher; current close order can queue data after the publisher has stopped.
- [ ] Define recovery on restart, bounded queues/spool growth and visible disk or
  ingestion errors. Never silently discard unacknowledged captures to free space.
  A full capture store should produce an explicit operational error.
- [ ] Distinguish locally saved, queued, broker-acknowledged and database-stored
  states. MQTT QoS 1/PUBACK is not a PostgreSQL commit acknowledgement. Do not
  report successful database storage or delete the sole recoverable copy at
  broker acknowledgement.
- [ ] Finish the database acknowledgement protocol with stage 5. Retain/retry the
  same immutable payload until durable database receipt is known; define a
  separate retention policy for local archived captures after acknowledgement.
- [ ] Verify crash/restart recovery, offline capture, broker and database outages,
  retries after machine selection changes, Stop during a cycle, duration expiry,
  close during capture and repeated Start/Stop/Next. Assert one retained identity
  and no duplicate stored samples after replay.

## 3. Cycle identity, metadata and reproducible configuration

Files: `config.py`, `config_window.py`, `main.py`, `sensor_types.py`,
`rheology.py`, `mqtt_publisher.py` and local export code.

- [ ] Use scoped identity `(machine_id, session_id, cycle_id)` consistently.
  Generate collision-resistant new session IDs, preserving historical session
  strings on import. Keep any readable session timestamp as a separate label
  if necessary. Numeric `cycle_id` stays an integer display/persistent counter;
  `session_cycle` is explicitly transmitted and stored.
- [ ] Fix counter ownership/persistence: the current `data/cycle_id.txt` is shared
  by all machine choices within a checkout. Maintain counters by machine in the
  installation, migrate the existing counter deliberately, and do not imply that
  independent acquisition computers share a global allocator. Protect allocation
  against restart/reuse; scoped identity remains authoritative.
- [ ] Add operator inputs for material grade, material batch, mold ID and relevant
  setpoints with explicit units. Use null/unknown for missing information, not
  zero. Reuse inputs until edited; changes apply to subsequent cycles.
- [ ] Freeze a snapshot at cycle start containing those inputs plus machine,
  DAQ parameters, channel IDs/names/units, ranges and calibration/conversion
  coefficients, trigger settings, relevant rheology geometry and software/driver
  versions. Setpoints and measured waveform temperatures remain distinct.
- [ ] Track true trigger start/end when observed, first/last sample times,
  acquisition outcome/reason, sample count and timing/overflow diagnostics.
  A sample span is not necessarily the full cycle duration. Keep later quality
  assessment separate so it can change without rewriting acquisition settings.
- [ ] Load the active configuration when reopening its dialog. Persist reusable
  operator settings in an ignored local file and provide an explicit reset to
  defaults; current edits are transient and the dialog reloads startup defaults.
  Validate channel-array alignment, allowed types/ranges and finite/positive
  parameters. Do not reinterpret previously captured arrays after config edits.
- [ ] Fix range-aware conversion/calibration, or temporarily disallow unsupported
  ranges. The driver accepts ranges other than +/-10 V while conversion uses a
  fixed 10 V scale. Verify known ADC inputs for each supported range and sensor
  type. Current 10 V defaults do not establish bad historical calibration.
- [ ] Define continuous-mode records explicitly: retain legacy `cycle_id=0` as
  a session-scoped continuous capture with bounded sample batches and explicit
  acquisition mode. Do not display it as a manufactured cycle or lose it through
  a positive-cycle-number filter. Freeze its settings at capture start.
- [ ] Verify that edits affect only future captures; retries, exports and plots
  for an old capture still use its original identity, units and configuration.

## 4. PostgreSQL schema and ingestion contract

Implement the schema and versioned contract together before replacing writers.
Proposed minimum: two tables in one database, not one table per cycle/channel.

| Table | Required content and constraints |
| --- | --- |
| `cycles` | Primary key `(machine_id, session_id, cycle_id)`; `session_cycle`, acquisition mode, observed/trigger times, acquisition status/reason, separate quality/part outcome, sample count, typed frequently filtered material/mold/setpoint fields, versioned configuration snapshot |
| `cycle_samples` | Same cycle identity as a foreign key; primary key including `sample_index`; original integer `timestamp_ns`, relative time and measured numeric channels; optional raw ADC counts for new captures where retained |

- [ ] Use integer cycle/sample counters, explicit units, nullable unknown metadata
  and database constraints that match the capture contract. Add indexes for
  machine/time and the actual material/mold filters; sample retrieval must use
  the cycle key plus sample order.
- [ ] Preserve nanoseconds as `BIGINT`; do not rely on a lower-precision timestamp
  column to round-trip original data. An additional UTC timestamp can support
  display/filtering. Transport nanosecond integers as decimal strings through
  JavaScript/JSON consumers where Number would lose precision. Avoid float-based
  epoch arithmetic for new capture timestamps.
- [ ] Finalize channel storage before DDL: use typed numeric columns if the sensor
  schema is stable; use a validated numeric JSONB map if varying channel layouts
  are a real requirement. Keep searchable cycle attributes typed and use JSONB
  for evolving configuration. Record the choice and query examples here; do not
  silently assume the present seven channels are permanent.
- [ ] Define a versioned envelope carrying identity, frozen metadata, lifecycle,
  ordered samples, expected sample count and a content checksum. Preserve
  `_channel_field_names()`/`_saved_values()` as the shared source for channel
  keys and values. Do not mix arbitrary metadata into numeric sample fields.
- [ ] Bound message sizes. For long cycles/continuous capture, use deterministic
  chunks and a final manifest; define when a cycle is complete and visible to
  normal plots. A partial upload must remain visibly incomplete.
- [ ] Validate all identities, types, counts, indices and checksums on ingestion.
  Insert cycle metadata and samples transactionally, or finalize a chunked
  capture only once every expected chunk is durable. Duplicate delivery must be
  idempotent; conflicting content for the same immutable key must be an error,
  not a silent overwrite. Later quality updates need a separate update path.

## 5. MQTT / Node-RED / naming integration

Files: `mqtt_publisher.py`, `main.py` publication paths,
`iot/nodered_function.js`, `iot/nodered_flows.json`; add only necessary schema/
ingestion assets. Preserve intentional topic routing by machine.

- [ ] Update publishers, automatic cycle upload, manual resend and offline replay
  to send the new versioned envelope, with the original metadata every time.
  Explicitly handle existing unversioned pending batches so they are not dropped
  or assigned invented settings during upgrade.
- [ ] Replace Influx-specific conversion/writing with PostgreSQL validation and
  transactional insertion. The current converter treats every non-META key as a
  numeric sensor field; appending material strings to that payload is insufficient.
  Keep standalone JavaScript and the function embedded in the flow synchronized,
  or remove duplication deliberately when replacing the flow.
- [ ] Add an application acknowledgement only after database commit, including
  scoped identity, payload/chunk version and checksum. Retries after a lost ACK
  must recognize an already committed identical payload and ACK it again.
  Ensure publisher/retry state accepts only an ACK matching that stored payload.
- [ ] Standardize `cycle_num` -> `cycle_id` in active storage contracts, queries,
  exports, dashboard generator, comments and documentation as one coordinated
  change. Python/CSV/MQTT already expose `cycle_id`; avoid a blind text replacement
  of internal variables with different meanings.
- [ ] Map legacy Influx `cycle_num` to PostgreSQL integer `cycle_id` during import.
  Validate integrality/range instead of silently truncating floats. If an interim
  Influx writer remains, keep its existing compatible field until consumers are
  switched; never strand historical rows through a writer-only rename or create
  a per-cycle Influx tag merely because the field is called an ID.
- [ ] Exercise ingestion using isolated machine IDs/data. Verify duplicate sends,
  conflicting replay, out-of-order chunks, lost ACK, database downtime and invalid
  payloads. No synthetic publishing to a real production machine topic.

## 6. Historical migration and server cutover

- [ ] Obtain a complete raw export and recoverable backup from the current server,
  including exact timestamps, field values, tags and retention-policy scope.
  Verify the export/restore method. The existing diagnostic ZIP is insufficient.
- [ ] Provision PostgreSQL with persistent storage, appropriate application and
  Grafana access, backup/restore procedures and an explicit retention policy.
  Keep credentials out of source control and diagnostic reports.
- [ ] Import legacy samples in deterministic timestamp order within each scoped
  cycle, assigning stable sample indices. Preserve original values/timestamps and
  record source/provenance; handle unexpected duplicates explicitly.
- [ ] Create legacy cycle records with unknown settings/quality and a legacy
  acquisition status where completion cannot be established. Preserve observed
  sample bounds separately from unknown trigger bounds. Do not infer
  `session_cycle` from the minimum observed ID if earlier session data may be
  absent, or fill historical metadata from current operator settings.
- [ ] For the supplied unchanged snapshot, verify 45,447 samples, 318,129 sensor
  values, 29 cycles and three sessions; compare every cycle's counts, exact
  timestamps and values. Reconcile against a fresh source baseline if the live
  database has changed since this report.
- [ ] Define an ingestion pause/checkpoint or final-delta procedure so data arriving
  during migration is accounted for exactly once. Import history, verify it,
  switch ingestion and dashboards, then verify newly completed cycles end to end.
- [ ] Keep the original Influx history and working rollback configuration until
  validation is complete. A rollback after PostgreSQL receives new data must also
  preserve those new captures. Retire active Influx ingestion/use afterward;
  destruction of the backup is not part of this plan.

## 7. Grafana queries and dashboard generation

Files: `scripts/generate_grafana_dashboard.py`, `iot/grafana_dashboard.json`
and deployed Grafana data-source configuration.

- [ ] Use Grafana's PostgreSQL data source and parameterized/safely interpolated
  SQL for dashboard variables. Keep relative-time XY cycle overlays and channel
  labels/units. Regenerate the checked-in dashboard from the updated generator.
- [ ] Select the N most recent actual eligible cycles by recorded time and scoped
  identity, then join their samples. Replace `cycle_num > max_cycle_num - N` and
  grouping by the number alone. Define whether the dashboard time picker applies
  to cycle selection, and make that behavior explicit.
- [ ] Add useful machine/session/material/mold/quality filters using cycle metadata.
  Label curves with enough identity to distinguish sessions with reused numbers.
  Bound queries to selected cycles; keep continuous capture as an explicit view.
- [ ] Default normal overlays to complete stored cycles; make interrupted captures
  available with clear status instead of treating them as complete production.
- [ ] Retain the current 5-second refresh initially. Verify that both cycle
  selection and panels refresh after a newly stored cycle; repository settings
  alone do not prove deployed variable refresh behavior. Expected latency also
  includes upload and commit time; this remains post-cycle visualization.
- [ ] Verify metadata-filtered overlays, exact last-N selection with counter gaps,
  two sessions sharing numbers, unknown legacy metadata, aborted cycles and the
  raw-data export panel against PostgreSQL results.

## 8. Exports, documentation and handoff

- [ ] Extend local exports so a capture can be reconstructed: machine/session/cycle
  identity, `session_cycle`, sample index, exact timestamp and relative time.
  Include a companion cycle metadata file/settings snapshot rather than repeating
  the entire snapshot on every CSV row. Preserve sensor names and explicit units.
- [ ] Keep acquisition status, quality and raw/converted value provenance in export
  metadata. Manual export must read the captured snapshot, not current UI config.
- [ ] Update README and `CLAUDE.md` when implemented behavior changes: storage
  architecture, identity scope, rate units, capture/retry guarantees, configuration
  persistence, export format and operating commands. Remove stronger-than-proven
  no-loss claims. Update local ignored notes and refresh their source index only
  after reviewing the corresponding changes.
- [ ] Keep `docs/`, reports, raw exports, local settings and runtime spools ignored.
  Do not force-add them. Keep `scripts/` diagnostic/debug tools simple; do not
  recreate the removed diagnostic Markdown guide or formal diagnostic test file.
  Focus regression checks on changed acquisition, persistence and ingestion
  behavior rather than adding scaffolding for this planning document.
- [ ] Record implemented schema/envelope versions, final channel-storage choice,
  deployment steps, validation results and unresolved limits here as work lands.
  Distinguish local completion from hardware verification and server deployment.

## 9. Secondary review findings to reproduce and fix where relevant

These are lower-priority follow-ups or checks to fold into the stages above.
Inferred races/performance issues require reproduction before claiming a fix.

- [ ] Ensure first/last trigger-boundary sample inclusion is intentional and
  documented. The current branches omit boundary samples. Clarify whether the
  inter-cycle gap is an elapsed-time gate or a required continuous-low debounce.
- [ ] Make missing/invalid trigger reads explicit errors rather than silently
  allowing acquisition to start with uncertain state. Review fresh-edge behavior
  when Start occurs while the trigger is already active.
- [ ] Clear a discarded live curve, reset extrema influenced by discarded data,
  and publish the final plot/cursor frame when a cycle ends. Check trigger-arrow
  visibility and the continuous display point-limit off-by-one behavior.
- [ ] Reproduce mutable Qt plot-payload races and repeated signal connections over
  many Next/reconnect sessions; use stable display snapshots and one intended
  connection per worker lifecycle.
- [ ] Make no-device discovery cancellable. Current external-driver discovery can
  poll indefinitely beyond the app's finite shutdown waits. Preserve the existing
  Windows reconnect strategy of reusing a healthy open serial connection.
- [ ] Verify scan-alignment heuristics with representative analog/digital patterns;
  a digital-looking analog value is not by itself proof of an alignment marker.
- [ ] Correct stale comments and the documented `plot_csv_raw.py <file.csv>` usage
  when touching those paths; the current script uses a hardcoded input. Avoid a
  broad UI/module reorganization unrelated to the reliability and storage work.

## Completion target

The next implementation is complete when a cycle has reproducible configuration,
accounted-for samples, a recoverable local record, idempotent delivery into the
single PostgreSQL database, metadata-based retrieval in Grafana, and a validated
historical import. Hardware checks and deployment must be reported separately if
they cannot be performed in the implementation environment.
