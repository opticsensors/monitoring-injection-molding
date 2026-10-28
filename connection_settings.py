"""Shared commissioning file for MQTT and read-only History access."""
import os
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None

ROOT = Path(__file__).resolve().parent
_local = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "InjectionMonitoring" / ".env"
# .gitignore does not prevent OneDrive uploading a secret. Use a local path for
# synced checkouts; MONITORING_ENV_FILE supports a managed installation location.
ENV_FILE = Path(os.environ.get("MONITORING_ENV_FILE") or
                (_local if any(part.lower().startswith("onedrive") for part in ROOT.parts) else ROOT / ".env"))


def read_env_file(path=None):
    path = Path(path or ENV_FILE)
    if dotenv_values:
        return dotenv_values(path, interpolate=False)
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def history_settings():
    values = read_env_file()
    url, token = (values.get("HISTORY_URL") or "").strip(), (values.get("HISTORY_TOKEN") or "").strip()
    if not url or not token:
        raise ValueError(f"Set HISTORY_URL and HISTORY_TOKEN in {ENV_FILE}")
    return url, token
