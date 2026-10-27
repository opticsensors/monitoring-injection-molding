"""Synthetic serial bytes through the installed driver; never open a DAQ port."""
import json
from itertools import count
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_acquisition import AcquisitionAudit, instrument_acquisition, write_report
import config

try:
    from daq_connectivity import Daq_serial
except ImportError:
    Daq_serial = None


class SerialBytes:
    def __init__(self, scans):
        self.data = b''.join(struct.pack('<hhh', *row) for row in scans)

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, size):
        result, self.data = self.data[:size], self.data[size:]
        return result


@unittest.skipIf(Daq_serial is None, 'Install the sibling daq_connectivity package for driver tests')
class AcquisitionAuditTests(unittest.TestCase):
    def setUp(self):
        # Bypass __init__: no serial.Serial(), discovery, configuration or device I/O.
        self.device = object.__new__(Daq_serial)
        self.device.channels = [0, 1]
        self.device.read_digital = True
        self.device.numofchannel = 3
        self.device.numofbyteperscan = 6
        self.device.output_mode = 'binary'
        self.device.srate, self.device.dec, self.device.deca = 6000, 100, 1
        self.device.ser = SerialBytes([])
        self.audit = AcquisitionAudit(clock=count(0, .01).__next__)

    def read(self, scans, session='session-1', method=1):
        self.device.ser = SerialBytes(scans)
        return self.audit.observe(self.device, lambda: self.device.collect_data(method), session, method)

    def stats(self, session='session-1'):
        return self.audit.report()['sessions'][session]

    def test_actual_driver_newest_scan_and_discard_count(self):
        scans = [(10, 20, 4096), (11, 21, 4096), (-12, 22, 0)]
        self.assertEqual(self.read(scans), list(scans[-1]))
        stats = self.stats()
        self.assertEqual((stats['complete_scans_read'], stats['scans_returned'],
                          stats['scans_not_returned']), (3, 1, 2))
        self.assertEqual(stats['result'], 'LOSS_OBSERVED')
        self.assertEqual(stats['first_nonempty_read_scans'], 3)
        self.assertEqual(stats['scans_not_returned_after_first_nonempty_read'], 0)
        self.read(scans[:2])
        self.assertEqual(self.stats()['scans_not_returned_after_first_nonempty_read'], 1)

    def test_single_scans_empty_reads_timing_and_session_separation(self):
        self.assertIsNone(self.read([]))
        self.assertEqual(self.stats()['result'], 'NO_DATA')
        self.read([(1, 2, 4096)])
        self.read([])
        self.read([(3, 4, 0)])
        stats = self.stats()
        self.assertEqual(stats['result'], 'NO_LOSS_OBSERVED')
        self.assertEqual(stats['empty_calls'], 2)
        self.assertAlmostEqual(stats['max_return_gap_seconds'], .04)
        self.assertAlmostEqual(stats['mean_return_gap_seconds'], .04)
        self.assertAlmostEqual(stats['scans_returned_per_second'], 2 / .07)
        self.read([(5, 6, 0)], session='session-2')
        self.assertEqual(self.stats()['scans_returned'], 2)
        self.assertEqual(self.stats('session-2')['scans_returned'], 1)

    def test_read_exception_preserved_and_serial_method_restored(self):
        self.device.ser = SerialBytes([(1, 2, 0)])
        def broken_read(size):
            raise OSError('synthetic read failure')
        self.device.ser.read = broken_read
        with self.assertRaisesRegex(OSError, 'synthetic read failure'):
            self.audit.observe(self.device, lambda: self.device.collect_data(1), 'session-1', 1)
        self.assertIs(self.device.ser.read, broken_read)
        self.assertEqual(self.stats()['read_errors'], 1)
        self.assertEqual(self.stats()['result'], 'REVIEW_REQUIRED')

    def test_partial_read_and_unsupported_flat_batch_require_review(self):
        self.device.ser = SerialBytes([(1, 2, 0)])
        original = self.device.ser.read
        self.device.ser.read = lambda size: original(4)
        self.audit.observe(self.device, lambda: self.device.collect_data(1), 'partial', 1)
        self.assertEqual(self.stats('partial')['partial_reads'], 1)
        self.assertEqual(self.stats('partial')['result'], 'REVIEW_REQUIRED')
        self.read([(1, 2, 0), (3, 4, 0)], session='flat', method=2)
        self.assertEqual(self.stats('flat')['result'], 'REVIEW_REQUIRED')

    def test_only_worker_acquisition_is_observed_and_patches_are_restored(self):
        class Worker:
            def Read_and_Process_DaqData(worker):
                return worker.daq_device.collect_data(1)
        worker = Worker()
        worker.daq_device = self.device
        application = SimpleNamespace(DaqThread=Worker, daq=SimpleNamespace(Daq_serial=Daq_serial))
        window = SimpleNamespace(session_id='session-1')
        original_collect = Daq_serial.collect_data
        original_acquire = Worker.Read_and_Process_DaqData
        with instrument_acquisition(application, window, self.audit):
            self.device.ser = SerialBytes([(1, 2, 0)])
            self.device.collect_data(1)  # pre-start trigger check
            self.assertFalse(self.audit.report()['sessions'])
            self.device.ser = SerialBytes([(3, 4, 0), (5, 6, 4096)])
            original_read = self.device.ser.read
            self.assertEqual(worker.Read_and_Process_DaqData(), [5, 6, 4096])
            self.assertEqual(self.device.ser.read, original_read)
            self.assertEqual(self.stats()['scans_not_returned'], 1)
        self.assertIs(Daq_serial.collect_data, original_collect)
        self.assertIs(Worker.Read_and_Process_DaqData, original_acquire)


class ReportAndRangeTests(unittest.TestCase):
    def test_report_is_valid_json_before_acquisition_and_replaces_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            audit = AcquisitionAudit()
            write_report(path, audit.report())
            self.assertEqual(json.loads(path.read_text())['sessions'], {})
            write_report(path, audit.report(finished=True))
            self.assertTrue(json.loads(path.read_text())['launcher_finished'])
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_non_ten_volt_config_is_normalized_to_selected_channels_without_rewriting_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            original = json.dumps({'channels': [0, 2], 'voltage_ranges': [5, .2], 'sample_rate_hz': 6000})
            path.write_text(original)
            with patch.object(config, 'CONFIG_DEFAULTS_FILE', path), self.assertLogs('config', 'WARNING'):
                loaded = config.load_config_defaults()
            self.assertEqual(loaded['voltage_ranges'], [10, 10])
            self.assertEqual(loaded['sample_rate_hz'], 6000)
            self.assertEqual(path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
