"""Compact run/part sidebar and integrated cycle history."""
from copy import deepcopy
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
from cycle_metadata import operator_settings, effective_settings, new_review, EDIT_FIELDS
from sensor_types import sensor_category
from plot_icons import refresh_icon, curves_icon


INPUT_WIDTH = 72
LABEL_WIDTH = 90


def compact_form(parent):
    layout = QtWidgets.QFormLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(8)
    layout.setVerticalSpacing(8)
    layout.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldsStayAtSizeHint)
    return layout


def add_field(layout, text, widget):
    label = QtWidgets.QLabel(text)
    label.setFixedWidth(LABEL_WIDTH)
    label.setBuddy(widget)
    layout.addRow(label, widget)


def value_text(value):
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


def input_box(label, tooltip):
    edit = QtWidgets.QLineEdit()
    edit.setFixedHeight(30)
    edit.setFixedWidth(INPUT_WIDTH)
    edit.setPlaceholderText("—")
    edit.setAccessibleName(label)
    edit.setToolTip(tooltip)
    edit.textChanged.connect(lambda value: edit.setToolTip(tooltip + ("\n" + value if value else "")))
    return edit


class RunSetup(QtWidgets.QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._pressures = deepcopy(settings.get("pressure_settings_bar", {}))
        layout = compact_form(self)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.machine = QtWidgets.QComboBox()
        self.machine.setEditable(True)
        self.machine.addItems(list(dict.fromkeys([settings["machine_id"], "55t", "160t"])))
        self.machine.setFixedHeight(30)
        self.machine.setFixedWidth(INPUT_WIDTH)
        self.machine.setAccessibleName("Machine")
        self.machine.setToolTip("Machine ID. Change between sessions.")
        self.material = input_box("Material", "Material / grade. Blank means unknown.")
        self.temperature = input_box("Mold (°C)", "Manual mold-temperature setpoint.")
        self.melt = input_box("Melt (°C)", "Manual melt-temperature setpoint.")
        self.speed = input_box("Speed (mm/s)", "Manual injection-speed setpoint, not the measured CH6 flow (cm³/s).")
        for label, widget in (("Machine", self.machine), ("Material", self.material),
                              ("Mold (°C)", self.temperature), ("Melt (°C)", self.melt), ("Speed (mm/s)", self.speed)):
            add_field(layout, label, widget)
        self.hint = QtWidgets.QLabel("Settings apply on Start")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #666;")
        layout.addRow(self.hint)
        self.set_values(settings)

    def values(self):
        # Preserve previously recorded pressure settings; never reinterpret bar as mm/s.
        return operator_settings(self.machine.currentText(), self.material.text(),
                                 self.temperature.text(), self._pressures, self.speed.text(), self.melt.text())

    def set_locked(self, locked):
        for widget in (self.machine, self.material, self.temperature, self.melt, self.speed):
            widget.setEnabled(not locked)
        self.hint.setText("Stop to change session settings" if locked else "Settings apply on Start")

    def set_values(self, settings):
        self._pressures = deepcopy(settings.get("pressure_settings_bar", {}))
        if self.machine.findText(settings["machine_id"]) < 0:
            self.machine.addItem(settings["machine_id"])
        self.machine.setCurrentText(settings["machine_id"])
        self.material.setText(value_text(settings.get("material")))
        self.temperature.setText(value_text(settings.get("mold_temperature_c")))
        self.melt.setText(value_text(settings.get("melt_temperature_c")))
        self.speed.setText(value_text(settings.get("injection_speed_mm_s")))
        for edit in (self.material, self.temperature, self.melt, self.speed):
            edit.setCursorPosition(0)


class PartEditor(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller, self.key, self.dirty = controller, None, False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.context = QtWidgets.QLabel("No cycle selected")
        self.context.setTextFormat(QtCore.Qt.PlainText)
        self.context.setWordWrap(True)
        self.context.setStyleSheet("color: #666;")
        layout.addWidget(self.context)
        self.weight = input_box("Weight (g)", "Weight of this selected part. Blank means unknown.")
        self.length = input_box("Spiral (mm)", "Spiral length of this selected part. Blank means unknown.")
        fields = QtWidgets.QWidget()
        form = compact_form(fields)
        for label, edit in (("Weight (g)", self.weight), ("Spiral (mm)", self.length)):
            add_field(form, label, edit)
            edit.textEdited.connect(self._edited)
        layout.addWidget(fields)
        self.saveButton = QtWidgets.QPushButton("Save")
        self.saveButton.setFixedSize(58, 32)
        self.saveButton.setToolTip("Save Weight/Spiral for this part. Offline changes remain pending sync.")
        self.saveButton.clicked.connect(self.apply)
        layout.addWidget(self.saveButton, alignment=QtCore.Qt.AlignRight)
        self.set_entry(None)

    def _edited(self):
        self.dirty = True
        self.saveButton.setEnabled(self.key is not None)

    def can_leave(self):
        if not self.dirty:
            return True
        answer = QtWidgets.QMessageBox.question(
            self, "Part measurements", "Apply the measurements for the selected part before continuing?",
            QtWidgets.QMessageBox.Apply | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Apply)
        if answer == QtWidgets.QMessageBox.Apply:
            return self.apply()
        if answer == QtWidgets.QMessageBox.Discard:
            self.dirty = False
            return True
        return False

    def set_entry(self, key):
        if key != self.key and not self.can_leave():
            return False
        self.key = key
        for widget in (self.weight, self.length):
            widget.setEnabled(key is not None)
        if key is None:
            self.context.setText("No cycle selected")
            self.context.setToolTip("Select a completed cycle in History to enter its weight and spiral length.")
            self.weight.clear()
            self.length.clear()
        else:
            entry = self.controller.cycle_history[key]
            stamp = datetime.fromtimestamp(int(entry["capture"]["first_time_ns"]) / 1e9).strftime("%d %b %Y · %H:%M:%S")
            self.context.setText(f"Part · Cycle {key[2]} · {key[0]}")
            self.context.setToolTip(f"{stamp}\nSession: {key[1]}\n{entry.get('delivery', 'Local')}")
            if not self.dirty:
                self.weight.setText(value_text(entry["measurements"].get("weight_g")))
                self.length.setText(value_text(entry["measurements"].get("length_mm")))
        self.saveButton.setEnabled(key is not None and self.dirty)
        return True

    def apply(self):
        if self.key is None:
            return False
        if self.controller.update_measurements(self.key, self.weight.text(), self.length.text()):
            self.dirty = False
            self.set_entry(self.key)
            return True
        return False


class SettingsCorrectionDialog(QtWidgets.QDialog):
    """Checked fields are applied to every selected cycle; blank explicitly clears."""
    def __init__(self, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit settings for {len(entries)} cycles")
        form = QtWidgets.QFormLayout(self)
        explanation = QtWidgets.QLabel("Tick the settings to change for every selected cycle.\nA blank checked field clears that setting.")
        form.addRow(explanation)
        self.fields = {}
        labels = ("Material", "Mold (°C)", "Melt (°C)", "Speed (mm/s)")
        for field, label in zip(EDIT_FIELDS, labels):
            check, edit = QtWidgets.QCheckBox(label), QtWidgets.QLineEdit()
            values = [effective_settings(entry).get(field) for entry in entries]
            if all(value == values[0] for value in values):
                edit.setText(value_text(values[0]))
            else:
                edit.setPlaceholderText("Mixed values")
            edit.setEnabled(False)
            check.toggled.connect(edit.setEnabled)
            form.addRow(check, edit)
            self.fields[field] = check, edit
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def changes(self):
        selected = {field: edit.text() for field, (check, edit) in self.fields.items() if check.isChecked()}
        normalized = operator_settings("validation", **selected)
        return {field: normalized[field] for field in selected}

    def accept(self):
        try:
            if not self.changes():
                raise ValueError("Tick at least one setting to change.")
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Edit settings", str(exc))
            return
        super().accept()


def peak_text(peaks, category):
    values = [(name, value) for name, value in peaks.items()
              if "_" in name and sensor_category(name.split("_", 1)[1]) == category and value is not None]
    if not values:
        return "", ""
    return (f"{max(v for _, v in values):.1f}",
            "\n".join(f"{name}: {value:.2f}" for name, value in sorted(values)))


class HistoryPanel(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.checked = set()
        layout = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search loaded cycles…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(30)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        self.loadButton = QtWidgets.QToolButton()
        self.loadButton.setText("Load server")
        self.loadButton.setIcon(refresh_icon())
        self.loadButton.setToolTip("Load the latest 10 cycle summaries. Already loaded rows are kept.")
        self.loadButton.setAccessibleName("Load cycle history from server")
        self.loadButton.clicked.connect(lambda: controller.load_server_history())
        toolbar.addWidget(self.loadButton)
        self.moreButton = QtWidgets.QToolButton()
        self.moreButton.setText("Load more")
        self.moreButton.setToolTip("Load the next 10 older cycle summaries")
        self.moreButton.setAccessibleName("Load more cycle summaries from server")
        self.moreButton.setEnabled(False)
        self.moreButton.clicked.connect(lambda: controller.load_more_server_history())
        toolbar.addWidget(self.moreButton)
        self.plotButton = QtWidgets.QToolButton()
        self.plotButton.setText("Plot")
        self.plotButton.setIcon(curves_icon())
        self.plotButton.setToolTip("Plot the checked cycles in a new comparison tab")
        self.plotButton.setAccessibleName("Plot selected cycles")
        self.plotButton.clicked.connect(lambda: controller.plot_history_cycles(self.selected_cycles()))
        self.plotButton.setEnabled(False)
        toolbar.addWidget(self.plotButton)
        for button in (self.loadButton, self.moreButton, self.plotButton):
            button.setAutoRaise(True)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            button.setIconSize(QtCore.QSize(20, 20))
            button.setFixedHeight(32)
        layout.addLayout(toolbar)
        actions = QtWidgets.QHBoxLayout()
        self.editSettingsButton = QtWidgets.QPushButton("Edit settings")
        self.excludeButton = QtWidgets.QPushButton("Exclude")
        self.restoreButton = QtWidgets.QPushButton("Restore")
        self.sendEditsButton = QtWidgets.QPushButton("Send edits")
        self.editSettingsButton.clicked.connect(lambda: controller.edit_history_settings(self.action_keys()))
        self.excludeButton.clicked.connect(lambda: controller.update_reviews(self.action_keys(), excluded=True))
        self.restoreButton.clicked.connect(lambda: controller.update_reviews(self.action_keys(), excluded=False))
        self.sendEditsButton.clicked.connect(lambda: controller.send_pending_edits(self.action_keys(), force=True))
        for button in (self.editSettingsButton, self.excludeButton, self.restoreButton, self.sendEditsButton):
            actions.addWidget(button)
        self.showExcluded = QtWidgets.QCheckBox("Show excluded")
        self.showExcluded.setToolTip("Show excluded cycles. Load server to include older excluded cycles.")
        self.showExcluded.toggled.connect(self._excluded_changed)
        actions.addStretch()
        actions.addWidget(self.showExcluded)
        layout.addLayout(actions)
        self.table = QtWidgets.QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(["", "Date / time", "Machine", "Cycle", "Material",
            "Mold (°C)", "Melt (°C)", "Speed (mm/s)", "Weight (g)", "Spiral (mm)",
            "Time (s)", "T max (°C)", "P max (bar)", "State"])
        self.table.horizontalHeaderItem(10).setToolTip("Recorded sample span; not necessarily the full molding cycle.")
        self.table.horizontalHeaderItem(11).setToolTip("Highest mold temperature. Hover a value for peaks by channel.")
        self.table.horizontalHeaderItem(12).setToolTip("Highest cavity pressure, excluding machine pressure. Hover for each channel.")
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.itemChanged.connect(self._checked)
        self.table.doubleClicked.connect(lambda _: controller.plot_history_cycles([self.selected_key()]))
        layout.addWidget(self.table)
        self.status = QtWidgets.QLabel("")
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        self.status.hide()
        self.refresh()

    def set_status(self, text):
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def selected_key(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(QtCore.Qt.UserRole) if item else None

    def selected_cycles(self):
        # Checkboxes survive filtering; explicit selection count reflects all of them.
        return sorted(self.checked)

    def action_keys(self):
        return self.selected_cycles() or [self.table.item(index.row(), 0).data(QtCore.Qt.UserRole)
                                         for index in self.table.selectionModel().selectedRows()]

    def _excluded_changed(self):
        self.controller._history_next_cursor = None
        self.moreButton.setEnabled(False)
        self.refresh()

    def _update_actions(self):
        keys = self.action_keys()
        for button in (self.editSettingsButton, self.excludeButton, self.restoreButton):
            button.setEnabled(bool(keys))
        self.editSettingsButton.setText(f"Edit settings ({len(keys)})" if keys else "Edit settings")
        self.sendEditsButton.setEnabled(any(self.controller.cycle_history[k].get("local_review_edit") or
            self.controller.cycle_history[k].get("local_measurement_edit") for k in keys))

    def select_key(self, key):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(QtCore.Qt.UserRole) == key:
                self.table.selectRow(row)
                return

    def _selected(self):
        key = self.selected_key()
        if key and not self.controller.partEditor.set_entry(key):
            self.table.blockSignals(True)
            self.select_key(self.controller.partEditor.key)
            self.table.blockSignals(False)
        self._update_actions()

    def _checked(self, item):
        if item.column() == 0:
            key = item.data(QtCore.Qt.UserRole)
            if item.checkState() == QtCore.Qt.Checked:
                self.checked.add(key)
            else:
                self.checked.discard(key)
            self.plotButton.setEnabled(bool(self.checked))
            self.plotButton.setText(f"Plot ({len(self.checked)})" if self.checked else "Plot")
            self._update_actions()

    def refresh(self):
        previous = self.selected_key()
        self.table.blockSignals(True)
        scroll = self.table.verticalScrollBar().value()
        self.table.setRowCount(0)
        query = self.search.text().lower()
        entries = sorted(self.controller.cycle_history.items(),
                         key=lambda item: int(item[1]["capture"]["first_time_ns"]), reverse=True)
        for key, entry in entries:
            c = entry["capture"]
            if c["mode"] != "cycle":
                continue
            review = entry.get("review", new_review())
            if review["excluded"] and not self.showExcluded.isChecked():
                self.checked.discard(key)
                continue
            settings = effective_settings(entry)
            peaks = c.get("signal_peaks", entry.get("summary", {}).get("signal_peaks", {}))
            t, tt = peak_text(peaks, "temp")
            p, pt = peak_text(peaks, "moldP")
            duration = (int(c["last_time_ns"]) - int(c["first_time_ns"])) / 1e9
            stamp = datetime.fromtimestamp(int(c["first_time_ns"]) / 1e9).strftime("%d/%m/%Y %H:%M:%S")
            stored = entry.get("waveform_status", "local")
            state = {"stored": "On server", "legacy": "On server · legacy", "pending": "Server processing",
                     "metadata_only": "Server metadata only"}.get(stored, "This PC · not sent")
            capture_delivery = entry.get("capture_delivery", "" if entry.get("delivery", "").startswith("Edit queued") else entry.get("delivery", ""))
            if stored == "local" and "queued" in capture_delivery.lower():
                state = "Upload queued"
            if entry.get("local_review_edit") or entry.get("local_measurement_edit"):
                state += " · " + ("Conflict" if entry.get("edit_conflict") else "Pending sync")
            if review["excluded"]:
                state += " · Excluded"
            if c["status"] == "interrupted":
                state += " · Incomplete"
            values = ["", stamp, c["machine_id"], c["cycle_id"], settings.get("material"),
                      settings.get("mold_temperature_c"), settings.get("melt_temperature_c"), settings.get("injection_speed_mm_s"),
                      entry["measurements"].get("weight_g"), entry["measurements"].get("length_mm"),
                      f"{duration:.3f}", t, p, state]
            if query and query not in (" ".join(map(str, values)) + " " + c["session_id"]).lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value_text(value))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setData(QtCore.Qt.UserRole, key)
                item.setToolTip(value_text(value))
                if column == 0:
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    item.setCheckState(QtCore.Qt.Checked if key in self.checked else QtCore.Qt.Unchecked)
                elif column == 3:
                    item.setToolTip(f"Session cycle: {value_text(c.get('session_cycle'))}\nSession: {key[1]}")
                elif column in (4, 5, 6, 7) and EDIT_FIELDS[column - 4] in review["settings"]:
                    item.setToolTip(f"{value_text(value)}\nRecorded as: {value_text(c.get(EDIT_FIELDS[column - 4])) or 'blank'}")
                elif column in (11, 12):
                    item.setToolTip(tt if column == 11 else pt)
                elif column == 13:
                    item.setToolTip(entry.get("delivery", state))
                    if c["status"] == "interrupted":
                        item.setBackground(QtGui.QColor("#ffe0ad"))
                        item.setToolTip(item.toolTip() + "\nIncomplete recording; duration and peaks may not represent the full cycle.")
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 30)
        for column, minimum in ((1, 158), (2, 70), (3, 50)):
            self.table.setColumnWidth(column, max(minimum, self.table.columnWidth(column)))
        for column in range(4, 14):
            self.table.setColumnWidth(column, max(80, self.table.columnWidth(column)))
        self.table.horizontalHeader().setSectionResizeMode(13, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(30)
        if previous:
            self.select_key(previous)
        self.table.verticalScrollBar().setValue(scroll)
        self.table.blockSignals(False)
        self.plotButton.setEnabled(bool(self.checked))
        self.plotButton.setText(f"Plot ({len(self.checked)})" if self.checked else "Plot")
        self._update_actions()


# Kept for callers importing the earlier widget name; history is now embedded.
MeasurementsDialog = HistoryPanel
