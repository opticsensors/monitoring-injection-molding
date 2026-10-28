"""History browsing, an in-memory waveform cache, and independent comparison tabs."""
from collections import OrderedDict
from copy import deepcopy
import os
import numpy as np
from PyQt5 import QtCore, QtWidgets
from cycle_metadata import identity, optional_number, new_review, validate_review, save_pending_edits
from connection_settings import history_settings, ENV_FILE
from history_client import HistoryClient, HistoryJob


class HistoryController:
    def initialize_browser(self):
        self._waveforms = OrderedDict()
        self._waveform_bytes = 0
        self._history_jobs = set()
        self._history_next_cursor = None
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

    def set_connection_status(self, kind, connected, detail):
        # The timer polls frequently; log transitions, not the same state every tick.
        state = (bool(connected), detail)
        if self._connection_states.get(kind) == state:
            return
        self._connection_states[kind] = state
        if kind == "broker" and detail == "Uploads off":
            message = "Automatic capture upload: Off"
        else:
            name = "Upload connection" if kind == "broker" else "History server"
            message = f"{name}: {detail}"
        if kind == "server" and detail == "Check .env":
            message += f" ({ENV_FILE})"
        timestamp = QtCore.QTime.currentTime().toString("HH:mm:ss")
        self.messagesBox.appendPlainText(f"[{timestamp}] {message}")

    def _client(self, quiet=False):
        try:
            return HistoryClient(*history_settings())
        except (ValueError, OSError) as exc:
            if not quiet:
                self.historyPanel.set_status(str(exc))
            self.set_connection_status("server", False, "Check .env")
            return None

    def _start_history_job(self, client, callback, keys=None, *, cursor="", refresh_keys=(), lookup_only=False, silent=False):
        if self._history_jobs:
            self.historyPanel.set_status("A server request is already running.")
            return
        job = HistoryJob(client, keys, self, cursor=cursor, refresh_keys=refresh_keys,
                         lookup_only=lookup_only, include_excluded=self.historyPanel.showExcluded.isChecked())
        self._history_jobs.add(job)
        progress = QtWidgets.QProgressDialog("Connecting to server…", "Cancel", 0, 0, self)
        progress.setWindowTitle("Cycle history")
        progress.setWindowModality(QtCore.Qt.NonModal)
        progress.setMinimumDuration(2147483647 if silent else 0)
        progress.canceled.connect(job.requestInterruption)
        job.progress.connect(progress.setLabelText)
        if not silent:
            job.progress.connect(self.historyPanel.set_status)
        def received(result):
            self.set_connection_status("server", True, "Available (last request)")
            callback(result)
        def failed(message):
            self.set_connection_status("server", False, "Unavailable")
            if not silent:
                self.historyPanel.set_status(message)
        job.ready.connect(received)
        job.failed.connect(failed)
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
            # Refresh all already-loaded identities when reloading latest, including
            # old excluded rows that no longer appear in the normal newest page.
            keys = [key for key in self.cycle_history if key[2] > 0] if not cursor else []
            self._start_history_job(client, self._receive_history_page, cursor=cursor, refresh_keys=keys)

    def _receive_history_page(self, page):
        # Advance only after the entire page has been accepted. Errors/cancellation
        # leave both the existing rows and the next-page position available to retry.
        if self.merge_server_history(page.get("updates", []) + page["cycles"]):
            self._history_next_cursor = page["next_cursor"]
            if self._history_next_cursor is None:
                self.historyPanel.set_status(self.historyPanel.status.text() + " · No older cycles")

    def merge_server_history(self, entries):
        staged, conflicts = {}, 0
        try:
            for incoming in entries:
                entry = deepcopy(incoming)
                c, m = entry["capture"], entry["measurements"]
                key = identity(c)
                if not key[0] or not key[1] or c["mode"] != "cycle":
                    raise ValueError("Invalid server cycle identity.")
                int(c["first_time_ns"])
                int(c["last_time_ns"])
                for field in ("weight_g", "length_mm"):
                    m[field] = optional_number(m.get(field), field)
                if type(m.get("revision")) is not int or not 0 <= m["revision"] <= 9007199254740991:
                    raise ValueError("Invalid measurement revision.")
                entry["review"] = validate_review(entry.get("review", new_review()))
                old = staged.get(key, self.cycle_history.get(key))
                if old:
                    if old["capture"] != c:
                        raise ValueError("The server and local capture disagree; existing history retained.")
                    merged = deepcopy(old)
                    merged.update(waveform_status=entry.get("waveform_status", "stored"),
                                  summary=entry.get("summary", {}), edit_conflict=False,
                                  delivery=entry.get("delivery", "On server"))
                    for field, flag, conflict_flag, values in (("measurements", "local_measurement_edit", "measurement_conflict", ("weight_g", "length_mm")),
                                               ("review", "local_review_edit", "review_conflict", ("settings", "excluded"))):
                        remote = entry[field]
                        previous = old.get(field, new_review())
                        same = all(previous.get(f) == remote.get(f) for f in values)
                        merged["server_" + field] = deepcopy(remote)
                        merged[conflict_flag] = False
                        if old.get(flag) and not (same and remote["revision"] >= previous["revision"]):
                            merged[field] = deepcopy(previous)
                            merged[flag] = True
                            if not same and remote["revision"] >= previous["revision"]:
                                merged[conflict_flag] = True
                            merged["delivery"] = "Local edit retained; pending sync. Send edits to resolve a server conflict."
                            conflicts += 1
                        elif remote["revision"] >= previous["revision"]:
                            merged[field] = deepcopy(remote)
                            merged.pop(flag, None)
                            if field == "review":
                                merged.pop("review_patch", None)
                    merged["edit_conflict"] = bool(merged.get("measurement_conflict") or merged.get("review_conflict"))
                    entry = merged
                staged[key] = deepcopy(entry)
            # A successful readback removes the durable proposal only after its
            # revision/values are confirmed. Disk failure retains the local edits.
            if self._edits_error:
                raise ValueError(self._edits_error)
            save_pending_edits({**self.cycle_history, **staged}.values())
            self.cycle_history.update(staged)
            self.refresh_measurements()
            self.historyPanel.set_status(f"{len(entries)} server summaries loaded" +
                (f" · {conflicts} local edits retained" if conflicts else ""))
            return True
        except (KeyError, TypeError, ValueError, OSError) as exc:
            self.historyPanel.set_status(str(exc))
            return False

    def select_latest_part(self):
        keys = [key for key, entry in self.cycle_history.items() if entry["capture"]["mode"] == "cycle"
                and not entry.get("review", new_review())["excluded"]]
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
        from cycle_metadata import effective_settings
        records = [dict(capture=deepcopy(effective_settings(self.cycle_history[k])), waveform=self._waveforms[k]) for k in keys]
        try:
            view = CycleReview(records, self)
        except ValueError as exc:
            self.historyPanel.set_status(str(exc))
            return
        self._comparison_count += 1
        view.cycle_keys = list(keys)
        view.focus.currentIndexChanged.connect(lambda _: self.select_comparison_part(view))
        view._plot_toolbar_changed = self.sync_plot_toolbar
        index = self.workspaceTabs.addTab(view, f"Plot {self._comparison_count}")
        self.workspaceTabs.setCurrentIndex(index)

    def close_workspace_tab(self, index):
        if index < 2:
            return
        widget = self.workspaceTabs.widget(index)
        self.workspaceTabs.removeTab(index)
        # Tear down graphics viewboxes before their parent scenes disappear.
        widget.reset_Data_n_Plot_Vars()
        widget.deleteLater()
