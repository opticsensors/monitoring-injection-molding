# CLAUDE.md

Project context for Claude Code. Keep this current when structure, commands, or
key conventions change.

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
python scripts/plot_csv_raw.py <file.csv>  # offline plot of a saved session
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
config.py, config_window.py, sensor_types.py, app_logging.py, mqtt_publisher.py
                                    ← the GUI app; all import each other flatly,
                                      so they must stay together on sys.path
config/    daq_config_defaults.json ← hand-maintained channel layout (source of truth)
scripts/   standalone tools (import the app only via sys.path shims)
iot/       nodered_flows.json, nodered_function.js, grafana_dashboard.json
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

Two datasets with **different** schemas:

- **Local CSV** (`save_Session`): `Cycle, Time(s), CH<n>_<type>[<unit>], ...`
  Physical units in the header; `Cycle` is always present (0 = continuous).
  `Time(s)` is relative to the session/cycle start.
- **Cloud (MQTT)** (`_publish_records` → `nodered_function.js`):
  `timestamp_ns, time_s, machine_id, session_id, cycle_id, CH<n>_<type>, ...`
  No units in the channel keys. `cycle_id` is always present (0 for continuous).
  In InfluxDB, `machine_id` / `cycle_id` / `session_id` are **tags**; identity is
  effectively `(machine_id, timestamp)`. The Node-RED function discovers channel
  fields per-record, so any channel config works without editing it.

`cycle_id` is a monotonic per-machine counter persisted in `data/cycle_id.txt`
across restarts. Discarded (too-short) cycles reuse the number, so there are no
spurious gaps.

## Sensor registry

`sensor_types.py` is the single source of truth: each channel type maps to a
label, unit, and a `category` that decides conversion, colour, and which
plot/axis it lands on (`temp`→mould-left, `moldP`→mould-right,
`machine`→machine tab, `trigger`→drives cycles, not plotted).

## Gotchas / conventions

- **DI-4108 scan alignment**: the reader must start on a scan boundary. See
  `daq_serial.align_stream()` in the `daq_connectivity` repo; a misaligned
  stream makes the digital word appear in an analog slot.
- **Next / reconnect**: reuse the open serial connection (`DaqThread.rearmDaq`)
  — do NOT close+reopen the COM port back-to-back (Windows "Acceso denegado").
- **Plot rebuilds**: rebuilding plots on the *current* tab yields no resize
  event; force a scene-level relayout (`_relayout_canvas`), not a widget resize
  (which Windows coalesces away).
- **MQTT**: never test-publish to a real machine's production topic
  (e.g. `160t/sensors`). Use a throwaway `machine_id`.
- Windows console is cp1252 — set `PYTHONIOENCODING=utf-8` when printing
  `Δ`, `°`, etc. in test scripts.
