"""Exercise one-page history loading and on-demand curves without network/DAQ."""
import os
import json
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5 import QtCore, QtWidgets
import cycle_metadata as meta
import main


def check():
    app = QtWidgets.QApplication([])
    errors = []
    previous_hook = sys.excepthook
    def capture_error(kind, error, trace):
        errors.append(error)
        previous_hook(kind, error, trace)
    sys.excepthook = capture_error

    with tempfile.TemporaryDirectory() as directory:
        meta.SETTINGS_FILE = Path(directory) / "run.json"
        meta.EDITS_FILE = Path(directory) / "edits.json"
        os.environ["MONITORING_UI_SETTINGS_FILE"] = str(Path(directory) / "ui.ini")
        window = main.MainWindow()
        window._edit_timer.stop()
        window.mqtt_enabled = False
        window.resize(1500, 920)
        window.show()
        window.show_measurements()
        app.processEvents()
        snapshot = deepcopy(window._run_snapshot)
        x = [0, .01, .02]
        rows = [[30 + i + channel for channel in window.daq_channels] for i in range(3)]
        records = []
        for n in range(25):
            snapshot["machine_id"] = "55t" if n % 2 else "160t"
            entry, _ = meta.finish_capture(snapshot, "paged-test", n + 1, n + 1,
                1785838969691369500 + n * 1000000000, 0, .03, x, rows)
            entry.update(waveform_status="stored", delivery="Server: stored")
            records.append(entry)
        records.reverse()
        fields = records[0]["capture"]["config_snapshot"]["field_names"]
        indices = records[0]["capture"]["config_snapshot"]["saved_indices"]
        waveform = dict(time_s=x, fields=fields,
                        values={f: [row[i] for row in rows] for f, i in zip(fields, indices)})

        class Reader:
            def __init__(self):
                self.requests = []
                self.fail = self.block = self.repeat = self.conflict = False
                self.entered, self.release = threading.Event(), threading.Event()

            def get(self, path, params):
                self.requests.append((path, dict(params)))
                if self.fail:
                    self.fail = False
                    raise ValueError("Simulated network failure")
                if self.block:
                    self.block = False
                    self.entered.set()
                    self.release.wait(3)
                if path == "/monitoring/waveform":
                    return deepcopy(waveform)
                assert path == "/monitoring/history"
                if "keys" in params:
                    requested = {tuple(key) for key in json.loads(params["keys"])}
                    return dict(cycles=[deepcopy(e) for e in records if meta.identity(e["capture"]) in requested], next_cursor=None)
                cursor = params["cursor"]
                start = int(cursor.split("-")[1]) if cursor else 0
                entries = deepcopy(records[start:start + 10])
                next_cursor = f"page-{start + 10}" if start + 10 < len(records) else None
                if self.repeat:
                    self.repeat = False
                    next_cursor = cursor
                if self.conflict:
                    self.conflict = False
                    entries[0]["capture"]["material"] = "Conflicting material"
                return dict(cycles=entries, next_cursor=next_cursor)

        reader = Reader()
        window._client = lambda: reader

        def wait_jobs():
            deadline = time.monotonic() + 5
            while window._history_jobs and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.005)
            assert not window._history_jobs, "History request did not finish"
            assert not errors, errors

        panel = window.historyPanel
        assert not panel.moreButton.isEnabled()
        panel.loadButton.click()
        assert not panel.loadButton.isEnabled() and not panel.moreButton.isEnabled()
        wait_jobs()
        assert len(reader.requests) == 1
        assert panel.table.rowCount() == 10 and panel.moreButton.isEnabled()
        assert not window._waveforms  # Summaries do not download curves.
        first_key = meta.identity(records[0]["capture"])
        panel.table.item(0, 0).setCheckState(QtCore.Qt.Checked)
        window.update_measurements(first_key, 12.5, "")

        # A finished local cycle still appears without making any server request.
        window.cycle_mode = True
        window.session_cycle_base = 0
        window.begin_metadata_session()
        window.capture_started(999, snapshot, 0)
        window.capture_finished(999, x, rows, 0, {"end_s": .03})
        local_key = (snapshot["machine_id"], window.session_id, 999)
        assert local_key in window.cycle_history and panel.table.rowCount() == 11
        assert len(reader.requests) == 1
        cursor = window._history_next_cursor

        reader.fail = True
        panel.moreButton.click()
        wait_jobs()
        assert window._history_next_cursor == cursor and panel.table.rowCount() == 11
        assert panel.moreButton.isEnabled() and "failure" in panel.status.text()

        reader.block = True
        panel.moreButton.click()
        deadline = time.monotonic() + 3
        while not reader.entered.is_set() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        assert reader.entered.is_set()
        next(iter(window._history_jobs)).requestInterruption()
        reader.release.set()
        wait_jobs()
        assert window._history_next_cursor == cursor and panel.table.rowCount() == 11
        assert panel.moreButton.isEnabled() and "cancelled" in panel.status.text()

        before = len(reader.requests)
        panel.moreButton.click()
        wait_jobs()
        assert len(reader.requests) == before + 1 and panel.table.rowCount() == 21
        assert reader.requests[-1][1]["cursor"] == cursor
        assert panel.selected_cycles() == [first_key]
        cursor = window._history_next_cursor

        reader.repeat = True
        panel.moreButton.click()
        wait_jobs()
        assert window._history_next_cursor == cursor and panel.table.rowCount() == 21
        assert "repeated" in panel.status.text()
        panel.moreButton.click()
        wait_jobs()
        assert panel.table.rowCount() == 26 and window._history_next_cursor is None
        assert not panel.moreButton.isEnabled()
        assert "No older cycles" in panel.status.text()

        # Reloading the newest page retains local rows/edits and does not fetch all pages.
        before = len(reader.requests)
        panel.loadButton.click()
        wait_jobs()
        assert len(reader.requests) == before + 3 and reader.requests[-1][1]["cursor"] == ""
        assert panel.table.rowCount() == 26 and local_key in window.cycle_history
        assert window.cycle_history[first_key]["measurements"]["weight_g"] == 12.5
        assert "retained" in panel.status.text()
        assert all(path == "/monitoring/history" for path, _ in reader.requests)
        # Changes to an older loaded row arrive via identity refresh, even though
        # it is outside the latest page. Hiding alone would leave a stale local row.
        oldest = records[-1]
        oldest_key = meta.identity(oldest['capture'])
        oldest['review'] = meta.edit_review(meta.new_review(), excluded=True)
        window.load_server_history()
        wait_jobs()
        assert window.cycle_history[oldest_key]['review']['excluded']
        assert panel.table.rowCount() == 25
        panel.showExcluded.setChecked(True)
        assert panel.table.rowCount() == 26
        panel.showExcluded.setChecked(False)
        oldest['review'] = meta.edit_review(oldest['review'], excluded=False)
        panel.loadButton.click()
        wait_jobs()
        assert panel.table.rowCount() == 26
        cursor = window._history_next_cursor
        reader.conflict = True
        window.load_server_history()
        wait_jobs()
        assert window._history_next_cursor == cursor and "disagree" in panel.status.text()
        assert window.cycle_history[first_key]["capture"] == records[0]["capture"]

        # Plot fetches only the requested waveform; a second plot reuses its cache.
        before = len(reader.requests)
        window.plot_history_cycles([first_key])
        wait_jobs()
        assert len(reader.requests) == before + 1
        assert reader.requests[-1] == ("/monitoring/waveform", dict(
            machine_id=first_key[0], session_id=first_key[1], cycle_id=first_key[2]))
        assert set(window._waveforms) == {local_key, first_key}
        window.plot_history_cycles([first_key])
        app.processEvents()
        assert len(reader.requests) == before + 1
        while window.workspaceTabs.count() > 2:
            window.close_workspace_tab(window.workspaceTabs.count() - 1)
        app.processEvents()
        window.hide()
        assert not errors, errors
    sys.excepthook = previous_hook
    print("PASS: one page per click, 10/20/25 summaries, automatic local row, "
          "retry/cancel, no duplicates or lost edits, last-page state, and selected-only cached waveforms.")


if __name__ == "__main__":
    check()
