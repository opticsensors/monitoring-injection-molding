#!/usr/bin/env python3
"""Read-only InfluxDB 1.x inventory and cycle diagnostics. Python 3.8+, stdlib only.

Run on the Docker host (not inside the Influx container):
    python3 scripts/diagnose_influxdb.py
Or copy just this file to the server:
    python3 diagnose_influxdb.py --output ~/influx_diagnosis

Defaults match: docker exec influxdb influx -database sensor_data ...
Reads every measurement in every retention policy, without LIMIT or time filter.
Writes a summary, JSON, CSV details and a ZIP alongside the output directory.
No database writes, container changes, app imports, credentials export, or pip
installation. A full scan does use server I/O/CPU; preferably run between tests.

The CLI's default chunked JSON responses are processed one chunk at a time.
Temporary SQLite stores timing/grouping data on disk; full raw values are not
retained unless --keep-raw is requested. Counts/min/max/means are exact over
returned rows; interval percentiles use bounded, deterministic reservoir samples.

Use --help for options; the generated report includes interpretation limits.
"""
import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import zipfile


REPORT_VERSION = 1
NS = 1_000_000_000
INSERT_BATCH = 2000
RESERVOIR_SIZE = 4096


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def utc_ns(value):
    if value is None:
        return None
    seconds, nanos = divmod(int(value), NS)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + '.%09dZ' % nanos


def ident(value):
    """Quote an InfluxQL identifier; no user-supplied query fragments are used."""
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def cycle_key(value):
    if value is None or value == '':
        return ''
    try:
        number = Decimal(str(value))
        if number.is_finite() and number >= 0 and number == number.to_integral_value():
            return str(int(number))
    except InvalidOperation:
        pass
    return 'invalid:' + str(value)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def progress(message):
    print(message, file=sys.stderr, flush=True)


class Stats:
    """Streaming numeric moments plus a fixed-size percentile reservoir."""
    def __init__(self, sample_size=0):
        self.n = 0
        self.mean = self.m2 = 0.0
        self.low = self.high = None
        self.sample_size = sample_size
        self.sample = []
        self.rng = random.Random(4108)

    def add(self, value):
        self.n += 1
        delta = value - self.mean
        self.mean = (self.mean + delta / self.n if math.isfinite(delta)
                     else self.mean * ((self.n - 1) / self.n) + value / self.n)
        self.m2 += delta * (value - self.mean)
        self.low = value if self.low is None else min(self.low, value)
        self.high = value if self.high is None else max(self.high, value)
        if len(self.sample) < self.sample_size:
            self.sample.append(value)
        elif self.sample_size:
            index = self.rng.randrange(self.n)
            if index < self.sample_size:
                self.sample[index] = value

    def result(self):
        variance = self.m2 / self.n if self.n else None
        result = {'n': self.n, 'min': self.low, 'max': self.high,
                  'mean': self.mean if self.n else None,
                  'stddev_population': math.sqrt(max(0.0, variance)) if variance is not None and math.isfinite(variance) else None,
                  'variance_overflow': variance is not None and not math.isfinite(variance)}
        if self.sample_size:
            sample = sorted(self.sample)
            for name, q in [('p01', .01), ('p50', .5), ('p95', .95), ('p99', .99)]:
                pos = (len(sample) - 1) * q
                lo, hi = math.floor(pos), math.ceil(pos)
                result[name] = (sample[lo] * (1 - (pos - lo)) + sample[hi] * (pos - lo)) if sample else None
            result['percentile_sample_n'] = len(sample)
            result['percentiles_approximate'] = self.n > len(sample)
        return result


class ColumnStats:
    def __init__(self):
        self.present = self.zeros = self.nonfinite = 0
        self.types = Counter()
        self.numeric = Stats()
        self.examples = []

    def add(self, value):
        if value is None:
            return
        self.present += 1
        self.types[type(value).__name__] += 1
        numeric = finite_number(value)
        if numeric is not None:
            self.numeric.add(numeric)
            self.zeros += numeric == 0
        elif isinstance(value, float):
            self.nonfinite += 1
        else:
            example = str(value)[:160]
            if len(self.examples) < 5 and example not in self.examples:
                self.examples.append(example)

    def result(self, total):
        return {'present': self.present, 'missing': total - self.present,
                'observed_json_types': dict(self.types), 'zeros': self.zeros,
                'nonfinite': self.nonfinite, 'numeric': self.numeric.result(),
                'examples': self.examples}


def response_rows(document):
    """Fail on errors even if a CLI returns exit code zero; accept chunk markers."""
    if not isinstance(document, dict) or 'results' not in document:
        raise RuntimeError('Unexpected Influx JSON response (expected results array).')
    if document.get('error'):
        raise RuntimeError(str(document['error']))
    for result in document['results']:
        if result.get('error'):
            raise RuntimeError(str(result['error']))
        for series in result.get('series', []):
            columns = series.get('columns', [])
            if len(set(columns)) != len(columns):
                raise RuntimeError('Duplicate result column names; cannot analyze without ambiguity.')
            for values in series.get('values') or []:
                if len(columns) != len(values):
                    raise RuntimeError('Malformed result row: column/value counts differ.')
                row = dict(series.get('tags', {}))
                row.update(zip(columns, values))
                yield row


class DockerInflux:
    def __init__(self, container, database, timeout):
        self.container, self.database, self.timeout = container, database, timeout
        self.audit = []

    def query(self, query):
        """Stream one JSON document per CLI chunk; no shell interpolation."""
        if not query.startswith(('SHOW ', 'SELECT ')):
            raise ValueError('Only generated SHOW and SELECT queries are allowed.')
        cmd = ['docker', 'exec']
        # Forward only named authentication variables, never put values in argv/report.
        for key in ('INFLUX_USERNAME', 'INFLUX_PASSWORD'):
            if key in os.environ:
                cmd += ['--env', key]
        cmd += [self.container, 'influx', '-database', self.database,
                '-format', 'json', '-precision', 'ns', '-execute', query]
        entry = {'query': query, 'started_utc': utc_now(), 'complete': False,
                 'response_bytes': 0}
        self.audit.append(entry)
        started = time.monotonic()
        timed_out = threading.Event()
        with tempfile.TemporaryFile() as errors:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors,
                                    text=True, encoding='utf-8')
            def expire():
                timed_out.set()
                proc.kill()
            timer = threading.Timer(self.timeout, expire) if self.timeout else None
            if timer:
                timer.start()
            try:
                for line in proc.stdout:
                    entry['response_bytes'] += len(line.encode('utf-8'))
                    if not line.strip():
                        continue
                    try:
                        document = json.loads(line)
                    except ValueError as exc:
                        raise RuntimeError('Non-JSON output from influx: ' + line.strip()[:500]) from exc
                    # Validate error envelopes before letting a caller consume a chunk.
                    if not isinstance(document, dict) or 'results' not in document:
                        raise RuntimeError('Unexpected Influx JSON response: ' + line.strip()[:500])
                    if document.get('error'):
                        raise RuntimeError(str(document['error']))
                    for result in document.get('results', []):
                        if result.get('error'):
                            raise RuntimeError(str(result['error']))
                    yield document
                code = proc.wait()
                errors.seek(0)
                stderr = errors.read(8192).decode('utf-8', errors='replace').strip()
                if timed_out.is_set():
                    raise RuntimeError('Query timeout; this scan is incomplete.')
                if code or stderr:
                    # An error/warning on stderr is never silently treated as success.
                    raise RuntimeError('influx/docker exit %s: %s' % (code, stderr))
                if entry['response_bytes'] == 0:
                    raise RuntimeError('Empty CLI response; query completeness cannot be established.')
                entry['complete'] = True
            finally:
                if timer:
                    timer.cancel()
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                proc.stdout.close()
                entry['elapsed_s'] = round(time.monotonic() - started, 3)

    def rows(self, query):
        for document in self.query(query):
            yield from response_rows(document)

    def metadata(self, query):
        return list(self.rows(query))

    def optional_command(self, args):
        try:
            result = subprocess.run(['docker'] + args, capture_output=True, text=True,
                                    encoding='utf-8', timeout=30)
            return {'ok': result.returncode == 0, 'stdout': result.stdout.strip()[:16000],
                    'stderr': result.stderr.strip()[:2000]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'ok': False, 'error': str(exc)}

    def infrastructure(self, data_dir, wal_dir):
        # Never collect docker inspect's full output: it contains environment secrets.
        result = {
            'influxd_version': self.optional_command(['exec', self.container, 'influxd', 'version']),
            'container_image': self.optional_command(['inspect', '--format', '{{.Config.Image}}', self.container]),
            'container_stats_before_scan': self.optional_command(
                ['stats', '--no-stream', '--format', '{{json .}}', self.container]),
        }
        for label, directory in [('data_disk_kib', data_dir), ('wal_disk_kib', wal_dir)]:
            if '/' in self.database or self.database in ('.', '..'):
                result[label] = {'ok': False, 'error': 'Disk probe skipped for non-simple database name.'}
            else:
                result[label] = self.optional_command(
                    ['exec', self.container, 'du', '-sk', str(PurePosixPath(directory) / self.database)])
        return result


def projection(field_keys, tag_keys):
    """Explicit aliases disambiguate a legacy cycle_id tag from a same-name field."""
    mapping, terms = {}, []
    for role, names in [('field', field_keys), ('tag', tag_keys)]:
        for i, name in enumerate(sorted(names)):
            alias = '__diag_%s_%d' % (role, i)
            mapping[alias] = (role, name)
            terms.append('%s::%s AS %s' % (ident(name), role, ident(alias)))
    return ', '.join(terms), mapping


class Analysis:
    def __init__(self, db):
        self.db = db
        self.datasets = []
        db.executescript('''
            CREATE TABLE series (id INTEGER PRIMARY KEY, dataset INTEGER, tags TEXT,
                                 UNIQUE(dataset,tags));
            CREATE TABLE points (dataset INTEGER, machine TEXT, session TEXT, cycle TEXT,
                                 time_ns INTEGER, t_ms REAL, series INTEGER, present TEXT);
            CREATE TABLE cycles (dataset INTEGER, machine TEXT, session TEXT, cycle TEXT,
                                 n INTEGER, start_ns INTEGER, end_ns INTEGER, span_s REAL);
            CREATE TABLE tag_values (dataset INTEGER, name TEXT, value TEXT,
                                     PRIMARY KEY(dataset,name,value));
        ''')
        self.buffer = []
        self.series_cache = {}

    def flush(self):
        self.db.executemany('INSERT INTO points VALUES (?,?,?,?,?,?,?,?)', self.buffer)
        self.buffer.clear()
        self.db.commit()

    def scan(self, client, database, rp, measurement, schema, raw=None):
        number = len(self.datasets)
        fields = sorted(schema['field_types'])
        tags = sorted(schema['tag_keys'])
        select, mapping = projection(fields, tags)
        dataset = {'id': number, 'retention_policy': rp, 'measurement': measurement,
                   'complete': False, 'points': 0, 'first_time_ns': None, 'last_time_ns': None,
                   'field_order': fields, 'schema': schema, 'issues': Counter()}
        self.datasets.append(dataset)
        stats = {(role, key): ColumnStats() for role, keys in [('field', fields), ('tag', tags)] for key in keys}
        first, last = [], []
        query = 'SELECT %s FROM %s ORDER BY time ASC' % (
            select, '.'.join(ident(s) for s in (database, rp, measurement)))
        progress('Scanning %s.%s (all rows)...' % (rp, measurement))
        tick = time.monotonic()
        try:
            if not fields:
                raise RuntimeError('No field keys discovered; cannot build a complete sample query.')
            for document in client.query(query):
                if raw:
                    raw.write(json.dumps({'dataset': number, 'response': document}, ensure_ascii=False) + '\n')
                for row in response_rows(document):
                    timestamp = row.get('time')
                    if not isinstance(timestamp, int) or isinstance(timestamp, bool):
                        raise RuntimeError('Expected integer nanosecond timestamp, got %r.' % timestamp)
                    if not -(2**63) < timestamp < 2**63:
                        raise RuntimeError('Timestamp outside signed 64-bit range.')
                    values, tag_values = {}, {}
                    for alias, (role, key) in mapping.items():
                        value = row.get(alias)
                        (values if role == 'field' else tag_values)[key] = value
                        stats[(role, key)].add(value)
                    machine = str(tag_values.get('machine_id') or values.get('machine_id') or '')
                    session = str(tag_values.get('session_id') or values.get('session_id') or '')
                    candidates = [cycle_key(v) for v in (values.get('cycle_id'), values.get('cycle_num'),
                                  tag_values.get('cycle_id'), tag_values.get('cycle_num')) if v is not None and v != '']
                    cycle = candidates[0] if candidates else ''
                    dataset['issues']['conflicting_cycle_identifiers'] += len(set(candidates)) > 1
                    dataset['issues']['missing_machine'] += not bool(machine)
                    dataset['issues']['missing_session'] += not bool(session)
                    dataset['issues']['missing_cycle'] += not bool(cycle)
                    dataset['issues']['invalid_cycle'] += cycle.startswith('invalid:')
                    t_ms = finite_number(values.get('t_ms'))
                    dataset['issues']['missing_or_invalid_t_ms'] += t_ms is None
                    dataset['issues']['negative_t_ms'] += t_ms is not None and t_ms < 0
                    dataset['issues']['future_timestamp_at_scan'] += timestamp > time.time_ns()
                    tag_json = json.dumps({k: v for k, v in tag_values.items() if v not in (None, '')}, sort_keys=True)
                    cache_key = (number, tag_json)
                    series_id = self.series_cache.get(cache_key)
                    if series_id is None:
                        self.db.execute('INSERT OR IGNORE INTO series(dataset,tags) VALUES (?,?)', cache_key)
                        self.db.executemany('INSERT OR IGNORE INTO tag_values VALUES (?,?,?)',
                                            ((number, k, str(v)) for k, v in tag_values.items() if v not in (None, '')))
                        series_id = self.db.execute('SELECT id FROM series WHERE dataset=? AND tags=?', cache_key).fetchone()[0]
                        if len(self.series_cache) >= 10000:
                            self.series_cache.clear()
                        self.series_cache[cache_key] = series_id
                    present = ','.join(str(i) for i, key in enumerate(fields) if values.get(key) is not None)
                    self.buffer.append((number, machine, session, cycle, timestamp, t_ms, series_id, present))
                    if len(self.buffer) >= INSERT_BATCH:
                        self.flush()
                    dataset['points'] += 1
                    dataset['first_time_ns'] = min(timestamp, dataset['first_time_ns']) if dataset['first_time_ns'] is not None else timestamp
                    dataset['last_time_ns'] = max(timestamp, dataset['last_time_ns']) if dataset['last_time_ns'] is not None else timestamp
                    want_first = len(first) < 3 or timestamp < first[-1]['time_ns']
                    want_last = len(last) < 3 or timestamp > last[0]['time_ns']
                    if want_first or want_last:
                        # Keep true oldest/newest examples even across series/chunks.
                        # JSON has no NaN/Infinity literals; counters flag those values.
                        example = {'time_ns': timestamp, 'time_utc': utc_ns(timestamp), 'tags': tag_values,
                                   'fields': {k: str(v) if isinstance(v, float) and not math.isfinite(v) else v
                                              for k, v in values.items()}}
                        if want_first:
                            first.append(example)
                            first.sort(key=lambda p: p['time_ns'])
                            del first[3:]
                        if want_last:
                            last.append(example)
                            last.sort(key=lambda p: p['time_ns'])
                            del last[:-3]
                if time.monotonic() - tick >= 5:
                    progress('  %s.%s: %s points read' % (rp, measurement, format(dataset['points'], ',')))
                    tick = time.monotonic()
            dataset['complete'] = True
        except (RuntimeError, OSError, ValueError) as exc:
            dataset['error'] = str(exc)
            progress('  INCOMPLETE: ' + str(exc))
        finally:
            self.flush()
            dataset['columns'] = [{'role': role, 'name': key, **value.result(dataset['points'])}
                                  for (role, key), value in stats.items()]
            dataset['first_examples'], dataset['last_examples'] = first, list(last)
            dataset['first_time_utc'] = utc_ns(dataset['first_time_ns'])
            dataset['last_time_utc'] = utc_ns(dataset['last_time_ns'])
            dataset['observed_series'] = self.db.execute('SELECT COUNT(*) FROM series WHERE dataset=?', (number,)).fetchone()[0]
            dataset['issues'] = dict(dataset['issues'])
        progress('  %s points, %s series, complete=%s' % (dataset['points'], dataset['observed_series'], dataset['complete']))

    def cycle_report(self, output):
        progress('Sorting stored timing data and calculating cycle/session statistics...')
        self.db.execute('CREATE INDEX point_groups ON points(dataset,machine,session,cycle,time_ns)')
        metrics = {d['id']: {'points_per_cycle': Stats(RESERVOIR_SIZE), 'observed_span_s': Stats(RESERVOIR_SIZE),
                            'effective_hz': Stats(RESERVOIR_SIZE), 'positive_interval_ms': Stats(RESERVOIR_SIZE),
                            'counts': Counter()} for d in self.datasets}
        columns = ['dataset', 'retention_policy', 'measurement', 'machine_id', 'session_id', 'cycle_id', 'kind',
                   'points', 'first_time_utc', 'last_time_utc', 'observed_span_s', 'effective_hz',
                   't_ms_min', 't_ms_max', 't_ms_resets', 'positive_intervals', 'dt_min_ms', 'dt_p01_ms',
                   'dt_p50_ms', 'dt_p95_ms', 'dt_p99_ms', 'dt_max_ms', 'dt_mean_ms',
                   'percentile_sample_n', 'percentiles_approximate', 'intervals_below_1ms', 'intervals_above_1s',
                   'duplicate_timestamps', 'series_count', 'fields_present', 'field_present_counts',
                   'max_timestamp_vs_t_ms_delta_error_ms']
        with (output / 'cycles.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            rows = self.db.execute('SELECT * FROM points ORDER BY dataset,machine,session,cycle,time_ns')
            processed, tick = 0, time.monotonic()
            for key, group in itertools.groupby(rows, key=lambda row: row[:4]):
                dataset_id, machine, session, cycle = key
                dataset, aggregate = self.datasets[dataset_id], metrics[dataset_id]
                dt = Stats(RESERVOIR_SIZE)
                n = resets = zeros = tiny = large = 0
                first = previous = prev_relative = last = None
                relative_min = relative_max = clock_error = None
                field_counts, series = Counter(), set()
                for _, _, _, _, ts, relative, series_id, present in group:
                    n += 1
                    first = ts if first is None else first
                    last = ts
                    if previous is not None:
                        delta_ms = (ts - previous) / 1_000_000
                        zeros += delta_ms == 0
                        if delta_ms > 0:
                            dt.add(delta_ms)
                            tiny += delta_ms < 1
                            large += delta_ms > 1000
                            if cycle.isdigit() and cycle != '0':
                                aggregate['positive_interval_ms'].add(delta_ms)
                        if relative is not None and prev_relative is not None:
                            rel_delta = relative - prev_relative
                            resets += rel_delta < -0.000001
                            error = abs(delta_ms - rel_delta)
                            clock_error = max(clock_error, error) if clock_error is not None else error
                    if relative is not None:
                        relative_min = min(relative_min, relative) if relative_min is not None else relative
                        relative_max = max(relative_max, relative) if relative_max is not None else relative
                    previous, prev_relative = ts, relative
                    series.add(series_id)
                    field_counts.update(dataset['field_order'][int(i)] for i in present.split(',') if i)
                span = (last - first) / NS
                hz = (n - 1) / span if span > 0 else None
                kind = 'cycle' if cycle.isdigit() and cycle != '0' else ('continuous' if cycle == '0' else 'unscoped_or_invalid')
                aggregate['counts'][kind + '_groups'] += 1
                aggregate['counts']['duplicate_timestamps'] += zeros
                aggregate['counts']['groups_with_t_ms_resets'] += resets > 0
                aggregate['counts']['groups_with_multiple_series'] += len(series) > 1
                if kind == 'cycle':
                    aggregate['points_per_cycle'].add(n)
                    aggregate['observed_span_s'].add(span)
                    if hz is not None:
                        aggregate['effective_hz'].add(hz)
                d = dt.result()
                result = dict(zip(columns[:6], [dataset_id, dataset['retention_policy'], dataset['measurement'], machine, session, cycle]))
                result.update(kind=kind, points=n, first_time_utc=utc_ns(first), last_time_utc=utc_ns(last),
                              observed_span_s=span, effective_hz=hz, t_ms_min=relative_min, t_ms_max=relative_max,
                              t_ms_resets=resets, positive_intervals=d['n'], dt_min_ms=d['min'], dt_max_ms=d['max'],
                              dt_mean_ms=d['mean'], intervals_below_1ms=tiny, intervals_above_1s=large,
                              duplicate_timestamps=zeros, series_count=len(series),
                              fields_present=json.dumps(sorted(field_counts)), field_present_counts=json.dumps(dict(field_counts), sort_keys=True),
                              max_timestamp_vs_t_ms_delta_error_ms=clock_error)
                result.update({'dt_' + p + '_ms': d[p] for p in ('p01', 'p50', 'p95', 'p99')})
                result.update({p: d[p] for p in ('percentile_sample_n', 'percentiles_approximate')})
                writer.writerow(result)
                self.db.execute('INSERT INTO cycles VALUES (?,?,?,?,?,?,?,?)', (*key, n, first, last, span))
                processed += 1
                if time.monotonic() - tick >= 5:
                    progress('  %s cycle/continuous/unscoped groups analyzed' % format(processed, ','))
                    tick = time.monotonic()
        self.db.commit()
        for dataset in self.datasets:
            m = metrics[dataset['id']]
            dataset['cycle_statistics'] = {k: dict(v) if isinstance(v, Counter) else v.result() for k, v in m.items()}

    def table_report(self, output, filename, query, parameters=()):
        cursor = self.db.execute(query, parameters)
        with (output / filename).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow([c[0] for c in cursor.description])
            writer.writerows(cursor)

    def finish(self, output):
        self.cycle_report(output)
        self.table_report(output, 'sessions.csv', '''
            SELECT dataset, machine AS machine_id, session AS session_id,
                   SUM(n) AS points, MIN(start_ns) AS first_time_ns, MAX(end_ns) AS last_time_ns,
                   (MAX(end_ns)-MIN(start_ns))/1000000000.0 AS wall_span_s,
                   SUM(CASE WHEN cycle NOT IN ('','0') AND cycle NOT LIKE 'invalid:%' THEN 1 ELSE 0 END) AS cycle_groups,
                   SUM(CASE WHEN cycle NOT IN ('','0') AND cycle NOT LIKE 'invalid:%' THEN span_s ELSE 0 END) AS summed_cycle_observed_span_s
            FROM cycles GROUP BY dataset,machine,session ORDER BY dataset,machine,MIN(start_ns)
        ''')
        self.table_report(output, 'daily.csv', '''
            SELECT dataset,machine AS machine_id,date(time_ns/1000000000,'unixepoch') AS utc_date,
                   COUNT(*) AS points,COUNT(DISTINCT session) AS session_values
            FROM points GROUP BY dataset,machine,utc_date ORDER BY dataset,machine,utc_date
        ''')
        self.table_report(output, 'reused_cycle_ids.csv', '''
            SELECT dataset,machine AS machine_id,cycle AS cycle_id,COUNT(DISTINCT session) AS session_count
            FROM cycles WHERE cycle NOT IN ('','0') AND cycle NOT LIKE 'invalid:%'
            GROUP BY dataset,machine,cycle HAVING COUNT(DISTINCT session)>1
        ''')
        with (output / 'fields.csv').open('w', encoding='utf-8', newline='') as stream:
            names = ['dataset', 'role', 'name', 'declared_influx_types', 'present', 'missing', 'zeros', 'nonfinite',
                     'observed_json_types', 'numeric_n', 'min', 'max', 'mean', 'stddev_population', 'examples']
            writer = csv.DictWriter(stream, fieldnames=names)
            writer.writeheader()
            for d in self.datasets:
                for col in d['columns']:
                    row = {k: col[k] for k in ('role', 'name', 'present', 'missing', 'zeros', 'nonfinite')}
                    row.update(dataset=d['id'], declared_influx_types=json.dumps(d['schema']['field_types'].get(col['name'], ['tag:string']) if col['role'] == 'field' else ['tag:string']),
                               observed_json_types=json.dumps(col['observed_json_types']), examples=json.dumps(col['examples']))
                    row.update({k: col['numeric'][k] for k in ('min', 'max', 'mean', 'stddev_population')})
                    row['numeric_n'] = col['numeric']['n']
                    writer.writerow(row)
        for d in self.datasets:
            key = (d['id'],)
            d['machines'] = [dict(zip(('machine_id', 'points', 'session_values'), row)) for row in
                             self.db.execute('SELECT machine,COUNT(*),COUNT(DISTINCT session) FROM points WHERE dataset=? GROUP BY machine', key)]
            d['peak_points_per_utc_second'] = self.db.execute('SELECT MAX(n) FROM (SELECT COUNT(*) n FROM points WHERE dataset=? GROUP BY machine,time_ns/1000000000)', key).fetchone()[0]
            d['same_series_same_timestamp_extra_rows'] = self.db.execute('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM points WHERE dataset=? GROUP BY series,time_ns HAVING COUNT(*)>1)', key).fetchone()[0]
            d['cycle_ids_reused_across_sessions'] = self.db.execute("SELECT COUNT(*) FROM (SELECT cycle FROM cycles WHERE dataset=? AND cycle NOT IN ('','0') AND cycle NOT LIKE 'invalid:%' GROUP BY machine,cycle HAVING COUNT(DISTINCT session)>1)", key).fetchone()[0]
            d['tag_cardinality'] = {}
            for name in d['schema']['tag_keys']:
                tag_key = (d['id'], name)
                count = self.db.execute('SELECT COUNT(*) FROM tag_values WHERE dataset=? AND name=?', tag_key).fetchone()[0]
                examples = [r[0] for r in self.db.execute('SELECT value FROM tag_values WHERE dataset=? AND name=? ORDER BY value LIMIT 20', tag_key)]
                d['tag_cardinality'][name] = {'distinct_values': count, 'examples': examples}


LIMITATIONS = [
    'This is a read-only diagnostic scan, not an atomic backup. Concurrent writes/deletions can change results between queries.',
    'Scope: all returned points in the selected database, all retention policies and measurements; no time filter or LIMIT. Different retention policies may hold copies/aggregates, so their totals are not deduplicated.',
    'Rates use STORED sample timestamps, not MQTT arrival times or physical DAQ frequency. Missing/overwritten/dropped samples cannot be reconstructed.',
    'Per-cycle observed span is last stored timestamp minus first, not trigger-to-trigger cycle duration. Aborted/discarded/unuploaded cycles may be absent.',
    'Intervals are calculated within (retention policy, measurement, machine, session, cycle), ordered by absolute time; all tag variants are included. Duplicates/multiple series can inflate rates.',
    'Interval percentiles use up to 4096 deterministically sampled intervals per group; percentile approximation flags are explicit. Counts, means, extrema and rates use all returned points.',
    'Influx field types come from SHOW FIELD KEYS. JSON numeric types reflect returned values; they do not prove the original field type. Mixed types across shards are flagged; server-side SELECT coercion can hide some original field values.',
    'String/tag example lists are bounded; units/calibrations and hardware configuration cannot be inferred reliably from stored numbers alone.',
    'Container CPU/RAM is a single observation before the scan, not a workload benchmark. du sizes cover default/custom data and WAL paths and may be unavailable or change during compaction.',
    'A full scan costs server I/O/CPU and local temporary disk. No full raw dataset is included unless --keep-raw was requested.',
]


def summary(report):
    lines = ['INFLUXDB DIAGNOSTIC REPORT', 'Status: ' + ('COMPLETE' if report['complete'] else 'INCOMPLETE / QUALIFIED - see warnings and read errors below'),
             'Database: ' + report['database'], 'Started UTC: ' + report['started_utc'],
             'Finished UTC: ' + report['finished_utc'],
             'Scanned points (across retention policies): {:,}'.format(sum(d['points'] for d in report['datasets'])),
             'Measurement/policy scans: %s' % len(report['datasets']), '']
    for d in report['datasets']:
        lines += ['[%s] %s.%s - %s points, %s series, complete=%s' %
                  (d['id'], d['retention_policy'], d['measurement'], format(d['points'], ','), d['observed_series'], d['complete']),
                  '  Range UTC: %s -> %s' % (d['first_time_utc'], d['last_time_utc']),
                  '  Machines: ' + json.dumps(d['machines']),
                  '  Fields/types: ' + json.dumps(d['schema']['field_types']),
                  '  Tags/distinct values: ' + json.dumps({k: v['distinct_values'] for k, v in d['tag_cardinality'].items()}),
                  '  Field/tag name collisions: ' + json.dumps(d['schema']['field_tag_collisions']),
                  '  Cycle/group counts: ' + json.dumps(d['cycle_statistics']['counts'])]
        for title, key in [('Points/cycle', 'points_per_cycle'), ('Observed cycle span (s)', 'observed_span_s'),
                           ('Stored effective Hz/cycle', 'effective_hz'), ('Positive intervals (ms)', 'positive_interval_ms')]:
            stat = d['cycle_statistics'][key]
            lines.append('  %s: n=%s min=%s median=%s p95=%s max=%s mean=%s (percentiles%s)' %
                         (title, stat['n'], fmt(stat['min']), fmt(stat['p50']), fmt(stat['p95']),
                          fmt(stat['max']), fmt(stat['mean']), ' sampled' if stat['percentiles_approximate'] else ' exact'))
        lines += ['  Peak points/UTC second per machine: %s' % d['peak_points_per_utc_second'],
                  '  Cycle IDs reused across sessions: %s' % d['cycle_ids_reused_across_sessions'],
                  '  Extra rows sharing full series + timestamp: %s' % d['same_series_same_timestamp_extra_rows'],
                  '  Row issues: ' + json.dumps({k: v for k, v in d['issues'].items() if v})]
        for col in d['columns']:
            if col['role'] == 'field':
                lines.append('  %s: present=%s missing=%s min=%s max=%s mean=%s' %
                             (col['name'], col['present'], col['missing'], fmt(col['numeric']['min']),
                              fmt(col['numeric']['max']), fmt(col['numeric']['mean'])))
        if d.get('error'):
            lines.append('  ERROR: ' + d['error'])
        lines.append('')
    lines += ['Infrastructure (read-only, best effort):', json.dumps(report['infrastructure'], indent=2),
              'Warnings/errors:', *('  - ' + s for s in report['warnings']), '', 'Interpretation limits:',
              *('  - ' + s for s in LIMITATIONS), '',
              'Share the ZIP for analysis. summary.txt is suitable for pasting; CSV/JSON preserve full detail.']
    return '\n'.join(lines) + '\n'


def fmt(value):
    return 'n/a' if value is None else '%.6g' % value


def collect(args, output, client):
    report = {'report_version': REPORT_VERSION, 'database': args.database, 'container': args.container,
              'started_utc': utc_now(), 'complete': False, 'warnings': [], 'limitations': LIMITATIONS,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    progress('Reading server/schema information (no database writes)...')
    report['infrastructure'] = client.infrastructure(args.data_dir, args.wal_dir)
    retention = client.metadata('SHOW RETENTION POLICIES ON ' + ident(args.database))
    measurements = client.metadata('SHOW MEASUREMENTS ON ' + ident(args.database))
    if not retention:
        raise RuntimeError('No retention policies returned; cannot establish database scope.')
    report['retention_policies'] = retention
    report['measurement_names'] = [r['name'] for r in measurements]
    raw = gzip.open(output / 'raw_responses.jsonl.gz', 'wt', encoding='utf-8') if args.keep_raw else None
    try:
        with tempfile.TemporaryDirectory(prefix='influx-analysis-', dir=args.temp_dir) as temp:
            with closing(sqlite3.connect(str(Path(temp) / 'timing.sqlite'))) as db:
                db.execute('PRAGMA temp_store=FILE')
                db.execute('PRAGMA cache_size=-32768')
                analysis = Analysis(db)
                for measurement in report['measurement_names']:
                    try:
                        field_rows = client.metadata('SHOW FIELD KEYS ON %s FROM %s' % (ident(args.database), ident(measurement)))
                        tag_rows = client.metadata('SHOW TAG KEYS ON %s FROM %s' % (ident(args.database), ident(measurement)))
                        types = {}
                        for r in field_rows:
                            types.setdefault(r['fieldKey'], set()).add(r['fieldType'])
                        tags = sorted({r['tagKey'] for r in tag_rows})
                        schema = {'field_types': {k: sorted(v) for k, v in sorted(types.items())}, 'tag_keys': tags,
                                  'field_tag_collisions': sorted(set(types) & set(tags))}
                        for name, kinds in types.items():
                            if len(kinds) > 1:
                                report['warnings'].append('%s.%s has multiple field types across shards: %s' % (measurement, name, sorted(kinds)))
                        for rp in retention:
                            analysis.scan(client, args.database, rp['name'], measurement, schema, raw)
                    except (RuntimeError, OSError, ValueError, KeyError) as exc:
                        report['warnings'].append('Could not fully inspect %s: %s' % (measurement, exc))
                analysis.finish(output)
                report['datasets'] = analysis.datasets
    finally:
        if raw:
            raw.close()
    report['query_audit'] = client.audit
    report['finished_utc'] = utc_now()
    report['complete'] = (not report['warnings'] and all(d['complete'] for d in report['datasets'])
                          and len(report['datasets']) == len(retention) * len(measurements))
    write_json(output / 'report.json', report)
    text = summary(report)
    (output / 'summary.txt').write_text(text, encoding='utf-8')
    return report, text


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--container', default='influxdb')
    parser.add_argument('--database', default='sensor_data')
    parser.add_argument('--output', type=Path, help='NEW output directory; never overwrite an existing report.')
    parser.add_argument('--temp-dir', type=Path, help='Temporary disk location for SQLite (default: OS temp directory).')
    parser.add_argument('--query-timeout', type=float, default=0, help='Seconds per query; 0 means no timeout for full history (default).')
    parser.add_argument('--keep-raw', action='store_true', help='Also save all query chunks as compressed JSONL; can be large.')
    parser.add_argument('--data-dir', default='/var/lib/influxdb/data', help='Container data directory, only for optional disk-size probe.')
    parser.add_argument('--wal-dir', default='/var/lib/influxdb/wal', help='Container WAL directory, only for optional disk-size probe.')
    args = parser.parse_args(argv)
    if args.query_timeout < 0 or not math.isfinite(args.query_timeout):
        parser.error('--query-timeout must be finite and >= 0')
    if not args.database or not args.container or args.container.startswith('-'):
        parser.error('Provide a database and a non-option container name.')
    if not PurePosixPath(args.data_dir).is_absolute() or not PurePosixPath(args.wal_dir).is_absolute():
        parser.error('--data-dir and --wal-dir must be absolute container paths.')
    return args


def main(argv=None):
    args = parse_args(argv)
    output = (args.output or Path('data/diagnostics') / ('influx_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))).expanduser().resolve()
    archive = output.parent / (output.name + '.zip')
    if output.exists() or archive.exists():
        print('Choose a new --output path; existing reports are never overwritten.', file=sys.stderr)
        return 2
    output.mkdir(parents=True)
    client = DockerInflux(args.container, args.database, args.query_timeout)
    try:
        report, text = collect(args, output, client)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, KeyboardInterrupt) as exc:
        error = 'Interrupted by user' if isinstance(exc, KeyboardInterrupt) else str(exc)
        write_json(output / 'failure.json', {'complete': False, 'error': error, 'query_audit': client.audit})
        print('Diagnostic incomplete: %s\nDetails: %s' % (error, output / 'failure.json'), file=sys.stderr)
        return 2
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(output.iterdir()):
            if path.is_file():
                zipped.write(path, output.name + '/' + path.name)
    print(text)
    print('Reports: ' + str(output))
    print('Share:   ' + str(archive))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
