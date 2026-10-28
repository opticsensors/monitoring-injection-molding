"""Compatibility launcher for the shared offline desktop preview."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    # History simulation is always included in the shared preview.
    if "--history-demo" in sys.argv:
        sys.argv.remove("--history-demo")
    from scripts.preview_layouts import main as preview_main
    preview_main()


if __name__ == "__main__":
    main()
