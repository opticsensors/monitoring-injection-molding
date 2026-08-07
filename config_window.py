"""
DAQ configuration dialog.

A self-contained ``QDialog`` with three tabs (DAQ / Display / Conversion). It
reads its initial values from ``CONFIG_DEFAULTS`` and communicates the result to
the rest of the app through a single ``configSignal`` carrying a config dict -
it never reaches into ``MainWindow`` internals.
"""
from PyQt5 import QtWidgets, QtCore

from sensor_types import (
    SENSOR_TYPES, SENSOR_TYPE_ORDER, MACHINE_CONVERSION_ORDER,
    TRIGGER_TYPE, TRIGGER_MODES, DIGITAL_INPUTS, normalize_trigger_type,
    normalize_trigger_mode,
    sensor_category, sensor_label, sensor_unit, sensor_tooltip,
)
from config import CONFIG_DEFAULTS


class DaqConfigWindow(QtWidgets.QDialog):
    # A single dict carries the whole configuration - far easier to extend than a
    # long positional signal.
    configSignal = QtCore.pyqtSignal(dict)

    AVAILABLE_CHANNELS = list(range(8))         # CH0..CH7
    ALLOWED_VOLTAGE_RANGES = [0.2, 0.5, 1, 2, 5, 10]
    # Legacy analog type codes. 'I' was an analog inductive trigger; triggers are
    # digital-only now, so it maps to 'none'.
    LEGACY_TYPE_MAP = {'T': 'T_futaba', 'P': 'P_kistler', 'I': 'none'}
    # Shared vertical-header width so the analog and digital tables line up.
    VHEADER_W = 110

    # Header of the cell being edited goes BOLD (like the analog table) instead of
    # the default blue "selected section" highlight. Applied to every config table.
    TABLE_HEADER_QSS = (
        "QHeaderView::section { background-color: palette(button); }"
        "QHeaderView::section:checked { background-color: palette(button); font-weight: bold; }"
    )

    def __init__(self, parent=None):
        super(DaqConfigWindow, self).__init__(parent)
        self.setWindowTitle("DAQ Configuration")
        self.setModal(True)
        # Drop the title-bar "?" (What's This) button Qt puts on dialogs by
        # default: nothing here implements context help, and every field already
        # explains itself through its tooltip. Close stays.
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

        self.available_channels = list(self.AVAILABLE_CHANNELS)
        self.num_channels = len(self.available_channels)

        # Widget storage
        self.channel_type_combos = {}
        self.voltage_range_edits = {}
        self.machine_init_edits = {}
        self.machine_res_edits = {}
        self.plot_var_checks = {}      # ch_num -> QCheckBox (rebuilt on refresh)
        self._plot_check_state = {}    # ch_num -> bool (persists across rebuilds)
        self.digital_combos = {}       # 'D0'..'D6' -> QComboBox

        self.setupUi()
        self.loadDefaults()
        self.resize(1240, 680)
        self.setMinimumWidth(1100)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _combo(pairs):
        """Build a QComboBox from (label, userData) pairs."""
        c = QtWidgets.QComboBox()
        for label, data in pairs:
            c.addItem(label, data)
        return c

    @staticmethod
    def _select_data(combo, data):
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _normalize_type(self, t):
        if t in SENSOR_TYPES:
            return t
        return self.LEGACY_TYPE_MAP.get(str(t), 'none')

    def _combo_of_types(self, codes):
        """Sensor-type dropdown over `codes`, with per-item and live tooltips."""
        combo = QtWidgets.QComboBox()
        for code in codes:
            combo.addItem(sensor_label(code), code)
            combo.setItemData(combo.count() - 1, sensor_tooltip(code), QtCore.Qt.ToolTipRole)
        combo.setMinimumWidth(120)
        combo.setToolTip(sensor_tooltip(codes[0]))
        combo.currentIndexChanged.connect(
            lambda _i, c=combo: c.setToolTip(sensor_tooltip(c.currentData())))
        return combo

    def _make_type_combo(self):
        """Per-channel dropdown for the analog table: measurement types only.

        The trigger is a digital input (the main relay contact), never an analog
        channel, so it is not offered here.
        """
        return self._combo_of_types([c for c in SENSOR_TYPE_ORDER
                                     if sensor_category(c) != 'trigger'])

    def _make_digital_combo(self):
        """Per-input dropdown for the digital table: 'none' or 'trigger'."""
        return self._combo_of_types(['none', TRIGGER_TYPE])

    def _style_table_headers(self, table):
        """Make the active cell's row/column header render BOLD (no blue fill),
        consistently across the analog, digital and machine tables."""
        table.horizontalHeader().setHighlightSections(True)
        table.verticalHeader().setHighlightSections(True)
        table.setStyleSheet(self.TABLE_HEADER_QSS)

    # --------------------------------------------------------------------- UI
    def setupUi(self):
        main_layout = QtWidgets.QVBoxLayout()

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_daq_tab(), "DAQ")
        self.tabs.addTab(self._build_display_tab(), "Display")
        self.tabs.addTab(self._build_conversion_tab(), "Conversion")
        main_layout.addWidget(self.tabs)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        self.okButton = QtWidgets.QPushButton("OK")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self.okButton)
        button_layout.addWidget(self.cancelButton)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        self.okButton.clicked.connect(self.accept_config)
        self.cancelButton.clicked.connect(self.close)

        # Keep the Display tab's variable checklists in sync with the DAQ tab's
        # channel types (both tabs exist by now).
        for combo in self.channel_type_combos.values():
            combo.currentIndexChanged.connect(self._refresh_plot_var_lists)

    def _build_daq_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        # -------- DAQ Settings --------
        daq_group = QtWidgets.QGroupBox("DAQ Settings")
        daq_layout = QtWidgets.QGridLayout()
        daq_layout.addWidget(QtWidgets.QLabel("Monitoring Time (s):"), 0, 0)
        self.timeEdit = QtWidgets.QLineEdit()
        self.timeEdit.setToolTip("Duration of monitoring session in seconds")
        daq_layout.addWidget(self.timeEdit, 0, 1)
        daq_layout.addWidget(QtWidgets.QLabel("Sample Rate (Hz):"), 1, 0)
        self.srateEdit = QtWidgets.QLineEdit()
        self.srateEdit.setToolTip("Sampling rate in Hz")
        daq_layout.addWidget(self.srateEdit, 1, 1)
        daq_layout.addWidget(QtWidgets.QLabel("Decimation (dec):"), 2, 0)
        self.decEdit = QtWidgets.QLineEdit()
        self.decEdit.setToolTip("Decimation factor for data reduction")
        daq_layout.addWidget(self.decEdit, 2, 1)
        daq_layout.setColumnStretch(2, 1)
        daq_group.setLayout(daq_layout)
        layout.addWidget(daq_group)

        # -------- Analog channels table (CH0..CH7 as columns) --------
        channel_group = QtWidgets.QGroupBox("Analog channels")
        channel_layout = QtWidgets.QVBoxLayout()

        self.channelTable = QtWidgets.QTableWidget()
        self.channelTable.setRowCount(2)     # Type, Voltage Range
        self.channelTable.setColumnCount(self.num_channels)
        self.channelTable.setHorizontalHeaderLabels([f"CH {ch}" for ch in self.available_channels])
        self.channelTable.setVerticalHeaderLabels(["Type", "Voltage Range"])

        for col, ch_num in enumerate(self.available_channels):
            combo = self._make_type_combo()
            self.channelTable.setCellWidget(0, col, combo)
            self.channel_type_combos[ch_num] = combo

            edit = QtWidgets.QLineEdit()
            edit.setToolTip(f"Voltage range for CH{ch_num} (one of 0.2, 0.5, 1, 2, 5, 10)")
            self.channelTable.setCellWidget(1, col, edit)
            self.voltage_range_edits[ch_num] = edit

        self.channelTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.channelTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.channelTable.verticalHeader().setDefaultSectionSize(34)
        self.channelTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.channelTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.channelTable.verticalHeader().setFixedWidth(self.VHEADER_W)
        header_h = self.channelTable.horizontalHeader().height()
        self.channelTable.setFixedHeight(header_h + 34 * 2 + 6)
        self.channelTable.setColumnWidth(0, 130)
        self._style_table_headers(self.channelTable)

        channel_layout.addWidget(self.channelTable)
        channel_group.setLayout(channel_layout)
        layout.addWidget(channel_group)

        # -------- Digital channels table (D0..D6, same layout as the analog one) --------
        digital_group = QtWidgets.QGroupBox("Digital channels")
        digital_layout = QtWidgets.QVBoxLayout()

        self.digitalTable = QtWidgets.QTableWidget()
        self.digitalTable.setRowCount(1)                       # Type only (no voltage range)
        self.digitalTable.setColumnCount(len(DIGITAL_INPUTS))  # D0..D6
        self.digitalTable.setHorizontalHeaderLabels([f"{d}" for d in DIGITAL_INPUTS])
        self.digitalTable.setVerticalHeaderLabels(["Type"])

        for col, name in enumerate(DIGITAL_INPUTS):
            combo = self._make_digital_combo()
            self.digitalTable.setCellWidget(0, col, combo)
            self.digital_combos[name] = combo

        # Sized exactly like the analog table above: stretched columns, same row
        # height and the same vertical-header width so the two line up.
        self.digitalTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.digitalTable.verticalHeader().setFixedWidth(self.VHEADER_W)
        self.digitalTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.digitalTable.verticalHeader().setDefaultSectionSize(34)
        self.digitalTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.digitalTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        dig_header_h = self.digitalTable.horizontalHeader().height()
        self.digitalTable.setFixedHeight(dig_header_h + 34 + 6)
        self._style_table_headers(self.digitalTable)

        digital_layout.addWidget(self.digitalTable)
        digital_group.setLayout(digital_layout)
        layout.addWidget(digital_group)
        layout.addStretch(1)
        return tab

    def _build_display_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        # -------- Display Settings --------
        display_group = QtWidgets.QGroupBox("Display Settings")
        display_layout = QtWidgets.QGridLayout()
        display_layout.addWidget(QtWidgets.QLabel("Points to Display:"), 0, 0)
        self.pointsEdit = QtWidgets.QLineEdit()
        self.pointsEdit.setToolTip("Number of data points visible on the plot (10-2000).")
        display_layout.addWidget(self.pointsEdit, 0, 1)
        display_layout.addWidget(QtWidgets.QLabel("Plot Refresh Rate (ms):"), 1, 0)
        self.refreshEdit = QtWidgets.QLineEdit()
        self.refreshEdit.setToolTip("How often the plot redraws, in ms (10-1000).")
        display_layout.addWidget(self.refreshEdit, 1, 1)
        display_layout.setColumnStretch(2, 1)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        combo_w = 190  # keep the dropdowns compact instead of full-width

        # -------- Mold plot (layout + variables to plot) --------
        mold_group = QtWidgets.QGroupBox("Mold plot")
        mold_layout = QtWidgets.QGridLayout()
        mold_layout.addWidget(QtWidgets.QLabel("Layout:"), 0, 0)
        self.moldAxesCombo = self._combo([
            ("Shared", False),
            ("One plot per channel", True),
        ])
        self.moldAxesCombo.setToolTip("How the mould sensors (temperature + Kistler pressure) are laid out.")
        self.moldAxesCombo.setMaximumWidth(combo_w)
        mold_layout.addWidget(self.moldAxesCombo, 0, 1)
        mold_layout.addWidget(QtWidgets.QLabel("Variables:"), 1, 0, QtCore.Qt.AlignTop)
        self.moldVarsLayout = QtWidgets.QVBoxLayout()
        self.moldVarsLayout.setSpacing(2)
        mold_layout.addLayout(self.moldVarsLayout, 1, 1)
        mold_layout.setColumnStretch(2, 1)
        mold_group.setLayout(mold_layout)
        layout.addWidget(mold_group)

        # -------- Machine plot (layout + variables to plot) --------
        mach_group = QtWidgets.QGroupBox("Machine plot")
        mach_layout = QtWidgets.QGridLayout()
        mach_layout.addWidget(QtWidgets.QLabel("Layout:"), 0, 0)
        self.machineLayoutCombo = self._combo([
            ("Shared", "shared"),
            ("One plot per channel", "separate"),
        ])
        self.machineLayoutCombo.setToolTip("How the machine signals are laid out on the Machine data tab.")
        self.machineLayoutCombo.setMaximumWidth(combo_w)
        mach_layout.addWidget(self.machineLayoutCombo, 0, 1)
        mach_layout.addWidget(QtWidgets.QLabel("Variables:"), 1, 0, QtCore.Qt.AlignTop)
        self.machineVarsLayout = QtWidgets.QVBoxLayout()
        self.machineVarsLayout.setSpacing(2)
        mach_layout.addLayout(self.machineVarsLayout, 1, 1)
        mach_layout.setColumnStretch(2, 1)
        mach_group.setLayout(mach_layout)
        layout.addWidget(mach_group)

        # -------- Trigger --------
        trig_group = QtWidgets.QGroupBox("Trigger")
        trig_layout = QtWidgets.QGridLayout()
        trig_layout.addWidget(QtWidgets.QLabel("Trigger for cycle control:"), 0, 0)
        self.triggerModeCombo = self._combo([(m, m) for m in TRIGGER_MODES])
        self.triggerModeCombo.setToolTip(
            "What gates acquisition into cycles (all analog signals start/stop together):\n"
            "• None: continuous acquisition, no cycles.\n"
            "• Manual / Inductive / Machine signal: each LOW→HIGH starts a cycle,\n"
            "  the following HIGH→LOW ends it.\n"
            "• Machine mold position: the SAME input read upside down - the cycle\n"
            "  runs while it is LOW. The machine's 0-10 V mould-position output is\n"
            "  the inverse of the other sources: it drives the SSR during the OPEN\n"
            "  phase, so between cycles the input sits HIGH.\n"
            "Cycles overlay on the same plot, with previous ones ghosted.\n\n"
            "Every source is read from the SAME digital input: they are wired in\n"
            "parallel onto the main relay coil, and the DAQ reads that relay's\n"
            "contact. Picking one here records which source you are using and, with\n"
            "it, the polarity - set which input it is in the Digital channels table\n"
            "(DAQ tab).")
        self.triggerModeCombo.setMaximumWidth(combo_w)
        trig_layout.addWidget(self.triggerModeCombo, 0, 1)
        trig_layout.setColumnStretch(2, 1)
        trig_group.setLayout(trig_layout)
        layout.addWidget(trig_group)

        # -------- Cloud upload --------
        cloud_group = QtWidgets.QGroupBox("Cloud upload")
        cloud_layout = QtWidgets.QGridLayout()
        self.mqttCheckBox = QtWidgets.QCheckBox("Send data to cloud via MQTT")
        self.mqttCheckBox.setToolTip(
            "Publish each completed cycle (or the whole session in continuous mode)\n"
            "to the MQTT broker configured in the .env file\n"
            "(BROKER / PORT / user / password).\n"
            "The topic is not configured there: it is '<Machine ID>/sensors'.\n"
            "Batches that cannot be delivered are kept in 'pending/' and retried.")
        cloud_layout.addWidget(self.mqttCheckBox, 0, 0, 1, 2)
        cloud_layout.addWidget(QtWidgets.QLabel("Machine ID:"), 1, 0)
        self.machineIdCombo = self._combo([('160t', '160t'), ('55t', '55t')])
        self.machineIdCombo.setMaximumWidth(combo_w)
        self.machineIdCombo.setToolTip(
            "Machine identifier sent with every record (pick 160t or 55t).\n"
            "It also selects the MQTT topic, '<Machine ID>/sensors'.")
        cloud_layout.addWidget(self.machineIdCombo, 1, 1)
        cloud_layout.setColumnStretch(2, 1)
        cloud_group.setLayout(cloud_layout)
        layout.addWidget(cloud_group)
        layout.addStretch(1)
        return tab

    def _refresh_plot_var_lists(self):
        """Rebuild the Mold/Machine variable checklists from the DAQ tab's types.

        Check state is remembered per channel number in _plot_check_state, so
        toggling a channel's type back and forth does not lose the selection.
        """
        for lay in (self.moldVarsLayout, self.machineVarsLayout):
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        self.plot_var_checks = {}
        found = {'mold': False, 'machine': False}
        for ch_num in self.available_channels:
            code = self.channel_type_combos[ch_num].currentData()
            cat = sensor_category(code)
            if cat in ('temp', 'moldP'):
                target, key = self.moldVarsLayout, 'mold'
            elif cat == 'machine':
                target, key = self.machineVarsLayout, 'machine'
            else:
                continue
            cb = QtWidgets.QCheckBox(f"CH{ch_num} - {sensor_label(code)}")
            cb.setToolTip("Unchecked channels are still acquired, saved and uploaded - just not drawn.")
            cb.setChecked(self._plot_check_state.get(ch_num, True))
            cb.toggled.connect(
                lambda checked, ch=ch_num: self._plot_check_state.__setitem__(ch, checked))
            target.addWidget(cb)
            self.plot_var_checks[ch_num] = cb
            found[key] = True
        if not found['mold']:
            self.moldVarsLayout.addWidget(QtWidgets.QLabel("No mold sensors configured (see DAQ tab)"))
        if not found['machine']:
            self.machineVarsLayout.addWidget(QtWidgets.QLabel("No machine signals configured (see DAQ tab)"))

    def _build_conversion_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setSpacing(10)

        # -------- Temperature (Futaba) --------
        temp_group = QtWidgets.QGroupBox("Temperature — T_futaba")
        temp_layout = QtWidgets.QGridLayout()
        temp_layout.addWidget(QtWidgets.QLabel("°C per Volt:"), 0, 0)
        self.tempDegPerVoltEdit = QtWidgets.QLineEdit()
        self.tempDegPerVoltEdit.setToolTip("Temperature scale. °C = (raw→Volts) × this factor. Default 100.")
        temp_layout.addWidget(self.tempDegPerVoltEdit, 0, 1)
        temp_layout.setColumnStretch(2, 1)
        temp_group.setLayout(temp_layout)
        layout.addWidget(temp_group)

        # -------- Pressure (Kistler) --------
        kist_group = QtWidgets.QGroupBox("Pressure — P_kistler")
        kist_layout = QtWidgets.QGridLayout()
        kist_layout.addWidget(QtWidgets.QLabel("sensitivity 1 [pC/bar]:"), 0, 0)
        self.kistlerS0Edit = QtWidgets.QLineEdit()
        kist_layout.addWidget(self.kistlerS0Edit, 0, 1)
        kist_layout.addWidget(QtWidgets.QLabel("sensitivity 2 [pC/bar]:"), 1, 0)
        self.kistlerS1Edit = QtWidgets.QLineEdit()
        kist_layout.addWidget(self.kistlerS1Edit, 1, 1)
        kist_layout.addWidget(QtWidgets.QLabel("max range [pC]:"), 2, 0)
        self.kistlerQmaxEdit = QtWidgets.QLineEdit()
        kist_layout.addWidget(self.kistlerQmaxEdit, 2, 1)
        kist_layout.setColumnStretch(2, 1)
        self.kistlerS0Edit.setToolTip("bar = raw × (Qmax / s) / 32768. First Kistler channel uses s0, next s1, alternating.")
        kist_group.setLayout(kist_layout)
        layout.addWidget(kist_group)

        # -------- Machine variables (table, same style as the channel tables) --------
        mach_group = QtWidgets.QGroupBox("Machine variables")
        mach_layout = QtWidgets.QVBoxLayout()

        n_mach = len(MACHINE_CONVERSION_ORDER)
        self.machineTable = QtWidgets.QTableWidget()
        self.machineTable.setRowCount(n_mach)
        self.machineTable.setColumnCount(2)
        self.machineTable.setHorizontalHeaderLabels(["Initial value", "Resolution (mV)"])
        self.machineTable.setVerticalHeaderLabels(
            [f"{sensor_label(c)} [{sensor_unit(c)}]" for c in MACHINE_CONVERSION_ORDER])

        for row, code in enumerate(MACHINE_CONVERSION_ORDER):
            init_edit = QtWidgets.QLineEdit()
            self.machine_init_edits[code] = init_edit
            self.machineTable.setCellWidget(row, 0, init_edit)
            res_edit = QtWidgets.QLineEdit()
            self.machine_res_edits[code] = res_edit
            self.machineTable.setCellWidget(row, 1, res_edit)
            header_item = self.machineTable.verticalHeaderItem(row)
            if header_item is not None:
                header_item.setToolTip(sensor_tooltip(code))

        # Fixed, compact sizing so the table doesn't fill the whole window width.
        col0_w, col1_w, vhead_w = 110, 180, 150
        self.machineTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.machineTable.setColumnWidth(0, col0_w)
        self.machineTable.setColumnWidth(1, col1_w)
        self.machineTable.verticalHeader().setFixedWidth(vhead_w)
        self.machineTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.machineTable.verticalHeader().setDefaultSectionSize(34)
        self.machineTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.machineTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        mh = self.machineTable.horizontalHeader().height()
        self.machineTable.setFixedHeight(mh + 34 * n_mach + 6)
        self.machineTable.setFixedWidth(vhead_w + col0_w + col1_w + 6)
        self._style_table_headers(self.machineTable)

        mach_row = QtWidgets.QHBoxLayout()
        mach_row.addWidget(self.machineTable)
        mach_row.addStretch(1)
        mach_layout.addLayout(mach_row)
        mach_group.setLayout(mach_layout)
        layout.addWidget(mach_group)
        layout.addStretch(1)
        return tab

    # ---------------------------------------------------------------- defaults
    def loadDefaults(self):
        d = CONFIG_DEFAULTS

        # Seed the plot-variable selection before touching the type combos
        # (changing a combo rebuilds the checklists from this state). Only seed
        # channels configured in the defaults - a channel the user newly enables
        # should start checked, not inherit "unplotted" from being unused.
        sel = d.get('plot_channels')
        if sel is not None:
            configured = set(d.get('channels', []))
            self._plot_check_state = {ch: (ch in sel)
                                      for ch in self.available_channels if ch in configured}

        self.timeEdit.setText(str(d.get('monitoring_time_s', 300)))
        self.srateEdit.setText(str(d.get('sample_rate_hz', 6000)))
        self.decEdit.setText(str(d.get('decimation', 100)))
        self.pointsEdit.setText(str(d.get('display_points', 1600)))
        self.refreshEdit.setText(str(d.get('plot_refresh_rate_ms', 50)))

        # Channels: reset all to none, then apply defaults
        for ch_num in self.available_channels:
            self._select_data(self.channel_type_combos[ch_num], 'none')
            self.voltage_range_edits[ch_num].setText("10")
        default_channels = d.get('channels', [])
        default_types = d.get('channel_types', [])
        default_voltages = d.get('voltage_ranges', [])
        for i, ch_num in enumerate(default_channels):
            if ch_num in self.channel_type_combos:
                if i < len(default_types):
                    self._select_data(self.channel_type_combos[ch_num],
                                      self._normalize_type(default_types[i]))
                if i < len(default_voltages):
                    self.voltage_range_edits[ch_num].setText(str(default_voltages[i]))

        # Plot layout
        self._select_data(self.moldAxesCombo, bool(d.get('separate_plots', False)))
        self._select_data(self.machineLayoutCombo, d.get('machine_layout', 'shared'))
        self._select_data(self.triggerModeCombo,
                          normalize_trigger_mode(d.get('trigger_mode', 'None')))
        self._refresh_plot_var_lists()

        # Cloud upload
        self.mqttCheckBox.setChecked(bool(d.get('mqtt_enabled', False)))
        machine_id = str(d.get('machine_id', '160t'))
        if self.machineIdCombo.findData(machine_id) < 0:  # keep any legacy id selectable
            self.machineIdCombo.addItem(machine_id, machine_id)
        self._select_data(self.machineIdCombo, machine_id)

        # Digital inputs D0..D6: 'none' unless this is the trigger input.
        # Legacy configs named it 'Inductive' / 'Machine_signal'; both normalise
        # onto the single 'trigger' type.
        dmap = d.get('digital_map', {})
        for name in DIGITAL_INPUTS:
            self._select_data(self.digital_combos[name],
                              normalize_trigger_type(dmap.get(name, 'none')))

        # Conversion
        conv = d.get('conversion', {})
        t = conv.get('T_futaba', {})
        self.tempDegPerVoltEdit.setText(str(t.get('deg_per_volt', 100.0)))
        k = conv.get('P_kistler', {})
        self.kistlerS0Edit.setText(str(k.get('s0', 2.500)))
        self.kistlerS1Edit.setText(str(k.get('s1', 2.508)))
        self.kistlerQmaxEdit.setText(str(k.get('Qmax', 20000.0)))
        for code in MACHINE_CONVERSION_ORDER:
            c = conv.get(code, {})
            self.machine_init_edits[code].setText(str(c.get('initial', 0.0)))
            self.machine_res_edits[code].setText(str(c.get('resolution_mV', 10.0)))

    # ------------------------------------------------------------------ accept
    def _warn(self, msg):
        QtWidgets.QMessageBox.warning(self, "Error", msg)

    def accept_config(self):
        try:
            timeint = float(self.timeEdit.text())
            srate = int(self.srateEdit.text())
            dec = int(self.decEdit.text())
            n_points = int(self.pointsEdit.text())
            refresh_rate = float(self.refreshEdit.text())
        except ValueError as e:
            self._warn(f"Please enter valid numeric values in DAQ / Display settings.\n\nError: {e}")
            return

        # Gather enabled channels (measurement channels only - the trigger is a
        # digital input, never an analog channel)
        channels, channel_types, voltage_ranges = [], [], []
        for ch_num in self.available_channels:
            code = self.channel_type_combos[ch_num].currentData()
            if code == 'none':
                continue
            channels.append(ch_num)
            channel_types.append(code)
            try:
                v = float(self.voltage_range_edits[ch_num].text())
            except ValueError:
                self._warn(f"Invalid voltage range for CH{ch_num}. Please enter a number.")
                return
            if v not in self.ALLOWED_VOLTAGE_RANGES:
                self._warn(f"Voltage range for CH{ch_num} must be one of "
                           f"{self.ALLOWED_VOLTAGE_RANGES} (V).")
                return
            voltage_ranges.append(v)

        if len(channels) == 0:
            self._warn("No channels selected!\n\nSet at least one channel to a real type.")
            return
        if len(channels) > 8:
            self._warn("Maximum 8 channels can be selected.")
            return
        if n_points < 10 or n_points > 2000:
            self._warn("Points to display must be between 10 and 2000.")
            return
        if refresh_rate < 10 or refresh_rate > 1000:
            self._warn("Refresh rate must be between 10 and 1000 ms.")
            return

        trigger_mode = self.triggerModeCombo.currentData()
        digital_map = {name: combo.currentData()
                       for name, combo in self.digital_combos.items()}
        trigger_inputs = [n for n, c in digital_map.items() if c == TRIGGER_TYPE]

        # Exactly one input carries the main relay contact; more than one would
        # leave the cycle logic silently picking the lowest-numbered.
        if len(trigger_inputs) > 1:
            self._warn("Only one digital input can be the trigger.\n\n"
                       f"'{sensor_label(TRIGGER_TYPE)}' is set on {', '.join(sorted(trigger_inputs))}.")
            return
        if trigger_mode != 'None' and not trigger_inputs:
            self._warn(f"Trigger mode '{trigger_mode}' needs one digital input (D0..D6) set to "
                       f"'{sensor_label(TRIGGER_TYPE)}'.\n\nSet it in the Digital channels table "
                       "on the DAQ tab.")
            return

        # Conversion parameters
        try:
            conversion = {
                'T_futaba':  {'deg_per_volt': float(self.tempDegPerVoltEdit.text())},
                'P_kistler': {'s0': float(self.kistlerS0Edit.text()),
                              's1': float(self.kistlerS1Edit.text()),
                              'Qmax': float(self.kistlerQmaxEdit.text())},
            }
            for code in MACHINE_CONVERSION_ORDER:
                conversion[code] = {
                    'initial': float(self.machine_init_edits[code].text()),
                    'resolution_mV': float(self.machine_res_edits[code].text()),
                }
        except ValueError as e:
            self._warn(f"Please enter valid numbers in the Conversion tab.\n\nError: {e}")
            return
        for code in MACHINE_CONVERSION_ORDER:
            if conversion[code]['resolution_mV'] == 0:
                self._warn(f"Resolution for {sensor_label(code)} cannot be 0.")
                return

        # Channels ticked for plotting (unticked ones are still acquired/saved).
        # Trigger channels are never drawn as a line, so they never appear here.
        plot_channels = [ch for ch, t in zip(channels, channel_types)
                         if sensor_category(t) != 'trigger'
                         and self._plot_check_state.get(ch, True)]

        cfg = {
            'monitoring_time_s': timeint,
            'channels': channels,
            'channel_types': channel_types,
            'voltage_ranges': voltage_ranges,
            'sample_rate_hz': srate,
            'decimation': dec,
            'display_points': n_points,
            'plot_refresh_rate_ms': refresh_rate,
            'separate_plots': bool(self.moldAxesCombo.currentData()),
            'machine_layout': self.machineLayoutCombo.currentData(),
            'plot_channels': plot_channels,
            'mqtt_enabled': self.mqttCheckBox.isChecked(),
            'machine_id': self.machineIdCombo.currentData() or '160t',
            'trigger_mode': trigger_mode,
            'digital_map': digital_map,
            'conversion': conversion,
        }
        self.configSignal.emit(cfg)
        self.close()
