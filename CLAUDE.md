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
config.py, config_window.py, sensor_types.py, rheology.py, app_logging.py,
mqtt_publisher.py
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

- **Local CSV** (`save_Session`):
  `session_id, cycle_id, session_cycle, time_s, CH<n>_<type>, ...` — identity,
  then time, then data. `cycle_id` is always present (0 = continuous);
  `session_cycle` is its session-relative twin (also 0 in continuous mode);
  `time_s` is relative to the session/cycle start.
- **Cloud (MQTT)** (`_publish_records` → `nodered_function.js`): the same
  `cycle_id, time_s, CH<n>_<type>, ...` plus cloud-only metadata
  `timestamp_ns, machine_id, session_id`. In InfluxDB, `machine_id` and
  `session_id` are **tags**; `cycle_id` is carried as the numeric **field**
  `cycle_num` — deliberately not a tag, since one series per cycle would blow
  up cardinality. Identity is effectively `(machine_id, session_id, timestamp)`.
  The Node-RED function discovers channel fields per-record, so any channel
  config works without editing it.

`time_s` and the channel columns are byte-for-byte identical between the CSV
header and the MQTT payload; keep `_channel_field_names()` the one place that
names channels. The two schemas differ only in the identity columns:
`session_cycle` is **CSV-only** (the cloud derives it from `session_id` +
`cycle_num` when it needs it, so it costs no Node-RED or dashboard change), and
`timestamp_ns` / `machine_id` stay cloud-only.

`_saved_indices()` decides which channels are written; `_channel_field_names()`
and `_saved_values()` are both built from it, so the header and every row stay the
same length. If you add a code path that writes channel values, filter it through
`_saved_values()`. (It drops `trigger`-category channels — a no-op now that the
trigger is digital-only, but it keeps a hand-edited config from corrupting the
CSV.)

### Two cycle numbers, one counter

`cycle_id` is a monotonic per-machine counter persisted in `data/cycle_id.txt`
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
  and Save/Send act on it (`stopReading` enables both), so the readout keeps
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
- **MQTT**: never test-publish to a real machine's production topic
  (e.g. `160t/sensors`). Use a throwaway `machine_id`.
- Windows console is cp1252 — set `PYTHONIOENCODING=utf-8` when printing
  `Δ`, `°`, etc. in test scripts.
