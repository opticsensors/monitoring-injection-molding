"""Launch the real GUI with scan-accounting diagnostics; use the normal Save too.

Run from the repository: py -3.11 scripts/validate_acquisition.py
The existing driver/GUI still acquires the data. Process-local wrappers count
bytes consumed by acquisition reads and scans returned, without extra serial
reads or changes to driver files, settings, timestamps or trigger handling.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class AcquisitionAudit:
    """Bounded counters per session; no waveform copies or I/O during a read."""

    def __init__(self, clock=time.perf_counter):
        self.clock = clock
        self.lock = threading.Lock()
        self.sessions = {}
        self.started_at = datetime.now(timezone.utc).isoformat()

    def observe(self, device, collect, session_id, binary_method):
        port = device.ser
        original_read = port.read
        owner = threading.get_ident()
        consumed = 0

        def counted_read(*args, **kwargs):
            nonlocal consumed
            data = original_read(*args, **kwargs)
            if threading.get_ident() == owner:
                consumed += len(data)
            return data

        result, failed = None, False
        start = self.clock()
        try:
            with patch.object(port, 'read', counted_read):
                result = collect()
            return result
        except Exception:
            failed = True
            raise
        finally:
            end = self.clock()
            valid = result is not None and len(result) == device.numofchannel
            scans, remainder = divmod(consumed, device.numofbyteperscan)
            parameters = dict(channels=list(device.channels), read_digital=device.read_digital,
                              srate=device.srate, dec=device.dec, deca=device.deca,
                              binary_method=binary_method, bytes_per_scan=device.numofbyteperscan)
            self.record(session_id, parameters, start, end, consumed, scans,
                        remainder, valid, result is not None and not valid, failed)

    def record(self, session_id, parameters, start, end, consumed, scans,
               remainder, valid, invalid, failed):
        with self.lock:
            s = self.sessions.setdefault(session_id, dict(
                parameters=parameters, calls=0, bytes_read=0, complete_scans_read=0,
                scans_returned=0, scans_not_returned=0, max_scans_per_read=0,
                partial_reads=0, invalid_returns=0, read_errors=0, empty_calls=0,
                accounting_errors=0, first_nonempty_read_scans=None,
                scans_not_returned_after_first_nonempty_read=0,
                max_read_seconds=0.0, max_return_gap_seconds=None,
                _first_call=start, _last_call=end, _first_return=None, _last_return=None))
            s['calls'] += 1
            s['bytes_read'] += consumed
            s['complete_scans_read'] += scans
            s['scans_returned'] += int(valid)
            missing = max(0, scans - int(valid))
            s['scans_not_returned'] += missing
            s['max_scans_per_read'] = max(s['max_scans_per_read'], scans)
            s['partial_reads'] += int(remainder != 0)
            s['invalid_returns'] += int(invalid)
            s['read_errors'] += int(failed)
            s['empty_calls'] += int(not consumed and not valid and not failed)
            s['accounting_errors'] += int((valid and scans == 0) or parameters['binary_method'] != 1
                                          or parameters != s['parameters'])
            if scans:
                if s['first_nonempty_read_scans'] is None:
                    s['first_nonempty_read_scans'] = scans
                else:
                    s['scans_not_returned_after_first_nonempty_read'] += missing
            s['max_read_seconds'] = max(s['max_read_seconds'], end - start)
            s['_last_call'] = end
            if valid:
                if s['_last_return'] is not None:
                    gap = end - s['_last_return']
                    s['max_return_gap_seconds'] = max(s['max_return_gap_seconds'] or 0.0, gap)
                else:
                    s['_first_return'] = end
                s['_last_return'] = end

    def report(self, finished=False):
        with self.lock:
            sessions = deepcopy(self.sessions)
        for s in sessions.values():
            duration = s.pop('_last_call') - s.pop('_first_call')
            first, last = s.pop('_first_return'), s.pop('_last_return')
            s['observed_duration_seconds'] = duration
            s['scans_read_per_second'] = s['complete_scans_read'] / duration if duration > 0 else None
            s['scans_returned_per_second'] = s['scans_returned'] / duration if duration > 0 else None
            s['mean_return_gap_seconds'] = ((last - first) / (s['scans_returned'] - 1)
                                            if s['scans_returned'] > 1 else None)
            if any(s[k] for k in ('read_errors', 'partial_reads', 'invalid_returns', 'accounting_errors')):
                s['result'] = 'REVIEW_REQUIRED'
            elif s['scans_not_returned']:
                s['result'] = 'LOSS_OBSERVED'
            elif s['scans_returned']:
                s['result'] = 'NO_LOSS_OBSERVED'
            else:
                s['result'] = 'NO_DATA'
        return dict(schema_version=1, started_at=self.started_at,
                    updated_at=datetime.now(timezone.utc).isoformat(), launcher_finished=finished,
                    scope='Acquisition calls only; setup and pre-start trigger reads excluded. '
                          'Includes waiting between cycles. First read may contain pre-Start backlog.',
                    limits='Counters cover serial bytes consumed by binary method 1, not upstream '
                           'DAQ/USB losses, calibrated accuracy, graph-queue processing or database '
                           'delivery. Host read intervals are not hardware sample timestamps. '
                           'Instrumentation adds overhead. This report is not a waveform backup.',
                    sessions=sessions)


@contextmanager
def instrument_acquisition(application, window, audit):
    """Limit observation to the DAQ worker; retain all original return values."""
    context = threading.local()
    original_acquire = application.DaqThread.Read_and_Process_DaqData
    original_collect = application.daq.Daq_serial.collect_data

    def acquire(worker):
        context.session_id = window.session_id
        try:
            return original_acquire(worker)
        finally:
            context.session_id = None

    def collect(device, binary_method=1):
        session = getattr(context, 'session_id', None)
        read = lambda: original_collect(device, binary_method)
        return read() if session is None else audit.observe(device, read, session, binary_method)

    with patch.object(application.DaqThread, 'Read_and_Process_DaqData', acquire), \
         patch.object(application.daq.Daq_serial, 'collect_data', collect):
        yield


def write_report(path, report):
    """Replace a complete report atomically; periodic snapshots survive GUI failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New JSON report path (default: data/diagnostics/).')
    args = parser.parse_args()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = args.output or ROOT / 'data' / 'diagnostics' / f'acquisition_{stamp}_{uuid4().hex[:8]}.json'
    if output.exists():
        parser.error('Report already exists; choose a new output path.')
    audit = AcquisitionAudit()
    write_report(output, audit.report())
    print(f'Acquisition report: {output.resolve()}', flush=True)
    print('Use the normal GUI to record. Save the CSV/metadata files before Next or closing.', flush=True)
    sys.path.insert(0, str(ROOT))
    import main as application
    application.setup_logging()
    app = application.QtWidgets.QApplication([sys.argv[0]])
    window = application.MainWindow()
    window.setWindowTitle(window.windowTitle() + ' — acquisition diagnostic')

    def snapshot():
        try:
            write_report(output, audit.report())
        except OSError:
            application.logger.exception('Could not update acquisition diagnostic report')

    timer = application.QtCore.QTimer(window)
    timer.setInterval(5000)
    timer.timeout.connect(snapshot)
    with instrument_acquisition(application, window, audit):
        try:
            timer.start()
            window.showMaximized()
            app.exec_()
        finally:
            timer.stop()
            report = audit.report(finished=True)
            write_report(output, report)
    for session, s in report['sessions'].items():
        print(f"{session}: {s['result']} — read {s['complete_scans_read']}, "
              f"returned {s['scans_returned']}, not returned {s['scans_not_returned']} "
              f"({s['scans_not_returned_after_first_nonempty_read']} after the first nonempty read)")
    if not report['sessions']:
        print('NO_DATA: no acquisition reads were observed.')
    print(f'Report saved: {output.resolve()}')


if __name__ == '__main__':
    main()
