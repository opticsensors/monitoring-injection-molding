"""Main-window integration for metadata; raw recordings retain their RAM/Save lifecycle."""
from copy import deepcopy
import csv
from datetime import datetime
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from PyQt5 import QtCore, QtWidgets
import cycle_metadata as metadata
from metadata_widgets import RunSetup, HistoryPanel, PartEditor, compact_form, add_field
from history_controller import HistoryController
from sensor_types import sensor_unit
from plot_icons import sidebar_icon

logger = logging.getLogger(__name__)


class MetadataController(HistoryController):
    def initialize_metadata(self):
        self.cycle_history = {}
        self._session_config = None
        self._capture_starts = {}
        self._measurements_dialog = None
        self.initialize_browser()
        try:
            self.run_settings = metadata.load_preferences(self.machine_id)
        except (OSError, ValueError, TypeError):
            logger.exception("Could not load run setup; using blank settings")
            self.run_settings = metadata.operator_settings(self.machine_id)
            self.messagesBox.appendPlainText("Saved run setup could not be read; check settings before recording.")
        self.machine_id = self.run_settings["machine_id"]
        self.runSetup = RunSetup(self.run_settings, self)
        self.historyButton.setCheckable(True)
        self.historyButton.clicked.connect(self.toggle_history)
        self.partEditor = PartEditor(self)
        self.historyPanel = HistoryPanel(self)
        self._measurements_dialog = self.historyPanel
        self.gridLayout_3.removeWidget(self.plotTabs)
        self.workspaceTabs = QtWidgets.QTabWidget()
        self.workspaceTabs.setTabsClosable(True)
        self.workspaceTabs.addTab(self.plotTabs, "Live")
        self.workspaceTabs.addTab(self.historyPanel, "History")
        for index in (0, 1):
            self.workspaceTabs.tabBar().setTabButton(index, QtWidgets.QTabBar.RightSide, None)
            self.workspaceTabs.tabBar().setTabButton(index, QtWidgets.QTabBar.LeftSide, None)
        self.workspaceTabs.tabCloseRequested.connect(self.close_workspace_tab)
        self._plot_toolbar_changed = self.sync_plot_toolbar
        def workspace_changed(index):
            self.historyButton.setChecked(index == 1)
            self.historyButton.setToolTip("Return to Live" if index == 1 else "Open cycle history")
            self.sync_plot_toolbar()
        self.workspaceTabs.currentChanged.connect(workspace_changed)
        workspace_changed(self.workspaceTabs.currentIndex())
        self.parametersButton = QtWidgets.QToolButton()
        self.parametersButton.setIcon(sidebar_icon())
        self.parametersButton.setIconSize(QtCore.QSize(22, 22))
        self.parametersButton.setFixedSize(32, 28)
        self.parametersButton.setAutoRaise(True)
        self.parametersButton.setAccessibleName("Toggle parameter panel")
        self.parametersButton.setShortcut("Ctrl+Alt+B")
        self.parametersButton.setCheckable(True)
        self.workspaceTabs.setCornerWidget(self.parametersButton)
        sidebar = QtWidgets.QWidget()
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 0, 12)
        sidebar_layout.setSpacing(12)
        sidebar_layout.addWidget(self.runSetup)
        sidebar_layout.addWidget(self.partEditor)
        self.parametersApplyButton = QtWidgets.QPushButton("Apply")
        self.parametersApplyButton.setFixedSize(58, 32)
        self.parametersApplyButton.setToolTip(
            "Apply settings to future cycles and save edited Weight/Spiral for the indicated cycle.")
        self.parametersApplyButton.clicked.connect(self.apply_parameters)
        actions = QtWidgets.QWidget()
        add_field(compact_form(actions), "", self.parametersApplyButton)
        sidebar_layout.addWidget(actions)
        sidebar_layout.addStretch()
        self.parameterPanel = QtWidgets.QScrollArea()
        self.parameterPanel.setWidgetResizable(True)
        self.parameterPanel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.parameterPanel.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.parameterPanel.setWidget(sidebar)
        self.parameterPanel.setFixedWidth(202)
        self.workspaceSplit = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.workspaceSplit.addWidget(self.workspaceTabs)
        self.workspaceSplit.addWidget(self.parameterPanel)
        self.workspaceSplit.setStretchFactor(0, 1)
        self.workspaceSplit.setSizes([1100, 202])
        self.gridLayout_3.addWidget(self.workspaceSplit, 0, 0)
        def toggle_parameters(visible):
            self.parameterPanel.setVisible(visible)
            self.parametersButton.setIcon(sidebar_icon(visible))
            self.parametersButton.setToolTip(
                ("Hide" if visible else "Show") + " parameters (Ctrl+Alt+B)")
            self.ui_settings.setValue("parameters_visible", visible)
        self.parametersButton.toggled.connect(toggle_parameters)
        visible = self.ui_settings.value("parameters_visible", True, type=bool)
        self.parametersButton.setChecked(visible)
        self.parameterPanel.setVisible(visible)
        self.parametersButton.setIcon(sidebar_icon(visible))
        self.parametersButton.setToolTip(("Hide" if visible else "Show") + " parameters (Ctrl+Alt+B)")
        menu = self.menubar.addMenu("File")
        menu.addAction("Import metadata…", self.import_measurements)
        menu.addAction("Export metadata…", self.export_measurements)
        menu.addSeparator()
        menu.addAction("Server connection…", self.server_connection)
        self.refresh_run_snapshot()

    def active_plot_view(self):
        index = self.workspaceTabs.currentIndex()
        if index == 0:
            return self
        return self.workspaceTabs.currentWidget() if index > 1 else None

    def route_plot_tool(self, name, checked=False):
        view = self.active_plot_view()
        if view is None:
            return
        if name == "home":
            view.resetPlotView()
        elif name == "ghosts":
            view._on_hide_ghosts_toggled(checked)
        else:
            view._on_tool_toggled(name, checked)

    def sync_plot_toolbar(self, changed_view=None):
        """One stationary toolbar; inactive plots never overwrite its state."""
        view = self.active_plot_view()
        if changed_view is not None and changed_view is not view:
            return
        enabled = bool(view is not None and not view.plot_is_live and
                       (view.splotlist or view.machine_splotlist))
        mode = view.tool_mode if view is not None else None
        for name, button in (("home", self.homeButton), ("zoom", self.zoomButton),
                             ("pan", self.panButton), ("cursor", self.cursorButton),
                             ("ghosts", self.hideGhostsButton)):
            button.setEnabled(enabled)
            if button.isCheckable():
                previous = button.blockSignals(True)
                button.setChecked(bool(getattr(view, "_ghosts_hidden", False))
                                  if name == "ghosts" else mode == name)
                button.blockSignals(previous)
        self.hideGhostsButton.setToolTip(
            "Hide other cycles" if view is not None and view is not self else "Hide previous cycles")
        self.readoutBox.setEnabled(view is not None)
        self.cycleReadoutLabel.setText(getattr(view, "_cycle_readout_text", "Cycle: --"))
        readout = getattr(view, "_cursor_readout", ("Δt: --", "ΔP: --", "η: --", ""))
        for label, text in zip((self.deltaTLabel, self.deltaPLabel, self.viscosityLabel), readout):
            label.setText(text)
        self.viscosityLabel.setToolTip(readout[3])
        self.readoutBox.layout().activate()
        self.readoutBox.adjustSize()

    def active_configuration(self):
        return deepcopy(dict(monitoring_time_s=self.time_lim, channels=self.daq_channels,
            voltage_ranges=self.voltage_ranges, channel_types=self.channel_types,
            sample_rate_hz=self.daq_srate, decimation=self.daq_dec,
            display_points=self.n_display_points, plot_refresh_rate_ms=self.plot_refresh_rate,
            separate_plots=self.separate_plots, machine_layout=self.machine_layout,
            plot_channels=self.plot_channels, mqtt_enabled=self.mqtt_enabled,
            machine_id=self.machine_id, min_cycle_s=self.min_cycle_s,
            inter_cycle_gap_s=self.inter_cycle_gap_s, trigger_mode=self.trigger_mode,
            digital_map=self.digital_map, conversion=self.conversion,
            viscosity={"L_mm": self.visc_L_mm, "Rc_mm": self.visc_Rc_mm}))

    def refresh_run_snapshot(self):
        config = self.active_configuration()
        indices = self._saved_indices()
        config.update(saved_indices=indices,
                      field_names=self._channel_field_names(),
                      field_units=[sensor_unit(self.channel_types[i]) for i in indices],
                      daq_parameters={"srate": self.daq_srate, "dec": self.daq_dec, "deca": self.daq_deca},
                      conversion_full_scale_v=self.voltage_scale,
                      software_contract="cycle-metadata-v1")
        # Assignment replaces the complete object. The worker only copies it at a boundary.
        self._run_snapshot = deepcopy({**self.run_settings, "config_snapshot": config})

    def apply_run_settings(self, settings):
        if self.is_monitoring and settings["machine_id"] != self.machine_id:
            QtWidgets.QMessageBox.warning(self, "Machine ID", "Stop the session before changing machine ID.")
            return False
        try:
            metadata.write_json(metadata.SETTINGS_FILE, settings)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Run setup", f"Could not save settings: {exc}")
            return False
        self.run_settings = deepcopy(settings)
        self.machine_id = settings["machine_id"]
        self.runSetup.set_values(settings)
        self.refresh_run_snapshot()
        self.statusbar.showMessage("Settings applied to the next cycle", 3000)
        return True

    def apply_parameters(self):
        """One explicit Apply: future-cycle settings and only edited part values."""
        try:
            settings = self.runSetup.values()
            # Validate both groups before saving either. Blank part values clear them.
            if self.partEditor.key and self.partEditor.dirty:
                metadata.optional_number(self.partEditor.weight.text(), "Weight (g)")
                metadata.optional_number(self.partEditor.length.text(), "Spiral (mm)")
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Parameters", str(exc))
            return False
        if not self.apply_run_settings(settings):
            return False
        if self.partEditor.key and self.partEditor.dirty:
            if not self.partEditor.apply():
                return False
            self.statusbar.showMessage("Settings and cycle measurements applied", 3000)
        return True

    def prepare_run_setup(self):
        try:
            return self.apply_run_settings(self.runSetup.values())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Run setup", str(exc))
            return False

    def begin_metadata_session(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid4().hex
        self.session_start_ns = time.time_ns()
        self.session_start_epoch = self.session_start_ns / 1e9
        self._session_machine_id = self.machine_id
        self._session_config = deepcopy(self._run_snapshot["config_snapshot"])
        self._session_cycle_mode = self.cycle_mode
        self._capture_starts = {}
        if not self.cycle_mode:
            self.capture_started(0, deepcopy(self._run_snapshot), 0.0)
        self.runSetup.machine.setEnabled(False)

    def start_acquisition_clock(self):
        """Anchor wall time and DAQ elapsed time together, after UI/plot setup.

        Both values are set before the start signal lets the DAQ consume scans.
        Subsequent wall-clock adjustments cannot change this recording's times.
        """
        before = time.perf_counter()
        self.session_start_ns = time.time_ns()
        after = time.perf_counter()
        self.session_start_epoch = self.session_start_ns / 1e9
        self.DaqThread.start_time = (before + after) / 2

    def capture_started(self, cycle_id, snapshot, start_s):
        self._capture_starts[cycle_id] = (deepcopy(snapshot), float(start_s))

    def capture_finished(self, cycle_id, xdata, rows, start_s, details=None):
        if not xdata:
            return
        details = details or {}
        snapshot, start_s = self._capture_starts[cycle_id]
        try:
            entry, message = metadata.finish_capture(snapshot, self.session_id,
                self._session_cycle(cycle_id), cycle_id, self.session_start_ns,
                start_s, details.get("end_s"), xdata, rows,
                details.get("status", "complete"), details.get("reason", "trigger"))
            key = metadata.identity(entry["capture"])
            self.cycle_history[key] = entry
            config = entry["capture"]["config_snapshot"]
            self.remember_waveform(key, dict(time_s=xdata, fields=config["field_names"],
                values={name: [row[index] for row in rows]
                        for name, index in zip(config["field_names"], config["saved_indices"])}))
            if self.mqtt_enabled:
                self._ensure_mqtt_publisher(machine_id=key[0])
                if self.mqtt_publisher is not None:
                    self.mqtt_publisher.publish_records(message)
                    entry["delivery"] = "Queued (unconfirmed)"
                    self._session_streamed = True
            self.refresh_measurements()
            if cycle_id and self.workspaceTabs.currentIndex() == 0 and not self.partEditor.dirty:
                # Live follows the newest completed part; history browsing and
                # unfinished edits retain their selection.
                if self.partEditor.set_entry(key):
                    self.historyPanel.select_key(key)
        except (ValueError, KeyError) as exc:
            logger.exception("Capture metadata validation failed")
            self.messagesBox.appendPlainText(f"Cycle {cycle_id} could not be prepared for upload: {exc}")

    def publish_capture(self, xdata, rows, cycle_id):
        key = (self._session_machine_id, self.session_id, cycle_id)
        entry = self.cycle_history[key]
        message = metadata.capture_message(entry, metadata.samples_for(entry["capture"], xdata, rows))
        self.mqtt_publisher.publish_records(message)
        entry["delivery"] = "Queued (unconfirmed)"
        self.refresh_measurements()
        self.messagesBox.appendPlainText(f"Queued {len(xdata)} samples and metadata for cycle {cycle_id}.")

    def toggle_history(self, checked):
        if checked:
            self.show_measurements()
        else:
            self.workspaceTabs.setCurrentIndex(0)

    def show_measurements(self):
        self.historyPanel.refresh()
        self.workspaceTabs.setCurrentIndex(1)

    def refresh_measurements(self):
        if self._measurements_dialog is not None:
            self._measurements_dialog.refresh()
        if self.partEditor.key:
            self.partEditor.set_entry(self.partEditor.key)
        else:
            self.select_latest_part()

    def update_measurements(self, key, weight, length):
        entry = self.cycle_history[key]
        if entry["capture"].get("mode") == "continuous":
            QtWidgets.QMessageBox.warning(self, "Measurements", "Continuous recordings do not represent a single part.")
            return
        try:
            baseline = max((entry["measurements"], entry.get("server_measurements", entry["measurements"])),
                           key=lambda m: m["revision"])
            entry["measurements"] = metadata.edit_measurements(baseline, weight, length)
            entry["local_measurement_edit"] = True
            entry["delivery"] = "Measurements not sent"
            if self.mqtt_enabled:
                self.send_measurements(key)
            self.refresh_measurements()
            return True
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Measurements", str(exc))
            return False

    def send_measurements(self, key, force=False):
        if self.is_monitoring and key[0] != self.machine_id:
            QtWidgets.QMessageBox.warning(self, "Send metadata", "Stop recording before sending metadata for another machine.")
            return
        entry = self.cycle_history[key]
        remote = entry.get("server_measurements")
        if remote and remote["revision"] >= entry["measurements"]["revision"]:
            values = entry["measurements"]
            entry["measurements"] = metadata.edit_measurements(remote, values.get("weight_g"), values.get("length_mm"))
            entry["local_measurement_edit"] = True
        self._ensure_mqtt_publisher(force=force, machine_id=key[0])
        if self.mqtt_publisher is not None and (self.mqtt_enabled or force):
            self.mqtt_publisher.publish_records(metadata.measurement_message(self.cycle_history[key]))
            self.cycle_history[key]["delivery"] = "Metadata queued (unconfirmed)"
            self.refresh_measurements()

    def export_measurements(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save cycle measurements", "", "JSON (*.json)")
        if path:
            try:
                metadata.export_metadata(path, self.cycle_history.values())
            except OSError as exc:
                QtWidgets.QMessageBox.warning(self, "Save measurements", str(exc))

    def import_measurements(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load saved cycle measurements", "", "JSON (*.json)")
        if not path:
            return
        try:
            entries, source = metadata.read_metadata(path, with_source=True)
            divergent = []
            # Validate conflicts before changing any entry.
            for entry in entries:
                old = self.cycle_history.get(metadata.identity(entry["capture"]))
                if old and old["capture"] != entry["capture"]:
                    raise ValueError("Capture identity conflicts with an existing recording.")
                if old and old["measurements"]["revision"] == entry["measurements"]["revision"]:
                    if any(old["measurements"].get(field) != entry["measurements"].get(field)
                           for field in ("weight_g", "length_mm")):
                        if source != 'server':
                            raise ValueError("Conflicting measurement edits have the same revision. Load a fresh server export to reconcile them.")
                        divergent.append(metadata.identity(entry['capture']))
                elif old and old['measurements']['revision'] > entry['measurements']['revision'] and source == 'server':
                    divergent.append(metadata.identity(entry['capture']))
            if divergent:
                answer = QtWidgets.QMessageBox.question(self, "Reconcile server measurements",
                    f"The server export differs from {len(divergent)} local edit(s).\n\n"
                    "Replace these local edits with the exported server values? "
                    "Use a fresh export. Cancel and Save your local metadata first if you need to retain the edits.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
                if answer != QtWidgets.QMessageBox.Yes:
                    return
            for entry in entries:
                key = metadata.identity(entry["capture"])
                old = self.cycle_history.get(key)
                if not old or source == 'server' or entry["measurements"]["revision"] > old["measurements"]["revision"]:
                    self.cycle_history[key] = entry
            self.refresh_measurements()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            QtWidgets.QMessageBox.warning(self, "Load measurements", str(exc))

    def save_session_export(self, path):
        """Save waveform/cycle CSVs and the full metadata snapshot as a file set."""
        path = Path(path)
        entries = {key[2]: entry for key, entry in self.cycle_history.items()
                   if key[:2] == (self._session_machine_id, self.session_id)}
        ordered_entries = [entries[cid] for cid in sorted(entries)]
        config = self._session_config
        cycles_path = path.with_suffix(".cycles.csv")
        metadata_path = path.with_suffix(".metadata.json")
        # Finish writing every file before replacing an existing export. Staging
        # beside the destination also keeps each individual replace on one volume.
        with TemporaryDirectory(prefix=".session-export-", dir=path.parent) as directory:
            staging = Path(directory)
            waveform = staging / path.name
            cycles = staging / cycles_path.name
            manifest = staging / metadata_path.name
            with waveform.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["session_id", "cycle_id", "session_cycle",
                                 "timestamp_ns", "time_s", *config["field_names"]])
                for i, (x, row) in enumerate(zip(self.xdata, self.ydata)):
                    cid = self.cycle_numbers_data[i] if self.cycle_numbers_data else 0
                    capture = entries[cid]["capture"]
                    stamp = int(capture["base_time_ns"]) + round(float(x) * 1e9)
                    writer.writerow([capture["session_id"], cid, capture["session_cycle"],
                                     str(stamp), x, *[row[j] for j in config["saved_indices"]]])
            metadata.export_cycle_summary(cycles, ordered_entries)
            metadata.export_metadata(manifest, ordered_entries)
            cycles.replace(cycles_path)
            manifest.replace(metadata_path)
            waveform.replace(path)
