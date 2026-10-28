"""Durable metadata proposals; captures and waveforms retain their existing lifecycle."""
from copy import deepcopy
import time
from PyQt5 import QtWidgets
import cycle_metadata as metadata
from metadata_widgets import SettingsCorrectionDialog


class EditController:
    def restore_pending_edits(self):
        self._submitted_updates = set()
        self._last_edit_sync = 0
        self._edits_error = None
        try:
            for entry in metadata.load_pending_edits():
                entry["delivery"] = "Pending sync (restored from disk)"
                self.cycle_history[metadata.identity(entry["capture"])] = entry
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._edits_error = f"Cannot read pending edits in {metadata.EDITS_FILE}: {exc}"
            self.messagesBox.appendPlainText(self._edits_error)

    def commit_metadata_edits(self, staged):
        """Write the whole proposal batch before changing any visible value."""
        try:
            if self._edits_error:
                raise ValueError(self._edits_error)
            metadata.save_pending_edits({**self.cycle_history, **staged}.values())
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Save edits", str(exc))
            return False
        for key, entry in staged.items():
            if key in self.cycle_history:
                self.cycle_history[key].clear()
                self.cycle_history[key].update(entry)
            else:
                self.cycle_history[key] = entry
        return True

    def edit_history_settings(self, keys):
        if not keys or not self.partEditor.can_leave():
            return
        dialog = SettingsCorrectionDialog([self.cycle_history[key] for key in keys], self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.update_reviews(keys, settings=dialog.changes())

    def update_reviews(self, keys, settings=None, excluded=None):
        if not keys or not self.partEditor.can_leave():
            return False
        staged = {}
        try:
            for key in keys:
                entry = deepcopy(self.cycle_history[key])
                if entry["capture"]["mode"] != "cycle":
                    raise ValueError("Only individual cycles can be corrected or excluded.")
                local = entry.get("review", metadata.new_review())
                baseline = max((local, entry.get("server_review", local)), key=lambda r: r["revision"])
                patch = deepcopy(entry.get("review_patch", {}))
                if settings:
                    patch.setdefault("settings", {}).update(settings)
                if excluded is not None:
                    patch["excluded"] = excluded
                proposed = metadata.edit_review(baseline, patch.get("settings"), patch.get("excluded"))
                if all(proposed[name] == local[name] for name in ("settings", "excluded")) and not entry.get("review_conflict"):
                    continue
                entry.update(review=proposed, review_patch=patch, local_review_edit=True,
                             delivery="Pending sync", review_conflict=False,
                             edit_conflict=bool(entry.get("measurement_conflict")))
                staged[key] = entry
        except (ValueError, TypeError) as exc:
            QtWidgets.QMessageBox.warning(self, "Edit cycles", str(exc))
            return False
        if staged and not self.commit_metadata_edits(staged):
            return False
        self.send_pending_edits(list(staged))
        self.refresh_measurements()
        return True

    def send_pending_edits(self, keys=None, force=False):
        if not self.mqtt_enabled and not force:
            return
        keys = list(self.cycle_history) if keys is None else keys
        staged, outgoing = {}, []
        for key in keys:
            entry = deepcopy(self.cycle_history[key])
            for field, flag, conflict_flag, factory in (("review", "local_review_edit", "review_conflict", metadata.review_message),
                                          ("measurements", "local_measurement_edit", "measurement_conflict", metadata.measurement_message)):
                if not entry.get(flag) or (entry.get(conflict_flag) and not force):
                    continue
                remote = entry.get("server_" + field)
                current = entry[field]
                if force and remote and remote["revision"] >= current["revision"]:
                    if field == "review":
                        patch = entry.get("review_patch", {"settings": current["settings"], "excluded": current["excluded"]})
                        entry[field] = metadata.edit_review(remote, patch.get("settings"), patch.get("excluded"))
                    else:
                        entry[field] = metadata.edit_measurements(remote, current.get("weight_g"), current.get("length_mm"))
                    entry[conflict_flag] = False
                    entry["edit_conflict"] = bool(entry.get("measurement_conflict") or entry.get("review_conflict"))
                    staged[key] = entry
                if entry[field]["update_id"] not in self._submitted_updates or force:
                    outgoing.append((key, factory(entry)))
        if not outgoing or (staged and not self.commit_metadata_edits(staged)):
            return
        self._ensure_mqtt_publisher(force=force)
        if self.mqtt_publisher is None:
            return
        self.mqtt_publisher.auto_drain = bool(self.mqtt_enabled)
        for key, message in outgoing:
            self.mqtt_publisher.publish_records(message)
            value = message["review"] if message["kind"] == "review" else message["measurements"]
            self._submitted_updates.add(value["update_id"])
            self.cycle_history[key]["delivery"] = "Edit queued (unconfirmed); pending sync until server readback"
        self.refresh_measurements()

    def sync_metadata(self):
        publisher = self.mqtt_publisher
        if publisher:
            publisher.auto_drain = bool(self.mqtt_enabled)
        client = getattr(publisher, "client", None)
        connected = bool(client and client.is_connected())
        self.set_connection_status("broker", connected, "Connected" if connected else
                                   ("Disconnected" if self.mqtt_enabled else "Uploads off"))
        if time.monotonic() - self._last_edit_sync < 30:
            return
        self._last_edit_sync = time.monotonic()
        self.send_pending_edits()
        keys = [key for key, entry in self.cycle_history.items()
                if entry.get("local_review_edit") or entry.get("local_measurement_edit")]
        if keys and (self.mqtt_enabled or self._submitted_updates) and not self._history_jobs:
            client = self._client(quiet=True)
            if client:
                self._start_history_job(client, lambda page: self.merge_server_history(page["updates"]),
                                        refresh_keys=keys, lookup_only=True, silent=True)
