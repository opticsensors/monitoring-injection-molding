"""Cycle metadata and wire format. No hardware, network, or automatic capture archive.

Only reusable operator preferences are automatically persisted. Cycle metadata
is kept in memory and written with the user's Save action (or explicit export).
"""
from copy import deepcopy
import csv
import json
import math
from pathlib import Path
import re
import time
from uuid import uuid4

SCHEMA_VERSION = 1
# Add pressure settings here; keys are stable identifiers, labels can change.
PRESSURE_SETTINGS = (("limit", "Limit pressure (bar)"),)
SETTINGS_FILE = Path(__file__).parent / "data" / "run_setup.json"


def optional_number(value, label, minimum=0):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number or blank.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number or blank.") from None
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{label} must be finite and at least {minimum}.")
    return number


def operator_settings(machine_id, material=None, mold_temperature_c=None,
                      pressure_settings_bar=None):
    machine = str(machine_id).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", machine):
        raise ValueError("Machine ID: use 1-64 letters, numbers, dots, underscores or hyphens.")
    material = str(material or "").strip() or None
    if material and (len(material) > 200 or any(ord(c) < 32 for c in material)):
        raise ValueError("Material must be at most 200 characters, on one line.")
    pressures = pressure_settings_bar or {}
    return {"machine_id": machine, "material": material,
            "mold_temperature_c": optional_number(mold_temperature_c, "Mold setpoint", -273.15),
            "pressure_settings_bar": {key: optional_number(pressures.get(key), label)
                                      for key, label in PRESSURE_SETTINGS}}


def load_preferences(default_machine, path=None):
    path = Path(path or SETTINGS_FILE)
    if not path.exists():
        return operator_settings(default_machine)
    value = json.loads(path.read_text(encoding="utf-8"))
    return operator_settings(**value)


def write_json(path, value):
    """Atomic replacement for preferences and explicitly requested exports."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def identity(capture):
    return (capture["machine_id"], capture["session_id"], int(capture["cycle_id"]))


def new_measurements():
    return {"revision": 0, "update_id": str(uuid4()), "weight_g": None,
            "length_mm": None, "updated_at_ns": str(time.time_ns())}


def edit_measurements(previous, weight, length):
    result = new_measurements()
    result.update(revision=previous["revision"] + 1,
                  weight_g=optional_number(weight, "Weight (g)"),
                  length_mm=optional_number(length, "Spiral length (mm)"))
    return result


def samples_for(capture, xdata, rows):
    if len(xdata) != len(rows) or not xdata:
        raise ValueError("A capture needs matching, non-empty time and sample arrays.")
    config = capture["config_snapshot"]
    names, indices = config["field_names"], config["saved_indices"]
    if not names or len(names) != len(indices) or len(set(names)) != len(names):
        raise ValueError("Invalid frozen channel configuration.")
    result = []
    previous = None
    for index, (x, row) in enumerate(zip(xdata, rows)):
        if not math.isfinite(float(x)) or x < 0:
            raise ValueError("Invalid sample time.")
        stamp = int(capture["base_time_ns"]) + round(float(x) * 1_000_000_000)
        if previous is not None and stamp <= previous:
            raise ValueError("Sample timestamps must be distinct and increasing.")
        previous = stamp
        sample = {"timestamp_ns": str(stamp), "time_s": round(float(x), 6),
                  "sample_index": index}
        for name, source_index in zip(names, indices):
            if source_index >= len(row) or not math.isfinite(float(row[source_index])):
                raise ValueError(f"Missing or non-finite sample for {name}.")
            sample[name] = float(row[source_index])
        result.append(sample)
    return result


def finish_capture(snapshot, session_id, session_cycle, cycle_id, session_ns,
                   start_s, end_s, xdata, rows, status="complete", reason="trigger"):
    snapshot = deepcopy(snapshot)
    capture = {"machine_id": snapshot.pop("machine_id"), "session_id": session_id,
               "cycle_id": int(cycle_id), "session_cycle": int(session_cycle),
               "mode": "cycle" if cycle_id else "continuous", "status": status,
               "reason": reason, "base_time_ns": str(session_ns + round(start_s * 1e9)),
               "trigger_start_ns": str(session_ns + round(start_s * 1e9)) if cycle_id else None,
               "trigger_end_ns": str(session_ns + round(end_s * 1e9))
                   if cycle_id and end_s is not None and status == "complete" else None,
               "timing_source": "host_elapsed", **snapshot}
    samples = samples_for(capture, xdata, rows)
    capture.update(first_time_ns=samples[0]["timestamp_ns"],
                   last_time_ns=samples[-1]["timestamp_ns"], sample_count=len(samples))
    entry = {"capture": capture, "measurements": new_measurements(), "delivery": "Not sent"}
    return entry, capture_message(entry, samples)


def capture_message(entry, samples):
    return deepcopy({"schema_version": SCHEMA_VERSION, "kind": "capture",
                     "capture": entry["capture"], "measurements": entry["measurements"],
                     "samples": samples})


def measurement_message(entry):
    machine, session, cycle = identity(entry["capture"])
    return deepcopy({"schema_version": SCHEMA_VERSION, "kind": "measurements",
                     "machine_id": machine, "session_id": session, "cycle_id": cycle,
                     "measurements": entry["measurements"]})


def export_metadata(path, entries):
    write_json(path, {"schema_version": SCHEMA_VERSION, "kind": "cycle_metadata_export",
                      "cycles": list(entries)})


def export_cycle_summary(path, entries):
    """Write one row per capture, with frozen settings and the latest measurements.

    Called inside the session export's staging directory. Unknown values become
    empty CSV cells; zero remains a real measurement. Names match the SQL catalog.
    """
    pressure_keys = [key for key, _ in PRESSURE_SETTINGS]
    fields = ["machine_id", "session_id", "cycle_id", "session_cycle", "material",
              "mold_temperature_c", *[f"pressure_{key}_bar" for key in pressure_keys],
              "weight_g", "length_mm", "mode", "acquisition_status", "acquisition_reason",
              "sample_count", "first_time_ns", "last_time_ns", "metadata_revision"]
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entry in entries:
            capture, measurements = entry["capture"], entry["measurements"]
            row = {name: capture.get(name) for name in fields}
            row.update(weight_g=measurements.get("weight_g"),
                       length_mm=measurements.get("length_mm"),
                       metadata_revision=measurements["revision"],
                       acquisition_status=capture["status"],
                       acquisition_reason=capture.get("reason"))
            for key in pressure_keys:
                row[f"pressure_{key}_bar"] = capture["pressure_settings_bar"].get(key)
            writer.writerow(row)


def read_metadata(path, *, with_source=False):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION or data.get("kind") != "cycle_metadata_export":
        raise ValueError("This is not a supported cycle metadata export.")
    entries = data.get("cycles")
    if not isinstance(entries, list):
        raise ValueError("Missing cycles list.")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("capture"), dict) or not isinstance(entry.get("measurements"), dict):
            raise ValueError("Invalid cycle metadata entry.")
        capture, measurements = entry["capture"], entry["measurements"]
        if type(capture.get("cycle_id")) is not int or not 0 <= capture["cycle_id"] <= 9007199254740991:
            raise ValueError("Invalid cycle number.")
        for name, limit in (("machine_id", 128), ("session_id", 200)):
            value = capture.get(name)
            if not isinstance(value, str) or not 1 <= len(value) <= limit or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"Invalid {name}.")
        if capture.get("mode") not in ("cycle", "continuous") or capture.get("status") not in ("complete", "interrupted", "legacy"):
            raise ValueError("Invalid capture mode or outcome.")
        if not isinstance(capture.get("pressure_settings_bar"), dict):
            raise ValueError("Missing pressure settings.")
        for name in ("first_time_ns", "last_time_ns"):
            if not isinstance(capture.get(name), str) or not capture[name].isdigit():
                raise ValueError("Invalid capture bounds.")
        if not isinstance(measurements.get("update_id"), str) or not measurements["update_id"]:
            raise ValueError("Missing measurement update ID.")
        key = identity(capture)
        if not key[0] or not key[1] or key[2] < 0 or key in seen:
            raise ValueError("Invalid or duplicate cycle identity in export.")
        seen.add(key)
        if type(measurements["revision"]) is not int or not 0 <= measurements["revision"] <= 9007199254740991:
            raise ValueError("Invalid measurement revision.")
        for name in ("weight_g", "length_mm"):
            measurements[name] = optional_number(measurements.get(name), name)
        entry["delivery"] = "Imported; server state unconfirmed"
    return (entries, data.get('source', 'local')) if with_source else entries
