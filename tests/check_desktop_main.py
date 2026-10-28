"""Real main window lifecycle with a fake serial device and controlled worker signals."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets
from scripts.preview_layouts import isolated_preview_state, settle_ui
import cycle_metadata as metadata
import main


class Device:
    DIGITAL_CHANNEL_CONFIG = 8

    def __init__(self, channels, voltage_ranges, dec, deca, srate, output_mode, read_digital=False):
        self.channels, self.dec, self.deca, self.srate = channels, dec, deca, srate
        self.ser = SimpleNamespace(is_open=True)
        self.read_digital = read_digital
        self.configs = self.voltage_range_to_config(voltage_ranges) + [8]
        self.numofchannel = len(self.configs)
        self.numofbyteperscan = 2 * self.numofchannel
        self.applied = []

    def voltage_range_to_config(self, ranges):
        assert all(value == 10 for value in ranges)
        return list(self.channels)

    def config_daq(self):
        self.applied.append((list(self.channels), self.srate, self.dec, self.numofchannel))

    def collect_data(self, method):
        return [0] * self.numofchannel

    def close_serial(self):
        self.ser.is_open = False


def check():
    app = QtWidgets.QApplication([])
    font_id = QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QtGui.QFont(families[0], 10))
    errors = []
    sys.excepthook = lambda kind, value, trace: errors.append(value)
    with isolated_preview_state() as directory, \
         patch.object(main, 'DaqDevice', Device), \
         patch.object(main.DaqThread, 'start', lambda thread: thread.ConnectDaq()), \
         patch.object(main.GraphThread, 'start', lambda thread: None), \
         patch.object(main, 'load_cycle_id', return_value=0), \
         patch.object(main, 'save_cycle_id') as counter, \
         patch('socket.create_connection', side_effect=AssertionError('Network access')), \
         patch.object(QtWidgets.QMessageBox, 'warning', side_effect=AssertionError('Unexpected warning')):
        window = main.MainWindow()
        window._edit_timer.stop()
        window.show()
        settle_ui(app)
        assert not hasattr(window, 'DaqThread') and not window.daq_connected
        assert window.presentation.tabs.count() == 3
        assert not window.startButton.isEnabled()
        window.configure()
        assert window.presentation.connection_button.text() == 'Connect'
        assert window.ModuleSelectWin.mqttCheckBox.isEnabled()
        # Saved settings are staged; Connect uses them, and Start commits them.
        cfg = window.active_configuration()
        cfg.update(channels=[0, 1], channel_types=['T_futaba', 'P_kistler'],
                   plot_channels=[0, 1], voltage_ranges=[10, 10],
                   trigger_mode='Inductive', mqtt_enabled=False, sample_rate_hz=7000)
        window._stage_configuration(cfg)
        window.presentation.connection_button.click()
        device = window.DaqThread.daq_device
        assert window.daq_connected and device.applied[-1] == ([0, 1], 7000, 100, 3)
        assert window.presentation.connection_button.text() == 'Disconnect'
        window.start_monitoring()
        assert window.is_monitoring and window.presentation.mode == 'monitor'
        assert not window.presentation.config_tabs.isEnabled()
        session = window.session_id
        snapshot = deepcopy(window._run_snapshot)
        window.onCycleStarted(1, snapshot, 0.0)
        first = (window.machine_id, session, 1)
        assert window.partEditor.key == first
        window.partEditor.weight.setFocus()
        QtTest.QTest.keyClicks(window.partEditor.weight, '12.5')
        QtTest.QTest.qWait(450)
        assert not window.partEditor.dirty
        journal = json.loads(window.part_drafts_path().read_text())
        assert journal['active'][0]['weight_g'] == 12.5
        x, rows = [0, .01, .02], [[30, 40], [35, 45], [32, 42]]
        y = list(map(list, zip(*rows)))
        window.onCycleEnded(1, x, y, 0.0, {'end_s': .02})
        assert window.cycle_history[first]['measurements']['weight_g'] == 12.5
        window.onCycleStarted(2, snapshot, 1.0)
        second = (window.machine_id, session, 2)
        assert window.partEditor.key == first  # Text focus still belongs to the first part.
        window.partEditor.weight.clearFocus()
        settle_ui(app)
        assert window.partEditor.key == second
        window.partEditor.length.setText('180')
        window.partEditor._edited()
        assert window.partEditor.apply()
        window.onCycleDiscarded(2, .05)
        assert second not in window._part_drafts and window.partEditor.key is None
        window.onCycleStarted(2, snapshot, 2.0)
        assert window.partEditor.key == second
        assert window.part_measurements(second)['length_mm'] is None
        assert json.loads(window.part_drafts_path().read_text())['orphaned'][0]['length_mm'] == 180
        window.stopReading()
        assert window._stopping and not window.presentation.connection_button.isEnabled()
        window.onCycleEnded(2, x, y, 2.0, {'end_s': 2.02, 'status': 'interrupted', 'reason': 'user_stop'})
        window.DaqThread.startsigrec = window.DaqThread.stopsigrec = False
        window.DaqThread._idle.set()  # Controlled worker finished stop_scan.
        window.receiveXYData(x + x, rows + rows, rows + rows, [1] * 3 + [2] * 3)
        assert not window._stopping and window.startButton.isEnabled()
        assert window.presentation.config_tabs.isEnabled()
        # Next is preparation only; neither old buffers nor recording identity change.
        window.next_Session()
        assert window.session_id == session and len(window.xdata) == 6 and not window.is_monitoring
        original = deepcopy(window.cycle_history[first]['capture'])
        window.edit_history_cell(first, 'machine_id', '160t')
        assert window.cycle_history[first]['capture'] == original
        assert metadata.effective_settings(window.cycle_history[first])['machine_id'] == '160t'
        window.show_measurements()
        window.historyPanel.select_key(first)
        table = window.historyPanel.table
        material = next(table.item(row, 4) for row in range(table.rowCount())
                        if table.item(row, 0).data(QtCore.Qt.UserRole) == first)
        material.setText('PA')
        with patch.object(window, 'send_pending_edits') as send:
            window.historyPanel.sendEditsButton.click()  # Before queued itemChanged runs.
            assert metadata.effective_settings(window.cycle_history[first])['material'] == 'PA'
            send.assert_any_call([first], force=True)
        # Reconfigure and export before Start: the stopped session remains intact.
        cfg.update(channels=[0], channel_types=['T_futaba'], plot_channels=[0], voltage_ranges=[10], sample_rate_hz=8000)
        window._stage_configuration(cfg)
        assert window.daq_channels == [0, 1]
        window.save_session_export(directory / 'before-restart.csv')
        window.start_monitoring()
        assert window.session_id != session and window.daq_channels == [0]
        assert window.DaqThread.daq_device is device
        assert device.applied[-1] == ([0], 8000, 100, 2)
        assert device.numofbyteperscan == 4 and window.xdata == []
        assert first in window.cycle_history
        window.stopReading()
        window.DaqThread.startsigrec = window.DaqThread.stopsigrec = False
        window.DaqThread._idle.set()
        window.receiveXYData([], [], [], [])
        window.rem_devs()
        assert not device.ser.is_open and not window.daq_connected
        assert window.presentation.connection_button.text() == 'Connect'
        # Same shared layout in the main entry point, including full-width groups.
        output = ROOT / 'data' / 'validation' / 'desktop-main'
        output.mkdir(parents=True, exist_ok=True)
        for mode in ('monitor', 'history', 'setup'):
            window.presentation.navigate(mode)
            settle_ui(app)
            window.grab().save(str(output / (mode + '.png')))
        window.ModuleSelectWin.tabs.setCurrentIndex(2)
        settle_ui(app)
        assert window.ModuleSelectWin.machineTable.parentWidget().geometry().right() == window.ModuleSelectWin.machineLayoutCombo.parentWidget().geometry().right()
        window.grab().save(str(output / 'machine.png'))
        window.hide()
        assert not errors, errors
    print('PASS: main layout, Connect/Start/Stop/Next/restart, staged physical scan settings, autosave, trigger follow, discarded-number reuse and frozen exports; no hardware/network.')


if __name__ == '__main__':
    check()
