"""Operator inputs and part measurements, separate from DAQ configuration."""
from PyQt5 import QtCore, QtWidgets
from cycle_metadata import PRESSURE_SETTINGS, operator_settings
from plot_icons import apply_icon, cloud_icon


def value_text(value):
    return "" if value is None else str(value)


class RunSetup(QtWidgets.QFrame):
    applied = QtCore.pyqtSignal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(8)
        self.machine = QtWidgets.QComboBox()
        self.machine.setEditable(True)
        self.machine.setFixedWidth(150)
        self.machine.setToolTip("Choose a machine or type a new ID. Change machines between sessions.")
        self.machine.addItems(list(dict.fromkeys([settings["machine_id"], "55t", "160t"])))
        self.material = QtWidgets.QLineEdit()
        self.material.setMinimumWidth(160)
        self.material.setMaximumWidth(360)
        self.material.setToolTip("Material / grade. Leave blank if unknown.")
        self.temperature = QtWidgets.QLineEdit()
        self.temperature.setFixedWidth(85)
        self.temperature.setToolTip("Mold-temperature setpoint (°C), entered manually. Leave blank if unknown.")
        self.pressures = {}
        fields = [("Machine", self.machine), ("Material", self.material),
                  ("Mold (°C)", self.temperature)]
        for key, label in PRESSURE_SETTINGS:
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(85)
            edit.setToolTip(f"{label}. Leave blank if unknown.")
            self.pressures[key] = edit
            fields.append((label.replace(" pressure", ""), edit))
        for index, (text, widget) in enumerate(fields):
            if index:
                layout.addSpacing(8)
            label = QtWidgets.QLabel(text)
            label.setBuddy(widget)
            label.setToolTip(widget.toolTip())
            layout.addWidget(label)
            layout.addWidget(widget, 1 if widget is self.material else 0)
            widget.setAccessibleName(text)
            widget.setMinimumHeight(28)
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setPlaceholderText("—")
        self.applyButton = QtWidgets.QPushButton()
        self.applyButton.setFixedSize(28, 28)
        self.applyButton.setIcon(apply_icon())
        self.applyButton.setIconSize(QtCore.QSize(18, 18))
        self.applyButton.setToolTip("Apply settings to the next cycle. A cycle already running keeps its settings.")
        self.applyButton.setAccessibleName("Apply run settings")
        self.applyButton.clicked.connect(self._apply)
        layout.addWidget(self.applyButton)
        layout.addStretch()
        self.set_values(settings)

    def values(self):
        return operator_settings(self.machine.currentText(), self.material.text(),
                                 self.temperature.text(),
                                 {key: edit.text() for key, edit in self.pressures.items()})

    def set_values(self, settings):
        if self.machine.findText(settings["machine_id"]) < 0:
            self.machine.addItem(settings["machine_id"])
        self.machine.setCurrentText(settings["machine_id"])
        self.material.setText(value_text(settings.get("material")))
        self.temperature.setText(value_text(settings.get("mold_temperature_c")))
        for key, edit in self.pressures.items():
            edit.setText(value_text(settings.get("pressure_settings_bar", {}).get(key)))

    def _apply(self):
        try:
            self.applied.emit(self.values())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Run setup", str(exc))


class MeasurementsDialog(QtWidgets.QDialog):
    def __init__(self, controller):
        super().__init__(controller)
        self.controller = controller
        self.setWindowTitle("Cycle history")
        self.resize(1180, 540)
        layout = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter cycles…")
        self.search.setToolTip("Filter by machine, session, cycle or material")
        self.search.setAccessibleName("Filter cycles")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search, 1)
        for label, tooltip, callback in (
                ("Load…", "Load saved cycle measurements", controller.import_measurements),
                ("Save…", "Save cycle history and measurements to a file", controller.export_measurements)):
            button = QtWidgets.QPushButton(label)
            button.setAutoDefault(False)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.table = QtWidgets.QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(["Machine", "Session", "Cycle", "Session #", "Material",
                                             "Mold (°C)", "Limit (bar)", "Weight (g)", "Spiral (mm)", "Status", "Delivery"])
        self.table.horizontalHeaderItem(2).setToolTip("Persistent cycle ID")
        self.table.horizontalHeaderItem(3).setToolTip("Cycle number within its session")
        self.table.horizontalHeaderItem(10).setToolTip("Queued does not confirm storage on the server.")
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableView::item { padding: 0 6px; }")
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selected)
        layout.addWidget(self.table)
        details = QtWidgets.QHBoxLayout()
        self.context = QtWidgets.QLabel("Select a cycle")
        self.context.setTextFormat(QtCore.Qt.PlainText)
        details.addWidget(self.context)
        details.addStretch()
        storage = QtWidgets.QLabel("History is kept in memory")
        storage.setToolTip("Save a file to keep a local copy. Sending queues metadata for the server; queued does not mean stored.")
        details.addWidget(storage)
        layout.addLayout(details)
        form = QtWidgets.QHBoxLayout()
        self.weight, self.length = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        for label, edit in (("Weight (g)", self.weight), ("Spiral (mm)", self.length)):
            edit.setPlaceholderText("—")
            edit.setToolTip("One part per cycle. Leave blank if unknown.")
            edit.setAccessibleName(label)
            edit.setMaximumWidth(150)
            form.addWidget(QtWidgets.QLabel(label))
            form.addWidget(edit)
        self.updateButton = QtWidgets.QPushButton("Apply")
        self.updateButton.setDefault(True)
        self.updateButton.setToolTip("Apply weight and spiral length to the selected cycle")
        self.updateButton.clicked.connect(self._update)
        form.addWidget(self.updateButton)
        self.sendButton = QtWidgets.QPushButton("Send")
        self.sendButton.setIcon(cloud_icon())
        self.sendButton.setToolTip("Send the selected cycle's applied measurements to the server")
        self.sendButton.clicked.connect(self._send)
        form.addWidget(self.sendButton)
        form.addStretch()
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)
        form.addWidget(close)
        layout.addLayout(form)
        self.refresh()

    def selected_key(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(QtCore.Qt.UserRole) if item else None

    def refresh(self):
        previous = self.selected_key()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        query = self.search.text().lower()
        for key, entry in reversed(list(self.controller.cycle_history.items())):
            c, m = entry["capture"], entry["measurements"]
            values = [c["machine_id"], c["session_id"], c["cycle_id"], c.get("session_cycle"),
                      c.get("material"), c.get("mold_temperature_c"),
                      c.get("pressure_settings_bar", {}).get("limit"), m.get("weight_g"),
                      m.get("length_mm"), c["status"], entry.get("delivery", "Unknown")]
            if query and query not in " ".join(map(str, values)).lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value_text(value))
                item.setToolTip(value_text(value))
                item.setData(QtCore.Qt.UserRole, key)
                self.table.setItem(row, column, item)
            if key == previous:
                self.table.selectRow(row)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(10, 210)
        self.table.blockSignals(False)
        self._selected()

    def _selected(self):
        key = self.selected_key()
        for widget in (self.weight, self.length, self.updateButton, self.sendButton):
            widget.setEnabled(key is not None)
        if key:
            entry = self.controller.cycle_history[key]
            self.weight.setText(value_text(entry["measurements"].get("weight_g")))
            self.length.setText(value_text(entry["measurements"].get("length_mm")))
            self.context.setText(f"Cycle {key[2]} · {key[0]}")
            self.context.setToolTip(f"Session {key[1]}")
        else:
            self.weight.clear()
            self.length.clear()
            self.context.setText("Select a cycle")
            self.context.setToolTip("")

    def _update(self):
        key = self.selected_key()
        if key:
            self.controller.update_measurements(key, self.weight.text(), self.length.text())

    def _send(self):
        key = self.selected_key()
        if key:
            self.controller.send_measurements(key, force=True)
