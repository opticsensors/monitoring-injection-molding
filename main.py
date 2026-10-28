"""
Low cost monitoring system adapted for DAQ connectivity.
Prepared to display and store values from a DAQ device with configurable channels.

User interface based on PyQt5.
Enhanced with unit conversion, dual-axis plotting, and configurable channel types.
Supports Temperature (T), Pressure (P), and Inductive sensor (I) channels.
"""
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
import sys
import os
import daq_connectivity as daq  # Import DAQ library
from time import sleep
from time import perf_counter
from datetime import datetime
import logging
import queue
import threading
import numpy as np
from pathlib import Path
from copy import deepcopy

import MainWindow
from app_logging import setup_logging
from config import CONFIG_DEFAULTS, DAQ_INPUT_RANGE_V, fixed_voltage_ranges
from sensor_types import (sensor_category,
                          TRIGGER_TYPE, DIGITAL_INPUTS, digital_bit,
                          normalize_trigger_type, normalize_trigger_mode,
                          trigger_is_inverted)
from config_window import DaqConfigWindow
from metadata_controller import MetadataController
from desktop_controller import DesktopController
from desktop_widgets import configure_application
from plot_view import PlotViewMixin

logger = logging.getLogger('main')

# Cycle-counter persistence: cycle numbers keep increasing across sessions,
# restarts and power loss (same idea as the Pi loggers' cycle_id.txt).
CYCLE_ID_FILE = Path(__file__).parent / 'data' / 'cycle_id.txt'


def load_cycle_id():
    """Last retained cycle number for this installation (0 if none yet)."""
    try:
        return int(CYCLE_ID_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def save_cycle_id(cid):
    """Write atomically (tmp + replace) so a power cut cannot truncate the file."""
    try:
        CYCLE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CYCLE_ID_FILE.with_suffix('.tmp')
        tmp.write_text(str(cid))
        os.replace(tmp, CYCLE_ID_FILE)
    except OSError as e:
        logger.exception("Could not save cycle_id %s: %s", cid, e)

##########################################################################################
################################## Program ###############################################
##########################################################################################

# User Interface threads: ################################################################
##########################################################################################
# The main GUI window class:
class MainWindow(DesktopController, MetadataController, PlotViewMixin, QtWidgets.QMainWindow, MainWindow.Ui_MainWindow):
    """Main window of the GUI:

    Shows buttons for configuration, to connect or disconnect DAQ communication, start/stop reading, save session data and exit app;
    Shows the "real-time" plots of the sensors with unit conversion;
    Shows messages in a message box.
    """
    #Define signals:
    startSig = QtCore.pyqtSignal() #Start monitoring signal
    stopSig = QtCore.pyqtSignal() #Stop monitoring signal
    disconnectSig = QtCore.pyqtSignal() #Disconnect DAQ signal
    stopThreadSig = QtCore.pyqtSignal() #Stop DAQ threads signal
    saveSig =QtCore.pyqtSignal() #Save session signal

    def __init__(self, parent = None):
        super(MainWindow, self).__init__(parent)
        configure_application(QtWidgets.QApplication.instance())
        self.setupUi(self)

        self.modules = 1 # Always use module 1 for DAQ (4 channels)
        self.sensors = [f'CH{ch}' for ch in CONFIG_DEFAULTS['channels']]
        self.nsensors_m1 = 4 # Number of DAQ channels
        self.time_lim = CONFIG_DEFAULTS['monitoring_time_s']
        self.daq_connected = False # State of DAQ (connected/disconnected)
        self.is_monitoring = False  # State of monitoring (running/stopped)
        self.nplots = len(CONFIG_DEFAULTS['channels'])
        self.xdata = [] # x data list for all x data from a session
        self.ydata = [] # y data list for all y data from a session (converted units)
        self.ydata_raw = [] # y data list for all raw voltage data from a session
        self.cycle_numbers_data = [] # cycle number for each data point (for cycle mode)
        self.xdata_plts = [] # x data list for plots
        self.ydata_plts = [] # y data list for plots (converted units)
        self.plotDataItem_lst = [] # List for plot data items identifiers (per channel index)
        self.splotlist = [] # Mold-tab subplots
        self.machine_splotlist = [] # Machine-tab subplots
        self.y_axis_groups = [] # List of (axis/viewbox, [channel indices]) for Y-range updates
        self.item_target = {} # channel index -> container (PlotItem/ViewBox) for adding line items
        self._extra_viewboxes = [] # extra ViewBoxes to tear down on reset
        self.right_viewbox = None # mold right (pressure) axis viewbox
        self.machine_left2_viewbox = None # machine 2nd-left (speed) axis viewbox
        self.machine_right_viewbox = None # machine right (pressure) axis viewbox
        self.machine_arrow_scatter = None # trigger arrows on machine tab
        self.machine_lines_item = None
        self.cycle_labels = [] # list of (TextItem, plot) per tab

        # Color palettes: temperature (warm), mould pressure (cold), machine (distinct)
        self.temp_colors = ['#FF0000', '#FF6600', '#FF9900', '#FFCC00']  # Red, Orange, Dark Orange, Gold
        self.pressure_colors = ['#0000FF', '#0099FF', '#00CCFF', '#00FFFF']  # Blue, Light Blue, Cyan, Aqua
        # Fixed colour per machine signal type
        self.machine_colors = {'pos_screw': '#8E44AD', 'vel_screw': '#16A085', 'P_machine': '#E67E22'}

        # Channel type configuration from defaults (full-name codes, see SENSOR_TYPES)
        self.channel_types = list(CONFIG_DEFAULTS['channel_types'])

        # Unit conversion constants + editable conversion parameters
        self.adc_resolution = 2**(16-1)  # 15-bit ADC full-scale count (32768)
        self.voltage_scale = DAQ_INPUT_RANGE_V  # Fixed app input/calibration range
        # Deep-ish copy so edits from the config window don't mutate CONFIG_DEFAULTS
        self.conversion = {k: dict(v) for k, v in CONFIG_DEFAULTS.get('conversion', {}).items()}

        # Trigger / cycle configuration.
        # The trigger is always a digital input: every source (manual switch,
        # inductive sensor, machine signal) is wired in parallel onto the main
        # relay coil, and the DAQ reads that relay's dry contact. trigger_mode
        # records which source is in use; they all read the same input, and the
        # only thing that varies with the source is the polarity (mould position
        # is active-LOW, see INVERTED_TRIGGER_MODES).
        self.trigger_mode = normalize_trigger_mode(  # see TRIGGER_MODES
            CONFIG_DEFAULTS.get('trigger_mode', 'None'))
        self.digital_map = dict(CONFIG_DEFAULTS.get('digital_map', {'D4': TRIGGER_TYPE}))
        self.machine_layout = CONFIG_DEFAULTS.get('machine_layout', 'shared')  # 'shared'|'separate'

        self.i_channel_state = None  # Current state: 'LOW', 'HIGH', or None
        self.i_channel_transitions = []  # List of (x_time, 'UP' or 'DOWN') tuples
        self.i_channel_digital_values = []  # List of (x_time, 0 or 1) for saving
        self.i_arrow_scatter = None  # ScatterPlotItem for arrows
        self.i_lines_item = None  # PlotDataItem for vertical lines
        
        # Cycle mode configuration (cycle control is on whenever a trigger mode is selected)
        self.cycle_mode = (self.trigger_mode != 'None')  # If True, trigger controls cycle start/end
        self.current_cycle = 0  # Current cycle number (1-based when active)
        self.cycle_max_x = 0  # Maximum X value seen across all cycles
        self.completed_cycles_data = []  # (cycle_num, cycle_start_s, xdata, ydata) per cycle; used for the manual cloud resend
        self.completed_cycles_plots = []  # List of plot items for completed cycles
        self.cycle_label = None  # Label showing current cycle number

        # Plot interaction tools (matplotlib-style Home/Zoom/Pan + time cursors).
        # Tools are only usable while the plot is "still" (not following data):
        # continuous mode -> after Stop; cycle mode -> between cycles (trigger LOW).
        self.plot_is_live = False
        self.tool_mode = None                   # None | 'pan' | 'zoom' | 'cursor'
        self._tool_viewboxes = []               # ToolViewBox of every subplot
        self._default_x_range = None            # (lo, hi, padding) of the live view
        self._default_y_ranges = []             # (lo, hi) per y_axis_groups entry
        self._last_plot_x = []                  # data currently on screen ...
        self._last_plot_y = []                  # ... used for the cursor readout
        self.cursor_lines = {'t1': [], 't2': []}  # per key: [(plot, InfiniteLine)]
        self._cursor_sync_guard = False
        # Cursors tool state before the plot went live, so a cycle that switches
        # the tool off can switch it back on afterwards (see _set_plot_live).
        self._cursor_tool_was_on = False
        self.cursor_pens = {
            't1': pg.mkPen('#E91E63', width=2, style=QtCore.Qt.DotLine),  # pink
            't2': pg.mkPen('#212121', width=2, style=QtCore.Qt.DotLine)}  # near-black
        # DAQ Configuration from defaults
        self.daq_channels = CONFIG_DEFAULTS['channels'].copy()
        self.voltage_ranges = fixed_voltage_ranges(self.daq_channels)
        self.daq_srate = CONFIG_DEFAULTS['sample_rate_hz']
        self.daq_dec = CONFIG_DEFAULTS['decimation']
        self.daq_deca = 1
        
        # Display Configuration from defaults
        self.n_display_points = CONFIG_DEFAULTS['display_points']
        self.plot_refresh_rate = CONFIG_DEFAULTS['plot_refresh_rate_ms']
        self.separate_plots = CONFIG_DEFAULTS['separate_plots']
        self.dual_axis_mode = True  # Enable dual axis plotting (always True now)
        # Channels ticked for plotting (all data is still acquired/saved)
        self.plot_channels = list(CONFIG_DEFAULTS.get('plot_channels', self.daq_channels))

        # Cloud upload (MQTT) configuration
        self.mqtt_enabled = bool(CONFIG_DEFAULTS.get('mqtt_enabled', False))
        self.machine_id = str(CONFIG_DEFAULTS.get('machine_id', '160t'))
        self.mqtt_publisher = None  # created lazily when monitoring starts
        self._mqtt_selftest_thread = None  # one-time cloud connectivity self-test
        self.session_id = None      # timestamp id shared by all cycles of a session
        # Global cycle_id the session started from: session_cycle is derived by
        # subtracting it, so the relative counter can never drift (see _session_cycle).
        self.session_cycle_base = 0
        self.session_start_epoch = None  # wall clock (epoch s) at monitoring start
        self._session_streamed = False   # True once this session's data went to the cloud
        # Cycles shorter than this are treated as trigger noise and discarded
        self.min_cycle_s = float(CONFIG_DEFAULTS.get('min_cycle_s', 1.0))
        # Debounce after a cycle ends before a new HIGH can start the next one
        # (JSON only; falls back to 2.0 - the old hard-coded value - if absent)
        self.inter_cycle_gap_s = float(CONFIG_DEFAULTS.get('inter_cycle_gap_s', 2.0))
        # Runner geometry for the apparent-viscosity readout (JSON only, see
        # rheology.py): sensor separation and runner radius, in mm.
        _visc = CONFIG_DEFAULTS.get('viscosity', {})
        self.visc_L_mm = float(_visc.get('L_mm', 100.0))
        self.visc_Rc_mm = float(_visc.get('Rc_mm', 1.5))
        
        #LABELS:
        self.x_Label = 'Time [s]'

        # Run configure function when configurationButton is clicked:
        self.configurationButton.clicked.connect(self.configure)
        # Run start_monitoring function when startButton is clicked
        self.startButton.clicked.connect(self.start_monitoring)
        # Run find_device function when findDeviceButton is clicked:
        self.findDeviceButton.clicked.connect(self.find_device)
        # Run stopReading and stop_message functions when stopButton is clicked:
        self.stopButton.clicked.connect(self.stopReading)
        self.stopButton.clicked.connect(self.stop_message)
        # Run rem_devs function when removeDeviceButton is clicked:
        self.removeDeviceButton.clicked.connect(self.rem_devs)
        # Run next_Session function when nextButton is clicked:
        self.nextButton.clicked.connect(self.next_Session)
        # Run save_Session function when saveSessionButton is clicked:
        self.saveSessionButton.clicked.connect(self.save_Session)
        self.sendSessionButton.clicked.connect(self.send_Session_to_cloud)
        # Plot-tool buttons (Home resets the view; the others are exclusive toggles):
        self.homeButton.clicked.connect(lambda: self.route_plot_tool('home'))
        self.zoomButton.toggled.connect(lambda on: self.route_plot_tool('zoom', on))
        self.panButton.toggled.connect(lambda on: self.route_plot_tool('pan', on))
        self.cursorButton.toggled.connect(lambda on: self.route_plot_tool('cursor', on))
        self.hideGhostsButton.toggled.connect(lambda on: self.route_plot_tool('ghosts', on))

        # Live matplotlib-style x/y coordinate readout (bottom-right of each
        # plot, light grey). One per tab; each scene persists across plot
        # rebuilds, so the mouse-move signals are connected once here.
        self._coord_readouts = {'mold': [], 'machine': []}
        self.GraphArea.canvas.scene().sigMouseMoved.connect(
            lambda p: self._update_coord_readouts('mold', p))
        self.GraphAreaMachine.canvas.scene().sigMouseMoved.connect(
            lambda p: self._update_coord_readouts('machine', p))

        # Initialize plot data structures
        for n in range(self.nplots):
            self.plotDataItem_lst.append([])
        
        #Initial message:
        self.messagesBox.appendHtml('<p style="color:blue;">DAQ Monitoring System v2.0</p><p></p>')
        self.initialize_desktop_state()
        self.initialize_metadata()
        if not self.preview_mode:
            self.install_desktop_layout()


    def raw_to_volts(self, raw):
        """Convert a raw ADC count to the 0-10 V scale."""
        return raw * self.voltage_scale / self.adc_resolution

    def convert_voltage_to_units(self, voltage_values):
        """Convert raw ADC counts to physical units per channel type.

        Triggers become digital 0/1 by threshold; machine signals use the editable
        initial + resolution (mV per unit) conversion; T/P use their editable scales.
        """
        converted_values = []
        pressure_seen = 0  # counts mould-pressure channels for s0/s1 alternation
        for i, raw in enumerate(voltage_values):
            if i >= len(self.channel_types):
                converted_values.append(raw)
                continue
            ch_type = self.channel_types[i]
            cat = sensor_category(ch_type)
            volts = self.raw_to_volts(raw)

            if cat == 'temp':
                deg = self.conversion.get('T_futaba', {}).get('deg_per_volt', 100.0)
                converted_values.append(volts * deg)
            elif cat == 'moldP':
                k = self.conversion.get('P_kistler', {})
                s0 = k.get('s0', 2.500); s1 = k.get('s1', 2.508); qmax = k.get('Qmax', 20000.0)
                s = s0 if (pressure_seen % 2 == 0) else s1
                pressure_seen += 1
                s = s if s else 1.0
                converted_values.append(raw * (qmax / s) / self.adc_resolution)
            elif cat == 'machine':
                c = self.conversion.get(ch_type, {})
                initial = c.get('initial', 0.0)
                res = c.get('resolution_mV', 10.0)
                mv = volts * 1000.0
                converted_values.append(initial + (mv / res if res else 0.0))
            else:
                converted_values.append(raw)
        return converted_values

    def trigger_input(self):
        """Name of the digital input carrying the main relay contact, or None."""
        for name in DIGITAL_INPUTS:
            if normalize_trigger_type(self.digital_map.get(name)) == TRIGGER_TYPE:
                return name
        return None

    def trigger_bit_index(self):
        """Bit position of the trigger inside the digital scan word.

        The digital inputs are reported in the HIGH byte, so Dn = bit 8+n
        (D4 = bit 12, confirmed on the bench 2026-07-08). None when no trigger
        mode is selected or no input is mapped."""
        if self.trigger_mode == 'None':
            return None
        name = self.trigger_input()
        return digital_bit(name) if name else None

    def read_trigger_high(self, ypoints_raw, digital_word, prev_high):
        """Return True/False (cycle active / idle) for the trigger, or None if there is none.

        The single seam the cycle logic reads the trigger through: one bit of the
        digital scan word, the main relay's contact. Which input it is comes from
        digital_map, so moving the wire to another D pin is a config change, not a
        code change. Returns a reading whenever a trigger is mapped (so arrows
        still work in continuous mode); cycle gating is controlled by cycle_mode.

        The value returned is the *active* sense, not the raw pin: an active-LOW
        source (mould position, see INVERTED_TRIGGER_MODES) is flipped here, so
        everything downstream - cycle start/end, arrows, the pre-start check -
        keeps reading True as "cycle running" whichever source is driving.
        """
        bit = self.trigger_bit_index()
        if bit is None or digital_word is None:
            return None
        high = bool((int(digital_word) >> bit) & 1)
        return high != trigger_is_inverted(self.trigger_mode)

    def record_trigger_transition(self, x_time, is_high):
        """Record a LOW/HIGH edge for the arrow display (works for any trigger source)."""
        new_state = 'HIGH' if is_high else 'LOW'
        if self.i_channel_state is not None and new_state != self.i_channel_state:
            self.i_channel_transitions.append((x_time, 'UP' if is_high else 'DOWN'))
        self.i_channel_state = new_state

    def check_trigger_initial_state(self):
        """Return False if the trigger is already active before starting.

        Monitoring should begin between cycles. Reads through read_trigger_high(),
        so "active" already accounts for an inverted source. Returns True when it
        is safe to proceed, including when no trigger is configured.
        """
        if self.trigger_mode == 'None':
            return True
        try:
            if hasattr(self, 'DaqThread') and self.DaqThread.IsConnected:
                values = self.DaqThread.daq_device.collect_data(self.DaqThread.binary_method)
                if values is not None:
                    n_analog = len(self.daq_channels)
                    digital_word = None
                    analog = list(values)
                    if len(values) > n_analog:
                        digital_word = values[n_analog]
                        analog = list(values[:n_analog])
                    if self.read_trigger_high(analog, digital_word, False):
                        return False  # HIGH -> should not start
        except Exception as e:
            logger.exception("Error checking trigger initial state: %s", e)
        return True

    # Backwards-compatible alias
    def check_i_channel_initial_state(self):
        return self.check_trigger_initial_state()

    def closeEvent(self, event):
        '''
        Action for when exitButton is clicked.
        1 - A message appears asking if user really wishes to leave.
        2 - On Close: stop the threads AND the DAQ device, then quit.
        3 - On Cancel: keep running (monitoring is not interrupted).
        '''
        if getattr(self, "_history_jobs", None):
            for job in self._history_jobs:
                job.requestInterruption()
            self._close_after_history = True
            self.messagesBox.appendPlainText("Cancelling the server request before closing…")
            event.ignore()
            return
        self._close_after_history = False
        if not self.historyPanel.flush_edits() or not self.partEditor.can_leave():
            event.ignore()
            return
        reply = QtWidgets.QMessageBox.question(self, "Message", 'Are you sure you want to leave? Any unsaved work will be lost.', 
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Close)

        if reply == QtWidgets.QMessageBox.Close:
            logger.info("Application closing (user confirmed)")
            self._shutdown_daq()
            QtWidgets.QApplication.processEvents()  # deliver final capture signals
            if self.mqtt_publisher is not None:
                self.mqtt_publisher.stop()
            QtWidgets.QApplication.instance().quit()
        else:
            try:
                event.ignore()
            except:
                pass

    def _shutdown_daq(self):
        '''
        Stop the monitoring threads, then send stop to the DAQ device and close
        the port. Without this the device is left scanning after the process
        exits, and the next program to configure it races a still-streaming
        device (config commands get dropped -> half-applied scan list).
        '''
        gt = getattr(self, 'graphThread', None)
        if gt is not None:
            try:
                gt.stop_reason = "application_close"
                gt.stop_Thread()
                gt.wait(1000)
            except Exception:
                pass
        thread = getattr(self, 'DaqThread', None)
        if thread is None:
            return
        try:
            thread.stop_Thread()
            thread.wait(2000)  # let the read loop release the port first
            thread.disconnectDaq()
        except Exception as e:
            logger.exception("Error shutting down DAQ: %s", e)

    def save_Session(self):
        """Manual waveform CSV, cycle-summary CSV and full metadata JSON export."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Session Data as:', '', 'CSV (*.csv)')
        if path:
            try:
                self.save_session_export(path)
                self.messagesBox.appendPlainText(
                    'Saved waveform CSV, cycle summary (.cycles.csv), and full metadata (.metadata.json).')
            except (OSError, ValueError, KeyError) as exc:
                logger.exception('Could not save session')
                QtWidgets.QMessageBox.warning(self, 'Save session', str(exc))

    def stopReading(self):
        '''
        To emit the signal to stop reading and enable/disable the buttons accordingly.
        '''
        logger.info("Monitoring stopped (session %s)", self.session_id)
        self._stopping = True
        self.stopSig.emit()
        self.is_monitoring = False  # New setup waits for the final-data signal
        self._set_plot_live(False)  # plot no longer follows data: tools usable
        # Final-data signal enables Save/Next after the worker finishes.

        #Enable/Disable buttons:
        self.stopButton.setEnabled(False)
        self.startButton.setEnabled(False)  # Explicitly disable Start button
        self.removeDeviceButton.setEnabled(False)
        self.nextButton.setEnabled(False)
        self.saveSessionButton.setEnabled(False)
        # Offer the manual cloud send only if this session did not already stream live
        self.sendSessionButton.setEnabled(False)
        self.refresh_desktop_controls()

    def stop_message(self):
        '''
        Write the stop message in the message box.
        '''
        self.messagesBox.appendHtml('<p>The session was stopped.</p>')

    def end_message(self):
        '''
        Write the end message in the message box.
        '''
        self.messagesBox.appendHtml('<p>Finished session.</p>')

    def rem_devs(self):
        """Release the worker before its serial handle or signal connections."""
        thread = getattr(self, "DaqThread", None)
        if thread is not None:
            thread.stop_Thread()
            if not thread.wait(2000):
                self.messagesBox.appendPlainText("DAQ is still stopping. Try disconnecting again.")
                return False
            thread.disconnectDaq()
            for signal, slot in ((thread.ConnectSig, self.HandleDaqConnectSig),
                                 (thread.readErrorSig, self.HandleReadErrorSig),
                                 (self.startSig, thread.startSignalRec),
                                 (self.stopSig, thread.stopSignalRec),
                                 (self.disconnectSig, thread.disconnectDaq),
                                 (self.stopThreadSig, thread.stop_Thread)):
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
        self.daq_connected = False
        self._connecting = False
        self.configurationButton.setEnabled(True)
        self.removeDeviceButton.setEnabled(False)
        self.nextButton.setEnabled(False)
        self.startButton.setEnabled(False)
        self.messagesBox.appendPlainText("DAQ disconnected.")
        self.refresh_desktop_controls()
        return True

    def next_Session(self):
        if self.desktop_busy() or not self.historyPanel.flush_edits() or not self.partEditor.can_leave():
            return
        self.presentation.navigate("monitor")
        self.presentation.side_toggle.setChecked(False)
        self.runSetup.material.setFocus()

    def start_monitoring(self):
        '''
        Start monitoring:
        - Check I channel initial state
        - Setup subplots;
        - Emit start signal.
        '''
        if self.desktop_busy() or not self.historyPanel.flush_edits() or not self.partEditor.can_leave():
            return
        if self.daq_connected:
            if not self.prepare_run_setup():
                return
            self.apply_staged_configuration()
            # Start also handles later sessions. Reuse the open serial handle,
            # applying the saved DAQ settings before reading the trigger.
            if not self.DaqThread.set_configuration(self.active_configuration()):
                self.messagesBox.appendPlainText("DAQ is still stopping. Try Start again.")
                return
            if not self.DaqThread.rearmDaq():
                self.HandleDaqConnectSig(False)
                return
            # Check trigger initial state
            if not self.check_trigger_initial_state():
                QtWidgets.QMessageBox.warning(self, "Trigger Warning",
                    f"The selected trigger ({self.trigger_mode}) is already active.\n\n"
                    "Monitoring must start between cycles, with the trigger inactive.\n\n"
                    "Please wait for the current cycle to finish and try again.")
                self.messagesBox.appendHtml('<p style="color:red;">Cannot start: trigger already active. Must be inactive to start.</p>')
                return
            
            self.reset_Data_n_Plot_Vars()
            self.begin_metadata_session()
            logger.info("Monitoring session %s starting (trigger=%s)", self.session_id, self.trigger_mode)
            self._ensure_mqtt_publisher()

            self.startButton.setEnabled(False)
            self.findDeviceButton.setEnabled(False)
            self.removeDeviceButton.setEnabled(False)
            self.saveSessionButton.setEnabled(False)
            self.sendSessionButton.setEnabled(False)

            self.SubplotSetup()
            self.graphThread = GraphThread(self.dataQueue, self.sensors[:self.nplots], self.time_lim,
                                           self.n_display_points, self.plot_refresh_rate, self)
            # Global counter this session starts from; session_cycle counts up
            # from 1 relative to it (see _session_cycle).
            self.session_cycle_base = self.graphThread.cycle_base
            self.graphThread.graphUpdateSig.connect(self.ploter)
            self.graphThread.updateYAxisSig.connect(self.updateYAxisRanges)
            self.graphThread.updateArrowsSig.connect(self.updateArrows)
            self.graphThread.updateXAxisRangeSig.connect(self.updateXAxisRange)  # NEW CONNECTION
            self.graphThread.monitTimeEndSig.connect(self.stopReading)
            self.graphThread.monitTimeEndSig.connect(self.end_message)
            self.graphThread.graphEndSig.connect(self.receiveXYData)
            self.DaqThread.readQueueSig.connect(self.graphThread.readQueue)
            self.stopSig.connect(self.graphThread.stop_Thread)
            
            # Connect cycle mode signals
            if self.cycle_mode:
                self.graphThread.cycleWaitingSig.connect(self.onCycleWaiting)
                self.graphThread.cycleStartedSig.connect(self.onCycleStarted)
                self.graphThread.cycleEndedSig.connect(self.onCycleEnded)
                self.graphThread.cycleDiscardedSig.connect(self.onCycleDiscarded)

            self.stopButton.setEnabled(True)
            self.graphThread.start()
            self.start_acquisition_clock()
            self.startSig.emit()
            self.is_monitoring = True  # Add this line
            self.nextButton.setEnabled(False)
            self.presentation.navigate("monitor")
            self.refresh_desktop_controls()
            # Continuous mode follows data all session; cycle mode starts still (waiting)
            self._set_plot_live(not self.cycle_mode)

            #Monitoring message:
            self.messagesBox.appendHtml('<p>Monitoring with unit conversion...</p>')
        else:
            self.startButton.setEnabled(False)
            self.configurationButton.setEnabled(True)
            self.messagesBox.appendHtml('<p style="color:red;">DAQ not connected!</p>')

    # -------------------------------------------------------------- cycle hooks
    def onCycleWaiting(self):
        """Handle waiting for first cycle signal."""
        nxt = getattr(self.graphThread, 'cycle_base', 0) + 1
        self.messagesBox.appendHtml(
            f'<p style="color:orange;">Waiting for trigger to go HIGH to start '
            f'cycle {self._cycle_label(nxt)}...</p>')
        self._set_cycle_readout(nxt)

    def onCycleStarted(self, cycle_num, snapshot, start_s):
        """Handle cycle started signal."""
        self.current_cycle = cycle_num
        self.capture_started(cycle_num, snapshot, start_s)
        # Plot follows the new cycle: lock the tools and restore the live view
        self._set_plot_live(True)
        self.messagesBox.appendHtml(
            f'<p style="color:green;">Cycle {self._cycle_label(cycle_num)} started</p>')
        self._set_cycle_readout(cycle_num)

    def onCycleEnded(self, cycle_num, xdata, ydata, cycle_start_s, details):
        """Handle cycle ended: persist the counter, store data, draw the ghost."""
        self.messagesBox.appendHtml(
            f'<p>Cycle {self._cycle_label(cycle_num)} ended '
            f'(duration: {xdata[-1]:.2f}s)</p>' if xdata
            else f'<p>Cycle {self._cycle_label(cycle_num)} ended</p>')
        save_cycle_id(cycle_num)  # survives restarts / power loss (cycle_id.txt)
        # Keep the cycle (with its start offset) so it can be resent to the cloud later.
        self.completed_cycles_data.append((cycle_num, float(cycle_start_s), xdata, ydata))
        if xdata and xdata[-1] > self.cycle_max_x:
            self.cycle_max_x = xdata[-1]
            self._set_all_x_range(0, self.cycle_max_x * 1.05, padding=0)
            self._default_x_range = (0, self.cycle_max_x * 1.05, 0)
        self.createGhostPlots(xdata, ydata, cycle_num)
        # Trigger is LOW until the next cycle: the plot is still, tools usable
        self._set_plot_live(False)
        self.capture_finished(cycle_num, xdata, list(zip(*ydata)), cycle_start_s, details)

    def onCycleDiscarded(self, cycle_num, duration):
        """A trigger blip shorter than min_cycle_s was dropped (number is reused)."""
        self.messagesBox.appendHtml(
            f'<p style="color:orange;">Cycle {self._cycle_label(cycle_num)} discarded '
            f'({duration:.2f}s &lt; {self.min_cycle_s:.2f}s minimum - treated as noise)</p>')
        self._capture_starts.pop(cycle_num, None)
        self.discard_part_draft(cycle_num)
        # Number is reused for the retry, so keep showing it while we wait again.
        self._set_cycle_readout(cycle_num)
        self._set_plot_live(False)


    def receiveXYData(self, xvals, yvals, yvals_raw, cycle_numbers):
        '''Receive DAQ collected data after monitoring stops (converted + raw).'''
        self.xdata = xvals
        self.ydata = yvals
        self.ydata_raw = yvals_raw
        self.cycle_numbers_data = cycle_numbers if cycle_numbers else []
        logger.info("Session %s finished: %d samples collected", self.session_id, len(xvals))
        if not self.cycle_mode and xvals:
            self.capture_finished(0, xvals, yvals, 0.0,
                                  {"status": "interrupted" if self.graphThread.stop_reason in ("device_error", "processing_error") else "complete",
                                   "reason": self.graphThread.stop_reason})
        self.is_monitoring = False
        self._stopping = False
        self.runSetup.set_locked(False)
        self.startButton.setEnabled(self.daq_connected)
        self.removeDeviceButton.setEnabled(self.daq_connected)
        self.nextButton.setEnabled(self.daq_connected)
        self.saveSessionButton.setEnabled(bool(xvals))
        self.sendSessionButton.setEnabled(bool(xvals) and not self._session_streamed)
        # A new GraphThread is created for Next; release the old worker's inbound
        # connections so finished sessions are not retained by repeated connects.
        daq_thread = getattr(self, 'DaqThread', None)
        if daq_thread is not None:
            try:
                daq_thread.readQueueSig.disconnect(self.graphThread.readQueue)
            except (TypeError, RuntimeError):
                pass
        try:
            self.stopSig.disconnect(self.graphThread.stop_Thread)
        except (TypeError, RuntimeError):
            pass

        self.refresh_desktop_controls()

    # ------------------------------------------------------------ cloud upload
    def _ensure_mqtt_publisher(self, force=False, machine_id=None):
        """Start the background MQTT publisher (once) when cloud upload is on.

        ``force=True`` starts it even when cloud upload is disabled - used by the
        manual "send session" button so it works regardless of the config toggle.
        """
        if not self.mqtt_enabled and not force:
            return
        machine_id = machine_id or self.machine_id
        if self.mqtt_publisher is not None:
            if self.mqtt_publisher.machine_id == machine_id:
                return
            self.mqtt_publisher.stop()
            self.mqtt_publisher = None
        try:
            from mqtt_publisher import MqttPublisher
            self.mqtt_publisher = MqttPublisher(machine_id=machine_id)
            self.mqtt_publisher.auto_drain = bool(self.mqtt_enabled)
            self.mqtt_publisher.start()
            s = self.mqtt_publisher.settings
            self.messagesBox.appendHtml(
                '<p style="color:green;">Cloud upload enabled - MQTT broker %s:%d, topic %s</p>'
                % (s['broker'], s['port'], self.mqtt_publisher.topic))
        except Exception as e:
            self.mqtt_publisher = None
            self.mqtt_enabled = False
            logger.exception("Cloud upload disabled: %s", e)
            self.messagesBox.appendHtml(
                '<p style="color:red;">Cloud upload disabled: %s</p>' % e)

    def _saved_indices(self):
        """Indices into daq_channels that are written to the CSV / sent to the cloud.

        Trigger channels are excluded: an analog trigger (trigger_machine) is
        acquired only to gate cycles, exactly like the digital inductive trigger,
        and carries no measurement worth storing.
        """
        return [i for i in range(len(self.daq_channels))
                if not (i < len(self.channel_types)
                        and sensor_category(self.channel_types[i]) == 'trigger')]

    def _saved_values(self, values):
        """Pick the saved/published subset out of one full row of channel values."""
        return [values[i] for i in self._saved_indices() if i < len(values)]

    def _channel_field_names(self):
        """Per-channel column/payload keys, e.g. CH2_P_kistler.

        The single source used for BOTH the CSV header and the MQTT payload, so
        the local and cloud schemas stay byte-for-byte identical (no units).
        Order and length match _saved_values(), so the two never drift apart.
        """
        names = []
        for i in self._saved_indices():
            ch = self.daq_channels[i]
            if i < len(self.channel_types):
                names.append(f'CH{ch}_{self.channel_types[i]}')
            else:
                names.append(f'CH{ch}')
        return names

    def _publish_records(self, xdata, rows, cycle_id, base_epoch=None):
        """Publish the frozen capture; base_epoch remains a compatibility argument."""
        if self.mqtt_publisher is not None and xdata:
            self.publish_capture(xdata, rows, cycle_id)

    def send_Session_to_cloud(self):
        """Manually push the whole finished session to the cloud in one shot.

        Works even when cloud upload is disabled (spins the publisher up on
        demand). Each cycle is replayed through the same _publish_records path as
        live streaming, so the cloud records are identical. The button is disabled
        after a live stream or a send (self._session_streamed), so this can never
        repeat a manual enqueue. MQTT duplicate delivery is still possible.
        """
        if not self.historyPanel.flush_edits() or not self.partEditor.can_leave():
            return
        if self._session_streamed:
            self.messagesBox.appendHtml(
                '<p style="color:orange;">Already queued. Database storage is unconfirmed.</p>')
            self.sendSessionButton.setEnabled(False)
            return

        self._ensure_mqtt_publisher(force=True, machine_id=self._session_machine_id)
        if self.mqtt_publisher is None:
            self.messagesBox.appendHtml(
                '<p style="color:red;">Cloud send failed: MQTT publisher unavailable '
                '(check .env / broker settings).</p>')
            return

        base = self.session_start_epoch or datetime.now().timestamp()
        n_batches = 0
        if self._session_cycle_mode:
            for cycle_num, cycle_start_s, xdata, ydata in self.completed_cycles_data:
                if not xdata or not ydata:
                    continue
                self._publish_records(xdata, list(zip(*ydata)), cycle_num, base + cycle_start_s)
                n_batches += 1
        elif self.xdata and self.ydata:
            self._publish_records(self.xdata, self.ydata, 0, base)
            n_batches += 1

        if n_batches:
            self._session_streamed = True          # block any further send of this session
            self.sendSessionButton.setEnabled(False)
            self.messagesBox.appendHtml(
                '<p style="color:green;">Session queued for cloud upload '
                '(%d %s).</p>' % (n_batches, 'cycles' if self._session_cycle_mode else 'batch'))
        else:
            self.messagesBox.appendHtml(
                '<p style="color:orange;">Nothing to send - no finished session data.</p>')
        self.refresh_desktop_controls()

    # ------------------------------------------------------------------- setup


    def find_device(self):
        '''
        What to do when findDeviceButton is clicked:
        - Connect to DAQ device
        '''
        if self.desktop_busy():
            return
        self.startButton.setEnabled(False)
        if not self.rem_devs():
            return

        # Start DAQ connection
        self._connecting = True
        self.refresh_desktop_controls()
        self.messagesBox.appendHtml('<p>Attempting to connect to DAQ device...</p>')
        self.daqThStart()

    def daqThStart(self):
        '''
        Start a parallel thread to handle DAQ communication.
        '''
        self.dataQueue = queue.Queue()

        # The trigger always lives on a digital input, so the digital word is
        # always part of the scan.
        cfg = self._configuration_draft or self.active_configuration()
        self.DaqThread = DaqThread(cfg['channels'], fixed_voltage_ranges(cfg['channels']),
                                   cfg['decimation'], self.daq_deca, cfg['sample_rate_hz'],
                                   self.dataQueue, [f'CH{ch}' for ch in cfg['channels']],
                                   read_digital=True)
        self.DaqThread.ConnectSig.connect(self.HandleDaqConnectSig)
        self.DaqThread.readErrorSig.connect(self.HandleReadErrorSig)

        self.startSig.connect(self.DaqThread.startSignalRec)
        self.stopSig.connect(self.DaqThread.stopSignalRec)
        self.disconnectSig.connect(self.DaqThread.disconnectDaq)
        self.stopThreadSig.connect(self.DaqThread.stop_Thread)

        self.DaqThread.start()

    def HandleReadErrorSig(self):
        '''
        Handle DAQ read errors
        '''
        if hasattr(self, "graphThread"):
            self.graphThread.stop_reason = "device_error"
        self.stopReading()
        self.stopButton.setEnabled(False)
        self.nextButton.setEnabled(False)
        self.saveSessionButton.setEnabled(False)
        self.sendSessionButton.setEnabled(False)
        self.removeDeviceButton.setEnabled(False)
        self.stop_message()
        try:
            self.rem_devs()
        except:
            pass
        self.findDeviceButton.setEnabled(True)

        QtWidgets.QMessageBox.information(self,"Message", 'Error! Something went wrong while trying to receive and read data from the DAQ device. Please check the DAQ connection and configuration.', 
        QtWidgets.QMessageBox.Ok)

    def HandleDaqConnectSig(self, ConnectedT_F):
        '''
        Handle DAQ connection status
        '''
        self._connecting = False
        if ConnectedT_F == True:
            self.messagesBox.appendHtml('<p style="color:green;">DAQ device: connected.</p>')
            # Only enable Start button if NOT currently monitoring
            if not self.is_monitoring:
                self.startButton.setEnabled(True)
            self.removeDeviceButton.setEnabled(True)
            self.configurationButton.setEnabled(False)
        else:
            reason = getattr(getattr(self, 'DaqThread', None), 'connection_error', '')
            self.messagesBox.appendPlainText('DAQ connection failed: ' + (reason or 'Check the USB connection and try again.'))
            self.startButton.setEnabled(False)
            self.nextButton.setEnabled(False)
            self.removeDeviceButton.setEnabled(False)
            self.findDeviceButton.setEnabled(True)
            self.configurationButton.setEnabled(True)
        self.daq_connected = ConnectedT_F
        self.refresh_desktop_controls()

    def configure(self):
        self.presentation.navigate("setup")

    def cnfg_Sig_Received(self, cfg):
        '''
        Store DAQ configuration values from the config window (dict payload).
        '''
        cfg = dict(cfg, voltage_ranges=fixed_voltage_ranges(cfg['channels']))
        self.time_lim = cfg['monitoring_time_s']
        self.daq_channels = cfg['channels']
        self.voltage_ranges = cfg['voltage_ranges']
        self.channel_types = cfg['channel_types']
        self.daq_srate = cfg['sample_rate_hz']
        self.daq_dec = cfg['decimation']
        self.n_display_points = cfg['display_points']
        self.plot_refresh_rate = cfg['plot_refresh_rate_ms']
        self.separate_plots = cfg['separate_plots']
        self.machine_layout = cfg.get('machine_layout', 'shared')
        self.plot_channels = list(cfg.get('plot_channels', cfg['channels']))
        self.mqtt_enabled = bool(cfg.get('mqtt_enabled', False))
        if not self.mqtt_enabled and self.mqtt_publisher is not None:
            self.mqtt_publisher.stop(flush=False)
            self.mqtt_publisher = None
        new_machine_id = str(cfg.get('machine_id', self.machine_id)).strip() or self.machine_id
        if new_machine_id != self.machine_id:
            self.machine_id = new_machine_id
            if self.mqtt_publisher is not None:  # recreated with the new id on next start
                self.mqtt_publisher.stop()
                self.mqtt_publisher = None
        self.min_cycle_s = float(cfg.get('min_cycle_s', self.min_cycle_s))
        self.inter_cycle_gap_s = float(cfg.get('inter_cycle_gap_s', self.inter_cycle_gap_s))
        # Not offered in the config window: the geometry only changes when the
        # mould does, so it is edited in the JSON. Read through cfg anyway so
        # both configuration paths behave the same.
        _visc = cfg.get('viscosity', {})
        self.visc_L_mm = float(_visc.get('L_mm', self.visc_L_mm))
        self.visc_Rc_mm = float(_visc.get('Rc_mm', self.visc_Rc_mm))
        self.trigger_mode = normalize_trigger_mode(cfg.get('trigger_mode', 'None'))
        self.digital_map = dict(cfg.get('digital_map', self.digital_map))
        self.conversion = {k: dict(v) for k, v in cfg.get('conversion', self.conversion).items()}
        self.cycle_mode = (self.trigger_mode != 'None')
        self.nplots = len(self.daq_channels)
        self.sensors = [f'CH{ch}' for ch in self.daq_channels]

        # Reset plot data structures for new number of channels
        self.plotDataItem_lst = []
        self.ydata_plts = []
        for n in range(self.nplots):
            self.plotDataItem_lst.append([])
            self.ydata_plts.append([])

        logger.info("Configuration applied: channels=%s, types=%s, srate=%d (divisor), dec=%d, "
                    "trigger=%s, machine_id=%s, mqtt=%s",
                    self.daq_channels, self.channel_types, self.daq_srate, self.daq_dec,
                    self.trigger_mode, self.machine_id, self.mqtt_enabled)
        # Run setup belongs to Start/Next. Applying DAQ configuration must not
        # discard settings the operator has typed while stopped.
        self.refresh_run_snapshot()
        self.config_message(cfg)
        self.findDeviceButton.setEnabled(True)

        # Cloud upload on -> run a one-time connectivity self-test right now.
        self._run_mqtt_selftest()

    # ------------------------------------------------------ cloud self-test
    def _run_mqtt_selftest(self):
        '''
        Fire the one-time cloud (MQTT) connectivity self-test, but only when
        cloud upload is enabled. Runs in a background thread and streams its
        results into the message box (same place as the DAQ connection status).
        '''
        if not self.mqtt_enabled:
            return
        if self._mqtt_selftest_thread is not None and self._mqtt_selftest_thread.isRunning():
            return  # a previous self-test is still running; don't overlap
        self.messagesBox.appendHtml('<p style="color:blue;">Running cloud (MQTT) self-test...</p>')
        self._mqtt_selftest_thread = MqttSelfTestThread(self.machine_id, self)
        self._mqtt_selftest_thread.progressSig.connect(self._on_mqtt_selftest_progress)
        self._mqtt_selftest_thread.doneSig.connect(self._on_mqtt_selftest_done)
        self._mqtt_selftest_thread.start()

    def _on_mqtt_selftest_progress(self, level, message):
        '''One step of the cloud self-test: colour it like the DAQ status lines.'''
        colors = {'ok': 'green', 'fail': 'red', 'warn': 'orange', 'info': 'blue'}
        color = colors.get(level, 'black')
        self.messagesBox.appendHtml(
            '<p style="color:%s;">[Cloud check] %s</p>' % (color, message))

    def _on_mqtt_selftest_done(self, connected_ok, published_ok):
        '''Final verdict of the cloud self-test.'''
        if connected_ok and published_ok:
            self.messagesBox.appendHtml(
                '<p style="color:green;">[Cloud check] Result: OK - cloud upload ready.</p>')
        elif connected_ok:
            self.messagesBox.appendHtml(
                '<p style="color:orange;">[Cloud check] Result: broker reachable but the '
                'test publish was unconfirmed. Data upload may still work.</p>')
        else:
            self.messagesBox.appendHtml(
                '<p style="color:red;">[Cloud check] Result: NOK - cloud upload not available. '
                'During monitoring, cycles will be spooled to disk and retried automatically.</p>')

    def config_message(self, cfg):
        '''
        Display configuration summary in the message box.
        '''
        channel_types = cfg['channel_types']
        temp_count = sum(1 for t in channel_types if sensor_category(t) == 'temp')
        pressure_count = sum(1 for t in channel_types if sensor_category(t) == 'moldP')
        machine_count = sum(1 for t in channel_types if sensor_category(t) == 'machine')

        self.messagesBox.appendHtml('<p>Configuration:</p>')
        self.messagesBox.appendHtml('<p>Monitoring time: %ds</p>' % cfg['monitoring_time_s'])
        self.messagesBox.appendHtml('<p>Channels: %s</p>' % cfg['channels'])
        self.messagesBox.appendHtml('<p>Channel types: %s</p>' % channel_types)
        self.messagesBox.appendHtml('<p>Voltage ranges: %s</p>' % cfg['voltage_ranges'])
        self.messagesBox.appendHtml('<p>Sampling divisor (srate): %d</p>' % cfg['sample_rate_hz'])
        self.messagesBox.appendHtml('<p>Decimation: %d</p>' % cfg['decimation'])
        self.messagesBox.appendHtml('<p>Display points: %d</p>' % cfg['display_points'])
        self.messagesBox.appendHtml('<p>Plot refresh rate: %.1f ms</p>' % cfg['plot_refresh_rate_ms'])

        mold_mode = "Separate plots" if cfg['separate_plots'] else f"Dual-axis ({temp_count} Temp, {pressure_count} Pressure)"
        self.messagesBox.appendHtml('<p>Mold layout: %s</p>' % mold_mode)
        if machine_count > 0:
            mach_mode = "shared 3-axis" if cfg.get('machine_layout', 'shared') == 'shared' else "one plot per signal"
            self.messagesBox.appendHtml('<p>Machine signals: %d (%s)</p>' % (machine_count, mach_mode))

        plot_sel = cfg.get('plot_channels', cfg['channels'])
        if len(plot_sel) < len(cfg['channels']):
            self.messagesBox.appendHtml(
                '<p>Plotted channels: %s (others acquired and saved, but not drawn)</p>' % plot_sel)
        if cfg.get('mqtt_enabled'):
            self.messagesBox.appendHtml('<p style="color:green;">Cloud upload (MQTT): enabled (machine_id: %s)</p>'
                                        % cfg.get('machine_id', self.machine_id))

        # Trigger summary
        mode = normalize_trigger_mode(cfg.get('trigger_mode', 'None'))
        if mode != 'None':
            where = self.trigger_input() or 'no digital input (!)'
            polarity = (' - inverted: the cycle runs while the input is LOW'
                        if trigger_is_inverted(mode) else '')
            self.messagesBox.appendHtml('<p style="color:green;">Trigger: %s cycle control via %s%s</p>'
                                        % (mode, where, polarity))
        else:
            self.messagesBox.appendHtml('<p>Trigger: None (continuous acquisition)</p>')


# Cloud self-test thread: ################################################################
##########################################################################################
class MqttSelfTestThread(QtCore.QThread):
    '''
    Runs the one-time cloud (MQTT) connectivity self-test off the GUI thread so
    the interface never freezes. Streams each step back through progressSig and
    the final verdict through doneSig.
    '''
    progressSig = QtCore.pyqtSignal(str, str)  # (level, message)
    doneSig = QtCore.pyqtSignal(bool, bool)     # (connected_ok, published_ok)

    def __init__(self, machine_id, parent=None):
        super(MqttSelfTestThread, self).__init__(parent)
        self.machine_id = machine_id

    def run(self):
        try:
            from mqtt_publisher import check_connectivity
            ok, published = check_connectivity(
                self.machine_id,
                progress=lambda level, msg: self.progressSig.emit(level, msg))
            self.doneSig.emit(ok, published)
        except Exception as e:
            logger.exception("Cloud self-test crashed: %s", e)
            self.progressSig.emit('fail', f"Cloud self-test crashed: {e}")
            self.doneSig.emit(False, False)


# DAQ thread: ############################################################################
##########################################################################################
class DaqNotFoundError(ConnectionError):
    """A Connect attempt found no DATAQ USB device."""


class DaqDevice(daq.Daq_serial):
    """Use the shared driver's configuration with single-attempt discovery.

    The driver's config_daq() otherwise polls discovery forever when absent.
    Raising here also covers unplugging before a rearm, without changing the
    shared package or bypassing its scan configuration/verification.
    """

    def discovery(self):
        if not super().discovery():
            raise DaqNotFoundError('DAQ not found. Connect the DAQ by USB and try again.')
        return True


class DaqThread(QtCore.QThread):
    ConnectSig = QtCore.pyqtSignal(bool)
    readQueueSig = QtCore.pyqtSignal()
    readErrorSig = QtCore.pyqtSignal()

    def __init__(self, channels, voltage_ranges, dec, deca, srate, dataQueue, sensors, read_digital=False, parent = None):
        super(QtCore.QThread, self).__init__()

        self.dataQueue = dataQueue
        self.channels = channels
        self.voltage_ranges = voltage_ranges
        self.dec = dec
        self.deca = deca
        self.srate = srate
        self.IsConnected = False
        self.connection_error = ''
        self.startsigrec = False
        self.stopsigrec = False
        self.stopThread = False
        self.sensors = sensors
        self.read_digital = read_digital  # append D4/D5 digital word to each scan
        self.daq_device = None
        self.binary_method = 1
        self._idle = threading.Event()
        self._idle.set()

    def set_configuration(self, cfg):
        """Update the scan description only after the previous read loop stops."""
        if not self._idle.wait(2):
            return False
        self.channels = list(cfg['channels'])
        self.voltage_ranges = fixed_voltage_ranges(self.channels)
        self.dec, self.srate = cfg['decimation'], cfg['sample_rate_hz']
        self.sensors = [f'CH{ch}' for ch in self.channels]
        dev = self.daq_device
        if dev is not None:
            dev.channels = list(self.channels)
            dev.dec, dev.deca, dev.srate = self.dec, self.deca, self.srate
            dev.read_digital = self.read_digital
            dev.configs = dev.voltage_range_to_config(self.voltage_ranges)
            if self.read_digital:
                dev.configs.append(dev.DIGITAL_CHANNEL_CONFIG)
            dev.numofchannel = len(dev.configs)
            dev.numofbyteperscan = 2 * dev.numofchannel
        return True

    def ConnectDaq(self):
        '''
        Connect to DAQ device with improved error handling
        '''
        self.connection_error = ''
        try:
            output_mode = 'binary'
            
            # Create DAQ connection
            self.daq_device = DaqDevice(
                channels=self.channels,
                voltage_ranges=self.voltage_ranges,
                dec=self.dec,
                deca=self.deca,
                srate=self.srate,
                output_mode=output_mode,
                read_digital=self.read_digital
            )
            
            # Configure the DAQ
            self.daq_device.config_daq()
            
            # Record connection time and reset counters
            self.connection_time = perf_counter()
            self.last_keepalive = perf_counter()
            self.reconnect_attempts = 0
            
            logger.info("DAQ connected (channels=%s, srate=%s, dec=%s)",
                        self.channels, self.srate, self.dec)
            self.IsConnected = True
            self.ConnectSig.emit(True)
            return True

        except Exception as e:
            self.connection_error = str(e)
            if isinstance(e, DaqNotFoundError):
                logger.info('%s', e)
            else:
                logger.exception("DAQ connection error: %s", e)
            self.disconnectDaq()
            self.ConnectSig.emit(False)
            return False

    def rearmDaq(self):
        '''
        Re-arm the DAQ for another session WITHOUT tearing down the serial
        connection. The first Start reuses the already-open connection; Next
        should behave the same. The old path closed the port (disconnectDaq)
        and immediately reopened it (ConnectDaq), which races the Windows
        serial-handle release and fails with PermissionError "Acceso denegado".

        Stop only paused reading - the port is still open and the device still
        scanning - so config_daq (stop-drain-reconfigure-restart) is all that's
        needed to re-arm, and with the now-idempotent discovery() it reuses the
        open port instead of reopening it. Falls back to a full reconnect only
        if the live connection has genuinely gone away.
        '''
        if not self._idle.wait(2):
            return False
        dev = self.daq_device
        if self.IsConnected and dev is not None and getattr(dev, 'ser', None) is not None \
                and dev.ser.is_open:
            try:
                dev.config_daq()          # stop, reconfigure and restart on the open port
                self.last_keepalive = perf_counter()
                self.reconnect_attempts = 0
                self.IsConnected = True
                logger.info("DAQ re-armed for next session (connection reused)")
                self.ConnectSig.emit(True)
                return True
            except Exception as e:
                logger.warning("DAQ re-arm failed (%s); falling back to full reconnect", e)

        # Live connection gone or re-arm failed: close and reopen, giving
        # Windows time to release the port handle before reopening it.
        self.disconnectDaq()
        sleep(1.0)
        return self.ConnectDaq()

    def run(self):
        while self.stopThread == False:
            # Initial connection
            if self.IsConnected == False:
                self.IsConnected = self.ConnectDaq()
                if not self.IsConnected:
                    self.stopThread = True
                    break
            
            # Wait for start signal
            if self.IsConnected and not self.startsigrec:
                sleep(0.1)
                continue
                
            # Data collection loop
            if self.IsConnected and self.startsigrec:
                try:
                    consecutive_failures = 0
                    max_consecutive_failures = 100
                    
                    while not self.stopsigrec and not self.stopThread:
                        try:
                            y_lst = self.Read_and_Process_DaqData()

                            if y_lst is not None:
                                consecutive_failures = 0
                                
                                msgLst = []
                                for el in y_lst:
                                    msgLst.append(el)
                                
                                x = self.Timer(self.start_time)
                                msgLst.append(x)
                                
                                if not self.stopsigrec:
                                    self.dataQueue.put(msgLst, timeout=0.1)
                                    self.readQueueSig.emit()
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    raise Exception("Multiple consecutive read failures")
                                sleep(0.001)

                        except Exception as e:
                            consecutive_failures += 1
                            if consecutive_failures >= max_consecutive_failures:
                                self.readErrorSig.emit()
                                self.stopThread = True
                                break
                            sleep(0.01)
                            
                except Exception as e:
                    logger.exception("DAQ thread error: %s", e)
                    self.readErrorSig.emit()
                    break
                
            # Session stopped (not app exit): halt the device so it does not
            # keep streaming into a buffer nobody reads until the next start.
            if (self.IsConnected and self.stopsigrec and not self.stopThread
                    and self.daq_device is not None):
                try:
                    self.daq_device.stop_scan()
                except Exception as e:
                    logger.warning("Could not stop DAQ streaming: %s", e)

            self.startsigrec = False
            self.stopsigrec = False
            self._idle.set()

    @QtCore.pyqtSlot()
    def stop_Thread(self):
        self.stopThread = True
        
    @QtCore.pyqtSlot()
    def disconnectDaq(self):
        # Configuration can fail after opening USB, before IsConnected is set.
        # Release that partial connection too, so a later click can retry.
        dev = self.daq_device
        port = getattr(dev, 'ser', None)
        if port is not None and port.is_open:
            try:
                dev.close_serial()
            except Exception as e:
                logger.error("Error closing DAQ: %s", e)
            finally:
                if port.is_open:
                    try:
                        port.close()
                    except Exception as e:
                        logger.error("Error releasing DAQ serial port: %s", e)
        self.IsConnected = False

    @QtCore.pyqtSlot()
    def stopSignalRec(self):
        self._idle.clear()
        self.stopsigrec = True

    @QtCore.pyqtSlot()
    def startSignalRec(self):
        self._idle.clear()
        # MainWindow set the shared wall/elapsed baseline immediately before
        # emitting startSig. Do not introduce a second, later time zero here.
        self.startsigrec = True
        self.stopsigrec = False

    def Timer(self, start):
        current = perf_counter()
        return current - start

    def Read_and_Process_DaqData(self):
        '''
        Read data from DAQ device with better error handling
        '''
        try:
            values = self.daq_device.collect_data(self.binary_method)
            
            if values is not None:
                ydata_lst = []
                for i in range(len(self.channels)):
                    if i < len(values):
                        ydata_lst.append(float(values[i]))
                    else:
                        ydata_lst.append(0.0)

                # When digital reading is enabled, the digital word streams as the
                # last value of the scan; pass it through after the analog channels.
                if self.read_digital:
                    if len(values) > len(self.channels):
                        ydata_lst.append(float(values[len(self.channels)]))
                    else:
                        ydata_lst.append(0.0)

                return ydata_lst
            else:
                return None
                
        except Exception as e:
            logger.warning("DAQ read error: %s", e)
            raise


# DAQ Configuration Window with Table-based Channel Selection
# Enhanced GraphThread class with unit conversion and I channel support
class GraphThread(QtCore.QThread):
    graphEndSig = QtCore.pyqtSignal(list, list, list, list)  # Added cycle_numbers
    monitTimeEndSig = QtCore.pyqtSignal()
    graphUpdateSig = QtCore.pyqtSignal(list, list)
    updateYAxisSig = QtCore.pyqtSignal(list, list)
    updateArrowsSig = QtCore.pyqtSignal(list, float, float)  # transitions, x_min, x_max
    cycleStartedSig = QtCore.pyqtSignal(int, object, float)  # ID, frozen settings, start offset
    cycleEndedSig = QtCore.pyqtSignal(int, list, list, float, object)  # cycle_number, xdata, ydata, cycle start (session-relative s)
    cycleDiscardedSig = QtCore.pyqtSignal(int, float)  # cycle_number, duration_s (too short, dropped as noise)
    cycleWaitingSig = QtCore.pyqtSignal()  # Emitted when waiting for first cycle
    updateXAxisRangeSig = QtCore.pyqtSignal(float, float)  # x_min, x_max for waiting mode

    def __init__(self, dataQueue, sensors, read_period, n_display_points=200, refresh_rate_ms=50, main_window=None, parent=None):
        super(QtCore.QThread, self).__init__()

        self.readQSigRec = False
        self.stop_reason = "operator_stop"
        self.stopThread = False
        self.dataQueue = dataQueue
        self.read_period = read_period
        self.xdata = []
        self.ydata = []
        self.ydata_raw = []
        self.xdata_plts = []
        self.ydata_plts = []
        self.n_disp_data_pts = n_display_points
        self.n_sensors = len(sensors)
        self.sensors = sensors
        self.update_interval = refresh_rate_ms / 1000.0
        self.main_window = main_window
        self.last_cycle_end_time = 0  # Timestamp of last HIGH→LOW transition
        # Emit plot updates only when the display data actually changed, so a
        # still plot (between cycles) is never re-ranged under the user's tools.
        self._plot_dirty = False
        
        # I channel tracking
        self.i_channel_transitions = []  # List of (x_time, 'UP' or 'DOWN')
        
        # Cycle mode tracking
        self.cycle_mode = main_window.cycle_mode if main_window else False
        # Cycle numbering continues across sessions/restarts (cycle_id.txt)
        self.cycle_base = load_cycle_id() if self.cycle_mode else 0
        self.current_cycle = self.cycle_base
        self.cycle_active = False  # True when I is HIGH and we're collecting data
        self.cycle_start_time = 0  # Absolute time when current cycle started
        self.cycle_xdata = []  # X data for current cycle (relative to cycle start)
        self.cycle_ydata = []  # Y data for current cycle
        self.cycle_numbers = []  # Cycle number for each data point (for saving)
        self.waiting_for_first_cycle = True if self.cycle_mode else False
        # Cycles shorter than this are discarded as trigger noise
        self.min_cycle_s = float(main_window.min_cycle_s) if main_window else 1.0
        # Quiet time required after a cycle ends before the next one may start
        self.inter_cycle_gap_s = float(main_window.inter_cycle_gap_s) if main_window else 2.0
        if self.cycle_mode and self.cycle_base:
            logger.info("Resuming with cycle_id=%d (next cycle is %d)",
                        self.cycle_base, self.cycle_base + 1)
        
        # Track historical min/max for Y-axis scaling (exclude I channel from scaling)
        self.y_min_hist = [float('inf')] * self.n_sensors
        self.y_max_hist = [float('-inf')] * self.n_sensors
        self.y_margin_factor = 1.2

        # Clear any existing data in queue
        try:
            while not self.dataQueue.empty():
                self.dataQueue.get_nowait()
        except:
            pass

        for n in range(self.n_sensors):
            self.ydata_plts.append([])

    @QtCore.pyqtSlot()
    def readQueue(self):
        self.readQSigRec = True

    @QtCore.pyqtSlot()
    def stop_Thread(self):
        self.stopThread = True

    def run(self):
        t0 = perf_counter()
        session_started = t0
        waiting_start_time = perf_counter()  # Track when waiting started
        last_heartbeat = perf_counter()  # Periodic "still alive" log line
        
        # In cycle mode, emit waiting signal at start
        if self.cycle_mode:
            self.cycleWaitingSig.emit()
        
        while not self.stopThread:  # Changed to check stopThread directly
            # Check stop condition at start of each iteration
            if self.stopThread:
                break
                
            if not self.dataQueue.empty():
                plot_T_F = False
                t1 = perf_counter()
                timer = t1 - t0

                # Process multiple data points at once
                processed_count = 0
                while processed_count < 20 and not self.stopThread:  # Added stopThread check
                    try:
                        self.serData = self.dataQueue.get_nowait()
                        x_time = self.serData[-1]

                        # Split the scan into analog channels + the digital word:
                        # the last pre-timestamp value is the D0..D6 word, not an
                        # analog channel.
                        raw_all = self.serData[:-1]
                        n_analog = self.n_sensors
                        digital_word = None
                        if len(raw_all) > n_analog:
                            digital_word = raw_all[n_analog]
                        ypoints_raw = list(raw_all[:n_analog])

                        # Determine trigger HIGH/LOW (source-agnostic) and record edges
                        i_is_high = False
                        if self.main_window:
                            trig_high = self.main_window.read_trigger_high(
                                ypoints_raw, digital_word, self.cycle_active)
                            if trig_high is not None:
                                i_is_high = bool(trig_high)
                                self.main_window.record_trigger_transition(x_time, i_is_high)
                                self.i_channel_transitions = self.main_window.i_channel_transitions.copy()

                        # Convert to physical units (analog channels only)
                        if self.main_window:
                            ypoints_converted = self.main_window.convert_voltage_to_units(ypoints_raw)
                        else:
                            ypoints_converted = ypoints_raw
                        
                        # Handle cycle mode
                        if self.cycle_mode:
                            if self.waiting_for_first_cycle:
                                # Check stop condition while waiting
                                if self.stopThread:
                                    break
                                    
                                # Waiting for first LOW->HIGH transition
                                if i_is_high:
                                    # Start first cycle (numbering continues from cycle_id.txt)
                                    self.waiting_for_first_cycle = False
                                    self.cycle_active = True
                                    self.current_cycle = self.cycle_base + 1
                                    self.cycle_start_time = x_time
                                    self.cycle_xdata = []
                                    self.cycle_ydata = []
                                    self.cycleStartedSig.emit(self.current_cycle, deepcopy(self.main_window._run_snapshot), float(x_time))
                                    logger.info("Cycle %d started at t=%.3fs", self.current_cycle, x_time)
                                #else:
                                #    # Update X-axis to show waiting time in seconds
                                #    waiting_elapsed = perf_counter() - waiting_start_time
                                #    self.updateXAxisRangeSig.emit(0, max(10, waiting_elapsed * 1.1))
                                    
                                # Don't save data while waiting
                                processed_count += 1
                                continue
                            
                            if self.cycle_active:
                                if i_is_high:
                                    # Continue collecting data for current cycle
                                    x_relative = x_time - self.cycle_start_time
                                    
                                    # Save to overall data with cycle number
                                    self.xdata.append(x_relative)
                                    self.ydata.append(ypoints_converted)
                                    self.ydata_raw.append(ypoints_raw)
                                    self.cycle_numbers.append(self.current_cycle)
                                    
                                    # Save to current cycle data
                                    self.cycle_xdata.append(x_relative)
                                    self.cycle_ydata.append(ypoints_converted)
                                    
                                    # Update graph data for current cycle
                                    self.update_graph_data_cycle_mode(x_relative, ypoints_converted)
                                else:
                                    # I went LOW - end current cycle
                                    self.cycle_active = False
                                    duration = x_time - self.cycle_start_time
                                    self.last_cycle_end_time = x_time  # Record end time for debounce
                                    if duration < self.min_cycle_s:
                                        # Trigger blip: drop the data and reuse the number
                                        n = len(self.cycle_xdata)
                                        if n:
                                            del self.xdata[-n:]
                                            del self.ydata[-n:]
                                            del self.ydata_raw[-n:]
                                            del self.cycle_numbers[-n:]
                                        self.xdata_plts = []
                                        for i in range(len(self.ydata_plts)):
                                            self.ydata_plts[i] = []
                                        self._plot_dirty = True
                                        logger.warning("Discarded cycle %d: %.3fs < %.2fs minimum "
                                                       "(%d samples, trigger noise?)",
                                                       self.current_cycle, duration, self.min_cycle_s, n)
                                        self.cycleDiscardedSig.emit(self.current_cycle, float(duration))
                                        self.current_cycle -= 1
                                    else:
                                        logger.info("Cycle %d ended at t=%.3fs, duration=%.3fs",
                                                    self.current_cycle, x_time, duration)
                                        # Emit signal with cycle data for creating ghost plot
                                        self.cycleEndedSig.emit(self.current_cycle,
                                                               self.cycle_xdata.copy(),
                                                               [list(y) for y in zip(*self.cycle_ydata)] if self.cycle_ydata else [],
                                                               float(self.cycle_start_time),
                                                               {"end_s": x_time, "status": "complete", "reason": "trigger"})
                            else:
                                # Waiting for next cycle
                                if i_is_high and (x_time - self.last_cycle_end_time) > self.inter_cycle_gap_s:
                                    # Start new cycle
                                    self.cycle_active = True
                                    self.current_cycle += 1
                                    self.cycle_start_time = x_time
                                    self.cycle_xdata = []
                                    self.cycle_ydata = []
                                    # Clear plot data for new cycle
                                    self.xdata_plts = []
                                    for i in range(len(self.ydata_plts)):
                                        self.ydata_plts[i] = []
                                    self.cycleStartedSig.emit(self.current_cycle, deepcopy(self.main_window._run_snapshot), float(x_time))
                                    logger.info("Cycle %d started at t=%.3fs", self.current_cycle, x_time)
                                # Don't save data between cycles
                        else:
                            # Normal mode (non-cycle)
                            self.xdata.append(x_time)
                            self.ydata.append(ypoints_converted)
                            self.ydata_raw.append(ypoints_raw)
                            
                            # Update graph data immediately
                            self.update_graph_data_only(x_time, ypoints_converted)
                        
                        processed_count += 1
                    except queue.Empty:
                        break
                    except Exception:
                        logger.exception("Failed to process DAQ sample")
                        self.stop_reason = "processing_error"
                        self.monitTimeEndSig.emit()
                        self.stopThread = True
                        break

                # Check stop condition after processing
                if self.stopThread:
                    break

                if len(self.xdata) % 200 == 0 and len(self.xdata) > 0:
                    logger.debug("GraphThread processed %d points this batch, total %d",
                                 processed_count, len(self.xdata))
                
                # Only update the actual plot display based on timer
                if timer >= self.update_interval:
                    t0 = perf_counter()
                    plot_T_F = True

                if plot_T_F and self._plot_dirty and len(self.xdata_plts) > 0:
                    self._plot_dirty = False
                    self.graphUpdateSig.emit(self.xdata_plts.copy(), [y.copy() for y in self.ydata_plts])
                    
                    # Update arrows for I channel (only in non-cycle mode)
                    if not self.cycle_mode and self.i_channel_transitions:
                        x_min = self.xdata_plts[0] if self.xdata_plts else 0
                        x_max = self.xdata_plts[-1] if self.xdata_plts else 0
                        self.updateArrowsSig.emit(self.i_channel_transitions, x_min, x_max)
                    
                self.readQSigRec = False

            # Heartbeat so long quiet stretches still leave a trace in the log
            if perf_counter() - last_heartbeat > 900:
                last_heartbeat = perf_counter()
                logger.info("Heartbeat: monitoring active (%d samples stored, cycle %d)",
                            len(self.xdata), self.current_cycle)

            sleep(0.001)

            # Session duration includes waiting time, independently of cycle-relative X.
            if perf_counter() - session_started >= self.read_period:
                self.stop_reason = "duration_limit"
                self.monitTimeEndSig.emit()
                self.stopThread = True
        
        # Preserve an interrupted cycle with its original identity/settings.
        if self.cycle_mode and self.cycle_active and self.cycle_xdata:
            self.cycle_active = False
            self.cycleEndedSig.emit(self.current_cycle, self.cycle_xdata.copy(),
                [list(y) for y in zip(*self.cycle_ydata)], float(self.cycle_start_time),
                {"status": "interrupted", "reason": self.stop_reason, "end_s": None})
        # Clean exit - emit final data
        self.graphEndSig.emit(self.xdata, self.ydata, self.ydata_raw, self.cycle_numbers)

    def update_graph_data_only(self, new_x, new_y):
        '''
        Update internal data arrays without triggering plot update.
        Excludes I channel from Y-axis scaling.
        '''
        self._plot_dirty = True
        # Update X data
        if len(self.xdata_plts) <= self.n_disp_data_pts:
            self.xdata_plts.append(new_x)
        else:
            self.xdata_plts = self.xdata_plts[1:] + [new_x]
    
        # Track Y-axis ranges and update data
        y_range_updated = False
        for i in range(len(self.ydata_plts)):
            if i < len(new_y):
                value = new_y[i]
                
                # Update historical min/max
                if value < self.y_min_hist[i]:
                    self.y_min_hist[i] = value
                    y_range_updated = True
                if value > self.y_max_hist[i]:
                    self.y_max_hist[i] = value
                    y_range_updated = True
                
                # Update plot data
                if len(self.ydata_plts[i]) <= self.n_disp_data_pts:
                    self.ydata_plts[i].append(value)
                else:
                    self.ydata_plts[i] = self.ydata_plts[i][1:] + [value]
    
        # Update Y-axis ranges if new extremes were found
        if y_range_updated:
            y_mins = []
            y_maxs = []
            for i in range(self.n_sensors):
                if self.y_min_hist[i] != float('inf') and self.y_max_hist[i] != float('-inf'):
                    y_range = self.y_max_hist[i] - self.y_min_hist[i]
                    margin = y_range * (self.y_margin_factor - 1) / 2
                    
                    if y_range == 0:
                        margin = abs(self.y_max_hist[i]) * 0.1 if self.y_max_hist[i] != 0 else 1.0
                    
                    y_min_with_margin = self.y_min_hist[i] - margin
                    y_max_with_margin = self.y_max_hist[i] + margin
                else:
                    # Default range based on channel category
                    cat = (sensor_category(self.main_window.channel_types[i])
                           if self.main_window and i < len(self.main_window.channel_types) else None)
                    if cat == 'temp':
                        y_min_with_margin = 0
                        y_max_with_margin = 100
                    elif cat == 'moldP':
                        y_min_with_margin = 0
                        y_max_with_margin = 10
                    elif cat == 'trigger':
                        y_min_with_margin = 0
                        y_max_with_margin = 1
                    else:
                        y_min_with_margin = 0
                        y_max_with_margin = 100
                
                y_mins.append(y_min_with_margin)
                y_maxs.append(y_max_with_margin)
            
            self.updateYAxisSig.emit(y_mins, y_maxs)

    def update_graph_data_cycle_mode(self, new_x, new_y):
        '''
        Update internal data arrays for cycle mode.
        In cycle mode, we don't limit display points - we show the entire cycle.
        '''
        self._plot_dirty = True
        # Update X data (no limit in cycle mode)
        self.xdata_plts.append(new_x)
    
        # Track Y-axis ranges and update data
        y_range_updated = False
        for i in range(len(self.ydata_plts)):
            if i < len(new_y):
                value = new_y[i]
                
                # Update historical min/max
                if value < self.y_min_hist[i]:
                    self.y_min_hist[i] = value
                    y_range_updated = True
                if value > self.y_max_hist[i]:
                    self.y_max_hist[i] = value
                    y_range_updated = True
                
                # Update plot data (no limit in cycle mode)
                self.ydata_plts[i].append(value)
    
        # Update Y-axis ranges if new extremes were found
        if y_range_updated:
            y_mins = []
            y_maxs = []
            for i in range(self.n_sensors):
                if self.y_min_hist[i] != float('inf') and self.y_max_hist[i] != float('-inf'):
                    y_range = self.y_max_hist[i] - self.y_min_hist[i]
                    margin = y_range * (self.y_margin_factor - 1) / 2
                    
                    if y_range == 0:
                        margin = abs(self.y_max_hist[i]) * 0.1 if self.y_max_hist[i] != 0 else 1.0
                    
                    y_min_with_margin = self.y_min_hist[i] - margin
                    y_max_with_margin = self.y_max_hist[i] + margin
                else:
                    cat = (sensor_category(self.main_window.channel_types[i])
                           if self.main_window and i < len(self.main_window.channel_types) else None)
                    if cat == 'temp':
                        y_min_with_margin = 0
                        y_max_with_margin = 100
                    elif cat == 'moldP':
                        y_min_with_margin = 0
                        y_max_with_margin = 10
                    elif cat == 'trigger':
                        y_min_with_margin = 0
                        y_max_with_margin = 1
                    else:
                        y_min_with_margin = 0
                        y_max_with_margin = 100
                
                y_mins.append(y_min_with_margin)
                y_maxs.append(y_max_with_margin)
            
            self.updateYAxisSig.emit(y_mins, y_maxs)


pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

if __name__ == "__main__":
    setup_logging()
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.showMaximized()
    app.exec_()
    logger.info("Application closed.")
