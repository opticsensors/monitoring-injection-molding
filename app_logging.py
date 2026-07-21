"""
Application-wide logging: one rotating file (logs/monitoring.log) + console.

Every module logs through ``logging.getLogger('<name>')`` and everything lands
in the same timeline (GUI events, DAQ, cycles, MQTT) - one merged log like the
Pi loggers' iot_platform.log. Uncaught exceptions are hooked into the log too,
so GUI crashes leave a trace instead of vanishing.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent / 'logs'
LOG_FILE = LOG_DIR / 'monitoring.log'


def setup_logging():
    """Configure the root logger once: rotating file + console + excepthook."""
    if getattr(setup_logging, '_configured', False):
        return
    setup_logging._configured = True

    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024,
                                       backupCount=5, encoding='utf-8')
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root.setLevel(logging.INFO)

    def _log_uncaught(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.getLogger('main').critical("Uncaught exception",
                                           exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _log_uncaught
    logging.getLogger('main').info("Session started - logging to %s", LOG_FILE)
