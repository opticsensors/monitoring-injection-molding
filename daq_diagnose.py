"""
daq_diagnose.py
===============

Bench diagnostic for the two open DAQ questions (2026-07-17):

  A) Trigger flicker: does D4/D5 physically pulse when nothing is activated?
     Every D4/D5 edge is printed live with a timestamp and the width of the
     state that just ended. Repeated 20-60 ms pulses while everything is idle
     mean a real electrical pulse on the input (wiring / relay / sensor),
     not software: leave the rig idle and just watch.

  B) The rotating 28416 (= 0x6F00, a digital-word value) in the ANALOG
     columns of test_hardware: each variant below counts how many analog
     words per scan look like a digital word and how the affected slot moves
     scan-to-scan. Comparing variants tells us whether the artifact needs
     the digital slot, the decimation, or all 8 analog channels.

BEFORE RUNNING: unplug the DAQ's USB cable, wait 10 seconds, plug it back
in. A USB replug is the only full reset of the device's scan engine - it
rules out state left over from previous sessions.

Run:   py daq_diagnose.py      (~40 s total, one summary block per variant)
Stop:  Ctrl+C
"""

import time

from daq_connectivity import Daq_serial

SRATE = 6000
SECONDS_PER_VARIANT = 4.0

# (name, analog channels, read_digital, dec)
VARIANTS = [
    ("V1  test_hardware config: CH0-7 + digital, dec=100", list(range(8)), True, 100),
    ("V2  app config: CH0-3,5-7 + digital, dec=100", [0, 1, 2, 3, 5, 6, 7], True, 100),
    ("V3  no digital slot: CH0-7 only, dec=100", list(range(8)), False, 100),
    ("V4  no decimation: CH0-7 + digital, dec=1", list(range(8)), True, 1),
    ("V5  same as V1 again (stability check)", list(range(8)), True, 100),
]


def looks_digital(word):
    """High-byte-only value >= 0x1000: idle analog noise cannot produce this."""
    return (word & 0xFF) == 0 and word >= 0x1000


class ScanStats:
    """Parses the raw byte stream scan-by-scan and accumulates diagnostics."""

    def __init__(self, n_analog, read_digital):
        self.n_analog = n_analog
        self.read_digital = read_digital
        self.n_words = n_analog + (1 if read_digital else 0)
        self.scan_bytes = 2 * self.n_words
        self.buf = bytearray()
        self.scans = 0
        self.rogue = 0             # digital-like words found in ANALOG slots
        self.rogue_slots = []      # slot index of the (first) rogue of each scan
        self.drift = {}            # slot delta (mod n_words) between consecutive rogues
        self.bad_digital_slot = 0  # scans whose digital slot is NOT digital-like
        self.first_state = None    # (D4, D5) at start
        self.d_state = None
        self.d_since = None
        self.edges = []            # (t_rel_s, 'D4'/'D5', new_value, prev_width_s)
        self.t0 = None
        self.t_last = None

    def feed(self, data, now):
        self.buf += data
        while len(self.buf) >= self.scan_bytes:
            raw = self.buf[:self.scan_bytes]
            del self.buf[:self.scan_bytes]
            words = [raw[i] | (raw[i + 1] << 8) for i in range(0, self.scan_bytes, 2)]
            self._scan(words, now)

    def _scan(self, words, now):
        if self.t0 is None:
            self.t0 = now
        self.t_last = now
        self.scans += 1

        rogues = [i for i, w in enumerate(words[:self.n_analog]) if looks_digital(w)]
        if rogues:
            self.rogue += len(rogues)
            if self.rogue_slots:
                d = (rogues[0] - self.rogue_slots[-1]) % self.n_words
                self.drift[d] = self.drift.get(d, 0) + 1
            self.rogue_slots.append(rogues[0])

        if not self.read_digital:
            return
        dword = words[-1]
        if not looks_digital(dword):
            self.bad_digital_slot += 1
            return
        state = ((dword >> 12) & 1, (dword >> 13) & 1)  # (D4, D5)
        if self.d_state is None:
            self.first_state = state
            self.d_state = state
            self.d_since = now
        elif state != self.d_state:
            width = now - self.d_since
            for bit, name in ((0, 'D4'), (1, 'D5')):
                if state[bit] != self.d_state[bit]:
                    self.edges.append((now - self.t0, name, state[bit], width))
                    print(f"    EDGE t={now - self.t0:7.3f}s  {name} -> {state[bit]}"
                          f"   (previous state lasted {width * 1000:8.1f} ms)")
            self.d_state = state
            self.d_since = now

    def report(self):
        dur = (self.t_last - self.t0) if self.t0 is not None else 0.0
        rate = self.scans / dur if dur > 0 else 0.0
        print(f"  scans: {self.scans}  ({rate:.1f}/s over {dur:.1f} s)")
        print(f"  rogue digital-like words in ANALOG slots: {self.rogue}"
              f"  ({100.0 * self.rogue / max(1, self.scans):.1f}% of scans)")
        if self.drift:
            top = sorted(self.drift.items(), key=lambda kv: -kv[1])[:4]
            moves = ", ".join(f"delta {d} x{c}" for d, c in top)
            print(f"  rogue slot movement between occurrences (mod {self.n_words}): {moves}")
        if self.read_digital:
            print(f"  idle D4/D5 at start: {self.first_state}")
            print(f"  scans with a NON-digital value in the digital slot: {self.bad_digital_slot}")
            print(f"  D4/D5 edges seen: {len(self.edges)}")


def run_variant(name, channels, read_digital, dec):
    print(f"\n=== {name} ===")
    daq = Daq_serial(channels=channels, voltage_ranges=[10] * len(channels),
                     dec=dec, deca=1, srate=SRATE, output_mode='binary',
                     read_digital=read_digital)
    stats = ScanStats(len(channels), read_digital)
    try:
        daq.config_daq()   # now echo-synced + self-verifying (raises if the
                           # stream never matches the configured scan list)
        t_end = time.perf_counter() + SECONDS_PER_VARIANT
        while time.perf_counter() < t_end:
            n = daq.ser.in_waiting
            if n:
                stats.feed(daq.ser.read(n), time.perf_counter())
            else:
                time.sleep(0.002)
    finally:
        try:
            daq.close_serial()
        except Exception:
            pass
    stats.report()
    return stats


def main():
    print(__doc__)
    try:
        input("Unplug/replug the DAQ USB first, then press Enter to start... ")
    except EOFError:
        pass
    try:
        for variant in VARIANTS:
            try:
                run_variant(*variant)
            except RuntimeError as e:
                print(f"  CONFIG FAILED PERMANENTLY: {e}")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    print("""
================ HOW TO READ THE RESULTS ================
- EDGE lines while everything is idle -> the input PHYSICALLY pulsed.
  Check the (new) D4 wire and screw terminal, the relay contact, and
  whether the sensor sees anything moving. Software cannot fake these.
- V1 rogue > 0 but V3 rogue = 0  -> artifact needs the digital slot.
- V1 rogue > 0 but V4 rogue = 0  -> artifact needs decimation (dec > 1).
- V2 rogue = 0 while V1 rogue > 0 -> the app's 7-channel config is clean;
  only test_hardware's 8-channel view ever showed the artifact.
- Rogue > 0 in V1 immediately after a real USB replug -> it is inherent
  to that configuration (firmware), not stale state; we then just avoid
  or ignore that configuration.
- Any 'NON-digital value in the digital slot' > 0 -> true misalignment,
  a different and more serious problem: report it.
""")


if __name__ == "__main__":
    main()
