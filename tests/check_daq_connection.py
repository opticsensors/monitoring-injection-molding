"""Exercise missing-device failure/retry through the real driver and Qt worker."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import importlib
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5 import QtTest, QtWidgets
from scripts.preview_layouts import isolated_preview_state
import main


def wait_for_result(app, window):
    deadline = time.monotonic() + 3
    while window._connecting and time.monotonic() < deadline:
        QtTest.QTest.qWait(10)
    app.processEvents()
    assert not window._connecting, 'Connect did not finish'


def check():
    app = QtWidgets.QApplication([])
    errors = []
    previous_hook = sys.excepthook
    sys.excepthook = lambda kind, value, trace: errors.append(value)
    driver = importlib.import_module('daq_connectivity.daq_serial')
    with isolated_preview_state(), \
         patch('socket.create_connection', side_effect=AssertionError('Network access')), \
         patch.object(QtWidgets.QMessageBox, 'warning', side_effect=AssertionError('Unexpected popup')):
        window = main.MainWindow()
        window._edit_timer.stop()
        window.configure()
        window.show()
        app.processEvents()
        button = window.presentation.connection_button
        try:
            # Real config_daq/discovery, no ports. A regression into the driver's
            # retry loop fails immediately instead of hanging this test process.
            with patch.object(driver.serial.tools.list_ports, 'comports', return_value=[]) as ports, \
                 patch.object(driver.time, 'sleep', side_effect=AssertionError('Unbounded discovery retry')) as retry, \
                 patch.object(driver.serial.Serial, 'open', side_effect=AssertionError('Opening hardware')):
                for attempt in range(2):
                    button.click()
                    wait_for_result(app, window)
                    assert window.DaqThread.wait(1000), 'Failed connection worker did not exit'
                    assert ports.call_count == attempt + 1
                    retry.assert_not_called()
                    assert not window.daq_connected and not window.DaqThread.IsConnected
                    assert button.isEnabled() and button.text() == 'Connect'
                    assert window.presentation.config_tabs.isEnabled()
                    assert not window.startButton.isEnabled()
                    assert 'DAQ not found. Connect the DAQ by USB and try again.' in window.messagesBox.toPlainText()
                assert window.messagesBox.toPlainText().count('DAQ connection failed:') == 2

            # Access errors also finish and expose the reason in the bottom log.
            candidate = SimpleNamespace(device='COM_TEST', hwid='USB VID:PID=0683:1456')
            with patch.object(driver.serial.tools.list_ports, 'comports', return_value=[candidate]), \
                 patch.object(driver.serial.Serial, 'open', side_effect=PermissionError('Port is already in use')):
                button.click()
                wait_for_result(app, window)
                assert window.DaqThread.wait(1000)
                assert 'Port is already in use' in window.messagesBox.toPlainText()
                assert button.isEnabled() and not window.startButton.isEnabled()

            # A failed configuration releases a port opened before IsConnected.
            port = SimpleNamespace(is_open=True)
            port.close = Mock(side_effect=lambda: setattr(port, 'is_open', False))
            def configuration_failure(device):
                device.ser = port
                raise RuntimeError('Scan configuration failed')
            with patch.object(main.DaqDevice, 'config_daq', configuration_failure), \
                 patch.object(main.DaqDevice, 'close_serial', side_effect=OSError('USB disappeared')):
                button.click()
                wait_for_result(app, window)
                assert window.DaqThread.wait(1000)
                port.close.assert_called_once()
                assert not port.is_open and button.isEnabled()
                assert 'Scan configuration failed' in window.messagesBox.toPlainText()

            # Retry can subsequently succeed and Disconnect still releases USB.
            port.is_open = True
            with patch.object(main.DaqDevice, 'config_daq', lambda device: setattr(device, 'ser', port)), \
                 patch.object(main.DaqDevice, 'close_serial', lambda device: device.ser.close()):
                button.click()
                wait_for_result(app, window)
                assert window.daq_connected and window.startButton.isEnabled()
                assert window.DaqThread.isRunning() and button.text() == 'Disconnect'
                button.click()
                assert window.DaqThread.wait(1000)
                assert not window.daq_connected and not port.is_open
                assert button.text() == 'Connect' and button.isEnabled()
            assert not errors, errors
        finally:
            window.rem_devs()
            window.hide()
            sys.excepthook = previous_hook
    print('PASS: absent DAQ fails once, worker exits, log shows the cause, Connect retries, failed ports are released, later connection/disconnection succeeds.')


if __name__ == '__main__':
    check()
