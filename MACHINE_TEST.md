# Supervised machine test

Use this checklist for the next injection-machine session. The purpose is to
validate the real workflow and retain evidence; it is not a declaration of
lossless acquisition. No server deployment or shared-driver change is needed
to run the desktop acquisition diagnostic.

## Before recording

- Use a trigger method already known to work on this rig. The documented
  **Machine mold position** wiring can hold the Kistler amplifiers in reset
  during injection. This is an accepted limitation, with hardware repair
  deferred. Use another working trigger for pressure recordings.
- Keep all analog inputs at **±10 V**. This app enforces that range; conversion
  assumes it. The shared DAQ library still supports other ranges for other apps.
- Retain the validated sampling settings. **Sampling divisor (srate)** is the
  existing command value, not Hz; this change does not convert or alter it.
- Check free space on the recording PC and server. Choose where to save the
  session files and an independent copy. Server backup restore testing and
  automatic alerts can follow this supervised trial; they are still needed
  before relying on the server as the sole store for valuable recordings.
- Run only one program that opens the DAQ. Close other hardware diagnostics.

## Record with scan accounting

From PowerShell in the repository:

```powershell
py -3.11 scripts/validate_acquisition.py
```

This launches the normal GUI. Connect the DAQ and use Start, Stop, Save and Next
as usual. Existing MQTT settings still determine automatic upload; manual Send
is available as usual. The diagnostic does not send additional messages or
change the acquisition settings, trigger logic or shared driver files.

The terminal prints a unique JSON report path under `data/diagnostics/`. A complete
snapshot is replaced every five seconds while the GUI event loop is responsive,
and again on normal exit. An optional `--output PATH.json` chooses a new report
file; an existing file is refused. Reports contain counters and settings, not
waveforms. A crash can leave only the last periodic snapshot.

1. Record a few actual injections with the normal plots visible. Check that
   cycle boundaries follow the chosen trigger and that pressure/temperature
   traces are plausible. Use known references where available for calibration.
2. Stop and Save before Next or closing. Keep the waveform `.csv`, `.cycles.csv`
   and `.metadata.json` together. Save again after editing part measurements.
3. Exercise Next and a second recording. Check that device reuse, numbering and
   exports work. A deliberate Stop during a test cycle should retain its data
   with an interrupted outcome. Observe a longer cycle if practical.
4. Close normally and retain the JSON diagnostic report alongside the exports.
   Copy the evidence to another location.

## Read the diagnostic

The report separates sessions and observes only calls made by the acquisition
worker. Setup/drain and pre-start trigger-check reads are excluded. It counts
all acquisition reads, including time waiting between cycles; therefore its
totals should **not** be compared directly with triggered CSV row counts.

| Field | Meaning |
| --- | --- |
| `complete_scans_read` | Complete scans represented by bytes consumed from serial during acquisition reads. |
| `scans_returned` | Correctly sized single scans returned by the existing driver. |
| `scans_not_returned` | Consumed complete scans that were not returned to the app. |
| `max_scans_per_read` | Largest observed batch; the current binary-1 reader retains only the newest scan. |
| `first_nonempty_read_scans` | Initial batch, which may include scans buffered before Start. |
| `scans_not_returned_after_first_nonempty_read` | Discards after that initial batch; still includes waiting between cycles. |
| `scans_returned_per_second` | Observed returned scans divided by the acquisition-read window. |
| `mean_return_gap_seconds`, `max_return_gap_seconds` | Host-time gaps between nonempty returns, not hardware sample intervals. |

`LOSS_OBSERVED` means software consumed complete scans it did not return.
`REVIEW_REQUIRED` flags errors, partial reads, unexpected return shapes or an
unsupported reader method. `NO_DATA` means there is no usable measurement.
`NO_LOSS_OBSERVED` applies only to the observed serial-read boundary in that
session. It does not establish absence of upstream DAQ/USB loss, correct channel
alignment/calibration, complete graph-queue processing or successful storage.
The observer adds some overhead, and startup buffering can inflate read rates.

Do not switch to binary method 2 as a quick fix: its flat batch return is not
compatible with the app's single-scan contract. Review the report before planning
an all-scan driver/app change. `daq_diagnose.py` is a different raw-stream and
alignment diagnostic; `debug_trigger.py` only sees scans returned by the driver.

## Verify upload and charts

For the saved sessions, confirm that the same `(machine_id, session_id, cycle_id)`
exists in PostgreSQL and InfluxDB. For each cycle, compare the waveform CSV row
count, the `.cycles.csv` sample count, server sample count and first/last timestamps.
Compare channel values and confirm the database marks the waveform stored.

Check that Grafana selects the newly recorded cycles and updates both its
selection and waveform panels. If a dashboard reload is needed, record that
separately. A green broker check or “Queued (unconfirmed)” is not database receipt.
Local/server agreement does not prove absence of earlier acquisition loss.

Desktop **History → Load server** additionally requires the documented
[history deployment](iot/SERVER_SETUP.md#desktop-history). That pending update
does not block testing acquisition, local export, upload and the existing Grafana
dashboard. Treat desktop history as a separate acceptance item.

Retain the diagnostic report, exports and a brief note of trigger mode, observed
injections, missing/extra cycles, restarts and chart behavior. Backup restoration,
off-server server backups and monitored health/disk alerts remain follow-up work.
