"""
Application configuration defaults.

Loads ``daq_config_defaults.json`` (next to this file) on import and exposes the
merged result as ``CONFIG_DEFAULTS``. Built-in fallbacks are used if the file is
missing or invalid. Standard library only, no Qt. Input ranges are fixed at ±10 V.
"""
import json
import logging
from pathlib import Path

# Path to configuration defaults file (in the config/ folder).
CONFIG_DEFAULTS_FILE = Path(__file__).parent / 'config' / 'daq_config_defaults.json'
DAQ_INPUT_RANGE_V = 10


def fixed_voltage_ranges(channels):
    """This application's physical-unit calibration requires +/-10 V inputs."""
    return [DAQ_INPUT_RANGE_V] * len(channels)


def load_config_defaults():
    """Load configuration defaults from JSON file."""
    defaults = {
        "monitoring_time_s": 300,
        "channels": [0, 1, 2, 3, 5, 6, 7],
        "channel_types": ["T_futaba", "T_futaba", "P_kistler", "P_kistler",
                          "P_machine", "vel_screw", "pos_screw"],
        "voltage_ranges": [10, 10, 10, 10, 10, 10, 10],
        "sample_rate_hz": 6000,
        "decimation": 100,
        "display_points": 1600,
        "plot_refresh_rate_ms": 50,
        "separate_plots": False,
        "machine_layout": "shared",
        "plot_channels": [0, 1, 2, 3, 5, 6, 7],
        "mqtt_enabled": False,
        "machine_id": "160t",
        "min_cycle_s": 1.0,
        # Which source drives the main relay (see TRIGGER_MODES: 'None' |
        # 'Inductive' | 'Machine signal' | 'Machine mold position' | 'Manual').
        # All of them are read from the one digital input marked 'trigger' below;
        # 'Machine mold position' is the only active-LOW one.
        "trigger_mode": "Inductive",
        "digital_map": {"D0": "none", "D1": "none", "D2": "none", "D3": "none",
                        "D4": "trigger", "D5": "none", "D6": "none"},
        # Runner geometry behind the apparent-viscosity readout (see rheology.py).
        # L_mm is the distance between the two cavity-pressure sensors - both the
        # melt-front travel Δx and the shear-stress length - and Rc_mm the runner
        # radius. The cross-section A = π Rc² is derived, never stored.
        "viscosity": {"L_mm": 100.0, "Rc_mm": 1.5},
        "conversion": {
            "T_futaba":   {"deg_per_volt": 100.0},
            "P_kistler":  {"s0": 2.500, "s1": 2.508, "Qmax": 20000.0},
            "P_machine":  {"initial": 0.0, "resolution_mV": 10.0},
            "vel_screw":  {"initial": 0.0, "resolution_mV": 10.0},
            "pos_screw":  {"initial": 0.0, "resolution_mV": 10.0}
        }
    }

    try:
        if CONFIG_DEFAULTS_FILE.exists():
            loaded = json.loads(CONFIG_DEFAULTS_FILE.read_text())
            defaults.update(loaded)
            print(f"Loaded configuration defaults from: {CONFIG_DEFAULTS_FILE}")
        else:
            print(f"Config file not found at {CONFIG_DEFAULTS_FILE}, using built-in defaults")
    except Exception as e:
        print(f"Error loading config defaults: {e}, using built-in defaults")

    ranges = fixed_voltage_ranges(defaults['channels'])
    if defaults.get('voltage_ranges') != ranges:
        logging.getLogger(__name__).warning(
            "This app requires +/-10 V on every channel; ignoring configured voltage ranges.")
    defaults['voltage_ranges'] = ranges
    return defaults


# Load defaults at import time.
CONFIG_DEFAULTS = load_config_defaults()
