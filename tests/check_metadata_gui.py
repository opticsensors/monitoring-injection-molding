"""One offscreen QApplication; synthetic scans only, no DAQ or MQTT connection."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import csv
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase, QFont
import cycle_metadata as meta
import main


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def check_export(path, entries):
    samples = read_csv(path)
    summaries = read_csv(path.with_suffix('.cycles.csv'))
    restored = meta.read_metadata(path.with_suffix('.metadata.json'))
    expected = {(e['capture']['session_id'], str(e['capture']['cycle_id'])): e for e in entries}
    assert len(summaries) == len(restored) == len(expected)
    assert {(s['session_id'], s['cycle_id']) for s in samples} == set(expected)
    assert 'machine_id' not in samples[0] and 'sample_index' not in samples[0]
    assert 'time_s' in samples[0] and 'CH0_T_futaba' in samples[0]
    for summary in summaries:
        key = (summary['session_id'], summary['cycle_id'])
        capture = expected[key]['capture']
        rows = [s for s in samples if (s['session_id'], s['cycle_id']) == key]
        assert len(rows) == int(summary['sample_count']) == capture['sample_count']
        assert summary['machine_id'] == capture['machine_id']
        assert summary['acquisition_status'] == capture['status']
        assert summary['mode'] == capture['mode']
        assert rows[0]['timestamp_ns'] == summary['first_time_ns'] == capture['first_time_ns']
        assert rows[-1]['timestamp_ns'] == summary['last_time_ns'] == capture['last_time_ns']
        assert all(s['session_cycle'] == summary['session_cycle'] for s in rows)
    assert [e['capture'] for e in restored] == [e['capture'] for e in entries]
    assert [e['measurements'] for e in restored] == [e['measurements'] for e in entries]
    return summaries


def check():
    qt_errors = []
    original_hook = sys.excepthook
    def record_exception(kind, value, traceback):
        qt_errors.append(value)
        original_hook(kind, value, traceback)
    sys.excepthook = record_exception
    app = QApplication([])
    def unexpected_warning(_parent, title, message):
        raise AssertionError(f'Unexpected GUI warning: {title}: {message}')
    main.QtWidgets.QMessageBox.warning = unexpected_warning
    # Windows offscreen Qt needs an explicit font to render inspection artifacts.
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 9))
    with tempfile.TemporaryDirectory() as directory:
        os.environ["MONITORING_UI_SETTINGS_FILE"] = str(Path(directory) / "ui.ini")
        meta.SETTINGS_FILE = Path(directory) / 'run_setup.json'
        meta.EDITS_FILE = Path(directory) / 'edits.json'
        main.load_cycle_id = lambda: 0
        main.save_cycle_id = lambda cid: None
        window = main.MainWindow()
        window._edit_timer.stop()  # No automatic connection attempts in synthetic tests.
        window.daq_channels = [0]
        window.voltage_ranges = [10]
        window.channel_types = ['T_futaba']
        window.nplots = 1
        window.plot_channels = [0]
        for mode in ('Inductive', 'Machine signal', 'Machine mold position', 'Manual'):
            window.trigger_mode = mode
            window.cycle_mode = True
            window.completed_cycles_data = []
            window.mqtt_enabled = False
            window.apply_run_settings(meta.operator_settings('test-machine', 'PP, "grade A"', 40, {'limit': 120}))
            window.begin_metadata_session()
            data = queue.Queue()
            graph = main.GraphThread(data, ['CH0'], .025, main_window=window)
            window.graphThread = graph
            window.session_cycle_base = graph.cycle_base
            graph.cycleStartedSig.connect(window.onCycleStarted)
            graph.cycleEndedSig.connect(window.onCycleEnded)
            graph.cycleDiscardedSig.connect(window.onCycleDiscarded)
            graph.graphEndSig.connect(window.receiveXYData)
            # Programmatic text changes do not alter a running session's snapshot.
            graph.cycleStartedSig.connect(lambda *_: window.runSetup.material.setText('Not applied'))
            window.is_monitoring = True
            assert all(not field.isEnabled() for field in (window.runSetup.machine, window.runSetup.material,
                window.runSetup.temperature, window.runSetup.melt, window.runSetup.speed))
            for stamp, active in [(0, False), (1, True), (1.1, True), (3.2, True), (3.3, False),
                                  (4, True), (4.1, True), (6.2, True), (6.3, False),
                                  (7, True), (7.1, True), (7.5, True)]:
                high = not active if mode == 'Machine mold position' else active
                data.put([3276, 4096 if high else 0, stamp])
            graph.run()
            entries = [e for e in window.cycle_history.values() if e['capture']['session_id'] == window.session_id]
            assert len(entries) == 3, (mode, len(entries))
            assert window.partEditor.key == meta.identity(entries[-1]['capture'])
            assert entries[0]['capture']['mold_temperature_c'] == 40
            assert entries[1]['capture']['mold_temperature_c'] == 40
            assert entries[2]['capture']['status'] == 'interrupted'
            assert all(e['delivery'] == 'Not sent' for e in entries)
            # Export must use captured settings even after setup changes, and use
            # the latest measurements (including a real zero) at the time of Save.
            first_key = meta.identity(entries[0]['capture'])
            window.update_measurements(first_key, 0, 125.5)
            window.apply_run_settings(meta.operator_settings('next-machine', 'PA', 80, {'limit': 200}))
            path = Path(directory) / f'{mode}.csv'
            window.save_session_export(path)
            summaries = check_export(path, entries)
            assert [s['material'] for s in summaries] == ['PP, "grade A"'] * 3
            assert [float(s['mold_temperature_c']) for s in summaries] == [40, 40, 40]
            assert [float(s['pressure_limit_bar']) for s in summaries] == [120, 120, 120]
            assert float(summaries[0]['weight_g']) == 0 and float(summaries[0]['length_mm']) == 125.5
            assert summaries[1]['weight_g'] == summaries[1]['length_mm'] == ''
            original_waveform = path.read_bytes()
            window.update_measurements(first_key, '', '')
            window.save_session_export(path)
            summaries = check_export(path, entries)
            assert summaries[0]['weight_g'] == summaries[0]['length_mm'] == ''
            assert summaries[0]['metadata_revision'] == '2'
            assert path.read_bytes() == original_waveform

        # Sending after changing the current trigger mode still uses the recorded
        # session mode and machine, without contacting a broker.
        sent = []
        window.mqtt_publisher = SimpleNamespace(publish_records=sent.append)
        window._ensure_mqtt_publisher = lambda **kwargs: None
        window._session_streamed = False
        window.cycle_mode = False
        window.send_Session_to_cloud()
        assert len(sent) == 3 and all(m['capture']['mode'] == 'cycle' for m in sent)
        assert all(m['capture']['machine_id'] == 'test-machine' for m in sent)
        # Wall/elapsed time zero is paired after setup, and the start slot retains it.
        window.DaqThread = SimpleNamespace(_idle=threading.Event())
        with patch('metadata_controller.time.perf_counter', side_effect=[100.0, 100.002]), \
             patch('metadata_controller.time.time_ns', return_value=1792400000000000001):
            window.start_acquisition_clock()
        assert window.session_start_ns == 1792400000000000001
        assert abs(window.DaqThread.start_time - 100.001) < 1e-9
        main.DaqThread.startSignalRec(window.DaqThread)
        assert window.DaqThread.startsigrec and not window.DaqThread.stopsigrec
        assert abs(window.DaqThread.start_time - 100.001) < 1e-9
        del window.DaqThread

        # Server import makes same-revision conflicts recoverable, with an
        # explicit Cancel path that preserves the user's unsent local edit.
        server_entry = json.loads(json.dumps(entries[0]))
        server_entry['measurements']['weight_g'] = 8
        server_file = Path(directory) / 'server.metadata.json'
        meta.export_metadata(server_file, [server_entry])
        document = json.loads(server_file.read_text(encoding='utf-8'))
        document['source'] = 'server'
        server_file.write_text(json.dumps(document), encoding='utf-8')
        with patch.object(main.QtWidgets.QFileDialog, 'getOpenFileName', return_value=(str(server_file), '')), \
             patch.object(main.QtWidgets.QMessageBox, 'question', return_value=main.QtWidgets.QMessageBox.No):
            window.import_measurements()
        assert window.cycle_history[first_key]['measurements']['weight_g'] is None
        with patch.object(main.QtWidgets.QFileDialog, 'getOpenFileName', return_value=(str(server_file), '')), \
             patch.object(main.QtWidgets.QMessageBox, 'question', return_value=main.QtWidgets.QMessageBox.Yes):
            window.import_measurements()
        assert window.cycle_history[first_key]['measurements']['weight_g'] == 8

        # A failure while writing a companion must leave the existing file set
        # intact, and staging files must be removed after the failed Save.
        saved_files = (path, path.with_suffix('.cycles.csv'), path.with_suffix('.metadata.json'))
        before = {p: p.read_bytes() for p in saved_files}
        with patch.object(meta, 'export_metadata', side_effect=OSError('simulated write failure')):
            try:
                window.save_session_export(path)
            except OSError:
                pass
            else:
                raise AssertionError('Export should report the write failure')
        assert all(p.read_bytes() == content for p, content in before.items())
        assert not list(Path(directory).glob('.session-export-*'))

        # Continuous recordings have one summary with cycle_id=0, not a part.
        window.trigger_mode = 'None'
        window.cycle_mode = False
        window.apply_run_settings(meta.operator_settings('continuous-machine'))
        window.begin_metadata_session()
        data = queue.Queue()
        graph = main.GraphThread(data, ['CH0'], .025, main_window=window)
        window.graphThread = graph
        graph.graphEndSig.connect(window.receiveXYData)
        for stamp in (0, .01, .02):
            data.put([3276, 0, stamp])
        graph.run()
        entries = [e for e in window.cycle_history.values() if e['capture']['session_id'] == window.session_id]
        path = Path(directory) / 'continuous.csv'
        window.save_session_export(path)
        summaries = check_export(path, entries)
        assert len(summaries) == 1 and summaries[0]['cycle_id'] == summaries[0]['session_cycle'] == '0'
        assert summaries[0]['mode'] == 'continuous' and summaries[0]['sample_count'] == '3'
        assert all(summaries[0][field] == '' for field in
                   ('material', 'mold_temperature_c', 'pressure_limit_bar', 'weight_g', 'length_mm'))
        sent.clear()
        window._session_streamed = False
        window.cycle_mode = True
        window.send_Session_to_cloud()
        assert len(sent) == 1 and sent[0]['capture']['mode'] == 'continuous'
        window.show()
        window.resize(1400, 850)
        app.processEvents()
        window.show_measurements()
        app.processEvents()
        # Optional visual artifact for local inspection; never a recording archive.
        output = ROOT / 'data' / 'validation'
        output.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(output / 'metadata-main.png'))
        window._measurements_dialog.grab().save(str(output / 'metadata-history.png'))
        assert window._measurements_dialog.table.rowCount() == 12  # Continuous capture is not a part.
        assert window.daq_srate == 6000 and window.daq_dec == 100
        window._measurements_dialog.hide()
        window.hide()
        assert not qt_errors, qt_errors
        sys.excepthook = original_hook
        print('PASS: four trigger modes, interrupted/continuous captures, paired CSV joins, frozen settings, '
              'manual Send after reconfiguration, shared clock, server conflict reconciliation, '
              'measurement edits/clearing, exact timestamps and staged-write failure; no hardware/network.')


if __name__ == '__main__':
    check()
