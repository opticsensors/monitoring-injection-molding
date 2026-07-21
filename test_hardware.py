"""
test_hardware.py
================

Standalone hardware check for the DATAQ DAQ, independent of the GUI.

Use this to confirm, BEFORE running main.py, that:
  1. the analog channels stream sensible raw counts, and
  2. the digital inputs D4 / D5 (the two triggers) toggle 0 <-> 1 as expected.

It prints, a few times per second:
  - the raw counts of every configured analog channel, and
  - the raw digital word plus the decoded D0..D6 bits (D4 and D5 highlighted).

Toggle each trigger by hand and watch which bit changes. The inputs are idle-HIGH
(internal pull-ups), so a port reads 1 when unconnected and 0 only when you pull it
to GND - applying a positive voltage will NOT change an already-high input. On this
unit the inputs live in the high byte (D4=bit12, D5=bit13), so the idle word is
0x7F00; grounding D5 gives 0x5F00 and grounding D4 gives 0x6F00.

Run:   py test_hardware.py
Stop:  Ctrl+C
"""

import time
from daq_connectivity import Daq_serial

# ----------------------------------------------------------------------------
# EDIT THESE to match how you have things wired for the test
# ----------------------------------------------------------------------------
ANALOG_CHANNELS = [0, 1, 2, 3, 4, 5, 6, 7]     # analog channels to read
VOLTAGE_RANGES  = [10] * len(ANALOG_CHANNELS)  # per-channel range (V): 0.2/0.5/1/2/5/10
SAMPLE_RATE_HZ  = 6000
DECIMATION      = 100
DECA            = 1
READ_DIGITAL    = True     # set False to test analog only
BINARY_METHOD   = 1        # 1 or 2 (must match how main.py reads)
PRINT_PERIOD_S  = 0.25     # how often to print a status line
# ----------------------------------------------------------------------------


def fmt_analog(values, n_analog):
    parts = []
    for i in range(n_analog):
        v = values[i] if i < len(values) else None
        parts.append(f"CH{ANALOG_CHANNELS[i]}={v:>7}" if v is not None else f"CH{ANALOG_CHANNELS[i]}=   ---")
    return "  ".join(parts)


def fmt_digital(word):
    bits = Daq_serial.decode_digital_word(word)
    d4, d5 = bits['D4'], bits['D5']
    all_bits = " ".join(f"D{b}={bits[f'D{b}']}" for b in range(7))
    return f"raw=0x{int(word) & 0xFFFF:04X} [{all_bits}]   >>> D4={d4}  D5={d5} <<<"


def main():
    n_analog = len(ANALOG_CHANNELS)
    print("Connecting to DATAQ device...")
    daq = Daq_serial(
        channels=ANALOG_CHANNELS,
        voltage_ranges=VOLTAGE_RANGES,
        dec=DECIMATION,
        deca=DECA,
        srate=SAMPLE_RATE_HZ,
        output_mode='binary',
        read_digital=READ_DIGITAL,
    )
    daq.config_daq()
    print("Connected. Reading... (Ctrl+C to stop)\n")
    if READ_DIGITAL:
        print("Toggle each trigger and watch which Dx bit flips.\n")

    last_print = 0.0
    try:
        while True:
            scan = daq.collect_data(BINARY_METHOD)
            if scan is None or len(scan) < n_analog + (1 if READ_DIGITAL else 0):
                time.sleep(0.001)
                continue

            now = time.perf_counter()
            if now - last_print >= PRINT_PERIOD_S:
                last_print = now
                line = fmt_analog(scan, n_analog)
                if READ_DIGITAL:
                    digital_word = scan[n_analog]     # digital word is the last value in the scan
                    line += "   ||   " + fmt_digital(digital_word)
                print(line)

            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        try:
            daq.close_serial()
        except Exception as e:
            print(f"Error closing serial: {e}")
        print("Done.")


if __name__ == "__main__":
    main()
