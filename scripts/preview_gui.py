"""Open the GUI with simulated cycles; no DAQ, MQTT or server requests."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, help="Render offscreen into this directory and exit.")
    args = parser.parse_args()
    if args.screenshots:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import numpy as np
    from PyQt5 import QtCore, QtGui, QtWidgets
    import cycle_metadata as meta
    import main as application
    app = QtWidgets.QApplication([])
    font_id = QtGui.QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QtGui.QFont(families[0], 9))
    with tempfile.TemporaryDirectory(prefix="monitoring-preview-") as directory:
        meta.SETTINGS_FILE = Path(directory) / "preferences.json"
        os.environ["MONITORING_UI_SETTINGS_FILE"] = str(Path(directory) / "ui.ini")
        window = application.MainWindow()
        window.mqtt_enabled = False
        window.send_measurements = lambda *a, **kw: window.statusbar.showMessage("Preview: uploads are disabled.")
        window.load_server_history = lambda: window.statusbar.showMessage("Preview: six simulated cycles are loaded.", 3000)
        window.setWindowTitle("Injection monitoring — GUI v3 PREVIEW / simulated cycles")
        window.resize(1500, 920)
        window.runSetup.set_values(meta.operator_settings("55t", "PP · demo", 40, injection_speed_mm_s=35))
        window.reset_Data_n_Plot_Vars()
        window.SubplotSetup()
        keys = []
        x = np.linspace(0, 8, 801)
        for n in range(6):
            pulse = np.exp(-((x - (1.5 + n*.025))/.7)**2)
            signals = {
                "T_futaba": 30+(135+n*3)*pulse,
                "P_kistler": (450+n*12)*np.exp(-((x-2.2)/1.3)**2),
                "P_machine": (650+n*15)*np.exp(-((x-1.9)/1.5)**2),
                "vel_screw": (35+n)*np.exp(-((x-1.5)/.8)**2),
                "pos_screw": 80-55/(1+np.exp(-(x-2)*2))}
            y = np.array([signals[t] * (1-.035*(i%2)) for i,t in enumerate(window.channel_types)]).T
            snapshot = deepcopy(window._run_snapshot)
            snapshot.update(material="PP · demo", mold_temperature_c=40,
                            injection_speed_mm_s=35+n, machine_id="55t" if n<3 else "160t")
            entry, _ = meta.finish_capture(snapshot, "preview_"+snapshot["machine_id"],
                n%3+1, 31+n, time.time_ns()-(6-n)*60000000000, 0, 8, x.tolist(), y.tolist())
            entry["delivery"] = "Preview only · not uploaded"
            key = meta.identity(entry["capture"])
            keys.append(key)
            window.cycle_history[key] = entry
            fields = entry["capture"]["config_snapshot"]["field_names"]
            window.remember_waveform(key, dict(time_s=x, fields=fields,
                values={f:y[:,i] for i,f in enumerate(fields)}))
        window.refresh_measurements()
        window.ploter(x.tolist(), y.T.tolist())
        window.updateYAxisRanges((y.min(axis=0)-5).tolist(), (y.max(axis=0)*1.1).tolist())
        window.current_cycle = 36
        window.session_cycle_base = 33
        window._set_cycle_readout(36)
        window._set_plot_live(False)
        for button in (window.configurationButton, window.findDeviceButton, window.removeDeviceButton,
                       window.startButton, window.nextButton, window.stopButton, window.saveSessionButton,
                       window.sendSessionButton):
            button.setEnabled(False)
        window.menubar.setEnabled(False)
        window.messagesBox.setPlainText("PREVIEW · Simulated cycles. No acquisition, server connection or upload.")
        window.show()
        app.processEvents()
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(args.screenshots / "live.png"))
            window.show_measurements()
            for row in range(2):
                window.historyPanel.table.item(row, 0).setCheckState(QtCore.Qt.Checked)
            app.processEvents()
            window.grab().save(str(args.screenshots / "history.png"))
            window.plot_history_cycles(window.historyPanel.selected_cycles())
            app.processEvents()
            window.grab().save(str(args.screenshots / "compare.png"))
            window.parametersButton.setChecked(False)
            app.processEvents()
            window.grab().save(str(args.screenshots / "expanded.png"))
            window.parametersButton.setChecked(True)
            window.workspaceTabs.currentWidget().plotTabs.setCurrentIndex(1)
            app.processEvents()
            window.grab().save(str(args.screenshots / "machine.png"))
            print(args.screenshots.resolve())
            window.hide()
        else:
            app.exec_()


if __name__ == "__main__":
    main()
