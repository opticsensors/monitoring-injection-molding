"""History browsing, an in-memory waveform cache, and independent comparison tabs."""
from collections import OrderedDict
from copy import deepcopy
import os
import numpy as np
from PyQt5 import QtCore, QtWidgets
from cycle_metadata import identity, optional_number
from history_client import HistoryClient, HistoryJob


class HistoryController:
    def initialize_browser(self):
        self._waveforms = OrderedDict()
        self._waveform_bytes = 0
        self._history_jobs = set()
        self._history_next_cursor = None
        self._history_token = os.environ.get("MONITORING_HISTORY_TOKEN", "")
        settings_path = os.environ.get("MONITORING_UI_SETTINGS_FILE")
        self.ui_settings = (QtCore.QSettings(settings_path, QtCore.QSettings.IniFormat)
                            if settings_path else QtCore.QSettings("Eurecat", "InjectionMonitoring"))
        self._comparison_count = 0
        self._pending_plot_keys = []

    def remember_waveform(self, key, waveform):
        x = np.array(waveform["time_s"], dtype=float, copy=True)
        fields = list(waveform["fields"])
        if x.ndim != 1 or not len(x) or not np.all(np.isfinite(x)) or np.any(np.diff(x) <= 0):
            raise ValueError("Waveform times must be finite and increasing.")
        values = {}
        for field in fields:
            y = np.array(waveform["values"][field], dtype=float, copy=True)
            if y.ndim != 1 or len(y) != len(x):
                raise ValueError("Waveform channel lengths do not match.")
            y.setflags(write=False)
            values[field] = y
        x.setflags(write=False)
        size = x.nbytes + sum(v.nbytes for v in values.values())
        if key in self._waveforms:
            self._waveform_bytes -= self._waveforms.pop(key)["bytes"]
        self._waveforms[key] = dict(time_s=x, fields=fields, values=values, bytes=size)
        self._waveform_bytes += size
        # A bounded RAM cache is not a recording archive. Existing Save is unchanged.
        while self._waveform_bytes > 128 * 1024 * 1024 and len(self._waveforms) > 1:
            _, old = self._waveforms.popitem(last=False)
            self._waveform_bytes -= old["bytes"]

    def server_connection(self):
        if self._history_jobs:
            self.historyPanel.set_status("Wait for the current server request before changing the connection.")
            return False
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Server connection")
        form = QtWidgets.QFormLayout(dialog)
        url = QtWidgets.QLineEdit(self.ui_settings.value("history_url", "http://172.20.48.28:1880"))
        token = QtWidgets.QLineEdit(self._history_token)
        token.setEchoMode(QtWidgets.QLineEdit.Password)
        token.setPlaceholderText("History access key")
        token.setToolTip("Kept only for this app run. MONITORING_HISTORY_TOKEN can supply it at startup.")
        form.addRow("Server", url)
        form.addRow("Access key", token)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return False
        try:
            HistoryClient(url.text().strip(), token.text().strip())
            if not token.text().strip():
                raise ValueError("Enter the history access key.")
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Server connection", str(exc))
            return False
        self.ui_settings.setValue("history_url", url.text().strip())
        self._history_token = token.text().strip()
        self._history_next_cursor = None
        self.historyPanel.moreButton.setEnabled(False)
        return True

    def _client(self):
        if not self._history_token and not self.server_connection():
            return None
        return HistoryClient(self.ui_settings.value("history_url", "http://172.20.48.28:1880"), self._history_token)

    def _start_history_job(self, client, callback, keys=None, *, cursor=""):
        if self._history_jobs:
            self.historyPanel.set_status("A server request is already running.")
            return
        job = HistoryJob(client, keys, self, cursor=cursor)
        self._history_jobs.add(job)
        progress = QtWidgets.QProgressDialog("Connecting to server…", "Cancel", 0, 0, self)
        progress.setWindowTitle("Cycle history")
        progress.setWindowModality(QtCore.Qt.NonModal)
        progress.setMinimumDuration(0)
        progress.canceled.connect(job.requestInterruption)
        job.progress.connect(progress.setLabelText)
        job.progress.connect(self.historyPanel.set_status)
        job.ready.connect(callback)
        job.failed.connect(self.historyPanel.set_status)
        def finish():
            progress.close()
            progress.deleteLater()
            self._history_jobs.discard(job)
            self.historyPanel.loadButton.setEnabled(True)
            self.historyPanel.moreButton.setEnabled(self._history_next_cursor is not None)
            if job.cancelled:
                self.historyPanel.set_status("Request cancelled; existing history retained.")
            job.deleteLater()
            if getattr(self, "_close_after_history", False) and not self._history_jobs:
                QtCore.QTimer.singleShot(0, self.close)
        job.finished.connect(finish)
        self.historyPanel.loadButton.setEnabled(False)
        self.historyPanel.moreButton.setEnabled(False)
        job.start()

    def load_server_history(self):
        self._load_history_page("")

    def load_more_server_history(self):
        if self._history_next_cursor is not None:
            self._load_history_page(self._history_next_cursor)

    def _load_history_page(self, cursor):
        if self._history_jobs:
            self.historyPanel.set_status("A server request is already running.")
            return
        if not self.partEditor.can_leave():
            return
        client = self._client()
        if client:
            self._start_history_job(client, self._receive_history_page, cursor=cursor)

    def _receive_history_page(self, page):
        # Advance only after the entire page has been accepted. Errors/cancellation
        # leave both the existing rows and the next-page position available to retry.
        if self.merge_server_history(page["cycles"]):
            self._history_next_cursor = page["next_cursor"]
            if self._history_next_cursor is None:
                self.historyPanel.set_status(self.historyPanel.status.text() + " · No older cycles")

    def merge_server_history(self, entries):
        staged, conflicts = {}, 0
        try:
            for entry in entries:
                c, m = entry["capture"], entry["measurements"]
                key = identity(c)
                if not key[0] or not key[1] or c["mode"] != "cycle":
                    raise ValueError("Invalid server cycle identity.")
                int(c["first_time_ns"])
                int(c["last_time_ns"])
                for field in ("weight_g", "length_mm"):
                    m[field] = optional_number(m.get(field), field)
                old = self.cycle_history.get(key)
                if old:
                    if old["capture"] != c:
                        raise ValueError("The server and local capture disagree; existing history retained.")
                    previous = old["measurements"]
                    differs = any(previous.get(f) != m.get(f) for f in ("weight_g", "length_mm"))
                    # Reading history must not silently discard a local proposal,
                    # including when another workstation has a newer revision.
                    if differs and (old.get("local_measurement_edit") or previous["revision"] >= m["revision"]):
                        kept = deepcopy(old)
                        kept["waveform_status"] = entry.get("waveform_status", "stored")
                        kept["summary"] = deepcopy(entry.get("summary", {}))
                        kept["server_measurements"] = deepcopy(m)
                        kept["delivery"] = "Local edit retained; server differs. Apply or Send to use these values."
                        staged[key] = kept
                        conflicts += 1
                        continue
                staged[key] = deepcopy(entry)
            self.cycle_history.update(staged)
            self.refresh_measurements()
            self.historyPanel.set_status(f"{len(entries)} server summaries loaded" +
                (f" · {conflicts} local edits retained" if conflicts else ""))
            return True
        except (KeyError, TypeError, ValueError) as exc:
            self.historyPanel.set_status(str(exc))
            return False

    def select_latest_part(self):
        keys = [key for key, entry in self.cycle_history.items() if entry["capture"]["mode"] == "cycle"]
        if keys:
            key = max(keys, key=lambda k: int(self.cycle_history[k]["capture"]["first_time_ns"]))
            if self.partEditor.set_entry(key):
                self.historyPanel.select_key(key)

    def plot_history_cycles(self, keys):
        keys = [k for k in keys if k in self.cycle_history]
        if not keys:
            return
        if len(keys) > 100:
            self.historyPanel.set_status("Select at most 100 cycles for one comparison.")
            return
        missing = [k for k in keys if k not in self._waveforms]
        if missing:
            client = self._client()
            if not client:
                return
            def received(waveforms):
                try:
                    for key, waveform in waveforms:
                        self.remember_waveform(key, waveform)
                    self._open_comparison(keys)
                except (ValueError, KeyError) as exc:
                    self.historyPanel.set_status(str(exc))
            self._start_history_job(client, received, missing)
        else:
            self._open_comparison(keys)

    def _open_comparison(self, keys):
        from cycle_review import CycleReview
        if any(k not in self._waveforms for k in keys):
            self.historyPanel.set_status("Selection exceeds the waveform cache; select fewer cycles.")
            return
        records = [dict(capture=deepcopy(self.cycle_history[k]["capture"]), waveform=self._waveforms[k]) for k in keys]
        try:
            view = CycleReview(records, self)
        except ValueError as exc:
            self.historyPanel.set_status(str(exc))
            return
        self._comparison_count += 1
        view._plot_toolbar_changed = self.sync_plot_toolbar
        index = self.workspaceTabs.addTab(view, f"Compare {self._comparison_count}")
        self.workspaceTabs.setCurrentIndex(index)
        self.messagesBox.appendPlainText(
            f"Compare {self._comparison_count}: cycles aligned to recording start. "
            "Cursor measurements use the cycle selected in the dropdown.")

    def close_workspace_tab(self, index):
        if index < 2:
            return
        widget = self.workspaceTabs.widget(index)
        self.workspaceTabs.removeTab(index)
        # Tear down graphics viewboxes before their parent scenes disappear.
        widget.reset_Data_n_Plot_Vars()
        widget.deleteLater()
