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

Two datasets that **share identical column/field names** (no units in any key —
units live only in the sensor registry). Both come from
`_channel_field_names()`, the single source for channel keys:

- **Local CSV** (`save_Session`): `cycle_id, time_s, CH<n>_<type>, ...`
  `cycle_id` is always present (0 = continuous); `time_s` is relative to the
  session/cycle start.
- **Cloud (MQTT)** (`_publish_records` → `nodered_function.js`): the same
  `cycle_id, time_s, CH<n>_<type>, ...` plus cloud-only metadata
  `timestamp_ns, machine_id, session_id`. In InfluxDB, `machine_id` / `cycle_id`
  / `session_id` are **tags**; identity is effectively `(machine_id, timestamp)`.
  The Node-RED function discovers channel fields per-record, so any channel
  config works without editing it.

The CSV header and MQTT payload are byte-for-byte identical for the shared
columns; keep `_channel_field_names()` the one place that names channels.

`_saved_indices()` decides which channels are written; `_channel_field_names()`
and `_saved_values()` are both built from it, so the header and every row stay the
same length. If you add a code path that writes channel values, filter it through
`_saved_values()`. (It drops `trigger`-category channels — a no-op now that the
trigger is digital-only, but it keeps a hand-edited config from corrupting the
CSV.)

`cycle_id` is a monotonic per-machine counter persisted in `data/cycle_id.txt`
across restarts. Discarded (too-short) cycles reuse the number, so there are no
spurious gaps.

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

`trigger_mode` (`None` | `Inductive` | `Machine` | `Manual`, `TRIGGER_MODES`) only
records **which source is driving the relay** — every non-`None` mode reads the
same input. `trigger_input()` finds it; moving the wire to another D pin is one
dropdown, no code change.

Two electrical constraints keep it this way: the digital inputs are idle-HIGH
with internal pull-ups and only register a pull *down* to GND (hence a dry
contact), and the machine's sourcing 0/10 V output both fails to drive them and
overdrives a 5 V pin — so it gets an opto/SSR onto the relay coil rather than a
wire to the DAQ.

`normalize_trigger_type()` maps the old `Inductive` / `Machine_signal` / `I`
values in a stored `digital_map` onto `trigger`, so old configs still load.

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
