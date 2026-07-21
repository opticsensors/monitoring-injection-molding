"""
Application configuration defaults.

Loads ``daq_config_defaults.json`` (next to this file) on import and exposes the
merged result as ``CONFIG_DEFAULTS``. Built-in fallbacks are used if the file is
missing or invalid. Pure: only ``json`` / ``pathlib``, no Qt.
"""
import json
from pathlib import Path

# Path to configuration defaults file (same folder as the source files).
CONFIG_DEFAULTS_FILE = Path(__file__).parent / 'daq_config_defaults.json'


def load_config_defaults():
    """Load configuration defaults from JSON file."""
    defaults = {
        "monitoring_time_s": 300,
        "channels": [0, 1, 2, 3, 5, 6, 7],
        "channel_types": ["T_futaba", "T_futaba", "P_kistler", "P_kistler",
                          "P_machine", "S_speed", "S_position"],
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
        "trigger_mode": "Inductive",
        "trigger_wiring": "digital",
        "digital_map": {"D4": "Inductive", "D5": "Machine_signal"},
        "conversion": {
            "T_futaba":   {"deg_per_volt": 100.0},
            "P_kistler":  {"s0": 2.500, "s1": 2.508, "Qmax": 20000.0},
            "P_machine":  {"initial": 0.0, "resolution_mV": 10.0},
            "S_speed":    {"initial": 0.0, "resolution_mV": 10.0},
            "S_position": {"initial": 0.0, "resolution_mV": 10.0}
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

    return defaults


# Load defaults at import time.
CONFIG_DEFAULTS = load_config_defaults()
