"""Read-only desktop history client. Network work never runs on the GUI thread."""
import json
import urllib.error
import urllib.parse
import urllib.request
from PyQt5 import QtCore


class HistoryClient:
    def __init__(self, url, token):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Enter an http(s) server URL without embedded credentials.")
        self.url, self.token = url.rstrip("/"), token

    def get(self, path, params=None):
        url = self.url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token})
        try:
            # Do not forward credentials across redirects.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(request, timeout=30) as response:
                raw = response.read(64 * 1024 * 1024 + 1)
                if len(raw) > 64 * 1024 * 1024:
                    raise ValueError("The server response is too large.")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError("Unexpected history response.")
                return result
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ValueError("History access denied. Check the access key in File → Server connection.") from None
            if exc.code == 404:
                raise ValueError("History API or waveform not found. The server may need the history update.") from None
            raise ValueError(f"History server returned HTTP {exc.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ValueError("Cannot reach the history server. Check the connection and try again.") from None


class HistoryJob(QtCore.QThread):
    ready = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, client, keys=None, parent=None):
        super().__init__(parent)
        self.client, self.keys = client, keys

    def run(self):
        try:
            result = []
            if self.keys is None:
                cursor = ""
                seen = set()
                while not self.isInterruptionRequested():
                    page = self.client.get("/monitoring/history", {"cursor": cursor})
                    rows = page["cycles"]
                    if not isinstance(rows, list):
                        raise ValueError("Invalid history page.")
                    result.extend(rows)
                    self.progress.emit(f"Loaded {len(result)} cycles…")
                    cursor = page.get("next_cursor")
                    if not cursor:
                        break
                    if cursor in seen:
                        raise ValueError("The history server repeated a page.")
                    seen.add(cursor)
            else:
                for index, key in enumerate(self.keys):
                    if self.isInterruptionRequested():
                        break
                    self.progress.emit(f"Loading waveform {index + 1} / {len(self.keys)}…")
                    waveform = self.client.get("/monitoring/waveform",
                        dict(machine_id=key[0], session_id=key[1], cycle_id=key[2]))
                    result.append((key, waveform))
            if not self.isInterruptionRequested():
                self.ready.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc) if isinstance(exc, ValueError) else "Invalid response from history server.")
