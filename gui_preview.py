"""Opt-in desktop layout previews using the application's real widgets and plots.

Only scripts/preview_layouts.py imports this module. Device operations and server
access are replaced by an in-memory simulator; production acquisition is untouched.
"""
from copy import deepcopy
from datetime import datetime
import json

import numpy as np
from PyQt5 import QtCore, QtWidgets

import cycle_metadata as metadata
from main import MainWindow



class PreviewWindow(MainWindow):
    """Exercise the real UI with synthetic scans; never open a device or socket."""

    preview_mode = True

    def __init__(self):
        self.demo_server = {}
        self.demo_waveforms = {}
        self._counter = 120
        self._demo_step = None
        self._wait_ticks = 0
        self._demo_x = np.linspace(0, 8, 401)
        super().__init__()
        self._edit_timer.stop()
        self.mqtt_enabled = False
        self.daq_connected = True
        self.trigger_mode = "Inductive"
        self.cycle_mode = True
        self.run_settings = metadata.operator_settings("55t", "PP · trial grade", 60,
            injection_speed_mm_s=35, melt_temperature_c=220)
        self.runSetup.set_values(self.run_settings)
        self.refresh_run_snapshot()
        self._demo_timer = QtCore.QTimer(self)
        self._demo_timer.setInterval(60)
        self._demo_timer.timeout.connect(self.advance_demo)
        self._start_demo_session()
        self.session_start_ns -= 60_000_000_000
        for _ in range(5):
            self._begin_demo_cycle()
            self._demo_step = len(self._demo_x)
            self._finish_demo_cycle()
        for index, (key, entry) in enumerate(self.cycle_history.items()):
            if index != 2:
                entry["measurements"] = metadata.edit_measurements(entry["measurements"], 12.8 + index * .03, 181 + index * 2)
            if index < 3:
                entry["waveform_status"] = "stored"
            self.demo_server[key] = deepcopy(entry)
            self.demo_waveforms[key] = self._waveforms[key]
        self._seed_older_history()
        self.is_monitoring = False
        self.runSetup.set_locked(False)
        self._set_plot_live(False)
        self.install_desktop_layout()
        self.messagesBox.clear()
        self.demo_message("5 cycles loaded.")
        self._update_demo_controls()

    def _seed_older_history(self):
        """Older records exist only on the demo server until History loads them."""
        for index in range(20):
            snapshot = deepcopy(self._run_snapshot)
            machine = "55t" if index % 2 == 0 else "160t"
            snapshot["machine_id"] = machine
            snapshot["config_snapshot"]["machine_id"] = machine
            snapshot["material"] = "PP · earlier trial"
            snapshot["mold_temperature_c"] = 50
            rows = self._signals().tolist()
            entry, _ = metadata.finish_capture(snapshot, "demo_history_" + machine, index // 2 + 1,
                101 + index, self.session_start_ns - 3_600_000_000_000,
                index * 60.0, index * 60.0 + 8, self._demo_x.tolist(), rows)
            entry["waveform_status"] = "stored"
            key = metadata.identity(entry["capture"])
            self.demo_server[key] = entry
            fields = entry["capture"]["config_snapshot"]["field_names"]
            indices = entry["capture"]["config_snapshot"]["saved_indices"]
            self.demo_waveforms[key] = dict(time_s=self._demo_x.copy(), fields=fields,
                values={field: [row[i] for row in rows] for field, i in zip(fields, indices)})

    def demo_message(self, text):
        self.messagesBox.appendPlainText(f"[{datetime.now():%H:%M:%S}] {text}")

    def _start_demo_session(self):
        self.reset_Data_n_Plot_Vars()
        self.begin_metadata_session()
        self.session_id = "demo_" + self.session_id
        self.session_cycle_base = self._counter
        self.SubplotSetup()
        self._set_all_x_range(0, 8.4, padding=0)
        self._default_x_range = (0, 8.4, 0)
        self._demo_step = None
        self._session_offset = 0.0

    def _signals(self):
        x = self._demo_x
        variation = self._counter % 6
        pulse = np.exp(-((x - (1.5 + variation * .025)) / .7) ** 2)
        signals = {"T_futaba": 30 + (135 + variation * 3) * pulse,
                   "P_kistler": (450 + variation * 12) * np.exp(-((x - 2.2) / 1.3) ** 2),
                   "P_machine": (650 + variation * 15) * np.exp(-((x - 1.9) / 1.5) ** 2),
                   "vel_screw": (35 + variation) * np.exp(-((x - 1.5) / .8) ** 2),
                   "pos_screw": 80 - 55 / (1 + np.exp(-(x - 2) * 2))}
        return np.array([signals.get(kind, np.zeros_like(x)) * (1 - .035 * (i % 2))
                         for i, kind in enumerate(self.channel_types)]).T

    def _begin_demo_cycle(self):
        if self.cycle_mode:
            self._counter += 1
        self.current_cycle = self._counter if self.cycle_mode else 0
        self._demo_y = self._signals()
        self._demo_step = 0
        self.capture_started(self.current_cycle, deepcopy(self._run_snapshot), self._session_offset)
        self._set_cycle_readout(self.current_cycle)
        self._set_plot_live(True)
        self.updateYAxisRanges((self._demo_y.min(axis=0) - 5).tolist(), (self._demo_y.max(axis=0) * 1.12).tolist())
        self.demo_message(f"Cycle {self.current_cycle} started.")

    def _finish_demo_cycle(self, interrupted=False):
        count = self._demo_step
        if count and count > 1:
            x, rows = self._demo_x[:count].tolist(), self._demo_y[:count].tolist()
            self.ploter(x, list(map(list, zip(*rows))))
            self.createGhostPlots(x, list(map(list, zip(*rows))), self.current_cycle)
            self.capture_finished(self.current_cycle, x, rows, self._session_offset,
                dict(end_s=self._session_offset + x[-1], status="interrupted" if interrupted else "complete",
                     reason="user_stop" if interrupted else "trigger"))
            self.xdata.extend(x)
            self.ydata.extend(rows)
            self.cycle_numbers_data.extend([self.current_cycle] * count)
            self.completed_cycles_data.append((self.current_cycle, self._session_offset, x, list(map(list, zip(*rows)))))
            self._session_offset += 10.0
            self.demo_message(f"Cycle {self.current_cycle} {'interrupted' if interrupted else 'completed'} · {x[-1]:.2f} s.")
        self._demo_step = None
        self._wait_ticks = 0
        self._set_plot_live(False)

    def advance_demo(self):
        if not self.is_monitoring:
            return
        if self._demo_step is None:
            self._wait_ticks += 1
            if self._wait_ticks >= 24:
                self._begin_demo_cycle()
            return
        self._demo_step = min(len(self._demo_x), self._demo_step + 6)
        self.ploter(self._demo_x[:self._demo_step].tolist(), self._demo_y[:self._demo_step].T.tolist())
        if self._demo_step == len(self._demo_x):
            self._finish_demo_cycle()
            if not self.cycle_mode:
                self.stopReading()

    def _update_demo_controls(self):
        running = self.is_monitoring
        self.startButton.setEnabled(self.daq_connected and not running)
        self.stopButton.setEnabled(running)
        self.nextButton.setEnabled(not running)
        self.configurationButton.setEnabled(not running)
        self.findDeviceButton.setEnabled(not running and not self.daq_connected)
        self.removeDeviceButton.setEnabled(not running and self.daq_connected)
        self.saveSessionButton.setEnabled(not running and bool(self.xdata))
        self.sendSessionButton.setEnabled(not running and bool(self.xdata))
        self.runSetup.set_locked(running)
        self.runSetup.hint.setText("Locked while recording. Each cycle keeps these settings." if running else
                                  "Applied when recording starts. Fixed for that session.")
        if self.presentation:
            self.presentation.save_action.setEnabled(self.saveSessionButton.isEnabled())
            self.presentation.send_action.setEnabled(self.sendSessionButton.isEnabled())
            self.presentation.refresh_device_control()
            self.presentation.refresh_configuration()
            self.presentation.refresh_summary()

    def start_monitoring(self):
        if self.is_monitoring or not self.daq_connected or not self.prepare_run_setup():
            return
        if self._configuration_draft:
            # Applying only at the next Start preserves the stopped session's
            # original plots, channel order and export buffer.
            cfg = dict(self._configuration_draft, mqtt_enabled=False, machine_id=self.machine_id)
            super().cnfg_Sig_Received(cfg)
            self._configuration_draft = None
        self._start_demo_session()
        self.is_monitoring = True
        self._wait_ticks = 0
        self.presentation.navigate("monitor")
        self.demo_message("Recording armed. Waiting for a simulated trigger.")
        self._update_demo_controls()
        if not self.cycle_mode:
            self._begin_demo_cycle()
        self._demo_timer.start()

    def next_Session(self):
        self.presentation.navigate("monitor")
        self.presentation.side_toggle.setChecked(False)
        self.runSetup.material.setFocus()
        self.demo_message("New session settings.")

    def stopReading(self):
        self._demo_timer.stop()
        if self._demo_step is not None:
            self._finish_demo_cycle(interrupted=True)
        self.is_monitoring = False
        self._set_plot_live(False)
        self._update_demo_controls()

    def stop_message(self):
        self.demo_message("Recording stopped. Save the demo session or start another.")

    def configure(self):
        self.presentation.navigate("setup")

    def _stage_configuration(self, cfg):
        self._configuration_draft = deepcopy(dict(cfg, mqtt_enabled=False))
        self.presentation.refresh_configuration()
        self.demo_message("Configuration saved for next recording.")

    def find_device(self):
        self.daq_connected = True
        self.demo_message("DAQ simulator connected.")
        self._update_demo_controls()

    def rem_devs(self):
        self.daq_connected = False
        self.demo_message("DAQ simulator disconnected.")
        self._update_demo_controls()

    def _ensure_mqtt_publisher(self, *args, **kwargs):
        raise RuntimeError("Real MQTT is disabled in layout previews.")

    def _client(self, quiet=False):
        return self

    def get(self, path, params):
        if path != "/monitoring/history":
            key = (params["machine_id"], params["session_id"], int(params["cycle_id"]))
            return deepcopy(self.demo_waveforms[key])
        if "keys" in params:
            keys = {tuple(key) for key in json.loads(params["keys"])}
            return dict(cycles=[deepcopy(entry) for key, entry in self.demo_server.items() if key in keys], next_cursor=None)
        entries = sorted(self.demo_server.values(), key=lambda entry: int(entry["capture"]["first_time_ns"]), reverse=True)
        include = str(params.get("include_excluded", "0")) == "1"
        entries = [entry for entry in entries if include or not entry.get("review", {}).get("excluded")]
        offset = int(params.get("cursor") or 0)
        return dict(cycles=deepcopy(entries[offset:offset + 10]), next_cursor=str(offset + 10) if offset + 10 < len(entries) else None)

    def send_pending_edits(self, keys=None, force=False):
        if not force:
            return
        if not self.partEditor.can_leave():
            return
        keys = list(self.cycle_history) if keys is None else keys
        incoming = []
        for key in keys:
            if key not in self.demo_server:
                continue
            entry = deepcopy(self.demo_server[key])
            local = self.cycle_history[key]
            for field in ("measurements", "review"):
                entry[field] = deepcopy(local[field])
            self.demo_server[key] = entry
            incoming.append(entry)
        self.merge_server_history(incoming)
        self.demo_message(f"{len(incoming)} cycles synced to demo server.")

    def send_Session_to_cloud(self):
        if not self.partEditor.can_leave():
            return
        entries = []
        for key, entry in self.cycle_history.items():
            if key[:2] == (self._session_machine_id, self.session_id):
                copied = deepcopy(entry)
                copied["waveform_status"] = "stored"
                copied.pop("local_review_edit", None)
                copied.pop("local_measurement_edit", None)
                self.demo_server[key] = copied
                self.demo_waveforms[key] = self._waveforms[key]
                entries.append(copied)
        self.merge_server_history(entries)
        self.demo_message(f"{len(entries)} cycles copied to the in-memory demo server.")

    def save_Session(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save simulated session", "demo-session.csv", "CSV (*.csv)")
        if path:
            try:
                self.save_session_export(path)
                self.demo_message("Saved demo waveforms, cycle summary and metadata.")
            except (OSError, ValueError, KeyError) as exc:
                QtWidgets.QMessageBox.warning(self, "Save demo session", str(exc))

    def closeEvent(self, event):
        if self._history_jobs:
            for job in self._history_jobs:
                job.requestInterruption()
            self._close_after_history = True
            event.ignore()
            return
        if not self.partEditor.can_leave():
            event.ignore()
            return
        self._demo_timer.stop()
        event.accept()
