"""One offscreen window: durable edits, offline/disabled uploads, conflicts, exclusion and Save."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from copy import deepcopy
import csv
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5 import QtCore, QtGui, QtWidgets
import cycle_metadata as meta
import main


def check():
    app = QtWidgets.QApplication([])
    font_id = QtGui.QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
    if families:
        app.setFont(QtGui.QFont(families[0], 9))
    with tempfile.TemporaryDirectory() as directory:
        meta.SETTINGS_FILE = Path(directory) / 'run.json'
        meta.EDITS_FILE = Path(directory) / 'pending.json'
        os.environ['MONITORING_UI_SETTINGS_FILE'] = str(Path(directory) / 'ui.ini')
        window = main.MainWindow()
        window._edit_timer.stop()
        window.mqtt_enabled = False
        window.cycle_mode = True
        window.reset_Data_n_Plot_Vars()
        window.runSetup.material.setText('PP')
        window.runSetup.temperature.setText('40')
        window.runSetup.melt.setText('220')
        assert window.prepare_run_setup()
        window.begin_metadata_session()
        window.is_monitoring = True
        assert not window.runSetup.melt.isEnabled()
        with patch.object(QtWidgets.QMessageBox, 'warning'):
            assert not window.apply_run_settings(meta.operator_settings('55t', material='ABS'))
        window.is_monitoring = False
        window.runSetup.set_locked(False)
        snapshot = deepcopy(window._run_snapshot)
        times = [.01, .02]
        rows = [[30 + channel for channel in window.daq_channels] for _ in times]
        keys = []
        for cycle in (1, 2):
            entry, _ = meta.finish_capture(snapshot, window.session_id, cycle, cycle,
                window.session_start_ns, cycle, cycle + .1, times, rows,
                status='interrupted' if cycle == 2 else 'complete')
            key = meta.identity(entry['capture'])
            keys.append(key)
            window.cycle_history[key] = entry
        original = {key: deepcopy(window.cycle_history[key]['capture']) for key in keys}
        window.refresh_measurements()
        panel = window.historyPanel
        assert panel.table.columnCount() == 14
        assert 'Incomplete' in panel.table.item(0, 13).text()
        assert panel.table.item(0, 13).background().color().name() == '#ffe0ad'
        sent = []
        publisher = SimpleNamespace(publish_records=sent.append, stop=lambda **kw: None,
                                    client=SimpleNamespace(is_connected=lambda: False))
        def ensure(**kwargs):
            window.mqtt_publisher = publisher
        window._ensure_mqtt_publisher = ensure
        window.show_measurements()
        assert window.update_reviews(keys, {'mold_temperature_c': 80, 'melt_temperature_c': 230})
        assert not sent
        assert meta.EDITS_FILE.exists()
        assert all(window.cycle_history[key]['capture'] == original[key] for key in keys)
        assert 'Recorded as: 40' in panel.table.item(0, 5).toolTip()
        assert 'Pending sync' in panel.table.item(0, 13).toolTip()
        # A failed disk write must not report success or change any selected row.
        before = deepcopy(window.cycle_history)
        with patch.object(meta, 'save_pending_edits', side_effect=OSError('disk full')), \
             patch.object(QtWidgets.QMessageBox, 'warning'):
            assert not window.update_reviews(keys, {'material': 'ABS'})
        assert window.cycle_history == before
        assert window.update_reviews([keys[0]], excluded=True)
        assert keys[0] in window.cycle_history and panel.table.rowCount() == 1
        panel.showExcluded.setChecked(True)
        assert panel.table.rowCount() == 2
        # A stopped session exports both waveforms, marked rather than deleted.
        window.xdata = times * 2
        window.ydata = rows * 2
        window.cycle_numbers_data = [1, 1, 2, 2]
        path = Path(directory) / 'session.csv'
        window.save_session_export(path)
        with path.open(newline='', encoding='utf8') as stream:
            waves = list(csv.DictReader(stream))
        with path.with_suffix('.cycles.csv').open(newline='', encoding='utf8') as stream:
            summaries = list(csv.DictReader(stream))
        assert len(waves) == 4 and waves[0]['excluded'] == 'True'
        assert summaries[0]['excluded'] == 'True' and summaries[0]['mold_temperature_c'] == '80.0'
        saved_capture = json.loads(path.with_suffix('.metadata.json').read_text(encoding='utf8'))['cycles'][0]['capture']
        assert saved_capture == original[keys[0]]
        # Simulate restart by rebuilding RAM solely from the saved edit journal.
        window.partEditor.set_entry(None)
        window.cycle_history.clear()
        window.restore_pending_edits()
        window.refresh_measurements()
        assert set(window.cycle_history) == set(keys) and not sent
        assert window.cycle_history[keys[0]]['review']['excluded']
        # Automatic upload off remains off. An explicit Send queues only the edits.
        window.send_pending_edits(keys)
        assert not sent
        window.send_pending_edits(keys, force=True)
        assert len(sent) == 2 and all(m['kind'] == 'review' for m in sent)
        assert not publisher.auto_drain and not window.mqtt_enabled
        assert len(meta.load_pending_edits()) == 2  # Broker enqueue is not DB confirmation.
        remote = deepcopy(window.cycle_history[keys[0]])
        remote.pop('local_review_edit', None)
        remote['waveform_status'] = 'stored'
        assert window.merge_server_history([remote])
        assert not window.cycle_history[keys[0]].get('local_review_edit')
        assert len(meta.load_pending_edits()) == 1
        # An old readback with the same values cannot clear a newer pending revision.
        previous = deepcopy(window.cycle_history[keys[1]])
        previous['review']['revision'] = 0
        assert window.merge_server_history([previous])
        assert window.cycle_history[keys[1]]['local_review_edit']
        # A competing update is retained for an explicit operator decision.
        remote = deepcopy(window.cycle_history[keys[1]])
        remote['review'] = meta.edit_review(remote['review'], {'material': 'ABS'}, True)
        assert window.merge_server_history([remote])
        assert window.cycle_history[keys[1]]['edit_conflict']
        window.mqtt_enabled = True
        # Saving an unrelated measurement must not clear/re-send the review conflict.
        before_count = len(sent)
        assert window.update_measurements(keys[1], 1, '')
        assert len(sent) == before_count + 1 and sent[-1]['kind'] == 'measurements'
        assert window.cycle_history[keys[1]]['edit_conflict']
        before_count = len(sent)
        window.send_pending_edits(keys)
        assert len(sent) == before_count
        window.send_pending_edits([keys[1]], force=True)
        review = [m['review'] for m in sent if m['kind'] == 'review'][-1]
        assert review['revision'] > remote['review']['revision']
        assert review['settings']['material'] == 'ABS'  # Preserve untouched server correction.
        assert review['settings']['mold_temperature_c'] == 80
        assert review['excluded']  # Preserve untouched server exclusion.
        # A remote exclusion hides an existing old row on this PC after refresh.
        confirmed = deepcopy(window.cycle_history[keys[1]])
        assert window.merge_server_history([confirmed])
        panel.showExcluded.setChecked(False)
        assert panel.table.rowCount() == 0
        window.mqtt_enabled = False
        assert window.update_reviews([keys[0]], excluded=False)
        assert panel.table.rowCount() == 1
        # Part autosave works during acquisition without applying session settings.
        window.partEditor.set_entry(keys[0])
        window.is_monitoring = True
        window.runSetup.set_locked(True)
        window.partEditor.weight.setText('12.5')
        window.partEditor._edited()
        assert window.partEditor.dirty
        assert window.partEditor.apply()
        assert window.cycle_history[keys[0]]['measurements']['weight_g'] == 12.5
        assert window.cycle_history[keys[0]]['capture'] == original[keys[0]]
        assert not window.partEditor.dirty and not window.partEditor.saveButton.isVisible()
        window.is_monitoring = False
        window.runSetup.set_locked(False)
        # DAQ configuration does not wipe a stopped operator's unfinished entry.
        window.runSetup.material.setText('Typed but not started')
        window.cnfg_Sig_Received(window.active_configuration())
        assert window.runSetup.material.text() == 'Typed but not started'
        panel.showExcluded.setChecked(True)
        window.resize(1550, 930)
        window.show()
        app.processEvents()
        output = ROOT / 'data/validation/cycle-edits.png'
        output.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(output))
        window.hide()
    print('PASS: locked session setup, melt, batch correction, durable offline edits, disabled/explicit sending, conflict merge, exclusion/restore, marked exports and independent part autosave.')


if __name__ == '__main__':
    check()
