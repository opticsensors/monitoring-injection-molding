"""One offscreen window, synthetic captures and a fake reader; no DAQ/server/MQTT."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cycle_metadata as meta
import main
from rheology import apparent_viscosity


def check():
    app = QtWidgets.QApplication([])
    font_id = QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QtGui.QFont(families[0], 10))
    errors = []
    previous_hook = sys.excepthook
    def capture_error(kind, value, trace):
        errors.append(value)
        previous_hook(kind, value, trace)
    sys.excepthook = capture_error
    with tempfile.TemporaryDirectory() as directory:
        meta.SETTINGS_FILE = Path(directory) / "run.json"
        meta.EDITS_FILE = Path(directory) / "edits.json"
        os.environ["MONITORING_UI_SETTINGS_FILE"] = str(Path(directory) / "ui.ini")
        window = main.MainWindow()
        window._edit_timer.stop()
        window.mqtt_enabled = False
        window.reset_Data_n_Plot_Vars()
        window.SubplotSetup()
        window.resize(1500, 920)
        window.show()
        app.processEvents()
        inputs = [window.runSetup.machine, window.runSetup.material, window.runSetup.temperature,
                  window.runSetup.speed, window.partEditor.weight, window.partEditor.length]
        sizes = [(w.width(), w.height()) for w in inputs]
        assert len({height for width, height in sizes}) == 1 and all(width >= 80 for width, height in sizes), sizes
        sidebar = window.presentation.sidebar
        window.presentation.side_toggle.setChecked(True)
        assert sidebar.isHidden()
        window.presentation.side_toggle.setChecked(False)
        # A short inspector still lets the user reach every measurement.
        sidebar.setFixedHeight(180)
        app.processEvents()
        assert sidebar.verticalScrollBar().maximum() > 0
        assert sidebar.horizontalScrollBar().maximum() == 0
        sidebar.setMinimumHeight(0)
        sidebar.setMaximumHeight(16777215)
        snapshot = deepcopy(window._run_snapshot)
        snapshot["injection_speed_mm_s"] = 35
        x = [0, .01, .02]
        rows = [[30 + index + channel for channel in window.daq_channels] for index in range(3)]
        keys = []
        for i, machine in enumerate(("55t", "160t")):
            snapshot["machine_id"] = machine
            snapshot["config_snapshot"]["viscosity"] = {"L_mm": 100 / (i + 1), "Rc_mm": 1.5}
            record_rows = [[value * (i + 1) for value in row] for row in rows]
            entry, _ = meta.finish_capture(snapshot, "history-test", 1, 7,
                1785838969691369500 + i * 1000000000, 0, .03, x, record_rows)
            key = meta.identity(entry["capture"])
            keys.append(key)
            window.cycle_history[key] = entry
            fields = entry["capture"]["config_snapshot"]["field_names"]
            indices = entry["capture"]["config_snapshot"]["saved_indices"]
            window.remember_waveform(key, {"time_s": x, "fields": fields,
                "values": {field: [row[index] for row in record_rows] for field, index in zip(fields, indices)}})
        window.refresh_measurements()
        assert window.historyPanel.table.rowCount() == 2
        window.show_measurements()
        table = window.historyPanel.table
        table.item(0, 0).setCheckState(QtCore.Qt.Checked)
        table.item(1, 0).setCheckState(QtCore.Qt.Checked)
        window.historyPanel.search.setText("160t")
        assert table.rowCount() == 1 and len(window.historyPanel.selected_cycles()) == 2
        window.historyPanel.search.clear()
        original = window.partEditor.key
        window.partEditor.weight.setText("12.5")
        window.partEditor._edited()
        window.refresh_measurements()
        assert window.partEditor.key == original and window.partEditor.weight.text() == "12.5"
        other = next(k for k in keys if k != original)
        assert window.partEditor.set_entry(other)  # Autosave before changing selection.
        assert window.cycle_history[original]["measurements"]["weight_g"] == 12.5
        window.partEditor.set_entry(original)
        # Part autosave never changes the session setup. Start applies settings.
        captures = {key: deepcopy(entry["capture"]) for key, entry in window.cycle_history.items()}
        window.runSetup.material.setText("Next material")
        window.runSetup.speed.setText("42")
        assert window.partEditor.apply()
        assert not window.partEditor.dirty
        assert window.cycle_history[original]["measurements"]["weight_g"] == 12.5
        assert window._run_snapshot["material"] != "Next material"
        assert window.prepare_run_setup()
        assert window._run_snapshot["material"] == "Next material"
        assert window._run_snapshot["injection_speed_mm_s"] == 42
        assert all(window.cycle_history[key]["capture"] == capture for key, capture in captures.items())
        revision = window.cycle_history[original]["measurements"]["revision"]
        assert window.partEditor.apply()
        assert window.cycle_history[original]["measurements"]["revision"] == revision
        # Invalid part input must not partially apply the edited future settings.
        saved_settings = meta.SETTINGS_FILE.read_bytes()
        window.runSetup.material.setText("Must not apply")
        window.partEditor.weight.setText("invalid")
        window.partEditor._edited()
        with patch.object(QtWidgets.QMessageBox, "warning") as warning:
            assert not window.partEditor.apply()
        warning.assert_not_called()
        assert "border" in window.partEditor.weight.styleSheet()
        assert meta.SETTINGS_FILE.read_bytes() == saved_settings
        assert window._run_snapshot["material"] == "Next material"
        assert window.cycle_history[original]["measurements"]["weight_g"] == 12.5
        window.runSetup.set_values(window.run_settings)
        window.partEditor.dirty = False
        window.partEditor.set_entry(original)
        older = deepcopy(window.cycle_history[original])
        older["measurements"].update(revision=0, weight_g=1)
        window.merge_server_history([older])
        assert window.cycle_history[original]["measurements"]["weight_g"] == 12.5
        assert "retained" in window.historyPanel.status.text()
        older["measurements"]["revision"] = 10
        window.merge_server_history([older])
        assert window.cycle_history[original]["measurements"]["weight_g"] == 12.5
        window.partEditor._edited()  # Explicit re-entry confirms the local value.
        assert window.partEditor.apply()
        assert window.cycle_history[original]["measurements"]["revision"] == 11
        # Same cycle number on two machines remains two distinct records/curves.
        window.workspaceTabs.setCurrentIndex(0)
        window.ploter(x, np.asarray(rows).T.tolist())
        window._set_cycle_readout(99)
        window._set_plot_live(False)
        window.cursorButton.click()
        window._on_cursor_click(QtCore.Qt.LeftButton, 0)
        window._on_cursor_click(QtCore.Qt.RightButton, .01)
        app.processEvents()
        toolbar_position = window.homeButton.pos()
        live_before = window.tool_mode
        window.plot_history_cycles(keys)
        review = window.workspaceTabs.currentWidget()
        assert review.focus.count() == 2
        assert review.plotTabs.count() == window.plotTabs.count() == 2
        assert not window.cursorButton.isChecked()
        window.panButton.click()
        assert review.tool_mode == "pan" and window.tool_mode == live_before
        window.cursorButton.click()
        assert review.tool_mode == "cursor" and all(v.interaction is review for v in review._tool_viewboxes)
        assert all(v.interaction is window for v in window._tool_viewboxes)
        assert not review.findChildren(QtWidgets.QPushButton)
        app.processEvents()
        assert window.homeButton.pos() == toolbar_position
        review._on_cursor_click(QtCore.Qt.LeftButton, 0)
        review._on_cursor_click(QtCore.Qt.RightButton, .02)
        assert window.deltaTLabel.text() == "Δt: 0.020 s"
        assert window.deltaPLabel.text() == "ΔP: 1.0 bar"
        first_eta = apparent_viscosity(.02, 1, 100, 1.5).eta
        assert window.viscosityLabel.text() == f"η: {first_eta:,.1f} Pa·s"
        measured = review._cursor_readout
        # Incoming Live events must never replace comparison tools/readouts.
        window._set_plot_live(True)
        window._set_cycle_readout(100)
        assert window.homeButton.isEnabled() and window.cursorButton.isChecked()
        assert window.deltaTLabel.text() == measured[0]
        assert "(#7)" in window.cycleReadoutLabel.text()
        window._set_plot_live(False)
        assert window.tool_mode == live_before == "cursor"
        review.focus.setCurrentIndex(1)
        assert review._last_plot_x == x
        assert np.array_equal(review._prepared[0][1][0], rows and [row[0] for row in rows])
        assert window.deltaPLabel.text() == "ΔP: 2.0 bar"
        second_eta = apparent_viscosity(.02, 2, 50, 1.5).eta
        assert window.viscosityLabel.text() == f"η: {second_eta:,.1f} Pa·s"
        assert second_eta == 8 * first_eta
        # Eye and Home act on the comparison only.
        window.hideGhostsButton.click()
        assert all(not line.isVisible() for line in review._review_lines[0])
        assert all(line.isVisible() for line in review._review_lines[1])
        review.focus.setCurrentIndex(0)
        assert all(line.isVisible() for line in review._review_lines[0])
        assert all(not line.isVisible() for line in review._review_lines[1])
        window.hideGhostsButton.click()
        live_range = window.splotlist[0].viewRange()[0]
        review._set_all_x_range(100, 200)
        window.homeButton.click()
        assert np.allclose(review.splotlist[0].viewRange()[0], review._default_x_range[:2])
        assert np.allclose(window.splotlist[0].viewRange()[0], live_range)
        window.workspaceTabs.setCurrentIndex(0)
        assert window.cursorButton.isChecked() and not window.hideGhostsButton.isChecked()
        assert window.deltaTLabel.text() == "Δt: 0.010 s"
        assert "(#100)" in window.cycleReadoutLabel.text()
        window.workspaceTabs.setCurrentWidget(review)
        assert window.cursorButton.isChecked() and window.deltaTLabel.text() == "Δt: 0.020 s"
        # A second comparison owns its state, even with the same source cycle.
        window.plot_history_cycles(keys[:1])
        second_review = window.workspaceTabs.currentWidget()
        assert second_review.tool_mode is None and not window.cursorButton.isChecked()
        assert window.deltaTLabel.text() == "Δt: --"
        window.close_workspace_tab(window.workspaceTabs.currentIndex())
        window.workspaceTabs.setCurrentWidget(review)
        window.close_workspace_tab(window.workspaceTabs.currentIndex())
        app.processEvents()
        assert window.workspaceTabs.count() == 2
        window.show_measurements()
        assert not window.homeButton.isEnabled() and not window.homeButton.isVisible()
        assert window.deltaTLabel.text() == "Δt: --"
        window.reset_Data_n_Plot_Vars()
        assert all(k in window._waveforms for k in keys)
        # A blocked server reader works on a QThread; the GUI still processes events.
        class Reader:
            def get(self, path, params):
                time.sleep(.03)
                return {"cycles": [], "next_cursor": None}
        finished, ticks = [], []
        window._start_history_job(Reader(), finished.append)
        QtCore.QTimer.singleShot(0, lambda: ticks.append(True))
        deadline = time.monotonic() + 3
        while window._history_jobs and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        assert ticks and finished == [{"cycles": [], "next_cursor": None, "updates": []}] and not window._history_jobs
        window.hide()
        assert not errors, errors
    sys.excepthook = previous_hook
    print("PASS: compact scrollable inspector, part autosave/session settings, frozen settings, live history, "
          "selection/filtering, dirty edits, server merge, "
          "shared toolbar routing, per-view state, selected-cycle calculations, "
          "cached waveforms and responsive background loading.")


if __name__ == "__main__":
    check()
