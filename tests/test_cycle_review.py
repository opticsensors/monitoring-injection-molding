from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import cycle_metadata as meta
import connection_settings


class CycleReviewTests(unittest.TestCase):
    def setUp(self):
        snapshot = meta.operator_settings('55t', 'PP', 40, injection_speed_mm_s=35, melt_temperature_c=220)
        snapshot['config_snapshot'] = {'field_names': ['CH0_T_futaba'], 'saved_indices': [0]}
        self.entry, _ = meta.finish_capture(snapshot, 'review-test', 1, 1,
            1785838969691369500, 0, 1, [.01, .02], [[30], [31]])

    def test_melt_preferences_bounds_and_old_settings(self):
        self.assertIsNone(meta.operator_settings('55t')['melt_temperature_c'])
        self.assertEqual(meta.operator_settings('55t', melt_temperature_c=0)['melt_temperature_c'], 0)
        for value in (-274, 'nan', True):
            with self.assertRaises(ValueError):
                meta.operator_settings('55t', melt_temperature_c=value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.json'
            settings = meta.operator_settings('55t', melt_temperature_c=230)
            meta.write_json(path, settings)
            self.assertEqual(meta.load_preferences('160t', path), settings)

    def test_correction_does_not_change_capture_and_clears_explicitly(self):
        original = deepcopy(self.entry['capture'])
        review = meta.edit_review(meta.new_review(), {'mold_temperature_c': 80, 'melt_temperature_c': 0}, True)
        self.entry['review'] = review
        message = meta.review_message(self.entry)
        self.entry['review'] = meta.edit_review(review, {'material': None}, False)
        self.assertEqual(self.entry['capture'], original)
        self.assertEqual(meta.effective_settings(self.entry)['mold_temperature_c'], 80)
        self.assertIsNone(meta.effective_settings(self.entry)['material'])
        self.assertEqual(self.entry['review']['revision'], 2)
        self.assertTrue(message['review']['excluded'])
        self.assertNotIn('samples', message)

    def test_export_retains_excluded_rows_and_effective_values(self):
        self.entry['review'] = meta.edit_review(meta.new_review(), {'mold_temperature_c': 80}, True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cycles.csv'
            meta.export_cycle_summary(path, [self.entry])
            with path.open(newline='', encoding='utf8') as stream:
                row, = csv.DictReader(stream)
            self.assertEqual(row['mold_temperature_c'], '80.0')
            self.assertEqual(row['melt_temperature_c'], '220.0')
            self.assertEqual(row['excluded'], 'True')
            self.assertEqual(self.entry['capture']['mold_temperature_c'], 40)

    def test_pending_edits_survive_restart_without_waveforms(self):
        self.entry.update(review=meta.edit_review(meta.new_review(), excluded=True), local_review_edit=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pending.json'
            meta.save_pending_edits([self.entry], path)
            restored, = meta.load_pending_edits(path)
            self.assertEqual(restored['review'], self.entry['review'])
            self.assertEqual(restored['capture'], self.entry['capture'])
            self.assertNotIn('samples', path.read_text())
            self.entry.pop('local_review_edit')
            meta.save_pending_edits([self.entry], path)
            self.assertEqual(meta.load_pending_edits(path), [])

    def test_shared_env_and_no_process_user_collision(self):
        import mqtt_publisher
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('BROKER=test.invalid\nPORT=1883\nuser=plant\npassword=test\n'
                            'HISTORY_URL=http://test.invalid:1880\nHISTORY_TOKEN=test-only\n')
            with patch.object(connection_settings, 'ENV_FILE', path), patch.object(mqtt_publisher, 'ENV_FILE', path):
                self.assertEqual(connection_settings.history_settings(), ('http://test.invalid:1880', 'test-only'))
                self.assertEqual(mqtt_publisher.load_settings()['user'], 'plant')
            path.write_text('BROKER=test.invalid\nPORT=1883\n')
            with patch.object(connection_settings, 'ENV_FILE', path), self.assertRaisesRegex(ValueError, 'HISTORY_TOKEN'):
                connection_settings.history_settings()

    def test_metadata_topics_and_upload_off_shutdown(self):
        import mqtt_publisher
        publisher = mqtt_publisher.MqttPublisher.__new__(mqtt_publisher.MqttPublisher)
        publisher.topic = '160t/sensors'
        receipt = SimpleNamespace(wait_for_publish=lambda **kw: None, is_published=lambda: True)
        publisher.client = SimpleNamespace(is_connected=lambda: True, publish=Mock(return_value=receipt))
        self.entry['review'] = meta.edit_review(meta.new_review(), excluded=True)
        message = meta.review_message(self.entry)
        self.assertTrue(publisher._publish(message))
        self.assertEqual(publisher.client.publish.call_args.args[0], '55t/sensors')
        publisher._stop_event = threading.Event()
        publisher._stop_event.set()
        publisher._flush_on_stop = False
        publisher._queue = queue.Queue()
        publisher._queue.put(message)
        publisher._publish, publisher._spill_to_disk = Mock(), Mock()
        publisher._run()
        publisher._publish.assert_not_called()
        publisher._spill_to_disk.assert_called_once_with(message)


if __name__ == '__main__':
    unittest.main()
