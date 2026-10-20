"""Build reviewable PostgreSQL catalog SQL from a fresh diagnostic cycles.csv.

No database connections/writes and no waveform migration. The input is the
cycles.csv produced by diagnose_influxdb.py, not a raw waveform backup.
"""
import argparse
import calendar
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cycle_metadata import export_metadata, read_metadata, identity


def timestamp_ns(text):
    match = re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z', text)
    if not match:
        raise ValueError(f'Expected exact UTC timestamp, got {text!r}')
    seconds = calendar.timegm(datetime.strptime(match[1], '%Y-%m-%dT%H:%M:%S').timetuple())
    return seconds * 1_000_000_000 + int((match[2] or '').ljust(9, '0'))


def read_cycles(path, catalog=None, report=None):
    """Reconcile a diagnostic with a server metadata export before importing.

    A sample_index field identifies native captures; absent catalog entries need
    replay/reconciliation, never a fabricated legacy manifest.
    """
    entries, seen = [], set()
    existing = {identity(e['capture']): e['capture'] for e in read_metadata(catalog)} if catalog else {}
    report = report if report is not None else []
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row['retention_policy'] != 'autogen' or row['measurement'] != 'sensor_data':
                raise ValueError('This importer is scoped to autogen.sensor_data.')
            cid = Decimal(row['cycle_id'])
            if not cid.is_finite() or cid != cid.to_integral_value() or not 0 <= cid <= 9007199254740991:
                raise ValueError('Invalid numeric cycle ID.')
            key = (row['machine_id'], row['session_id'], int(cid))
            if not key[0] or not key[1] or key in seen:
                raise ValueError(f'Missing/ambiguous identity: {key}')
            if (int(row['series_count']) != 1 or int(row['duplicate_timestamps']) != 0
                    or int(row['t_ms_resets']) != 0):
                raise ValueError(f'Inspect anomalous cycle before import: {key}')
            count = int(row['points'])
            first, last = timestamp_ns(row['first_time_utc']), timestamp_ns(row['last_time_utc'])
            if count <= 0 or not 0 < first <= last:
                raise ValueError(f'Invalid bounds/count: {key}')
            seen.add(key)
            field_counts = json.loads(row['field_present_counts'])
            native_count = int(field_counts.get('sample_index', 0))
            if native_count not in (0, count):
                raise ValueError(f'Mixed legacy/native samples need reconciliation: {key}')
            if key in existing:
                previous = existing[key]
                if (int(previous['first_time_ns']), int(previous['last_time_ns']), previous['sample_count']) != (first, last, count):
                    raise ValueError(f'Catalog bounds/count differ from Influx: {key}')
                if bool(native_count) != (previous['status'] != 'legacy'):
                    raise ValueError(f'Catalog format differs from Influx: {key}')
                report.append(f'Already cataloged: {key}')
                continue
            if native_count:
                raise ValueError(f'Native capture needs a matching --catalog export or server replay: {key}')
            capture = dict(machine_id=key[0], session_id=key[1], cycle_id=key[2], session_cycle=None,
                mode='continuous' if key[2] == 0 else 'cycle', status='legacy', reason='historical_catalog',
                first_time_ns=str(first), last_time_ns=str(last), sample_count=count,
                base_time_ns=None, trigger_start_ns=None, trigger_end_ns=None,
                timing_source='legacy_unknown', material=None, mold_temperature_c=None,
                pressure_settings_bar={'limit': None}, config_snapshot={})
            entries.append(dict(capture=capture, measurements=dict(revision=0, update_id='legacy',
                weight_g=None, length_mm=None, updated_at_ns=None), delivery='Legacy; verify server catalog'))
    if not seen:
        raise ValueError('No cycles found.')
    return entries


def build_sql(entries):
    statements = ['-- Generated catalog only: no Influx writes or waveform copies.',
                  'BEGIN;', 'SET standard_conforming_strings = on;']
    for entry in entries:
        value = json.dumps(entry['capture'], ensure_ascii=False, allow_nan=False).replace("'", "''")
        statements.append(f"SELECT monitoring.import_legacy('{value}'::jsonb);")
    statements.append('COMMIT;')
    return '\n'.join(statements) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cycles_csv', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, help='Fresh server.metadata.json; required for mixed old/new history')
    parser.add_argument('--metadata-export', type=Path, help='Optional GUI-loadable metadata, without waveforms')
    args = parser.parse_args()
    report = []
    entries = read_cycles(args.cycles_csv, args.catalog, report)
    args.output.write_text(build_sql(entries), encoding='utf-8')
    if args.metadata_export:
        export_metadata(args.metadata_export, entries)
    print(f"Prepared {len(entries)} cycles, {sum(e['capture']['sample_count'] for e in entries)} observed samples.")
    print(f'Skipped {len(report)} matching catalog entries.')
    print('Review the SQL and compare against a fresh server diagnostic before applying.')


if __name__ == '__main__':
    main()
