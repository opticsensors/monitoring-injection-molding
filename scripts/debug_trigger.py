"""
debug_trigger.py
================

Trigger-only diagnostic for the DATAQ digital inputs D0..D6.

Why this exists: ``test_hardware.py`` prints 4x/s but reads continuously, so a
short trigger pulse is read and thrown away without ever reaching the screen.
"I never saw it toggle" is therefore not proof that it never toggled.

This script inspects EVERY scan and never forgets an edge. It reports, per bit:
how many edges it saw, how long it stayed in each state, and the shortest pulse
it caught. It also measures the effective scan rate, so you know what pulse
width the hardware itself is physically able to resolve.

It reads the real channel/rate settings from config/daq_config_defaults.json, so
it sees exactly what main.py would see, and it flags which bit main.py is
currently configured to trigger on.

Run:   py -3.11 scripts/debug_trigger.py
Stop:  Ctrl+C   ->  prints the summary and the verdict

While it runs, exercise every trigger source in turn - manual switch, inductive
sensor, and (once wired) the machine signal. All three are parallelled onto the
main relay coil, so all three must produce edges on the SAME input: the one the
main relay's dry contact (COM 21 / NC 22) is wired to. A source that produces no
edges is not reaching that coil.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import CONFIG_DEFAULTS                                     # noqa: E402
from sensor_types import (TRIGGER_TYPE, DIGITAL_INPUTS, digital_bit,   # noqa: E402
                          normalize_trigger_type)
from daq_connectivity import Daq_serial                                # noqa: E402

BINARY_METHOD = 1      # must match main.py
PRINT_PERIOD_S = 0.5   # live-line period (edge counts are cumulative, nothing is lost)
N_BITS = 7             # D0..D6


class BitStats:
    """Edge/duration bookkeeping for one digital input, updated on every scan."""

    def __init__(self, bit):
        self.bit = bit
        self.state = None
        self.rises = 0
        self.falls = 0
        self.t_state_start = None
        self.t_high = 0.0
        self.t_low = 0.0
        self.min_high = None
        self.min_low = None
        self.first_edge = None
        self.last_edge = None

    def update(self, value, t):
        if self.state is None:
            self.state = value
            self.t_state_start = t
            return
        if value == self.state:
            return

        dur = t - self.t_state_start
        if self.state == 1:
            self.t_high += dur
            self.min_high = dur if self.min_high is None else min(self.min_high, dur)
            self.falls += 1
        else:
            self.t_low += dur
            self.min_low = dur if self.min_low is None else min(self.min_low, dur)
            self.rises += 1

        self.state = value
        self.t_state_start = t
        if self.first_edge is None:
            self.first_edge = t
        self.last_edge = t

    @property
    def edges(self):
        return self.rises + self.falls

    def totals(self, now):
        """(t_high, t_low) including the state currently in progress."""
        hi, lo = self.t_high, self.t_low
        if self.state is not None and self.t_state_start is not None:
            dur = now - self.t_state_start
            if self.state == 1:
                hi += dur
            else:
                lo += dur
        return hi, lo

    def verdict(self):
        if self.edges == 0 and self.state == 1:
            return "idle HIGH, never moved -> nothing pulling it down (unconnected, or signal never reaches GND)"
        if self.edges == 0 and self.state == 0:
            return "STUCK LOW -> tied to GND: swapped wires (10 V on the GND pin), or damaged input"
        return "ALIVE"


def fmt_ms(seconds):
    return "   --  " if seconds is None else f"{seconds * 1000:7.1f}"


def main():
    channels = list(CONFIG_DEFAULTS['channels'])
    ranges = list(CONFIG_DEFAULTS['voltage_ranges'])
    srate = CONFIG_DEFAULTS['sample_rate_hz']
    dec = CONFIG_DEFAULTS['decimation']
    n_analog = len(channels)

    # Replicates main.py trigger_bit_index(): which bit would actually gate cycles?
    trigger_mode = CONFIG_DEFAULTS.get('trigger_mode', 'None')
    digital_map = CONFIG_DEFAULTS.get('digital_map', {})
    active_bit = None
    active_name = None
    if trigger_mode != 'None':
        for name in DIGITAL_INPUTS:
            if normalize_trigger_type(digital_map.get(name)) == TRIGGER_TYPE:
                active_bit, active_name = digital_bit(name), name
                break

    print("=" * 78)
    print(f"config: channels={channels}  srate={srate} Hz  decimation={dec}")
    print(f"trigger_mode={trigger_mode!r}  digital_map={digital_map}")
    if active_bit is None:
        print("ACTIVE TRIGGER: none -- main.py will NEVER start a cycle with this config.")
    else:
        print(f"ACTIVE TRIGGER: {active_name} (bit {active_bit}) -- this is the bit main.py gates cycles on.")
    print("=" * 78)
    print()
    print("Exercise EVERY trigger source in turn: manual switch, inductive sensor,")
    print("machine signal. All are parallelled onto the main relay coil, so all must")
    print("produce edges on the same input. Ctrl+C when done.")
    print()

    daq = Daq_serial(
        channels=channels,
        voltage_ranges=ranges,
        dec=dec,
        deca=1,
        srate=srate,
        output_mode='binary',
        read_digital=True,
    )
    daq.config_daq()
    print("connected, reading every scan...\n")

    bits = [BitStats(b) for b in range(N_BITS)]
    a_min = [None] * n_analog
    a_max = [None] * n_analog
    scans = 0
    words_seen = {}
    t0 = time.perf_counter()
    last_print = 0.0

    try:
        while True:
            scan = daq.collect_data(BINARY_METHOD)
            if scan is None or len(scan) <= n_analog:
                time.sleep(0.0005)
                continue

            t = time.perf_counter()
            scans += 1

            for i in range(n_analog):
                v = scan[i]
                if a_min[i] is None or v < a_min[i]:
                    a_min[i] = v
                if a_max[i] is None or v > a_max[i]:
                    a_max[i] = v

            word = int(scan[n_analog]) & 0xFFFF
            words_seen[word] = words_seen.get(word, 0) + 1
            decoded = Daq_serial.decode_digital_word(word)
            for b in range(N_BITS):
                bits[b].update(decoded[f'D{b}'], t)

            if t - last_print >= PRINT_PERIOD_S:
                last_print = t
                live = " ".join(f"D{b}={bits[b].state}" for b in range(N_BITS))
                edge = " ".join(f"D{b}:{bits[b].edges}" for b in range(N_BITS))
                rate = scans / max(t - t0, 1e-9)
                print(f"0x{word:04X} [{live}] | edges {edge} | {rate:5.1f} scan/s")

    except KeyboardInterrupt:
        pass
    finally:
        try:
            daq.close_serial()
        except Exception as e:
            print(f"error closing serial: {e}")

    now = time.perf_counter()
    elapsed = now - t0
    rate = scans / max(elapsed, 1e-9)

    print()
    print("=" * 78)
    print(f"SUMMARY  --  {elapsed:.1f} s, {scans} scans, {rate:.1f} scan/s effective")
    print(f"resolution: pulses shorter than ~{1000.0 / max(rate, 1e-9):.1f} ms CANNOT be seen by the hardware")
    print("=" * 78)
    print()
    print("bit  now  rises  falls   %high   min_high(ms) min_low(ms)  verdict")
    for b in range(N_BITS):
        s = bits[b]
        hi, lo = s.totals(now)
        pct = 100.0 * hi / max(hi + lo, 1e-9)
        mark = " <== ACTIVE" if active_bit == 8 + b else ""
        print(f"D{b}    {s.state}   {s.rises:5d}  {s.falls:5d}  {pct:6.1f}%  "
              f"{fmt_ms(s.min_high)}      {fmt_ms(s.min_low)}   {s.verdict()}{mark}")

    print()
    print("distinct digital words seen:")
    for w, n in sorted(words_seen.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / max(scans, 1)
        print(f"  0x{w:04X}  {n:8d} scans ({pct:5.1f}%)")
    if len(words_seen) == 1:
        print("  -> ONE word only: no digital input changed at all during the capture.")

    print()
    print("analog raw counts (min .. max):")
    for i, ch in enumerate(channels):
        span = (a_max[i] - a_min[i]) if a_min[i] is not None else 0
        note = "  <- flat, channel saw no activity" if span < 50 else ""
        print(f"  CH{ch}: {a_min[i]:>8} .. {a_max[i]:>8}   span {span:>8}{note}")

    print()
    if active_bit is None:
        print("VERDICT: no trigger bit is mapped -- fix trigger_mode / digital_map first.")
    else:
        s = bits[active_bit - 8]
        if s.edges > 0:
            print(f"VERDICT: {active_name} is toggling ({s.edges} edges). main.py should now cut cycles.")
            print(f"         HIGH = cycle running. {active_name} was HIGH "
                  f"{100.0 * s.totals(now)[0] / max(sum(s.totals(now)), 1e-9):.0f}% of the time --")
            print("         if that is inverted from your machine's mould-closed time, the polarity is backwards.")
        elif s.state == 0:
            print(f"VERDICT: {active_name} STUCK LOW, 0 edges -- the main relay never energised,")
            print("         or its contact is not reaching this input. Check COM 21 / NC 22 on the")
            print("         main relay, and that the source you are using actually pulls in the coil.")
            print("         Jumper to GND gave nothing either -> the input is dead; move to a free")
            print("         one (any shown above as 'idle HIGH') and change the Digital table.")
        else:
            print(f"VERDICT: {active_name} idle HIGH, 0 edges -- nothing is pulling it to GND.")
    print()


if __name__ == "__main__":
    main()
