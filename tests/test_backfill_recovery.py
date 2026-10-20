import csv
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import cycle_metadata as meta
from scripts.build_legacy_catalog import read_cycles


class BackfillRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cycles.csv'
        self.catalog = self.path.with_suffix('.metadata.json')
        self.row = dict(retention_policy='autogen', measurement='sensor_data', machine_id='55t',
            session_id='old-session', cycle_id='3', points='2', series_count='1',
            duplicate_timestamps='0', t_ms_resets='0',
            first_time_utc='2026-08-04T10:22:49.691369500Z',
            last_time_utc='2026-08-04T10:22:49.701369500Z',
            field_present_counts='{"t_ms":2}')

    def write(self):
        with self.path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerow(self.row)

    def test_repeat_with_fresh_catalog_skips_and_validates_bounds(self):
        self.write()
        entries = read_cycles(self.path)
        meta.export_metadata(self.catalog, entries)
        report = []
        self.assertEqual(read_cycles(self.path, self.catalog, report), [])
        self.assertEqual(len(report), 1)
        self.row['points'] = '3'
        self.write()
        with self.assertRaisesRegex(ValueError, 'bounds/count differ'):
            read_cycles(self.path, self.catalog)

    def test_native_capture_requires_matching_catalog(self):
        self.write()
        entry = deepcopy(read_cycles(self.path)[0])
        entry['capture']['status'] = 'complete'
        self.row['field_present_counts'] = '{"t_ms":2,"sample_index":2}'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Native capture needs'):
            read_cycles(self.path)
        meta.export_metadata(self.catalog, [entry])
        self.assertEqual(read_cycles(self.path, self.catalog), [])

    def test_resets_and_mixed_formats_are_rejected(self):
        self.row['t_ms_resets'] = '1'
        self.write()
        with self.assertRaisesRegex(ValueError, 'anomalous cycle'):
            read_cycles(self.path)
        self.row['t_ms_resets'] = '0'
        self.row['field_present_counts'] = '{"t_ms":2,"sample_index":1}'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Mixed legacy/native'):
            read_cycles(self.path)

    def test_server_export_provenance(self):
        self.write()
        entries = read_cycles(self.path)
        meta.export_metadata(self.catalog, entries)
        self.assertEqual(meta.read_metadata(self.catalog, with_source=True)[1], 'local')
        document = json.loads(self.catalog.read_text())
        document['source'] = 'server'
        self.catalog.write_text(json.dumps(document))
        self.assertEqual(meta.read_metadata(self.catalog, with_source=True)[1], 'server')
