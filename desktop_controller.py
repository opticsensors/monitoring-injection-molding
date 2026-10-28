"""Desktop interactions shared by the real DAQ window and the isolated preview."""
from copy import deepcopy
import json

from PyQt5 import QtGui

import cycle_metadata as metadata
from desktop_widgets import InspectorLayout, STYLE


class DesktopController:
    preview_mode = False

    def initialize_desktop_state(self):
        self.presentation = None
        self._configuration_draft = None
        self._connecting = self._stopping = False
        self._part_drafts = {}
        self._orphan_part_drafts = []
        self._latest_part_key = self._pending_follow_key = None
        self._suppress_part_selection = False
        self._drafts_readable = True
        try:
            path = self.part_drafts_path()
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict) or saved.get("schema_version") != 1:
                    raise ValueError("Unknown active part journal version")
                # A restart has a new session identity. Retain unfinished values
                # for recovery, but never attach them to a different recording.
                self._orphan_part_drafts = saved["orphaned"] + saved["active"]
                if self._orphan_part_drafts:
                    self.messagesBox.appendPlainText(f"Unfinished part measurements retained in {path.name}.")
        except (OSError, ValueError, KeyError, TypeError):
            self._drafts_readable = False
            self.messagesBox.appendPlainText("Cannot read active part measurements; autosave needs the journal repaired.")

    def install_desktop_layout(self):
        self.setStyleSheet(STYLE)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#ffffff"))
        self.setPalette(palette)
        self.presentation = InspectorLayout(self)
        self.refresh_measurements()
        self.refresh_desktop_controls()
        self.resize(1500, 960)

    def desktop_busy(self):
        return self.is_monitoring or self._connecting or self._stopping

    def refresh_desktop_controls(self):
        if not self.presentation:
            return
        self.presentation.save_action.setEnabled(self.saveSessionButton.isEnabled())
        self.presentation.send_action.setEnabled(self.sendSessionButton.isEnabled())
        self.presentation.refresh_device_control()
        self.presentation.refresh_configuration()

    def _stage_configuration(self, cfg):
        self._configuration_draft = deepcopy(cfg)
        self.presentation.refresh_configuration()
        self.messagesBox.appendPlainText("Configuration saved for next recording.")

    def apply_staged_configuration(self):
        if self._configuration_draft:
            self.cnfg_Sig_Received(dict(self._configuration_draft, machine_id=self.machine_id))
            self._configuration_draft = None

    def load_next_history(self):
        if self._history_next_cursor is None:
            self.load_server_history()
        else:
            self.load_more_server_history()

    def _receive_history_page(self, page):
        super()._receive_history_page(page)
        self.historyPanel.refresh()

    def edit_history_cell(self, key, field, value):
        entry = self.cycle_history[key]
        try:
            if field in metadata.EDIT_FIELDS:
                normalized = metadata.operator_settings(**{"machine_id": key[0], field: value})[field]
                return self.update_reviews([key], settings={field: normalized})
            values = {name: entry["measurements"].get(name) for name in ("weight_g", "length_mm")}
            values[field] = metadata.optional_number(value, field)
            return self.update_measurements(key, values["weight_g"], values["length_mm"])
        except ValueError as exc:
            self.messagesBox.appendPlainText(str(exc))
            return False

    def select_comparison_part(self, view):
        index = view.focus.currentIndex()
        if index >= 0 and self.partEditor.set_entry(view.cycle_keys[index]) and self.presentation:
            self.presentation.refresh_selection()

    def part_drafts_path(self):
        return metadata.EDITS_FILE.with_name("active_part_measurements.json")

    def _write_part_drafts(self, drafts):
        if not self._drafts_readable:
            raise OSError("Active part journal could not be read; existing values were preserved.")
        metadata.write_json(self.part_drafts_path(), dict(schema_version=1,
            active=[dict(machine_id=key[0], session_id=key[1], cycle_id=key[2], **values)
                    for key, values in drafts.items()], orphaned=self._orphan_part_drafts))

    def part_measurements(self, key):
        if key in self._part_drafts:
            return self._part_drafts[key]
        return self.cycle_history[key]["measurements"]

    def save_part_measurements(self, key, weight_g, length_mm):
        if key in self.cycle_history:
            if not self.update_measurements(key, weight_g, length_mm):
                return False
            if key in self._part_drafts:
                del self._part_drafts[key]
                try:
                    self._write_part_drafts(self._part_drafts)
                except OSError as exc:
                    self.messagesBox.appendPlainText(f"Draft cleanup failed: {exc}")
            return True
        staged = deepcopy(self._part_drafts)
        staged[key].update(weight_g=weight_g, length_mm=length_mm)
        try:
            self._write_part_drafts(staged)
        except OSError as exc:
            self.messagesBox.appendPlainText(f"Measurements not saved: {exc}")
            return False
        self._part_drafts = staged
        return True

    def follow_current_part(self):
        if not self.presentation or self.presentation.mode != "monitor":
            return
        if not self.cycle_mode:
            self._pending_follow_key = None
            self.partEditor.set_entry(None)
            return
        key = self._latest_part_key
        if not key or key == self.partEditor.key:
            self._pending_follow_key = None
            return
        if self.partEditor.editing() or not self.partEditor.can_leave():
            self._pending_follow_key = key
            return
        self._pending_follow_key = None
        self.partEditor.set_entry(key)
        self.presentation.refresh_selection()

    def resume_part_follow(self):
        if self._pending_follow_key:
            self.follow_current_part()

    def capture_started(self, cycle_id, snapshot, start_s):
        super().capture_started(cycle_id, snapshot, start_s)
        if not cycle_id:
            return
        key = (snapshot["machine_id"], self.session_id, cycle_id)
        self._part_drafts[key] = dict(weight_g=None, length_mm=None,
            started_ns=self.session_start_ns + round(start_s * 1e9))
        self._latest_part_key = key
        if self.presentation:
            self.presentation.refresh_selection()
            self.follow_current_part()

    def discard_part_draft(self, cycle_id):
        key = (self._session_machine_id, self.session_id, cycle_id)
        values = self._part_drafts.pop(key, None)
        if values is None:
            return
        # Noise cycles reuse their number. Keep any typed values separate from
        # the retry, including invalid/uncommitted text, without blocking DAQ.
        if self.partEditor.key == key and self.partEditor.dirty:
            values.update(weight_text=self.partEditor.weight.text(), spiral_text=self.partEditor.length.text())
        if any(values.get(field) is not None for field in ("weight_g", "length_mm", "weight_text", "spiral_text")):
            self._orphan_part_drafts.append(dict(machine_id=key[0], session_id=key[1], cycle_id=key[2],
                                                reason="discarded_trigger", **values))
        try:
            self._write_part_drafts(self._part_drafts)
        except OSError as exc:
            self.messagesBox.appendPlainText(f"Draft cleanup failed: {exc}")
        self._latest_part_key = self._pending_follow_key = None
        if self.partEditor.key == key:
            self.partEditor.dirty = False
            self.partEditor.weight.clearFocus()
            self.partEditor.length.clearFocus()
            self.partEditor.set_entry(None)
        if self.presentation:
            self.presentation.refresh_selection()

    def capture_finished(self, cycle_id, xdata, rows, start_s, details=None):
        key = (self._session_machine_id, self.session_id, cycle_id)
        if self.partEditor.key == key:
            self.partEditor.apply()
        self._suppress_part_selection = True
        try:
            super().capture_finished(cycle_id, xdata, rows, start_s, details)
        finally:
            self._suppress_part_selection = False
        if key in self.cycle_history and key in self._part_drafts:
            values = self._part_drafts[key]
            if self.update_measurements(key, values["weight_g"], values["length_mm"]):
                del self._part_drafts[key]
                try:
                    self._write_part_drafts(self._part_drafts)
                except OSError as exc:
                    self.messagesBox.appendPlainText(f"Draft cleanup failed: {exc}")
        self.refresh_measurements()

    def refresh_measurements(self):
        super().refresh_measurements()
        if self.presentation:
            self.presentation.refresh_selection()

    def save_session_export(self, path):
        if not self.historyPanel.flush_edits() or not self.partEditor.can_leave():
            raise ValueError("Check the highlighted part measurement before exporting.")
        super().save_session_export(path)
