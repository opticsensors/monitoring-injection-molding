"""
MQTT cloud publisher.

Publishes cycle/session data batches (list-of-record dicts) to an MQTT broker
from a background worker thread, so the GUI never blocks on the network.

Connection settings come from a ``.env`` file next to this module with the
keys ``BROKER``, ``PORT``, ``TOPIC``, ``user`` and ``password``.

Batches that cannot be delivered (broker down, no network) are spilled to the
``pending/`` folder on disk and drained automatically once the broker is
reachable again - so no cycle is ever lost. Activity goes to the shared
application log (see app_logging.py).

Pure Python (threading / queue / paho-mqtt / python-dotenv): no Qt, no DAQ.
"""
import json
import logging
import queue
import socket
import threading
import time
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:          # python-dotenv not installed: minimal parser below
    dotenv_values = None

import paho.mqtt.client as mqtt

_MODULE_DIR = Path(__file__).parent
ENV_FILE = _MODULE_DIR / '.env'
PENDING_DIR = _MODULE_DIR / 'data' / 'pending'

logger = logging.getLogger('mqtt_publisher')


def _read_env_file(path):
    """Minimal .env fallback parser (KEY=VALUE lines, strips quotes)."""
    vals = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            vals[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return vals


def load_settings():
    """Read broker settings from the .env file next to this module.

    The file is read directly (never through os.environ) so keys like ``user``
    cannot collide with same-named Windows/shell environment variables.
    Raises RuntimeError if BROKER, PORT or TOPIC is missing.
    """
    vals = dotenv_values(ENV_FILE) if dotenv_values else _read_env_file(ENV_FILE)
    broker = (vals.get('BROKER') or '').strip()
    port = (vals.get('PORT') or '').strip()
    topic = (vals.get('TOPIC') or '').strip()
    if not broker or not port or not topic:
        raise RuntimeError(
            f"MQTT settings missing. Set BROKER, PORT and TOPIC in {ENV_FILE}")
    return {
        'broker': broker,
        'port': int(port),
        'topic': topic,
        'user': vals.get('user') or '',
        'password': vals.get('password') or '',
    }


def check_connectivity(machine_id='machine-01', progress=None, connect_timeout=5.0):
    """One-shot cloud self-test, run once at startup after the config is applied.

    Runs the standard MQTT health-check sequence using the settings from .env:
      1. TCP reachability to the broker host:port. This works whether the broker
         is on the local network (as here, 172.20.48.28) or in the cloud, and is
         the signal that actually matters - not public-internet reachability.
      2. MQTT connect + CONNACK (verifies the broker accepts us + credentials).
      3. A QoS-1 test publish to '<machine_id>/status' - a dedicated health
         topic, never the real data topic - waiting for the broker's PUBACK.

    ``progress(level, message)`` is called for each step (level is one of
    'info' | 'ok' | 'warn' | 'fail') so a GUI can stream results live. This
    function is blocking and must be run off the GUI thread. It never raises;
    it returns ``(connected_ok: bool, published_ok: bool)``.
    """
    def _p(level, msg):
        if progress:
            progress(level, msg)

    try:
        settings = load_settings()
    except Exception as e:
        _p('fail', f"MQTT settings error: {e}")
        return False, False

    broker, port, topic = settings['broker'], settings['port'], settings['topic']
    _p('info', f"Cloud self-test: broker {broker}:{port}, data topic {topic}")

    # 1) TCP reachability to the broker (LAN or cloud) -------------------------
    try:
        with socket.create_connection((broker, port), timeout=connect_timeout):
            pass
        _p('ok', f"Network path to broker {broker}:{port}: reachable")
    except Exception as e:
        _p('fail', f"Broker {broker}:{port} unreachable ({e}). "
                   "Check the network/Wi-Fi, the broker IP/port and any firewall.")
        return False, False

    # 2) MQTT connect + CONNACK ------------------------------------------------
    result = {'rc': None}
    done = threading.Event()

    def _on_connect(client, userdata, flags, rc):
        result['rc'] = rc
        done.set()

    client_id = f"daqmon-selftest-{machine_id}-{socket.gethostname()}"
    try:
        try:  # paho-mqtt >= 2.0
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
        except AttributeError:  # paho-mqtt 1.x
            client = mqtt.Client(client_id=client_id)
        if settings['user']:
            client.username_pw_set(settings['user'], settings['password'])
        client.on_connect = _on_connect
        client.connect_async(broker, port, keepalive=30)
        client.loop_start()
    except Exception as e:
        _p('fail', f"MQTT connect error: {e}")
        try:
            client.loop_stop()
        except Exception:
            pass
        return False, False

    if not done.wait(timeout=connect_timeout) or result['rc'] != 0:
        _p('fail', f"MQTT broker refused/timed out on connect (rc={result['rc']}).")
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
        return False, False
    _p('ok', "MQTT broker: connected (credentials accepted)")

    # 3) QoS-1 test publish to the health topic (never the data topic) ---------
    health_topic = f"{machine_id}/status"
    published = False
    try:
        payload = json.dumps({'status': 'healthcheck',
                              'machine_id': str(machine_id),
                              'timestamp_ns': time.time_ns()})
        info = client.publish(health_topic, payload, qos=1)
        info.wait_for_publish(timeout=connect_timeout)
        published = info.is_published()
    except Exception as e:
        _p('warn', f"Test publish error: {e}")

    if published:
        _p('ok', f"Test publish to {health_topic}: acknowledged - cloud upload verified.")
    else:
        _p('warn', f"Connected, but the test publish to {health_topic} was not "
                   "acknowledged (possible broker ACL). Live data upload may still work.")

    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass
    return True, published


class MqttPublisher:
    """Background MQTT publisher with disk spill-over for offline periods.

    Usage:
        pub = MqttPublisher(machine_id='160t')  # reads .env, raises if missing
        pub.start()
        pub.publish_records([{...}, {...}])     # one batch = one MQTT message
        pub.stop()
    """

    def __init__(self, machine_id='machine-01'):
        self.settings = load_settings()
        self.machine_id = str(machine_id)
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True,
                                        name='MqttPublisherWorker')

        # Stable client_id + clean_session=False lets the broker hold QoS>=1
        # messages for us across reconnects.
        client_id = f"daqmon-{self.machine_id}-{socket.gethostname()}"
        try:
            # paho-mqtt >= 2.0
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1,
                                      client_id=client_id, clean_session=False)
        except AttributeError:
            # paho-mqtt 1.x
            self.client = mqtt.Client(client_id=client_id, clean_session=False)
        if self.settings['user']:
            self.client.username_pw_set(self.settings['user'], self.settings['password'])
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)

    # ------------------------------------------------------------- callbacks
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected to %s:%s (topic %s)",
                        self.settings['broker'], self.settings['port'],
                        self.settings['topic'])
        else:
            logger.error("MQTT connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("MQTT disconnected rc=%s, will auto-reconnect", rc)

    # ------------------------------------------------------------- lifecycle
    def start(self):
        """Connect asynchronously and start the worker thread. Non-blocking."""
        self.client.connect_async(self.settings['broker'], self.settings['port'],
                                  keepalive=30)
        self.client.loop_start()
        self._worker.start()
        logger.info("Publisher started (machine_id=%s)", self.machine_id)

    def stop(self, timeout=5):
        """Flush what we can, spill the rest to disk and shut down."""
        self._stop_event.set()
        self._worker.join(timeout=timeout)
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.exception("Error closing MQTT client: %s", e)
        logger.info("Publisher stopped.")

    # -------------------------------------------------------------- enqueue
    def publish_records(self, records):
        """Queue one batch (list of dicts) for publishing. Thread-safe, instant."""
        if records:
            self._queue.put(records)

    # ----------------------------------------------------------- worker loop
    def _run(self):
        last_drain = 0.0
        while not self._stop_event.is_set():
            try:
                records = self._queue.get(timeout=0.5)
            except queue.Empty:
                # Idle: retry any batches spilled to disk (at most every 10 s)
                if time.time() - last_drain > 10:
                    self._drain_pending()
                    last_drain = time.time()
                continue
            if not self._publish(records):
                self._spill_to_disk(records)
            else:
                self._drain_pending()
                last_drain = time.time()

        # Shutting down: try to publish whatever is still queued, spill on failure
        while True:
            try:
                records = self._queue.get_nowait()
            except queue.Empty:
                break
            if not self._publish(records):
                self._spill_to_disk(records)

    # -------------------------------------------------------------- internals
    def _publish(self, records):
        """Returns True only if the broker has acknowledged the message."""
        if not records:
            return True
        try:
            if not self.client.is_connected():
                logger.warning("MQTT not connected, batch will be spilled to disk")
                return False
            payload = json.dumps(records)
            info = self.client.publish(self.settings['topic'], payload, qos=1)
            info.wait_for_publish(timeout=5)
            if info.is_published():
                logger.info("Published %d records to %s",
                            len(records), self.settings['topic'])
                return True
            logger.error("Publish to %s failed rc=%s", self.settings['topic'], info.rc)
            return False
        except Exception as e:
            logger.exception("Error publishing to MQTT: %s", e)
            return False

    def _spill_to_disk(self, records):
        """Persist a batch we couldn't publish so it survives restarts."""
        try:
            PENDING_DIR.mkdir(parents=True, exist_ok=True)
            path = PENDING_DIR / f"batch_{time.time_ns()}.json"
            path.write_text(json.dumps(records))
            logger.warning("Spilled %d records to %s", len(records), path.name)
        except Exception as e:
            logger.exception("Failed to spill batch to disk: %s", e)

    def _drain_pending(self):
        """Try to publish batches saved to disk from previous failures."""
        if not PENDING_DIR.exists():
            return
        files = sorted(PENDING_DIR.glob('batch_*.json'))
        if not files:
            return
        logger.info("Attempting to drain %d pending batch(es)...", len(files))
        for path in files:
            if self._stop_event.is_set():
                break
            try:
                records = json.loads(path.read_text())
            except Exception as e:
                logger.exception("Could not read pending file %s: %s", path.name, e)
                continue
            if self._publish(records):
                try:
                    path.unlink()
                    logger.info("Drained pending %s (%d records)", path.name, len(records))
                except OSError as e:
                    logger.exception("Couldn't remove %s: %s", path.name, e)
            else:
                logger.warning("Drain stopped - broker unreachable")
                break
