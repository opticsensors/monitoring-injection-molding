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

### Hardware / diagnostic scripts (need the DAQ connected)

```bash
python scripts/test_hardware.py            # raw read of all channels incl. D4/D5
python scripts/daq_diagnose.py             # scan-structure diagnostics (~40 s)
python scripts/plot_csv_raw.py  # choose the waveform CSV in the file dialog; no CLI argument parser
python scripts/generate_grafana_dashboard.py   # regen iot/grafana_dashboard.json from config
```

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
mqtt_publisher.py
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
- `mqtt_publisher.py` `PENDING_DIR` → `data/pending/`, `ENV_FILE` → `.env` (root)
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
restore verification remain pending; no further deployment rerun is required.
Earlier installer fixes are retained: connector lookup uses package.json;
Grafana PUT uses a freshly read datasource version; only test Grafana joins a
second project bridge to publish localhost:13000. All 54 local unit tests pass;
the corrected full container test passed on the user's server. Container logs
survive test teardown, and cleanup errors do not replace the original failure.
The user is not recording; avoid repeating the acquisition-pause reminder.
Readiness and subsequent Node-RED GET requests now retry transient connections
within a deadline; writes are not automatically repeated. Manual procedures are kept in
`iot/maintenance/MANUAL_SETUP.md` rather than the quick-start guide.

- **Manual Save:** waveform `.csv` with `session_id, cycle_id, session_cycle,
  timestamp_ns, time_s, CH<n>_<type>, ...`; companion `.cycles.csv` with one row
  per capture (machine ID, identity, settings, latest measurements, mode/outcome,
  counts/bounds and revision). Join on `(session_id, cycle_id)`; the summary
  supplies machine ID. Nulls are blank, zeros are preserved. Full manifests and
  calibration/units remain in `.metadata.json`, which history Load still uses.
  All files are staged before replacement; re-Save refreshes edited measurements.
- **MQTT capture v1:** `schema_version=1`, `kind=capture`, `capture` (scoped
  identity, immutable settings, status/count/exact bounds), `measurements`
  (weight/length/revision), `samples` (decimal-string ns, index, relative time,
  physical channel values). Metadata is not repeated in each sample.
- **MQTT measurements v1:** `kind=measurements`, scoped identity and a complete
  weight/length pair plus increasing revision/update ID. Explicit null clears a
  value. Old retries must never overwrite newer measurements.
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

Reusable Run setup preferences are saved in `data/run_setup.json`; sidebar visibility
and history URL use QSettings. Machine/Material/Mold/Speed inputs share one right
scrollable sidebar with per-part Weight/Spiral editing and one Apply. The sidebar
icon toggles it; Live follows the latest completed part unless an edit is unfinished.
Apply validates all inputs before saving; unchanged part values do not gain a revision.
`Speed (mm/s)` is a manual injection
setting, unrelated to measured CH6 flow (cm³/s); old pressure values are preserved.
History is an embedded tab; Refresh loads server history, check rows and Plot to create independent
Mold/Machine comparison tabs. Live and review share `PlotViewMixin` construction/tools,
with per-view interaction state and one stationary top toolbar routed to the active
plot. Hidden Live updates cannot overwrite comparison controls/readouts. Comparison
dropdowns select one recorded waveform/geometry for calculations; the eye hides other
cycles. The sidebar uses 72 px fields with full values in tooltips. Raw converted values use recorded fields/units,
never current calibration. A 128 MB RAM waveform cache survives Next, not restart.
History loads all metadata via paged read-only HTTP on a QThread, waveforms on demand.
The server key stays in memory (or MONITORING_HISTORY_TOKEN); reader DB credentials
remain on the server. Migration 003 and the new Node-RED runtime/routes need deployment.
The normal Save remains; metadata import/export moved to File. Existing failed-MQTT spooling
and broker-ACK cleanup remain unchanged. There is no automatic capture journal
and no client database-ACK protocol. Sampling settings/commands and the external
DAQ driver are unchanged by the metadata feature.

Server recovery lives in `iot/nodered/capture_queue.cjs`, loaded through Node-RED's
`functionGlobalContext.captureQueue`. Originals are persisted before processing,
with leases, bounded retry and quarantine/review. Native Influx writes are
sequential chunks (5,000 points / 4 MB), retaining the whole-capture hash.
The MQTT-to-disk acknowledgement gap remains; do not claim lossless delivery.
Legacy arrays are now quarantined, so drain old PC spools before cutover.
Apply `001_cycle_metadata.sql` on fresh schemas and `002_ingestion_recovery.sql`
plus `003_history_reader.sql` on fresh/existing schemas; use `scripts/apply_server_migrations.sh`.
Migration 002 records measurement conflicts without rejecting a valid capture,
preserves client edit timestamps as provenance and uses a non-login object owner.
Backfill must reconcile a fresh diagnostic against `server.metadata.json`.
The desktop freezes the session mode for Send and pairs wall/elapsed clocks
after plot setup. Server metadata imports prompt before replacing divergent edits.

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

A **session** runs from Start (or Next) until the next Start/Next — exactly the
span of one `session_id`, which both paths mint. `session_cycle` resets there
and nowhere else:

- **Stop** ends acquisition but *not* the session: its data is still in memory
  and Save/Send act on it (the final worker-data signal enables Save/Send), so the readout keeps
  showing the final count.
- **Save** is a read-only export and never a boundary — it is optional (a
  cloud-only session is never saved) and may run more than once.
- **Next** is only reachable after Stop and calls `reset_Data_n_Plot_Vars()`,
  which is what actually retires a session.

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

⚠️ Open hardware issue with this mode: the relay coil also gates the Kistler
charge-amp reset, so driving it from mould-open leaves the amps in **reset during
injection** — the cavity-pressure trace is destroyed at the source and no software
can recover it. The proper fix is to invert *ahead of* the coil (an interposing
relay whose NC contact feeds A1), which would also make this mode a pure label.
The software inversion landed first, deliberately, to try the signal on the
machine.

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
- **Next / reconnect**: reuse the open serial connection (`DaqThread.rearmDaq`)
  — do NOT close+reopen the COM port back-to-back (Windows "Acceso denegado").
- **Plot rebuilds**: rebuilding plots on the *current* tab yields no resize
  event; force a scene-level relayout (`_relayout_canvas`), not a widget resize
  (which Windows coalesces away).
- **MQTT topics are derived, never configured**: `data_topic()` /
  `status_topic()` in `mqtt_publisher.py` build `<machine_id>/sensors` and
  `<machine_id>/status` from the `machine_id` in the config window. `.env` holds
  only `BROKER` / `PORT` / `user` / `password` — there is no `TOPIC` key, so the
  topic and the `machine_id` tag on the records cannot disagree. The `sensors`
  suffix is part of the contract with Node-RED's `+/sensors` subscription: a new
  machine needs no server-side change, but renaming the suffix breaks ingestion.
  Never test-publish to a real machine's production topic (e.g. `160t/sensors`)
  — a throwaway `machine_id` now diverts the data topic too, not just the tag.
- Windows console is cp1252 — set `PYTHONIOENCODING=utf-8` when printing
  `Δ`, `°`, etc. in test scripts.
