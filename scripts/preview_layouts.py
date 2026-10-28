"""Full inspector preview with simulated acquisition and server data.

Run: py -3.11 scripts/preview_layouts.py
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def isolated_preview_state():
    """Keep settings, metadata proposals and connection configuration disposable."""
    keys = ("MONITORING_ENV_FILE", "MONITORING_UI_SETTINGS_FILE")
    before = {key: os.environ.get(key) for key in keys}
    with tempfile.TemporaryDirectory(prefix="injection-layout-preview-") as directory:
        path = Path(directory)
        os.environ["MONITORING_ENV_FILE"] = str(path / ".env")
        os.environ["MONITORING_UI_SETTINGS_FILE"] = str(path / "ui.ini")
        import cycle_metadata as metadata
        previous = metadata.SETTINGS_FILE, metadata.EDITS_FILE
        metadata.SETTINGS_FILE = path / "settings.json"
        metadata.EDITS_FILE = path / "pending-edits.json"
        try:
            yield path
        finally:
            metadata.SETTINGS_FILE, metadata.EDITS_FILE = previous
            for key, value in before.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def wait_history(app, window):
    deadline = time.monotonic() + 8
    while window._history_jobs and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    if window._history_jobs:
        raise RuntimeError("The simulated History request did not finish.")


def settle_ui(app):
    # Layout switches post resize/adaptive-toolbar events for the following turn.
    for _ in range(4):
        app.sendPostedEvents()
        app.processEvents()


def render_previews(app, window, output):
    """Inspect the native preview at desktop/laptop sizes and actual UI states."""
    output.mkdir(parents=True, exist_ok=True)
    window.resize(1500, 960)
    for mode in ("monitor", "setup", "history"):
        window.presentation.navigate(mode)
        settle_ui(app)
        assert window.grab().save(str(output / f"inspector-{mode}.png"))
    window.presentation.navigate("monitor")
    window.resize(1100, 760)
    settle_ui(app)
    assert window.grab().save(str(output / "inspector-compact.png"))
    window.resize(1500, 960)
    keys = list(window.cycle_history)[-2:]
    window.plot_history_cycles(keys)
    window.plot_history_cycles(keys[:1])
    settle_ui(app)
    assert window.grab().save(str(output / "comparison.png"))
    window.start_monitoring()
    window._demo_timer.stop()
    settle_ui(app)
    assert window.grab().save(str(output / "waiting.png"))
    for _ in range(55):
        window.advance_demo()
    settle_ui(app)
    assert window.grab().save(str(output / "recording.png"))
    window.stopReading()
    window.presentation.navigate("history")
    settle_ui(app)
    assert window.grab().save(str(output / "interrupted.png"))
    window.presentation.navigate("setup")
    window.configure()
    for index, name in enumerate(("daq", "mold", "machine", "display")):
        window.ModuleSelectWin.tabs.setCurrentIndex(index)
        settle_ui(app)
        assert window.grab().save(str(output / f"configuration-{name}.png"))
    window.ModuleSelectWin.tabs.setCurrentIndex(0)
    window.presentation.navigate("monitor")
    print(f"Preview images: {output.resolve()}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=("inspector",), default="inspector", help=argparse.SUPPRESS)
    parser.add_argument("--workspace", choices=("setup", "monitor", "history"), default="monitor")
    parser.add_argument("--screenshots", type=Path, help="Render all preview states offscreen and exit.")
    args = parser.parse_args()
    if args.screenshots:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt5 import QtCore, QtGui, QtWidgets
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication([])
    with isolated_preview_state():
        from gui_preview import PreviewWindow
        window = PreviewWindow()
        window.presentation.navigate(args.workspace)
        screen = app.primaryScreen().availableGeometry()
        if not args.screenshots:
            window.resize(min(1500, screen.width() - 70), min(960, screen.height() - 80))
        window.show()
        settle_ui(app)
        if args.screenshots:
            render_previews(app, window, args.screenshots)
            wait_history(app, window)
            window.hide()
        else:
            app.exec_()


if __name__ == "__main__":
    main()
