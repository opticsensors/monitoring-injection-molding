"""Exercise inspector edits, tabs, embedded configuration and isolated demo I/O."""
from copy import deepcopy
import csv
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5 import QtCore, QtTest, QtWidgets
from scripts.preview_layouts import isolated_preview_state, settle_ui, wait_history


def check():
    app = QtWidgets.QApplication([])
    errors = []
    original_hook = sys.excepthook

    def report_error(kind, value, trace):
        errors.append(value)
        original_hook(kind, value, trace)

    sys.excepthook = report_error
    with isolated_preview_state() as directory:
        import main
        from gui_preview import PreviewWindow
        with patch.object(main, "save_cycle_id", side_effect=AssertionError("Real cycle counter touched")), \
             patch("socket.create_connection", side_effect=AssertionError("Network access")), \
             patch("serial.Serial", side_effect=AssertionError("Device access")), \
             patch.object(QtWidgets.QMessageBox, "warning", side_effect=AssertionError("Unexpected warning")):
            window = PreviewWindow()
            window.show()
            settle_ui(app)
            assert len(window.cycle_history) == 5
            key = window.partEditor.key
            assert window.presentation.cycle_selector.currentData() == key
            original_capture = deepcopy(window.cycle_history[key]["capture"])
            window.runSetup.material.setText("Draft material")
            for mode in ("setup", "history", "monitor"):
                window.presentation.navigate(mode)
                settle_ui(app)
                assert window.presentation.mode == mode
                assert window.presentation.session_group.isVisible() == (mode == "monitor")
                assert window.presentation.sidebar.isVisible() == (mode == "monitor")
                assert window.runSetup.material.text() == "Draft material"
                assert window.startButton.isVisible() == (mode == "monitor")
                assert window.stopButton.isVisible() == (mode == "monitor")
                assert window.nextButton.isVisible() == (mode == "monitor")
                assert window.saveSessionButton.isVisible() == (mode == "monitor")
                assert window.sendSessionButton.isVisible() == (mode == "monitor")
                assert window.presentation.vertical.parentWidget() is window.presentation.workspaces.currentWidget()
            monitor_buttons = (window.startButton, window.stopButton, window.nextButton,
                               window.saveSessionButton, window.sendSessionButton,
                               window.homeButton, window.zoomButton, window.panButton)
            assert len({button.mapTo(window, button.rect().center()).y() for button in monitor_buttons}) == 1

            window.presentation.navigate("history")
            panel, table = window.historyPanel, window.historyPanel.table

            def cell(column, target=key):
                return next(table.item(row, column) for row in range(table.rowCount())
                            if table.item(row, 0).data(QtCore.Qt.UserRole) == target)

            assert not panel.editSettingsButton.isVisible() and not panel.moreButton.isVisible()
            assert panel.loadButton.isVisible()
            history_buttons = (panel.loadButton, panel.plotButton, panel.excludeButton,
                               panel.restoreButton, panel.sendEditsButton)
            assert len({button.mapTo(window, button.rect().center()).y() for button in history_buttons}) == 1
            for button in (panel.loadButton, panel.plotButton, panel.excludeButton, panel.restoreButton,
                           panel.sendEditsButton, window.startButton, window.saveSessionButton):
                assert not button.text() and button.toolTip() and not button.icon().isNull()

            # Every requested field commits in-place without changing capture identity.
            for column, value in ((2, "160t"), (4, "ABS"), (5, "80"), (6, "240"),
                                  (7, "42.5"), (8, "13.4"), (9, "210")):
                assert cell(column).flags() & QtCore.Qt.ItemIsEditable
                cell(column).setText(value)
                settle_ui(app)
                assert float(cell(column).text()) == float(value) if column >= 5 else cell(column).text() == value
            entry = window.cycle_history[key]
            assert entry["capture"] == original_capture
            assert entry["review"]["settings"]["machine_id"] == "160t" and entry["local_review_edit"]
            assert entry["review"]["settings"]["material"] == "ABS"
            assert entry["measurements"]["weight_g"] == 13.4
            assert not cell(3).flags() & QtCore.Qt.ItemIsEditable
            cell(5).setText("nan")
            settle_ui(app)
            assert float(cell(5).text()) == 80
            cell(8).setText("")
            settle_ui(app)
            assert window.cycle_history[key]["measurements"]["weight_g"] is None

            # A background refresh leaves an active editor intact until Return.
            table.setCurrentItem(cell(4))
            table.editItem(cell(4))
            settle_ui(app)
            editor = table.findChild(QtWidgets.QLineEdit)
            assert editor and editor.isVisible()
            editor.selectAll()
            QtTest.QTest.keyClicks(editor, "POM")
            window.refresh_measurements()
            settle_ui(app)
            assert editor.text() == "POM" and table.state() == QtWidgets.QAbstractItemView.EditingState
            QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
            settle_ui(app)
            assert cell(4).text() == "POM"
            assert window.workspaceTabs.count() == 2
            panel.search.setText("160t")
            assert table.rowCount() == 1
            panel.search.clear()
            settle_ui(app)
            assert abs(table.columnWidth(13) - table.columnWidth(5)) <= 2

            # Exclusion preserves waveform Save, corrected summaries and undo.
            assert window.update_reviews([key], excluded=True)
            assert key in window._waveforms and key in window.cycle_history
            export = directory / "demo.csv"
            window.save_session_export(export)
            with export.open(encoding="utf-8", newline="") as stream:
                samples = list(csv.DictReader(stream))
            assert len(samples) == 5 * 401 and any(row["excluded"] == "True" for row in samples)
            with export.with_suffix(".cycles.csv").open(encoding="utf-8", newline="") as stream:
                summary = next(row for row in csv.DictReader(stream) if int(row["cycle_id"]) == key[2])
            assert summary["machine_id"] == "160t" and summary["material"] == "POM"
            assert window.update_reviews([key], excluded=False)
            # Reading old demo-server data must not wipe unsent cell edits.
            window.merge_server_history([window.demo_server[key]])
            assert window.cycle_history[key]["local_review_edit"]
            assert cell(4).text() == "POM"
            window.send_pending_edits([key], force=True)
            assert not window.cycle_history[key].get("local_measurement_edit")
            assert not window.cycle_history[key].get("local_review_edit")

            # One visible load action drives the real asynchronous pagination.
            for expected in (10, 20, 25, 25):
                panel.loadButton.click()
                wait_history(app, window)
                settle_ui(app)
                assert len(window.cycle_history) == expected
                assert panel.loadButton.isEnabled() and not panel.moreButton.isVisible()
            assert cell(2).text() == "160t"

            # Plots remain separate, closable peers of Setup/Monitor/History.
            window.plot_history_cycles(list(window.cycle_history)[-2:])
            wait_history(app, window)
            window.plot_history_cycles([key])
            settle_ui(app)
            assert window.presentation.mode == "comparison"
            assert not window.presentation.session_group.isVisible()
            assert window.presentation.part_group.isVisible()
            assert not window.startButton.isVisible() and window.homeButton.isVisible()
            assert window.workspaceTabs.count() == 4 and window.presentation.tabs.count() == 5
            view = window.workspaceTabs.currentWidget()
            assert view.records[0]["capture"]["machine_id"] == "160t"
            assert window.partEditor.key == key
            for mode in ("monitor", "history"):
                window.presentation.navigate(mode)
                assert window.workspaceTabs.count() == 4
            window.presentation.close_tab(3)
            settle_ui(app)
            assert window.workspaceTabs.count() == 3 and window.workspaceTabs.widget(2) is view
            window.presentation.close_tab(0)
            assert window.presentation.tabs.count() == 4
            window.presentation.workspaces.setCurrentIndex(3)
            window.presentation.close_tab(3)
            assert window.workspaceTabs.count() == 2
            assert window.presentation.mode == "history"
            assert window.presentation.vertical.parentWidget() is window.presentation.workspaces.currentWidget()

            # All configuration controls live inside Setup; Reset/Apply stay isolated.
            window.configure()
            settle_ui(app)
            dialog = window.ModuleSelectWin
            assert not window.configurationButton.isVisible() and not dialog.isVisible()
            assert dialog.tabs.isVisible()
            assert window.presentation.connection_button.isVisible()
            assert window.presentation.connection_button.icon().isNull()
            assert window.presentation.connection_button.text() == "Disconnect"
            assert not window.findDeviceButton.isVisible() and not window.removeDeviceButton.isVisible()
            window.presentation.connection_button.click()
            assert not window.daq_connected and not window.startButton.isEnabled()
            assert window.presentation.connection_button.toolTip() == "Connect DAQ"
            assert window.presentation.connection_button.text() == "Connect"
            window.presentation.connection_button.click()
            assert window.daq_connected and window.startButton.isEnabled()
            assert window.presentation.connection_button.toolTip() == "Disconnect DAQ"
            setup_buttons = (window.presentation.connection_button, dialog.okButton, dialog.cancelButton)
            assert len({button.mapTo(window, button.rect().center()).y() for button in setup_buttons}) == 1
            assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["DAQ", "Mold sensors", "Machine data", "Display"]
            trigger_group = dialog.triggerModeCombo.parentWidget()
            daq_group = dialog.timeEdit.parentWidget()
            assert trigger_group.geometry().top() > daq_group.geometry().bottom()
            assert trigger_group.height() < daq_group.height()
            dialog.tabs.setCurrentIndex(2)
            settle_ui(app)
            table = dialog.machineTable
            assert table.viewport().height() >= sum(table.rowHeight(i) for i in range(table.rowCount()))
            assert table.parentWidget().geometry().right() == dialog.machineLayoutCombo.parentWidget().geometry().right()
            dialog.tabs.setCurrentIndex(0)
            dialog.srateEdit.setText("7000")
            dialog.cancelButton.click()
            assert dialog.srateEdit.text() == "6000" and window._configuration_draft is None
            dialog.srateEdit.setText("7000")
            dialog.channel_type_combos[7].setCurrentIndex(dialog.channel_type_combos[7].findData("none"))
            dialog.okButton.click()
            settle_ui(app)
            assert dialog.tabs.isVisible()
            assert window._configuration_draft["sample_rate_hz"] == 7000
            assert len(window._configuration_draft["channels"]) == 6
            assert window.daq_srate == 6000 and len(window.daq_channels) == 7
            window.save_session_export(directory / "before-config-applies.csv")
            window.next_Session()
            settle_ui(app)
            assert window.presentation.mode == "monitor" and window.runSetup.material.isVisible()

            # Wait -> cycle start -> interrupted Stop uses real metadata/export.
            window.start_monitoring()
            window._demo_timer.stop()
            assert window.is_monitoring and not window.runSetup.material.isEnabled()
            assert not dialog.tabs.isEnabled()
            assert window.daq_srate == 7000 and len(window.daq_channels) == 6
            for _ in range(55):
                window.advance_demo()
            window.stopReading()
            entry = window.cycle_history[(window._session_machine_id, window.session_id, window.current_cycle)]
            assert entry["capture"]["status"] == "interrupted"
            assert entry["capture"]["material"] == "Draft material"
            assert window.runSetup.material.isEnabled()
            window.save_session_export(directory / "interrupted.csv")
            window.send_Session_to_cloud()
            assert entry["capture"]["cycle_id"] > 125 and window.mqtt_publisher is None

            # Trigger=None is a continuous preview, with no part/cycle identity.
            window.configure()
            dialog.triggerModeCombo.setCurrentIndex(dialog.triggerModeCombo.findData("None"))
            dialog.okButton.click()
            window.start_monitoring()
            window._demo_timer.stop()
            for _ in range(10):
                window.advance_demo()
            window.stopReading()
            continuous = window.cycle_history[(window._session_machine_id, window.session_id, 0)]
            assert continuous["capture"]["mode"] == "continuous"
            window.save_session_export(directory / "continuous.csv")

            # The compact inspector autosaves and follows trigger starts.
            window.configure()
            dialog.triggerModeCombo.setCurrentIndex(dialog.triggerModeCombo.findData("Inductive"))
            dialog.okButton.click()
            window.start_monitoring()
            window._demo_timer.stop()
            for _ in range(24):
                window.advance_demo()
            settle_ui(app)
            part = window.partEditor
            first = (window._session_machine_id, window.session_id, window.current_cycle)
            assert part.key == first and first not in window.cycle_history
            assert window.presentation.cycle_selector.currentData() == first
            assert not part.saveButton.isVisible()
            assert window.presentation.sidebar.width() <= 270
            part.weight.setFocus()
            part.weight.selectAll()
            QtTest.QTest.keyClicks(part.weight, "14.25")
            QtTest.QTest.qWait(450)
            assert not part.dirty and window._part_drafts[first]["weight_g"] == 14.25
            journal = json.loads((directory / "active_part_measurements.json").read_text())["active"]
            assert next(row for row in journal if row["cycle_id"] == first[2])["weight_g"] == 14.25
            window._demo_step = len(window._demo_x)
            window._finish_demo_cycle()
            assert window.cycle_history[first]["measurements"]["weight_g"] == 14.25
            assert first not in window._part_drafts
            assert window.presentation.cycle_selector.currentData() == first

            # Even a completed autosave must not move a still-focused field to
            # the next part. Remaining keystrokes stay on the original identity.
            assert part.weight.hasFocus()
            window._begin_demo_cycle()
            second = (window._session_machine_id, window.session_id, window.current_cycle)
            assert part.key == first and window._pending_follow_key == second
            part.weight.selectAll()
            QtTest.QTest.keyClicks(part.weight, "14.5")
            QtTest.QTest.keyClick(part.weight, QtCore.Qt.Key_Return)
            settle_ui(app)
            assert window.cycle_history[first]["measurements"]["weight_g"] == 14.5
            assert part.key == second and part.weight.text() == ""
            assert window._part_drafts[second]["weight_g"] is None
            part.length.setFocus()
            QtTest.QTest.keyClicks(part.length, "205")
            QtTest.QTest.keyClick(part.length, QtCore.Qt.Key_Tab)
            settle_ui(app)
            assert window._part_drafts[second]["length_mm"] == 205

            # History browsing remains on the chosen part as live cycles arrive.
            window.presentation.navigate("history")
            panel.select_key(first)
            assert part.key == first
            window._demo_step = len(window._demo_x)
            window._finish_demo_cycle()
            window._begin_demo_cycle()
            third = (window._session_machine_id, window.session_id, window.current_cycle)
            assert part.key == first
            window.presentation.navigate("monitor")
            settle_ui(app)
            assert part.key == third and part.length.text() == ""
            for _ in range(5):
                window.advance_demo()
            window.stopReading()
            assert not window._part_drafts
            assert window.cycle_history[second]["measurements"]["length_mm"] == 205

            # Export flushes a value before its debounce elapses, with no Save
            # button, and blank inputs clear existing measurements.
            part.weight.setFocus()
            QtTest.QTest.keyClicks(part.weight, "15.2")
            window.save_session_export(directory / "autosaved.csv")
            assert window.cycle_history[third]["measurements"]["weight_g"] == 15.2
            part.weight.selectAll()
            QtTest.QTest.keyClick(part.weight, QtCore.Qt.Key_Backspace)
            QtTest.QTest.keyClick(part.weight, QtCore.Qt.Key_Return)
            settle_ui(app)
            assert window.cycle_history[third]["measurements"]["weight_g"] is None
            window.close()
            app.processEvents()
    sys.excepthook = original_hook
    assert not errors, errors
    print("PASS: autosave, trigger-follow and typing safety; inline edits, exports, pagination, tabs, configuration, isolated acquisition simulation.")


if __name__ == "__main__":
    check()
