# CLAUDE.md

Project context for Claude Code. Keep this current when structure, commands, or
key conventions change.

## Local reference notes

When present, start with `docs/INDEX.md` for the detailed code map, behavior,
data contracts, troubleshooting, and source-review caveats. These notes are
local-only and Git-ignored; they are not available in a fresh clone. Run
`py -3.11 docs/reference_index.py --check` to check their source snapshot,
then read changed code and update the affected notes before refreshing it.

## What this is

A PyQt5 desktop app that monitors an **injection-moulding machine** through a
**DATAQ DI-4108** DAQ over serial. It acquires temperature (Futaba), mould
cavity pressure (Kistler) and machine signals (injection pressure, screw speed,
screw position), splits a cycle on a digital trigger (D4/D5), plots everything
live, saves sessions to CSV, and optionally streams to the cloud
(MQTT → Node-RED → InfluxDB → Grafana).

## Run

```bash
python main.py            # from the repo root (Windows: py -3.11 main.py)
```

The DAQ driver is a **separate editable package** at `../daq_connectivity`
(`pip install -e ../daq_connectivity`); edits there are live. App deps:
`pip install -r requirements.txt`.

`main.DaqDevice` subclasses that driver so discovery tries once per Connect.
The shared driver's `config_daq()` otherwise waits indefinitely for a missing
device. An absent device now ends the worker, logs the reason and re-enables
Connect; failed configuration also releases any partly opened serial port.
`py -3.11 tests/check_daq_connection.py` covers absence, retry and port failures.

### Hardware / diagnostic scripts (need the DAQ connected)

```bash
python scripts/test_hardware.py            # raw read of all channels incl. D4/D5
python scripts/daq_diagnose.py             # scan-structure diagnostics (~40 s)
python scripts/validate_acquisition.py     # normal GUI + per-session serial scan accounting
python scripts/plot_csv_raw.py  # choose the waveform CSV in the file dialog; no CLI argument parser
python scripts/generate_grafana_dashboard.py   # regen iot/grafana_dashboard.json from config
```

For the next supervised machine session, use [MACHINE_TEST.md](MACHINE_TEST.md).
The validation launcher observes acquisition reads in-process without editing
the external driver or changing sampling/trigger behavior. JSON reports under
data/diagnostics update every five seconds and on exit; normal Save is still
required. Counts include waiting between cycles and distinguish the first
buffered batch. Zero observed discards is not an end-to-end no-loss guarantee.
This app now enforces ±10 V per analog channel; the GUI range cells are read-only.
Non-10-V values in configuration files are normalized with a warning. Other apps
retain the shared driver's range support. Sampling UI/logs say divisor (srate);
the legacy sample_rate_hz key, numeric values and hardware commands are unchanged.

### GUI testing without a display (offscreen)

```bash
QT_QPA_PLATFORM=offscreen py -3.11 <script>.py
```
`MainWindow.__init__` does not touch the DAQ, so it is safe to instantiate
headless. Creating multiple `MainWindow`s in one process can segfault — run one
per process.

## Layout

```
main.py, MainWindow.py, graphswidget.py, plot_tools.py, plot_icons.py,
plot_view.py, cycle_review.py, history_controller.py, history_client.py,
config.py, config_window.py, sensor_types.py, rheology.py, app_logging.py,
mqtt_publisher.py, connection_settings.py, edit_controller.py,
desktop_controller.py, desktop_widgets.py
                                    ← the GUI app; all import each other flatly,
                                      so they must stay together on sys.path
config/    daq_config_defaults.json ← hand-maintained channel layout (source of truth)
scripts/   standalone tools (import the app only via sys.path shims)
iot/       deploy.sh, two generated JSON files, short SERVER_SETUP.md
           nodered/ (runtime), postgres/ (SQL), validation/, maintenance/
figures/   images / assets
data/      (gitignored) logs/, pending/ (MQTT spool), results/, cycle_id.txt
```

Because the app modules use **flat imports** (`import MainWindow`,
`from config import ...`), never move only some of them — keep them together.

### Paths are code-anchored — update them if you move files

- `config.py` → `config/daq_config_defaults.json`
- `main.py` `CYCLE_ID_FILE` → `data/cycle_id.txt`
- `app_logging.py` `LOG_DIR` → `data/logs/`
- `mqtt_publisher.py` `PENDING_DIR` → `data/pending/`; `connection_settings.py`
  resolves the shared `.env` (outside OneDrive for synced checkouts).
- `cycle_metadata.py` → `data/pending_edits.json` for edited metadata only.
- `scripts/generate_grafana_dashboard.py` anchors to repo root (`ROOT`) and adds
  it to `sys.path` to import `sensor_types`.

## Data schemas

The cycle-metadata implementation is in `cycle_metadata.py`,
`metadata_controller.py` and `metadata_widgets.py`. Deployment instructions and
message/storage behavior are in [iot/SERVER_SETUP.md](iot/SERVER_SETUP.md).
Repository implementation does not imply that the live server is updated.

Deployment entry points: `scripts/deploy.ps1` packages/uploads curated files and
runs `iot/deploy.sh`; the latter invokes the stdlib `scripts/deploy_server.py` on
the Docker host. Each upload extracts into a fresh directory under
`~/injection-monitoring-releases/`, delays restoring archive directory modes,
then fixes owner permissions there (Windows/OneDrive directories may be 0555).
The installer preserves unrelated flow tabs and the existing
MQTT broker config/credential ID, uses Node-RED's revision-checked v2 Admin API
and Grafana's datasource/dashboard APIs, backs up before modifying services,
and retains private state under `~/.local/state/injection-monitoring/`.
Before production mutations it runs the isolated Docker integration test, caching
success by the tested release's content hash. Failed tests leave production alone.
`--check` inspects without deployment. It never resets existing admin passwords,
upgrades production images, or deletes waveform history. User-provided output on
2026-10-19 confirms release.oqzIvlaQ completed all eight installer stages, including
isolated Docker integration, backups, PostgreSQL setup, 29 matching historical
cycles, Node-RED/Grafana deployment and production database/queue/count checks.
Daily backups at 02:00 server time and five-minute health logs are scheduled.
Latest backup: 20261019T142821Z-bc4f36. Browser checks, one real new cycle and backup
restore verification remain pending. The subsequent History/correction release requires
a new coordinated deployment through migration 005.
Earlier installer fixes are retained: connector lookup uses package.json;
Grafana PUT uses a freshly read datasource version; only test Grafana joins a
second project bridge to publish localhost:13000. The earlier local unit tests passed;
the corrected full container test passed on the user's server. Container logs
survive test teardown, and cleanup errors do not replace the original failure.
The user is not recording; avoid repeating the acquisition-pause reminder.
Readiness and subsequent Node-RED GET requests now retry transient connections
within a deadline; writes are not automatically repeated. Manual procedures are kept in
`iot/maintenance/MANUAL_SETUP.md` rather than the quick-start guide.

- **Manual Save:** waveform `.csv` with `session_id, cycle_id, session_cycle,
  timestamp_ns, time_s, excluded, CH<n>_<type>, ...`; companion `.cycles.csv` with one row
  per capture (machine ID, identity, effective settings, latest measurements, exclusion, mode/outcome,
  counts/bounds and revision). Join on `(session_id, cycle_id)`; the summary
  supplies machine ID. Nulls are blank, zeros are preserved. Full manifests and
  calibration/units remain in `.metadata.json`. There is no File/Import menu.
  All files are staged before replacement; re-Save refreshes edited measurements.
- **MQTT capture v1:** `schema_version=1`, `kind=capture`, `capture` (scoped
  identity, immutable settings, status/count/exact bounds), `measurements`
  (weight/length/revision), `samples` (decimal-string ns, index, relative time,
  physical channel values). Metadata is not repeated in each sample.
- **MQTT measurements v1:** `kind=measurements`, scoped identity and a complete
  weight/length pair plus increasing revision/update ID. Explicit null clears a
  value. Old retries must never overwrite newer measurements.
- **MQTT review v1:** `kind=review`, scoped identity, `review` with revision,
  update ID, client timestamp, excluded boolean and partial settings overrides.
  Explicit null clears a setting; missing keys inherit the original capture.
  Only the latest accepted correction is kept; rejected proposals are diagnostic records.
- **Influx:** existing `machine_id` and `session_id` tags, `cycle_num` float
  mapped to logical cycle_id, `t_ms`, channel floats; new captures add integer
  `sample_index`. Do not rename historical fields or add a per-cycle tag.
- **PostgreSQL:** `monitoring.cycles` stores catalog/metadata, not samples.
  The catalog supplies full identity predicates and exact nanosecond bounds;
  Grafana wraps the selected identities in one shared time range (InfluxQL 1.x
  cannot OR separate time ranges). Grafana now shows only Latest cycles (max 100),
  default 10, and numeric cycle legends. Selection combines 55t and 160t with one
  total count limit and no machine variable. It spans dates, excludes continuous captures and has no
  metadata filters/table. The collapsed raw Export row remains. The simplified
  2026-10-20 dashboard works on the server per the user;
  this does not remove stored metadata or
  continuous acquisition support from the desktop/backend.

`refresh_run_snapshot()` uses `_saved_indices()` and `_channel_field_names()`
to freeze channel order/units/configuration, then samples and exports use those
frozen indices. Do not interpret old data using the current GUI configuration.
Settings are copied at the actual trigger boundary in GraphThread; measurements
start unknown for every part. New sessions have a readable timestamp plus UUID.

Reusable settings are saved in `data/run_setup.json` on Start. Machine,
Material, Mold, Melt and Speed are locked while recording, and unlock after final
Stop data. Mold/Melt are manual setpoints; Speed is a manual mm/s setting, distinct
from measured CH6 flow in cm³/s. Applying DAQ configuration preserves unfinished
sidebar text. Part measurements autosave after 400 ms, Enter or focus loss.
Monitor selects the cycle at trigger start, deferring selection while a field has
focus. Active measurements use `data/active_part_measurements.json`; completion
moves them into the normal pending-edit journal. Discarded/restarted unfinished
parts retain separate recovery records and never inherit a reused cycle number.

History shows Weight/Spiral, effective corrected settings, delivery/storage state
and orange Incomplete. Edit Machine/Material/Mold/Melt/Speed/Weight/Spiral inline;
check/select multiple rows for Exclude / Restore / Send edits. Corrections never change `capture`; a tooltip shows the
recorded value. Show excluded reveals hidden rows. CSV exports retain all samples
with an excluded flag; cycle summaries use effective settings, while full metadata
keeps original captures. No physical deletion or waveform migration is introduced.

`edit_controller.py` persists pending review/measurement proposals to
`data/pending_edits.json` before reporting success. This is not a waveform archive.
Uploads off means pending; explicit Send edits or session Send can queue changes.
Enabled uploads retry through the existing MQTT mechanism. Pending metadata remains
until History readback confirms the same/newer revision and values. A competing
server edit remains a visible conflict for explicit resolution; only the local
changed fields are rebased over untouched server corrections.

History uses a read-only QThread client, 10 summaries per page and a 128 MB RAM
waveform cache. Load server also refreshes already-loaded identities in bounded
batches, including excluded records, before merging the newest page. This updates
old rows after changes on another PC. One load icon pages until exhausted, then
refreshes. Failed loads retain the cursor.
Waveforms load only on Plot. Comparison views preserve their independent tools,
recorded units/geometry and calculations; the shared toolbar follows the active tab.
The main window and offline preview share `desktop_widgets.py` and
`desktop_controller.py`: native Setup/Monitor/History/closable Plot tabs, embedded
configuration, narrow Monitor inspector and icon toolbars. The preview only
replaces device/network operations and isolates preferences/journals in a temporary
directory. Setup configuration is staged until Start (Connect uses staged scan
settings). Start waits for the DAQ's idle acknowledgement and rearms the same serial
handle with the updated scan description before checking the trigger.

`connection_settings.py` reads both MQTT and History from one commissioning file:
BROKER/PORT/user/password and HISTORY_URL/HISTORY_TOKEN. For OneDrive checkouts the
default is `%LOCALAPPDATA%\InjectionMonitoring\.env`; otherwise it is `.env` beside
the app. MONITORING_ENV_FILE overrides both. The existing local file was moved
outside this checkout without changing contents. No credential dialog/hard-coded
History IP remains. Broker status reflects the client connection; server status is
the latest History request. Database credentials stay on the server. Internal-only
`.env` configuration is the user's decision; no Credential Manager/TLS work here.

Migrations 004/005, the History runtime and Grafana selector require deployment through
the existing installer. Local implementation/test success is not live-server proof.
No automatic capture journal or new database-ACK protocol is added. Sampling and
the external DAQ driver remain unchanged.

Server recovery lives in `iot/nodered/capture_queue.cjs`, loaded through Node-RED's
`functionGlobalContext.captureQueue`. Originals are persisted before processing,
with leases, bounded retry and quarantine/review. Native Influx writes are
sequential chunks (5,000 points / 4 MB), retaining the whole-capture hash.
The MQTT-to-disk acknowledgement gap remains; do not claim lossless delivery.
Legacy arrays are now quarantined, so drain old PC spools before cutover.
Apply `001_cycle_metadata.sql` on fresh schemas and `002_ingestion_recovery.sql`
plus missing `003_history_reader.sql`, `004_cycle_review.sql` and
`005_machine_correction.sql`; use
`scripts/apply_server_migrations.sh`. The runner skips older view definitions on
newer schemas and safely reapplies the current migration. The isolated deployment
test exercises this runner twice against its own container.
Migration 002 records measurement conflicts without rejecting a valid capture,
preserves client edit timestamps as provenance and uses a non-login object owner.
Backfill must reconcile a fresh diagnostic against `server.metadata.json`.
The desktop freezes the session mode for Send and pairs wall/elapsed clocks
after plot setup. History readback preserves divergent local edit proposals.

### Two cycle numbers, one counter

`cycle_id` is a monotonic installation-wide counter persisted in `data/cycle_id.txt`
across restarts — the database key, never reset. Discarded (too-short) cycles
reuse the number, so there are no spurious gaps.

`session_cycle` is the human-readable one: 1, 2, 3… within the current session,
for annotating sample bags and for seeing at a glance how many cycles a session
produced. It is **derived, not counted** — `_session_cycle()` returns
`cycle_id - session_cycle_base`, where `session_cycle_base` is the thread's
`cycle_base` captured when the session starts. There is no second counter to
drift, and discards reuse both numbers for free.

A **session** starts on Start; each Start creates its own `session_id` and resets
`session_cycle`. Stop ends acquisition but retains its buffers for Save/Send.
The final worker-data signal unlocks configuration and enables Start/Save/Send.
Save exports the retained session and may run more than once. **Next** only opens
Monitor and focuses the session inputs; it neither clears buffers nor starts
acquisition. The next Start retires the previous session buffers.

The toolbar readout and the message log both show the pair as
`Cycle: 3  (#1487)` / `Cycle 3 (#1487) started` via `_cycle_label()`.

## Sensor registry

`sensor_types.py` is the single source of truth: each channel type maps to a
label, unit, and a `category` that decides conversion, colour, and which
plot/axis it lands on (`temp`→mould-left, `moldP`→mould-right,
`machine`→machine tab, `trigger`→drives cycles; never plotted, saved or
uploaded).

### The trigger is one digital input, always

There is a single trigger type, `trigger`, and it is only ever a **digital**
input (D0..D6; `digital_bit()` gives Dn = bit 8+n, so D4 = bit 12). It is not
selectable on an analog channel, and there is no `trigger_wiring` setting —
`read_trigger_high()` reads one bit of the digital scan word, full stop.

This mirrors the panel. Every source — manual switch, inductive sensor, machine
signal — is wired **in parallel onto the main relay coil** (Schneider RXG, 24 VDC:
A1 fed from all three, A2 to 0 V). That relay also switches the 24 V that takes
the Kistler charge amps out of reset, and the DAQ reads its dry contact on a
spare pole (COM 21 / NC 22 → D-pin / GND). So *amp in operate ⟺ D-pin HIGH ⟺
cycle running*, on one contact, with no skew between the amp's integration window
and the cycle boundary.

`trigger_mode` (`None` | `Inductive` | `Machine signal` | `Machine mold position` |
`Manual`, `TRIGGER_MODES`) records **which source is driving the relay** — every
non-`None` mode reads the same input. `trigger_input()` finds it; moving the wire
to another D pin is one dropdown, no code change.

Two electrical constraints keep it this way: the digital inputs are idle-HIGH
with internal pull-ups and only register a pull *down* to GND (hence a dry
contact), and the machine's sourcing 0/10 V output both fails to drive them and
overdrives a 5 V pin — so it gets an opto/SSR onto the relay coil rather than a
wire to the DAQ.

#### Polarity: one mode is active-LOW

`Machine mold position` (`INVERTED_TRIGGER_MODES`) is the machine's 0-10 V
mould-position output taken as a two-state signal: it sits at one rail while the
mould is shut and at the other while it is open, and the SSR's ~4 V threshold is
far from both, so the DAQ sees a clean digital edge. But it is the **inverse** of
every other source — the SSR pulls in during the mould's *open* phase — so the
input reads HIGH between cycles and LOW while the part is being made.

`read_trigger_high()` XORs `trigger_is_inverted(trigger_mode)` into the bit and
returns the **active sense**, not the raw pin. That is the only place polarity is
known: cycle start/end, the arrows, the min-cycle discard and the pre-start check
all keep reading `True` as "cycle running" whichever source is selected. If cycles
come out inverted on the bench, the fix is switching between the two `Machine …`
entries, not touching code.

Accepted hardware limitation with this mode: the relay coil also gates the Kistler
charge-amp reset, so driving it from mould-open leaves the amps in **reset during
injection** — the cavity-pressure trace is destroyed at the source and no software
can recover it. The proper fix is to invert *ahead of* the coil (an interposing
relay whose NC contact feeds A1), which would also make this mode a pure label.
The software inversion landed first, deliberately, to try the signal on the
machine. Hardware repair is deferred by the user. Keep this limitation documented;
use the other known-working trigger methods for pressure recording. It is not a
blocker for supervised tests using those methods, and no wiring change is planned
in the current software work.

`normalize_trigger_type()` maps the old `Inductive` / `Machine_signal` / `I`
values in a stored `digital_map` onto `trigger`, and `normalize_trigger_mode()`
maps a stored `trigger_mode` of `Machine` onto `Machine signal`
(`LEGACY_TRIGGER_MODES`), so old configs still load.

## Cursor readout: Δt, ΔP and the viscosity

The toolbar readout box shows `Cycle | Δt | ΔP | η`. Δt is the gap between the
two time cursors and ΔP the spread between the plotted cavity-pressure curves at
the later cursor (`_pressure_drop_at`). η is derived from exactly those two
numbers by `rheology.apparent_viscosity()`, so it is recomputed inside
`_update_cursor_readout()` — the one place Δt and ΔP are produced — and cannot go
stale against them. All four quantities (Q, τ, γ̇a, η) are returned; the label
shows η and `_viscosity_tooltip()` puts the rest, plus the geometry used, in its
tooltip.

The cursors are a **Mold-sensors tab** tool: `_cursor_subplots()` returns
`splotlist` only, so no line is ever drawn on the Machine tab, and
`_on_cursor_click` ignores clicks made while that tab is on top (they would
otherwise drag lines the operator cannot see). Both ends of the measurement —
Δt against the Futaba/Kistler traces, ΔP between the cavity pressures — live on
that tab, and nothing on the Machine tab is measured.

### The Cursors tool owns the lines

`_set_cursor_lines_shown()` is the single switch: the lines are drawn, draggable
and measured **only** while the Cursors tool is checked, and all three readings
fall back to `--` otherwise. Hiding keeps the `InfiniteLine` objects in
`cursor_lines`, so re-checking the tool restores them at the same positions —
only a middle-click (`_clear_cursor_lines`) deletes them. It is called at the end
of `_on_tool_toggled` for *every* tool, because switching to Zoom/Pan unchecks
Cursors with its signals blocked, so no `toggled` ever fires for it.

Going live unchecks the tool, which would otherwise make a capture lose the
operator's cursors. `_set_plot_live` therefore records `_cursor_tool_was_on` on
the way in and re-checks the button on the way out, so a cycle only *interrupts*
the measurement: the lines come back where they were and ΔP/η recompute against
the curve that just replaced the old one.

`rheology.py` is pure (no Qt/DAQ). Its geometry comes from `viscosity` in
`config/daq_config_defaults.json` — `L_mm` (the cavity-pressure sensor
separation, which is both the melt-front travel Δx and the shear-stress length)
and `Rc_mm` (runner radius). The cross-section `A = π Rc²` is **derived**
(`cross_section_mm2()`), never stored, so it cannot disagree with the radius.
The constants are JSON-only — not exposed in the config window, since they only
change when the mould does.

## Gotchas / conventions

- **DI-4108 scan alignment**: the reader must start on a scan boundary. See
  `daq_serial.align_stream()` in the `daq_connectivity` repo; a misaligned
  stream makes the digital word appear in an analog slot.
- **Start / reconnect**: reuse the open serial connection (`DaqThread.rearmDaq`)
  — do NOT close+reopen the COM port back-to-back (Windows "Acceso denegado").
- **Plot rebuilds**: rebuilding plots on the *current* tab yields no resize
  event; force a scene-level relayout (`_relayout_canvas`), not a widget resize
  (which Windows coalesces away).
- **MQTT topics are derived, never configured**: `data_topic()` /
  `status_topic()` in `mqtt_publisher.py` build `<machine_id>/sensors` and
  `<machine_id>/status` from the `machine_id` in the config window. the shared `.env` holds
  `BROKER` / `PORT` / `user` / `password` plus History URL/token — there is no `TOPIC` key, so the
  topic and the `machine_id` tag on the records cannot disagree. The `sensors`
  suffix is part of the contract with Node-RED's `+/sensors` subscription: a new
  machine needs no server-side change, but renaming the suffix breaks ingestion.
  Never test-publish to a real machine's production topic (e.g. `160t/sensors`)
  — a throwaway `machine_id` now diverts the data topic too, not just the tag.
- Windows console is cp1252 — set `PYTHONIOENCODING=utf-8` when printing
  `Δ`, `°`, etc. in test scripts.
