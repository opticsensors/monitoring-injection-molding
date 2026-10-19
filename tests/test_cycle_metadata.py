from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import cycle_metadata as meta
from build_legacy_catalog import timestamp_ns, build_sql
from dashboard_metadata import selection_sql, variables


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = meta.operator_settings('test-55t', 'PP', 40, {'limit': 120})
        self.snapshot['config_snapshot'] = {'field_names': ['CH0_T_futaba'], 'saved_indices': [0]}
        self.entry, self.message = meta.finish_capture(self.snapshot, 'session-1', 1, 123,
            1785838969691369500, 2.0, 4.0, [0.01, 1.0], [[30], [31]])

    def test_exact_times_and_independent_snapshot(self):
        self.assertEqual(self.message['samples'][0]['timestamp_ns'], '1785838971701369500')
        self.snapshot['mold_temperature_c'] = 99
        self.assertEqual(self.entry['capture']['mold_temperature_c'], 40)
        self.assertNotIn('material', self.message['samples'][0])
        self.assertEqual(self.entry['capture']['sample_count'], 2)

    def test_measurement_edit_clear_and_capture_retry(self):
        frozen = deepcopy(self.message)
        self.entry['measurements'] = meta.edit_measurements(self.entry['measurements'], 0, 125.5)
        self.assertEqual(self.entry['measurements']['weight_g'], 0)
        update = meta.measurement_message(self.entry)
        self.assertEqual(update['measurements']['revision'], 1)
        self.assertNotIn('samples', update)
        self.assertEqual(frozen['measurements']['weight_g'], None)
        self.entry['measurements'] = meta.edit_measurements(self.entry['measurements'], '', '')
        self.assertIsNone(self.entry['measurements']['length_mm'])

    def test_reject_invalid_numbers_and_machine_topics(self):
        for value in ('nan', 'inf', '-1', True):
            with self.assertRaises(ValueError):
                meta.optional_number(value, 'Weight')
        for machine in ('', 'a/b', '+', 'x\ny'):
            with self.assertRaises(ValueError):
                meta.operator_settings(machine)

    def test_reject_duplicate_missing_and_reversed_samples(self):
        for times, rows in (([0, 0], [[1], [2]]), ([2, 1], [[1], [2]]), ([0, 1], [[1]])):
            with self.assertRaises(ValueError):
                meta.samples_for(self.entry['capture'], times, rows)

    def test_scoped_identity_and_explicit_export(self):
        other = deepcopy(self.entry)
        other['capture']['session_id'] = 'session-2'
        self.assertNotEqual(meta.identity(self.entry['capture']), meta.identity(other['capture']))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cycle.metadata.json'
            meta.export_metadata(path, [self.entry, other])
            result = meta.read_metadata(path)
            self.assertEqual(len(result), 2)
            self.assertNotIn('samples', path.read_text())
            self.assertEqual(result[0]['capture'], self.entry['capture'])
            path.write_text('[]')
            with self.assertRaises(ValueError):
                meta.read_metadata(path)

    def test_legacy_precision_and_sql_literal_safety(self):
        self.assertEqual(timestamp_ns('2026-08-04T10:22:49.691369500Z'), 1785838969691369500)
        self.entry['capture']['material'] = "x'); DROP TABLE cycles; --"
        sql = build_sql([self.entry])
        self.assertIn("x''); DROP TABLE cycles; --", sql)

    def test_dashboard_selection_scopes_and_escapes(self):
        query = selection_sql()
        self.assertIn('${weight_min:sqlstring}', query)
        self.assertNotIn('${weight_min:raw}', query)
        self.assertIn('ORDER BY first_time_ns DESC', query)
        self.assertNotIn('max_cycle_num', query)
        predicate = variables('55t')[-1]['query']
        self.assertIn('influx_predicate', predicate)
        self.assertIn('cycle_key', predicate)

    def test_existing_spool_accepts_both_formats_and_deletes_only_on_broker_ack(self):
        import mqtt_publisher
        publisher = mqtt_publisher.MqttPublisher.__new__(mqtt_publisher.MqttPublisher)
        publisher._stop_event = threading.Event()
        with tempfile.TemporaryDirectory() as directory, patch.object(mqtt_publisher, 'PENDING_DIR', Path(directory)):
            publisher._spill_to_disk(self.message)
            publisher._spill_to_disk([{'cycle_id': 1, 'machine_id': 'old-machine'}])
            publisher._publish = lambda value: False
            publisher._drain_pending()
            files = list(Path(directory).glob('*.json'))
            self.assertEqual(len(files), 2)
            queued = [json.loads(p.read_text()) for p in files]
            self.assertIn(self.message, queued)
            publisher._publish = lambda value: True
            publisher._drain_pending()
            self.assertEqual(list(Path(directory).glob('*.json')), [])


if __name__ == '__main__':
    unittest.main()
