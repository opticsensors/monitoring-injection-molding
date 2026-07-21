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
import csv
import daq_connectivity as daq  # Import DAQ library
from time import sleep
from time import perf_counter
from datetime import datetime
import logging
import queue
import numpy as np
from pathlib import Path

import MainWindow
from app_logging import setup_logging
from config import CONFIG_DEFAULTS
from sensor_types import (sensor_category, sensor_label, sensor_unit,
                          TRIGGER_MODE_TO_TYPE)
from config_window import DaqConfigWindow
from plot_tools import ToolViewBox, PassThroughViewBox

logger = logging.getLogger('main')

# Cycle-counter persistence: cycle numbers keep increasing across sessions,
# restarts and power loss (same idea as the Pi loggers' cycle_id.txt).
CYCLE_ID_FILE = Path(__file__).parent / 'cycle_id.txt'


def load_cycle_id():
    """Last completed cycle number for this machine (0 if none yet)."""
    try:
        return int(CYCLE_ID_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0


def save_cycle_id(cid):
    """Write atomically (tmp + replace) so a power cut cannot truncate the file."""
    try:
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
class MainWindow(QtWidgets.QMainWindow, MainWindow.Ui_MainWindow):
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
        self.machine_colors = {'S_position': '#8E44AD', 'S_speed': '#16A085', 'P_machine': '#E67E22'}

        # Channel type configuration from defaults (full-name codes, see SENSOR_TYPES)
        self.channel_types = list(CONFIG_DEFAULTS['channel_types'])

        # Unit conversion constants + editable conversion parameters
        self.adc_resolution = 2**(16-1)  # 15-bit ADC full-scale count (32768)
        self.voltage_scale = 10          # Volts at full-scale count
        # Deep-ish copy so edits from the config window don't mutate CONFIG_DEFAULTS
        self.conversion = {k: dict(v) for k, v in CONFIG_DEFAULTS.get('conversion', {}).items()}

        # Trigger / cycle configuration
        self.trigger_mode = CONFIG_DEFAULTS.get('trigger_mode', 'None')        # 'None'|'Inductive'|'Machine'
        self.trigger_wiring = CONFIG_DEFAULTS.get('trigger_wiring', 'digital')  # always 'digital' (D4/D5)
        self.digital_map = dict(CONFIG_DEFAULTS.get('digital_map', {'D4': 'Inductive', 'D5': 'Machine_signal'}))
        self.machine_layout = CONFIG_DEFAULTS.get('machine_layout', 'shared')  # 'shared'|'separate'

        # Trigger channel (analog wiring): index of the Inductive/Machine_signal channel.
        # Kept named i_channel_* for continuity with the rest of the pipeline.
        self.i_channel_index = None  # Index of the trigger channel in channel_types (analog wiring)
        self.trigger_channel_index = None  # Alias, kept in sync by _update_i_channel_index
        self.i_channel_state = None  # Current state: 'LOW', 'HIGH', or None
        self.i_channel_transitions = []  # List of (x_time, 'UP' or 'DOWN') tuples
        self.i_channel_digital_values = []  # List of (x_time, 0 or 1) for saving
        # Thresholds as percentage of ADC range (raw integer values)
        self.i_threshold_low_pct = 0.20  # Below 20% = LOW state
        self.i_threshold_high_pct = 0.80  # Above 80% = HIGH state
        self.i_threshold_low = int(self.i_threshold_low_pct * self.adc_resolution)
        self.i_threshold_high = int(self.i_threshold_high_pct * self.adc_resolution)
        self.i_arrow_scatter = None  # ScatterPlotItem for arrows
        self.i_lines_item = None  # PlotDataItem for vertical lines
        
        # Cycle mode configuration (cycle control is on whenever a trigger mode is selected)
        self.cycle_mode = (self.trigger_mode != 'None')  # If True, trigger controls cycle start/end
        self.current_cycle = 0  # Current cycle number (1-based when active)
        self.cycle_max_x = 0  # Maximum X value seen across all cycles
        self.completed_cycles_data = []  # List of (xdata, ydata) for completed cycles
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
        self.cursor_pens = {
            't1': pg.mkPen('#E91E63', width=2, style=QtCore.Qt.DotLine),  # pink
            't2': pg.mkPen('#212121', width=2, style=QtCore.Qt.DotLine)}  # near-black
        ToolViewBox.tool_mode = None
        ToolViewBox.cursor_click_callback = self._on_cursor_click

        # DAQ Configuration from defaults
        self.daq_channels = CONFIG_DEFAULTS['channels'].copy()
        self.voltage_ranges = CONFIG_DEFAULTS['voltage_ranges'].copy()
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
        self.session_start_epoch = None  # wall clock (epoch s) at monitoring start
        # Cycles shorter than this are treated as trigger noise and discarded
        self.min_cycle_s = float(CONFIG_DEFAULTS.get('min_cycle_s', 1.0))
        
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
        # Plot-tool buttons (Home resets the view; the others are exclusive toggles):
        self.homeButton.clicked.connect(self.resetPlotView)
        self.zoomButton.toggled.connect(lambda on: self._on_tool_toggled('zoom', on))
        self.panButton.toggled.connect(lambda on: self._on_tool_toggled('pan', on))
        self.cursorButton.toggled.connect(lambda on: self._on_tool_toggled('cursor', on))

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
        
        # Find I channel index if present in defaults
        self._update_i_channel_index()

        #Initial message:
        self.messagesBox.appendHtml('<p style="color:blue;">DAQ Monitoring System v2.0</p><p></p>')

    def _update_i_channel_index(self):
        """Locate the analog trigger channel (Inductive/Machine_signal), if any.

        Only meaningful with analog trigger wiring; with digital wiring the trigger
        is read from D4/D5 and this stays None.
        """
        self.i_channel_index = None
        if self.trigger_wiring == 'analog':
            for i, ct in enumerate(self.channel_types):
                if sensor_category(ct) == 'trigger':
                    self.i_channel_index = i
                    break
        self.trigger_channel_index = self.i_channel_index

    def get_channel_color(self, channel_index):
        """Colour for a channel based on its sensor category."""
        if channel_index >= len(self.channel_types):
            return '#808080'  # Gray fallback

        channel_type = self.channel_types[channel_index]
        cat = sensor_category(channel_type)

        if cat == 'trigger':
            return '#00FF00'  # Green for trigger arrows
        if cat == 'machine':
            return self.machine_colors.get(channel_type, '#808080')

        # Temperature / mould-pressure: cycle through the palette by position among same category
        type_count = sum(1 for i in range(channel_index)
                         if i < len(self.channel_types)
                         and sensor_category(self.channel_types[i]) == cat)
        if cat == 'temp':
            return self.temp_colors[type_count % len(self.temp_colors)]
        if cat == 'moldP':
            return self.pressure_colors[type_count % len(self.pressure_colors)]
        return '#808080'

    def get_channel_label(self, channel_index):
        """Legend label for a channel, e.g. 'CH2 - P_kistler'."""
        if channel_index >= len(self.daq_channels):
            return f'CH{channel_index}'
        ch_num = self.daq_channels[channel_index]
        if channel_index < len(self.channel_types):
            return f'CH{ch_num} - {sensor_label(self.channel_types[channel_index])}'
        return f'CH{ch_num}'

    def get_y_label(self, channel_index):
        """Y-axis label for a channel, e.g. 'Screw position [mm]'."""
        if channel_index >= len(self.channel_types):
            return 'Value [V]'
        ch_type = self.channel_types[channel_index]
        unit = sensor_unit(ch_type)
        label = sensor_label(ch_type)
        return f'{label} [{unit}]' if unit else label

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
            elif cat == 'trigger':
                # Digital 0/1 by threshold on the raw count
                if raw < self.i_threshold_low:
                    converted_values.append(0)
                elif raw > self.i_threshold_high:
                    converted_values.append(1)
                else:
                    mid_point = (self.i_threshold_low + self.i_threshold_high) / 2
                    converted_values.append(0 if raw < mid_point else 1)
            else:
                converted_values.append(raw)
        return converted_values

    def trigger_bit_index(self):
        """Bit position of the active trigger inside the digital scan word.

        The digital inputs are reported in the HIGH byte, so D4 = bit 12 and
        D5 = bit 13 (confirmed on the bench 2026-07-08)."""
        want = TRIGGER_MODE_TO_TYPE.get(self.trigger_mode)
        if want is None:
            return None
        if self.digital_map.get('D4') == want:
            return 12
        if self.digital_map.get('D5') == want:
            return 13
        return None

    def read_trigger_high(self, ypoints_raw, digital_word, prev_high):
        """Return True/False (HIGH/LOW) for the active trigger, or None if no trigger.

        Abstracts the physical source: an analog channel (thresholded, with
        hysteresis) or a digital input bit (D4/D5). This is the single seam the
        cycle logic uses, so analog->digital is a config change, not a code change.
        Returns a reading whenever a trigger source exists (so arrows still work in
        continuous mode); cycle gating is controlled separately by cycle_mode.
        """
        if self.trigger_wiring == 'analog':
            idx = self.trigger_channel_index
            if idx is None or idx >= len(ypoints_raw):
                return None
            raw = ypoints_raw[idx]
            if raw > self.i_threshold_high:
                return True
            if raw < self.i_threshold_low:
                return False
            return bool(prev_high)  # hysteresis zone -> keep previous state
        else:  # digital wiring
            bit = self.trigger_bit_index()
            if bit is None or digital_word is None:
                return None
            return bool((int(digital_word) >> bit) & 1)

    def record_trigger_transition(self, x_time, is_high):
        """Record a LOW/HIGH edge for the arrow display (works for any trigger source)."""
        new_state = 'HIGH' if is_high else 'LOW'
        if self.i_channel_state is not None and new_state != self.i_channel_state:
            self.i_channel_transitions.append((x_time, 'UP' if is_high else 'DOWN'))
        self.i_channel_state = new_state

    def check_trigger_initial_state(self):
        """Return False if the active trigger is already HIGH before starting.

        Monitoring should begin from a LOW trigger. Returns True when it is safe to
        proceed, including when no trigger is configured.
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
                    if self.trigger_wiring == 'digital' and len(values) > n_analog:
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
        reply = QtWidgets.QMessageBox.question(self, "Message", 'Are you sure you want to leave? Any unsaved work will be lost.', 
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Close)

        if reply == QtWidgets.QMessageBox.Close:
            logger.info("Application closing (user confirmed)")
            if self.mqtt_publisher is not None:
                self.mqtt_publisher.stop()
            self._shutdown_daq()
            app.quit()
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
        '''
        Save session dialog:
        Save a csv file with session data in converted physical units
        (same values as plotted/uploaded; analog trigger channels as 0/1).
        In cycle mode, includes a Cycle column.
        '''
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Session Data as:', os.getenv('HOME'), 'CSV(*.csv)')

        if fname[0] != '':
            with open(fname[0], 'w', newline='') as csv_file:
                writer = csv.writer(csv_file, dialect='excel')
                
                # Write header with channel types. The Cycle column is always
                # present (0 = continuous / no cycle), matching the MQTT payload
                # where cycle_id is always set (0 for a full continuous session).
                header = []
                header.append("Cycle")
                header.append("Time(s)")
                for i, ch in enumerate(self.daq_channels):
                    if i < len(self.channel_types):
                        ct = self.channel_types[i]
                        if sensor_category(ct) == 'trigger':
                            header.append(f"CH{ch}_{ct}[0/1]")
                        else:
                            unit = sensor_unit(ct)
                            header.append(f"CH{ch}_{ct}[{unit}]" if unit else f"CH{ch}_{ct}")
                    else:
                        header.append(f"CH{ch}")
                writer.writerow(header)
                
                # Write data
                for i in range(len(self.xdata)):
                    if i < len(self.ydata):
                        row_data = []
                        if self.cycle_numbers_data and i < len(self.cycle_numbers_data):
                            row_data.append(self.cycle_numbers_data[i])
                        else:
                            row_data.append(0)  # continuous / no cycle -> 0, like MQTT
                        row_data.append(self.xdata[i])
                        row_data.extend(self.ydata[i])
                        writer.writerow(row_data)
                
                logger.info("Session data saved to %s (%d rows)", fname[0], len(self.xdata))
                #Saved session message:
                if self.cycle_mode and self.cycle_numbers_data:
                    self.messagesBox.appendHtml('<p>Session data was saved with cycle numbers (converted physical units).</p>')
                else:
                    self.messagesBox.appendHtml('<p>Session data was saved (converted physical units).</p>')

    def stopReading(self):
        '''
        To emit the signal to stop reading and enable/disable the buttons accordingly.
        '''
        logger.info("Monitoring stopped (session %s)", self.session_id)
        self.stopSig.emit()
        self.is_monitoring = False  # Add this line
        self._set_plot_live(False)  # plot no longer follows data: tools usable
        sleep(0.2)

        #Enable/Disable buttons:
        self.stopButton.setEnabled(False)
        self.startButton.setEnabled(False)  # Explicitly disable Start button
        self.removeDeviceButton.setEnabled(True)
        self.nextButton.setEnabled(True)
        self.saveSessionButton.setEnabled(True)

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
        '''
        Remove/disconnect the DAQ device.
        Enable/disable the buttons accordingly.
        '''
        self.disconnectSig.emit()
        self.stopThreadSig.emit()
        self.is_monitoring = False  
        sleep(0.2)
        
        try:
            #Disconnect signals:
            self.DaqThread.ConnectSig.disconnect(self.HandleDaqConnectSig)
            self.startSig.disconnect(self.DaqThread.startSignalRec)
            self.disconnectSig.disconnect(self.DaqThread.disconnectDaq)
            self.stopThreadSig.disconnect(self.DaqThread.stop_Thread)
        except:
            pass
        
        #Enable/Disable buttons:
        self.configurationButton.setEnabled(True)
        self.removeDeviceButton.setEnabled(False)
        self.nextButton.setEnabled(False)
        self.startButton.setEnabled(False)

        #Disconnected DAQ message:
        self.messagesBox.appendHtml('<p>DAQ device is disconnected.</p>')

    def next_Session(self):
        '''
        Reset variables for data storage and plots.
        Setup the plots.
        Initially defined configuration is assumed.
        Verify DAQ connection before starting, reconnect if needed.
        '''
        # Re-arm the DAQ for the next session. Reuse the still-open connection
        # (like the first Start does) instead of closing and reopening the COM
        # port back-to-back, which raced the Windows handle release and failed
        # with "Acceso denegado". rearmDaq falls back to a full reconnect only
        # if the live connection has actually dropped.
        self.messagesBox.appendHtml('<p>Verifying DAQ connection...</p>')

        reconnected = self.DaqThread.rearmDaq()

        if not reconnected:
            self.messagesBox.appendHtml('<p style="color:red;">DAQ reconnection failed. Please use "Find Device" to reconnect.</p>')
            self.daq_connected = False
            self.nextButton.setEnabled(False)
            self.startButton.setEnabled(False)
            self.findDeviceButton.setEnabled(True)
            self.removeDeviceButton.setEnabled(False)
            self.configurationButton.setEnabled(True)
            return
        
        self.messagesBox.appendHtml('<p style="color:green;">DAQ connection verified.</p>')
        
        # Check trigger initial state
        if not self.check_trigger_initial_state():
            QtWidgets.QMessageBox.warning(self, "Trigger Warning",
                f"The selected trigger ({self.trigger_mode}) is currently in HIGH state.\n\n"
                "The signal must be LOW before starting monitoring.\n\n"
                "Please ensure the trigger is in its inactive state and try again.")
            self.messagesBox.appendHtml('<p style="color:red;">Cannot start: trigger is HIGH. Must be LOW to start.</p>')
            return

        # Proceed with session setup
        self.reset_Data_n_Plot_Vars()
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_start_epoch = datetime.now().timestamp()
        logger.info("Monitoring session %s starting (trigger=%s)", self.session_id, self.trigger_mode)
        self._ensure_mqtt_publisher()
        self.startButton.setEnabled(False)
        self.findDeviceButton.setEnabled(False)

        self.SubplotSetup()
        self.graphThread = GraphThread(self.dataQueue, self.sensors[:self.nplots], self.time_lim, 
                                       self.n_display_points, self.plot_refresh_rate, self)
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
        #Monitoring message:
        self.messagesBox.appendHtml('<p>Monitoring with unit conversion...</p>')
        self.graphThread.start()
        self.startSig.emit()
        self.is_monitoring = True  # Add this line
        # Continuous mode follows data all session; cycle mode starts still (waiting)
        self._set_plot_live(not self.cycle_mode)

        self.nextButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.removeDeviceButton.setEnabled(False)
        self.saveSessionButton.setEnabled(False)
        
    def start_monitoring(self):
        '''
        Start monitoring:
        - Check I channel initial state
        - Setup subplots;
        - Emit start signal.
        '''
        if self.daq_connected:
            # Check trigger initial state
            if not self.check_trigger_initial_state():
                QtWidgets.QMessageBox.warning(self, "Trigger Warning",
                    f"The selected trigger ({self.trigger_mode}) is currently in HIGH state.\n\n"
                    "The signal must be LOW before starting monitoring.\n\n"
                    "Please ensure the trigger is in its inactive state and try again.")
                self.messagesBox.appendHtml('<p style="color:red;">Cannot start: trigger is HIGH. Must be LOW to start.</p>')
                return
            
            self.reset_Data_n_Plot_Vars()
            self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.session_start_epoch = datetime.now().timestamp()
            logger.info("Monitoring session %s starting (trigger=%s)", self.session_id, self.trigger_mode)
            self._ensure_mqtt_publisher()

            self.startButton.setEnabled(False)
            self.findDeviceButton.setEnabled(False)
            self.removeDeviceButton.setEnabled(False)

            self.SubplotSetup()
            self.graphThread = GraphThread(self.dataQueue, self.sensors[:self.nplots], self.time_lim,
                                           self.n_display_points, self.plot_refresh_rate, self)
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
            self.startSig.emit()
            self.is_monitoring = True  # Add this line
            # Continuous mode follows data all session; cycle mode starts still (waiting)
            self._set_plot_live(not self.cycle_mode)

            #Monitoring message:
            self.messagesBox.appendHtml('<p>Monitoring with unit conversion...</p>')
        else:
            self.startButton.setEnabled(False)
            self.configurationButton.setEnabled(True)
            self.messagesBox.appendHtml('<p style="color:red;">DAQ not connected!</p>')

    # ------------------------------------------------------------ small helpers
    def _indices_of_category(self, cat):
        return [i for i in range(len(self.channel_types))
                if sensor_category(self.channel_types[i]) == cat]

    def _plot_indices_of_category(self, cat):
        """Like _indices_of_category, but only channels ticked for plotting."""
        selected = set(self.plot_channels)
        return [i for i in self._indices_of_category(cat)
                if i < len(self.daq_channels) and self.daq_channels[i] in selected]

    def _has_trigger_display(self):
        """True if a trigger exists worth drawing arrows for."""
        if self.trigger_mode != 'None':
            return True
        return any(sensor_category(t) == 'trigger' for t in self.channel_types)

    def _grid_dims(self, n):
        if n <= 1:
            return 1, 1
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        return rows, cols

    def _add_side_viewbox(self, main_plot, axisitem):
        """Attach an extra Y-axis (ViewBox linked to axisitem) sharing main_plot's X.

        The side ViewBox is mouse-transparent and registered as a y-buddy of the
        main ToolViewBox, so pan/zoom gestures move every axis of the plot
        together (see plot_tools.py).
        """
        vb = PassThroughViewBox()
        main_plot.scene().addItem(vb)
        axisitem.linkToView(vb)
        vb.setXLink(main_plot)

        # *_args swallows the ViewBox that sigResized passes, which would
        # otherwise shadow mp and break the re-sync on every window resize.
        def _sync(*_args, mp=main_plot, v=vb):
            v.setGeometry(mp.vb.sceneBoundingRect())
            v.linkedViewChanged(mp.vb, v.XAxis)

        _sync()
        main_plot.vb.sigResized.connect(_sync)
        # Keep the closure so SubplotSetup can re-pin the side axis after a
        # no-resize rebuild (sigResized won't fire then). See _resync_side_axes.
        self._side_syncs.append(_sync)
        vb.enableAutoRange(axis='y', enable=False)
        self._extra_viewboxes.append(vb)
        if isinstance(main_plot.vb, ToolViewBox):
            main_plot.vb.y_buddies.append(vb)
        return vb

    def _add_placeholder(self, canvas, text):
        canvas.addLabel(text, row=0, col=0)

    def _add_arrow_items(self, canvas_plot, which):
        """Create trigger arrow (vertical line + head) items on a plot."""
        if canvas_plot is None or not self._has_trigger_display():
            return
        lines = pg.PlotDataItem(pen=pg.mkPen('#00FF00', width=2), connect='finite')
        scatter = pg.ScatterPlotItem()
        canvas_plot.addItem(lines)
        canvas_plot.addItem(scatter)
        if which == 'mold':
            self.i_lines_item = lines
            self.i_arrow_scatter = scatter
        else:
            self.machine_lines_item = lines
            self.machine_arrow_scatter = scatter

    # ----------------------------------------------------------------- plotting
    def ploter(self, xpoints, ypoints):
        '''
        Push new data to every channel's line item. Each item already lives on the
        correct tab/axis (set up in SubplotSetup), so this is source-agnostic.
        '''
        if not xpoints:
            return
        for i in range(min(len(self.plotDataItem_lst), len(ypoints))):
            items = self.plotDataItem_lst[i]
            if items and len(ypoints[i]) > 0:
                items[0].setData(xpoints, ypoints[i])
        self._update_all_x_ranges(xpoints)
        # Remember what is on screen for the time-cursor readout, and refresh
        # it so DP always matches the curve currently displayed (e.g. the new
        # cycle that just replaced the previous one).
        self._last_plot_x = xpoints
        self._last_plot_y = ypoints
        if self.cursor_lines['t1'] and self.cursor_lines['t2']:
            self._update_cursor_readout()

    def _set_all_x_range(self, lo, hi, padding=0):
        for sp in self.splotlist:
            sp.setXRange(lo, hi, padding=padding)
        for sp in self.machine_splotlist:
            sp.setXRange(lo, hi, padding=padding)

    def _update_all_x_ranges(self, xpoints):
        if not xpoints:
            return
        if self.cycle_mode:
            if xpoints[-1] > self.cycle_max_x:
                self.cycle_max_x = xpoints[-1]
            self._set_all_x_range(0, self.cycle_max_x * 1.05, padding=0)
            self._default_x_range = (0, self.cycle_max_x * 1.05, 0)
        else:
            self._set_all_x_range(xpoints[0], xpoints[-1], padding=0.02)
            self._default_x_range = (xpoints[0], xpoints[-1], 0.02)

    def updateArrows(self, transitions, x_min, x_max):
        """Draw trigger transition arrows on both the mold and machine tabs."""
        visible = [(x, d) for (x, d) in transitions if x_min <= x <= x_max]
        self._draw_arrows_on_plot(self.splotlist[0] if self.splotlist else None,
                                  self.i_lines_item, self.i_arrow_scatter, visible)
        self._draw_arrows_on_plot(self.machine_splotlist[0] if self.machine_splotlist else None,
                                  self.machine_lines_item, self.machine_arrow_scatter, visible)

    def _draw_arrows_on_plot(self, plot, lines_item, scatter, visible):
        if plot is None or scatter is None:
            return
        if not visible:
            scatter.setData([], [])
            if lines_item is not None:
                lines_item.setData([], [])
            return
        y_bottom, y_top = plot.viewRange()[1]
        y_margin = (y_top - y_bottom) * 0.05
        y_bottom_arrow = y_bottom + y_margin
        y_top_arrow = y_top - y_margin

        line_x, line_y = [], []
        arrow_x, arrow_y, arrow_symbols = [], [], []
        for x_time, direction in visible:
            line_x.extend([x_time, x_time, np.nan])
            line_y.extend([y_bottom_arrow, y_top_arrow, np.nan])
            arrow_x.append(x_time)
            if direction == 'UP':
                arrow_y.append(y_top_arrow)
                arrow_symbols.append('t1')
            else:
                arrow_y.append(y_bottom_arrow)
                arrow_symbols.append('t')
        if lines_item is not None:
            lines_item.setData(line_x, line_y)
        scatter.setData(x=arrow_x, y=arrow_y, symbol=arrow_symbols,
                        brush=pg.mkBrush('#00FF00'), size=15, pen=pg.mkPen(None))

    # ------------------------------------------------- plot interaction tools
    def _set_plot_live(self, live):
        """Enter/leave the live (auto-following) plot state.

        The Home/Zoom/Pan/Cursors tools are only usable while the plot is
        still. Entering live mid-interaction cancels the active tool, hides a
        half-drawn zoom rectangle and snaps the view back to the default
        ranges so the plot follows the incoming data again.
        """
        self.plot_is_live = live
        has_plots = bool(self.splotlist or self.machine_splotlist)
        enable = (not live) and has_plots
        for btn in (self.homeButton, self.zoomButton, self.panButton, self.cursorButton):
            btn.setEnabled(enable)
        if live:
            for btn in (self.zoomButton, self.panButton, self.cursorButton):
                if btn.isChecked():
                    btn.setChecked(False)  # emits toggled -> clears tool_mode
            for vb in self._tool_viewboxes:
                vb.cancel_active_gesture()
            self.resetPlotView()

    def _on_tool_toggled(self, name, checked):
        """Keep Zoom/Pan/Cursors mutually exclusive; update the global mode."""
        buttons = {'zoom': self.zoomButton, 'pan': self.panButton,
                   'cursor': self.cursorButton}
        if checked:
            for other, btn in buttons.items():
                if other != name and btn.isChecked():
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
            self.tool_mode = name
        elif self.tool_mode == name:
            self.tool_mode = None
        ToolViewBox.tool_mode = self.tool_mode
        # Cursor lines may only be dragged while the cursor tool is active
        self._set_cursor_lines_movable(self.tool_mode == 'cursor')

    def resetPlotView(self):
        """Home: restore the ranges the live auto-scaling last applied."""
        if self._default_x_range is not None:
            lo, hi, padding = self._default_x_range
            self._set_all_x_range(lo, hi, padding=padding)
        for (setter, _), rng in zip(self.y_axis_groups, self._default_y_ranges):
            if rng is not None:
                setter.setYRange(rng[0], rng[1], padding=0)

    def _snapshot_default_ranges(self):
        """Record the initial axis ranges as the Home/default view."""
        self._default_x_range = (0, 10, 0)
        self._default_y_ranges = [tuple(setter.viewRange()[1])
                                  for setter, _ in self.y_axis_groups]

    # ------------------------------------------------------- time cursor lines
    def _iter_subplots(self):
        return list(self.splotlist) + list(self.machine_splotlist)

    def _on_cursor_click(self, button, x):
        """Place/move a time cursor: left -> t1, right -> t2, middle -> clear."""
        if self.plot_is_live or self.tool_mode != 'cursor':
            return
        if button == QtCore.Qt.LeftButton:
            self._place_cursor('t1', x)
        elif button == QtCore.Qt.RightButton:
            self._place_cursor('t2', x)
        elif button == QtCore.Qt.MiddleButton:
            self._clear_cursor_lines()
        self._update_cursor_readout()

    def _place_cursor(self, key, x):
        """Create the key's line on every subplot (first use) or move it there.

        The same time position is mirrored on all subplots of both tabs, since
        every X axis shows the same time range.
        """
        if self.cursor_lines[key]:
            self._move_cursor_lines(key, x)
            return
        pen = self.cursor_pens[key]
        hover = pg.mkPen(pen.color(), width=4)
        label_pos = 0.95 if key == 't1' else 0.88  # keep the two labels apart
        for sp in self._iter_subplots():
            line = pg.InfiniteLine(pos=x, angle=90, movable=True, pen=pen,
                                   hoverPen=hover, label=key,
                                   labelOpts={'position': label_pos,
                                              'color': pen.color(),
                                              'fill': (255, 255, 255, 180)})
            line.setZValue(20)
            sp.addItem(line)
            line.sigDragged.connect(lambda ln, k=key: self._on_cursor_dragged(k, ln))
            line.sigPositionChangeFinished.connect(
                lambda ln, k=key: self._on_cursor_dragged(k, ln))
            self.cursor_lines[key].append((sp, line))

    def _move_cursor_lines(self, key, x):
        if self._cursor_sync_guard:
            return
        self._cursor_sync_guard = True
        try:
            for _, line in self.cursor_lines[key]:
                line.setValue(x)
        finally:
            self._cursor_sync_guard = False

    def _on_cursor_dragged(self, key, line):
        """One line was dragged: mirror its position to the other subplots."""
        self._move_cursor_lines(key, line.value())
        self._update_cursor_readout()

    def _clear_cursor_lines(self):
        for key in ('t1', 't2'):
            for sp, line in self.cursor_lines[key]:
                try:
                    sp.removeItem(line)
                except Exception:
                    pass
            self.cursor_lines[key] = []

    def _set_cursor_lines_movable(self, movable):
        for key in ('t1', 't2'):
            for _, line in self.cursor_lines[key]:
                line.setMovable(movable)

    def _cursor_x(self, key):
        entries = self.cursor_lines[key]
        return entries[0][1].value() if entries else None

    def _update_cursor_readout(self):
        """Refresh the Δt / ΔP label from the cursor lines and on-screen curves."""
        x1 = self._cursor_x('t1')
        x2 = self._cursor_x('t2')
        dt_txt = dp_txt = '--'
        if x1 is not None and x2 is not None:
            t_lo, t_hi = sorted((x1, x2))
            dt_txt = f'{t_hi - t_lo:.3f} s'
            dp = self._pressure_drop_at(t_hi)
            if dp is not None:
                dp_txt = f'{dp:.1f} bar'
        self.deltaTLabel.setText(f'Δt: {dt_txt}')
        self.deltaPLabel.setText(f'ΔP: {dp_txt}')

    def _set_cycle_readout(self, cycle_num):
        """Show the cycle number in the toolbar readout box.

        Replaces the old light-grey TextItem that used to sit in the corner of
        the plot; the number now lives beside the Δt / ΔP readings. A falsy
        cycle_num (0 / None, e.g. before the first cycle or in continuous mode)
        shows a placeholder.
        """
        self.cycleReadoutLabel.setText(f'Cycle: {cycle_num}' if cycle_num else 'Cycle: --')

    # ------------------------------------------------ live coordinate readout
    _COORD_TAGS = {
        'T_futaba': 'T', 'T_typeK': 'T', 'T_typeJ': 'T',
        'P_kistler': 'P', 'P_machine': 'P',
        'S_speed': 'v', 'S_position': 'pos',
    }

    def _coord_tag(self, ch_type):
        """Short axis tag for the coordinate readout (T / P / pos / v)."""
        return self._COORD_TAGS.get(ch_type, sensor_label(ch_type)[:3])

    def _add_coord_readout(self, which, main_plot, axes):
        """Register a matplotlib-style x/y readout at the bottom-right of a plot.

        `axes` is a list of (tag, unit, viewbox): each adds one y value, the
        cursor's vertical position expressed in that axis's data coordinates
        (so dual/triple-axis plots show one number per axis). x comes from
        main_plot's own viewbox. The light-grey label follows the cursor and
        hides when the pointer leaves the plot.
        """
        item = pg.TextItem(anchor=(1, 1), color='#8a8a8a')
        item.setFont(QtGui.QFont('Arial', 9))
        item.setZValue(1e9)
        item.hide()
        main_plot.addItem(item, ignoreBounds=True)
        self._coord_readouts[which].append(
            {'item': item, 'vb': main_plot.vb, 'axes': axes})

    def _update_coord_readouts(self, which, scene_pos):
        """Refresh the x/y readout under the cursor for one tab (mold/machine)."""
        for e in self._coord_readouts.get(which, ()):
            vb = e['vb']
            try:
                inside = vb.sceneBoundingRect().contains(scene_pos)
            except Exception:
                inside = False
            if not inside:
                e['item'].hide()
                continue
            x = vb.mapSceneToView(scene_pos).x()
            parts = [f't={x:.3f} s']
            for tag, unit, axvb in e['axes']:
                y = axvb.mapSceneToView(scene_pos).y()
                parts.append(f'{tag}={y:.1f} {unit}'.rstrip())
            e['item'].setText('   '.join(parts))
            (x0, x1), (y0, y1) = vb.viewRange()
            e['item'].setPos(x1, y0)  # bottom-right corner of the view
            e['item'].show()

    def _pressure_drop_at(self, t):
        """|Pmax - Pmin| between the plotted cavity-pressure curves at time t.

        Values are read off the curves currently on screen (linear
        interpolation between samples). None when fewer than two pressure
        curves are plotted, no data is shown yet, or t lies outside the
        displayed time range.
        """
        idxs = self._plot_indices_of_category('moldP')
        if len(idxs) < 2 or not self._last_plot_x:
            return None
        x = np.asarray(self._last_plot_x, dtype=float)
        if x.size < 2 or not (x[0] <= t <= x[-1]):
            return None
        values = []
        for i in idxs:
            if i >= len(self._last_plot_y):
                return None
            y = np.asarray(self._last_plot_y[i], dtype=float)
            n = min(x.size, y.size)
            if n < 2:
                return None
            values.append(float(np.interp(t, x[:n], y[:n])))
        return max(values) - min(values)

    # -------------------------------------------------------------- cycle hooks
    def onCycleWaiting(self):
        """Handle waiting for first cycle signal."""
        nxt = getattr(self.graphThread, 'cycle_base', 0) + 1
        self.messagesBox.appendHtml(
            f'<p style="color:orange;">Waiting for trigger to go HIGH to start cycle {nxt}...</p>')
        self._set_cycle_readout(nxt)

    def onCycleStarted(self, cycle_num):
        """Handle cycle started signal."""
        self.current_cycle = cycle_num
        # Plot follows the new cycle: lock the tools and restore the live view
        self._set_plot_live(True)
        self.messagesBox.appendHtml(f'<p style="color:green;">Cycle {cycle_num} started</p>')
        self._set_cycle_readout(cycle_num)

    def onCycleEnded(self, cycle_num, xdata, ydata, cycle_start_s):
        """Handle cycle ended: persist the counter, store data, draw the ghost."""
        self.messagesBox.appendHtml(
            f'<p>Cycle {cycle_num} ended (duration: {xdata[-1]:.2f}s)</p>' if xdata
            else f'<p>Cycle {cycle_num} ended</p>')
        save_cycle_id(cycle_num)  # survives restarts / power loss (cycle_id.txt)
        self.completed_cycles_data.append((xdata, ydata))
        if xdata and xdata[-1] > self.cycle_max_x:
            self.cycle_max_x = xdata[-1]
            self._set_all_x_range(0, self.cycle_max_x * 1.05, padding=0)
            self._default_x_range = (0, self.cycle_max_x * 1.05, 0)
        self.createGhostPlots(xdata, ydata, cycle_num)
        # Trigger is LOW until the next cycle: the plot is still, tools usable
        self._set_plot_live(False)
        # ydata arrives per-channel; transpose to per-sample rows for the payload
        if self.mqtt_enabled and self.mqtt_publisher is not None and xdata and ydata:
            base_epoch = (self.session_start_epoch or datetime.now().timestamp()) + cycle_start_s
            self._publish_records(xdata, list(zip(*ydata)), cycle_num, base_epoch)

    def onCycleDiscarded(self, cycle_num, duration):
        """A trigger blip shorter than min_cycle_s was dropped (number is reused)."""
        self.messagesBox.appendHtml(
            f'<p style="color:orange;">Cycle {cycle_num} discarded '
            f'({duration:.2f}s &lt; {self.min_cycle_s:.2f}s minimum - treated as noise)</p>')
        # Number is reused for the retry, so keep showing it while we wait again.
        self._set_cycle_readout(cycle_num)
        self._set_plot_live(False)

    def createGhostPlots(self, xdata, ydata, cycle_num):
        """Semi-transparent copy of a completed cycle, added to each channel's axis."""
        if not xdata or not ydata:
            return
        alpha = 80
        ghost_plots = []
        for i in range(len(self.channel_types)):
            cat = sensor_category(self.channel_types[i])
            if cat in (None, 'trigger') or i >= len(ydata):
                continue
            target = self.item_target.get(i)
            if target is None:
                continue
            color = pg.mkColor(self.get_channel_color(i))
            color.setAlpha(alpha)
            ghost_item = pg.PlotDataItem(xdata, ydata[i], pen=pg.mkPen(color, width=1))
            target.addItem(ghost_item)
            ghost_plots.append(ghost_item)
        self.completed_cycles_plots.append(ghost_plots)

    def updateXAxisRange(self, x_min, x_max):
        '''Update X-axis range on both tabs (used during waiting mode in cycle mode).'''
        self._set_all_x_range(x_min, x_max, padding=0)
        self._default_x_range = (x_min, x_max, 0)

    def updateYAxisRanges(self, y_mins, y_maxs):
        '''Update every configured Y-axis from its channels' historical min/max.'''
        for k, (setter, idxs) in enumerate(self.y_axis_groups):
            mins = [y_mins[i] for i in idxs if i < len(y_mins)]
            maxs = [y_maxs[i] for i in idxs if i < len(y_maxs)]
            if mins and maxs:
                setter.setYRange(min(mins), max(maxs), padding=0)
                if k < len(self._default_y_ranges):
                    self._default_y_ranges[k] = (min(mins), max(maxs))

    def receiveXYData(self, xvals, yvals, yvals_raw, cycle_numbers):
        '''Receive DAQ collected data after monitoring stops (converted + raw).'''
        self.xdata = xvals
        self.ydata = yvals
        self.ydata_raw = yvals_raw
        self.cycle_numbers_data = cycle_numbers if cycle_numbers else []
        logger.info("Session %s finished: %d samples collected", self.session_id, len(xvals))
        # Continuous (no-trigger) mode: upload the whole session as one batch
        if self.mqtt_enabled and self.mqtt_publisher is not None and not self.cycle_mode:
            self._publish_records(xvals, yvals, 0,
                                  self.session_start_epoch or datetime.now().timestamp())

    # ------------------------------------------------------------ cloud upload
    def _ensure_mqtt_publisher(self):
        """Start the background MQTT publisher (once) when cloud upload is on."""
        if not self.mqtt_enabled or self.mqtt_publisher is not None:
            return
        try:
            from mqtt_publisher import MqttPublisher
            self.mqtt_publisher = MqttPublisher(machine_id=self.machine_id)
            self.mqtt_publisher.start()
            s = self.mqtt_publisher.settings
            self.messagesBox.appendHtml(
                '<p style="color:green;">Cloud upload enabled - MQTT broker %s:%d, topic %s</p>'
                % (s['broker'], s['port'], s['topic']))
        except Exception as e:
            self.mqtt_publisher = None
            self.mqtt_enabled = False
            logger.exception("Cloud upload disabled: %s", e)
            self.messagesBox.appendHtml(
                '<p style="color:red;">Cloud upload disabled: %s</p>' % e)

    def _mqtt_field_names(self):
        """Per-channel payload keys, matching the CSV header (e.g. CH2_P_kistler)."""
        names = []
        for i, ch in enumerate(self.daq_channels):
            if i < len(self.channel_types):
                names.append(f'CH{ch}_{self.channel_types[i]}')
            else:
                names.append(f'CH{ch}')
        return names

    def _publish_records(self, xdata, rows, cycle_id, base_epoch):
        """Queue one batch for cloud upload.

        rows holds one entry per sample, each a sequence of converted channel
        values in daq_channels order. cycle_id 0 means a full continuous
        session. base_epoch is the wall-clock instant (epoch seconds) of
        xdata's zero, used to stamp every record with an absolute timestamp.
        """
        if self.mqtt_publisher is None or not xdata:
            return
        names = self._mqtt_field_names()
        records = []
        for j, x in enumerate(xdata):
            rec = {'timestamp_ns': int((base_epoch + x) * 1e9),
                   'time_s': round(float(x), 6),
                   'machine_id': self.machine_id,
                   'session_id': self.session_id,
                   'cycle_id': cycle_id}
            vals = rows[j] if j < len(rows) else []
            for k, name in enumerate(names):
                if k < len(vals):
                    rec[name] = vals[k]
            records.append(rec)
        self.mqtt_publisher.publish_records(records)
        what = f'cycle {cycle_id}' if cycle_id else 'full session'
        self.messagesBox.appendHtml(
            '<p>Queued %d records for cloud upload (%s).</p>' % (len(records), what))

    # ------------------------------------------------------------------- setup
    def reset_Data_n_Plot_Vars(self):
        '''Reset data storage and tear down all plot items/viewboxes on both tabs.'''
        # Remove extra viewboxes from their scenes first
        for vb in getattr(self, '_extra_viewboxes', []):
            try:
                for item in vb.allChildren():
                    if hasattr(item, 'scene') and item.scene() is not None:
                        item.scene().removeItem(item)
                if vb.scene() is not None:
                    vb.scene().removeItem(vb)
            except Exception:
                pass
        self._extra_viewboxes = []
        self._side_syncs = []
        self._coord_readouts = {'mold': [], 'machine': []}
        self.right_viewbox = None
        self.machine_left2_viewbox = None
        self.machine_right_viewbox = None

        # Clear both canvases
        self.GraphArea.canvas.clear()
        self.GraphAreaMachine.canvas.clear()

        self.xdata = []
        self.ydata = []
        self.ydata_raw = []
        self.cycle_numbers_data = []
        self.splotlist = []
        self.machine_splotlist = []
        self.y_axis_groups = []
        self.item_target = {}
        self.xdata_plts = []
        self.ydata_plts = []
        # Must be rebuilt from scratch: ploter draws into items[0], and the old
        # session's (now dead) line items would otherwise stay in front.
        self.plotDataItem_lst = []

        # Reset trigger/arrow state
        self.i_channel_state = None
        self.i_channel_transitions = []
        self.i_channel_digital_values = []
        self.i_arrow_scatter = None
        self.i_lines_item = None
        self.machine_arrow_scatter = None
        self.machine_lines_item = None

        # Reset cycle state
        self.current_cycle = 0
        self.cycle_max_x = 0
        self.completed_cycles_data = []
        self.completed_cycles_plots = []
        self.cycle_labels = []
        self.cycle_label = None

        # Reset plot-tool state (the line items died with canvas.clear())
        self._tool_viewboxes = []
        self.cursor_lines = {'t1': [], 't2': []}
        self._last_plot_x = []
        self._last_plot_y = []
        self._default_x_range = None
        self._default_y_ranges = []
        self._update_cursor_readout()  # back to 'Δt: -- | ΔP: --'

        for n in range(self.nplots):
            self.ydata_plts.append([])
            self.plotDataItem_lst.append([])

    def _relayout_canvas(self, canvas):
        """Force a GraphicsLayoutWidget to recompute its item geometry.

        Plots rebuilt (on Next / Start) while their tab is the *current* page
        get no resize event, so the GraphicsLayout keeps a stale ~8px column
        split: the machine plot shrinks to a thin sliver, its x-axis squashes
        both tick labels onto 0, and the linked side viewboxes (speed / press)
        lock onto that sliver.

        Nudging the widget (resize +1/-1) does NOT fix this on Windows: that is
        a QWidget-level resize, and two same-turn resizes to w+1 then w net zero
        change, so the window manager coalesces them and no resizeEvent ever
        reaches the view. Instead drive the relayout entirely inside the graphics
        scene - size the central item to the real viewport and re-activate its
        grid layout. Scene-level setGeometry is synchronous and immune to native
        event coalescing, so it works whether or not the tab is visible.
        """
        vp = canvas.viewport().rect()
        if vp.width() <= 2 or vp.height() <= 2:
            return
        canvas.ci.setGeometry(QtCore.QRectF(0, 0, vp.width(), vp.height()))
        canvas.ci.layout.invalidate()
        canvas.ci.layout.activate()

    def _resync_side_axes(self):
        """Re-pin every extra Y-axis viewbox to its main plot's current geometry.

        _add_side_viewbox links each side viewbox via the main plot's sigResized,
        but on a no-resize rebuild that signal never fires, so the side viewboxes
        keep the stale sliver geometry (x-range mis-scaled -> near-vertical
        traces). Call this AFTER _relayout_canvas has restored the real geometry
        so the resync locks onto the correct rectangle, not the collapsed one.
        """
        for sync in getattr(self, '_side_syncs', []):
            try:
                sync()
            except Exception:
                pass

    def SubplotSetup(self):
        '''Build the Mold and Machine plot tabs for the current configuration.'''
        self._setup_mold_plots()
        self._setup_machine_plots()
        self._add_cycle_labels()
        self._snapshot_default_ranges()
        self.show()
        # Freshly rebuilt plots on the current tab get no resize event; force the
        # grid to re-lay-out, then re-pin the side axes to the corrected geometry
        # so the machine plot doesn't stay a thin sliver (see methods above).
        self._relayout_canvas(self.GraphArea.canvas)
        self._relayout_canvas(self.GraphAreaMachine.canvas)
        self._resync_side_axes()

    def _add_tool_plot(self, canvas, row, col):
        """addPlot wrapper: every user-facing plot gets a ToolViewBox and no
        context menu / autorange button (interaction goes through the toolbar)."""
        sp = canvas.addPlot(row, col, viewBox=ToolViewBox(), enableMenu=False)
        sp.hideButtons()
        self._tool_viewboxes.append(sp.vb)
        return sp

    def _setup_mold_plots(self):
        canvas = self.GraphArea.canvas
        temp_idx = self._plot_indices_of_category('temp')
        moldp_idx = self._plot_indices_of_category('moldP')

        if not temp_idx and not moldp_idx:
            self._add_placeholder(canvas, "No mold variables selected to plot")
            return

        if self.separate_plots:
            mold_channels = sorted(temp_idx + moldp_idx)
            rows, cols = self._grid_dims(len(mold_channels))
            for pos, i in enumerate(mold_channels):
                r, c = divmod(pos, cols)
                sp = self._add_tool_plot(canvas, r, c)
                self.splotlist.append(sp)
                item = sp.plot(pen=pg.mkPen(self.get_channel_color(i), width=2))
                self.plotDataItem_lst[i].append(item)
                self.item_target[i] = sp
                sp.setLabel('left', self.get_y_label(i))
                sp.setLabel('bottom', 'Time [s]')
                sp.getAxis("bottom").setStyle(tickTextOffset=5, tickTextHeight=9)
                legend = sp.addLegend(offset=(10, 10))
                legend.addItem(item, self.get_channel_label(i))
                sp.enableAutoRange(axis='y', enable=False)
                sp.setYRange(0, 100 if sensor_category(self.channel_types[i]) == 'temp' else 10, padding=0)
                sp.enableAutoRange(axis='x', enable=False)
                sp.setXRange(0, 10, padding=0)
                self.y_axis_groups.append((sp, [i]))
                self._add_coord_readout('mold', sp, [(self._coord_tag(self.channel_types[i]),
                                                      sensor_unit(self.channel_types[i]), sp.vb)])
            self._add_arrow_items(self.splotlist[0] if self.splotlist else None, 'mold')
        else:
            main_plot = self._add_tool_plot(canvas, 0, 0)
            self.splotlist.append(main_plot)
            main_plot.enableAutoRange(axis='x', enable=False)
            main_plot.setXRange(0, 10, padding=0)
            main_plot.setLabel('bottom', 'Time [s]')
            main_plot.getAxis("bottom").setStyle(tickTextOffset=5, tickTextHeight=9)

            if temp_idx:
                main_plot.setLabel('left', 'Temperature [°C]', color='#FF0000')
                main_plot.getAxis("left").setPen(pg.mkPen('#FF0000', width=2))
            else:
                main_plot.setLabel('left', 'Temperature [°C] (unused)', color='#888888')
                main_plot.getAxis("left").setPen(pg.mkPen('#888888', width=1))

            legend = pg.LegendItem(offset=(-80, 10))
            legend.setParentItem(main_plot.graphicsItem())

            for i in temp_idx:
                item = main_plot.plot(pen=pg.mkPen(self.get_channel_color(i), width=2))
                self.plotDataItem_lst[i].append(item)
                self.item_target[i] = main_plot
                legend.addItem(item, self.get_channel_label(i))

            main_plot.showAxis('right')
            rvb = self._add_side_viewbox(main_plot, main_plot.getAxis('right'))
            self.right_viewbox = rvb
            if moldp_idx:
                main_plot.setLabel('right', 'Pressure [bar]', color='#0000FF')
                main_plot.getAxis("right").setPen(pg.mkPen('#0000FF', width=2))
            else:
                main_plot.setLabel('right', 'Pressure [bar] (unused)', color='#888888')
                main_plot.getAxis("right").setPen(pg.mkPen('#888888', width=1))
            for i in moldp_idx:
                item = pg.PlotDataItem(pen=pg.mkPen(self.get_channel_color(i), width=2))
                rvb.addItem(item)
                self.plotDataItem_lst[i].append(item)
                self.item_target[i] = rvb
                legend.addItem(item, self.get_channel_label(i))

            main_plot.enableAutoRange(axis='y', enable=False)
            main_plot.setYRange(0, 100, padding=0)
            rvb.setYRange(0, 10, padding=0)
            self.y_axis_groups.append((main_plot, temp_idx))
            self.y_axis_groups.append((rvb, moldp_idx))
            coord_axes = []
            if temp_idx:
                coord_axes.append(('T', sensor_unit(self.channel_types[temp_idx[0]]), main_plot.vb))
            if moldp_idx:
                coord_axes.append(('P', sensor_unit(self.channel_types[moldp_idx[0]]), rvb))
            self._add_coord_readout('mold', main_plot, coord_axes)
            self._add_arrow_items(main_plot, 'mold')

    def _setup_machine_plots(self):
        canvas = self.GraphAreaMachine.canvas
        machine_idx = self._plot_indices_of_category('machine')

        if not machine_idx:
            self._add_placeholder(canvas, "No machine variables selected to plot")
            return

        if self.machine_layout == 'separate':
            rows, cols = self._grid_dims(len(machine_idx))
            for pos, i in enumerate(machine_idx):
                r, c = divmod(pos, cols)
                sp = self._add_tool_plot(canvas, r, c)
                self.machine_splotlist.append(sp)
                item = sp.plot(pen=pg.mkPen(self.get_channel_color(i), width=2))
                self.plotDataItem_lst[i].append(item)
                self.item_target[i] = sp
                sp.setLabel('left', self.get_y_label(i))
                sp.setLabel('bottom', 'Time [s]')
                sp.getAxis("bottom").setStyle(tickTextOffset=5, tickTextHeight=9)
                legend = sp.addLegend(offset=(10, 10))
                legend.addItem(item, self.get_channel_label(i))
                sp.enableAutoRange(axis='y', enable=False)
                sp.setYRange(0, 100, padding=0)
                sp.enableAutoRange(axis='x', enable=False)
                sp.setXRange(0, 10, padding=0)
                self.y_axis_groups.append((sp, [i]))
                self._add_coord_readout('machine', sp, [(self._coord_tag(self.channel_types[i]),
                                                         sensor_unit(self.channel_types[i]), sp.vb)])
            self._add_arrow_items(self.machine_splotlist[0] if self.machine_splotlist else None, 'machine')
        else:
            # Shared layout: position (native left), speed (extra left), pressure (right)
            pos_idx = [i for i in machine_idx if self.channel_types[i] == 'S_position']
            spd_idx = [i for i in machine_idx if self.channel_types[i] == 'S_speed']
            prs_idx = [i for i in machine_idx if self.channel_types[i] == 'P_machine']

            extra_ax = None
            if spd_idx:
                extra_ax = pg.AxisItem('left')
                canvas.addItem(extra_ax, 0, 0)
            main_plot = self._add_tool_plot(canvas, 0, 1)
            self.machine_splotlist.append(main_plot)
            main_plot.enableAutoRange(axis='x', enable=False)
            main_plot.setXRange(0, 10, padding=0)
            main_plot.setLabel('bottom', 'Time [s]')
            main_plot.getAxis("bottom").setStyle(tickTextOffset=5, tickTextHeight=9)
            legend = pg.LegendItem(offset=(-80, 10))
            legend.setParentItem(main_plot.graphicsItem())

            # Native left axis: Screw position
            col_pos = self.machine_colors['S_position']
            if pos_idx:
                main_plot.setLabel('left', f"{sensor_label('S_position')} [{sensor_unit('S_position')}]", color=col_pos)
                main_plot.getAxis("left").setPen(pg.mkPen(col_pos, width=2))
            else:
                main_plot.setLabel('left', f"{sensor_label('S_position')} (unused)", color='#888888')
                main_plot.getAxis("left").setPen(pg.mkPen('#888888', width=1))
            for i in pos_idx:
                item = main_plot.plot(pen=pg.mkPen(self.get_channel_color(i), width=2))
                self.plotDataItem_lst[i].append(item)
                self.item_target[i] = main_plot
                legend.addItem(item, self.get_channel_label(i))
            main_plot.enableAutoRange(axis='y', enable=False)
            main_plot.setYRange(0, 100, padding=0)
            self.y_axis_groups.append((main_plot, pos_idx))

            # Extra left axis: Injection speed
            if spd_idx and extra_ax is not None:
                lvb = self._add_side_viewbox(main_plot, extra_ax)
                self.machine_left2_viewbox = lvb
                col_spd = self.machine_colors['S_speed']
                extra_ax.setLabel(f"{sensor_label('S_speed')} [{sensor_unit('S_speed')}]", color=col_spd)
                extra_ax.setPen(pg.mkPen(col_spd, width=2))
                for i in spd_idx:
                    item = pg.PlotDataItem(pen=pg.mkPen(self.get_channel_color(i), width=2))
                    lvb.addItem(item)
                    self.plotDataItem_lst[i].append(item)
                    self.item_target[i] = lvb
                    legend.addItem(item, self.get_channel_label(i))
                lvb.setYRange(0, 100, padding=0)
                self.y_axis_groups.append((lvb, spd_idx))

            # Right axis: Injection pressure
            if prs_idx:
                main_plot.showAxis('right')
                rvb = self._add_side_viewbox(main_plot, main_plot.getAxis('right'))
                self.machine_right_viewbox = rvb
                col_prs = self.machine_colors['P_machine']
                main_plot.setLabel('right', f"{sensor_label('P_machine')} [{sensor_unit('P_machine')}]", color=col_prs)
                main_plot.getAxis("right").setPen(pg.mkPen(col_prs, width=2))
                for i in prs_idx:
                    item = pg.PlotDataItem(pen=pg.mkPen(self.get_channel_color(i), width=2))
                    rvb.addItem(item)
                    self.plotDataItem_lst[i].append(item)
                    self.item_target[i] = rvb
                    legend.addItem(item, self.get_channel_label(i))
                rvb.setYRange(0, 100, padding=0)
                self.y_axis_groups.append((rvb, prs_idx))

            coord_axes = []
            if pos_idx:
                coord_axes.append(('pos', sensor_unit('S_position'), main_plot.vb))
            if spd_idx and self.machine_left2_viewbox is not None:
                coord_axes.append(('v', sensor_unit('S_speed'), self.machine_left2_viewbox))
            if prs_idx and self.machine_right_viewbox is not None:
                coord_axes.append(('P', sensor_unit('P_machine'), self.machine_right_viewbox))
            self._add_coord_readout('machine', main_plot, coord_axes)
            self._add_arrow_items(main_plot, 'machine')

    def _add_cycle_labels(self):
        '''Initialise the cycle-number readout in the toolbar box.

        The cycle number used to be drawn as a light-grey TextItem in the corner
        of each plot; it now lives in the readout box next to Δt / ΔP. This just
        seeds that box for the (re)built session.
        '''
        self.cycle_labels = []  # on-plot labels removed; kept empty for legacy refs
        self.cycle_label = None
        # Continuous mode has no cycles -> placeholder; cycle mode shows the
        # current number (0 before the first cycle -> placeholder too).
        self._set_cycle_readout(self.current_cycle if self.cycle_mode else None)

    def find_device(self):
        '''
        What to do when findDeviceButton is clicked:
        - Connect to DAQ device
        '''
        self.startButton.setEnabled(False)
        try:
            self.rem_devs()
        except:
            pass

        # Start DAQ connection
        self.messagesBox.appendHtml('<p>Attempting to connect to DAQ device...</p>')
        self.daqThStart()

    def daqThStart(self):
        '''
        Start a parallel thread to handle DAQ communication.
        '''
        self.dataQueue = queue.Queue()

        # Read the digital inputs (D4/D5) only when the trigger is wired there.
        read_digital = (self.trigger_wiring == 'digital')
        self.DaqThread = DaqThread(self.daq_channels, self.voltage_ranges,
                                   self.daq_dec, self.daq_deca, self.daq_srate,
                                   self.dataQueue, self.sensors[:self.nplots],
                                   read_digital=read_digital)
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
        self.stopReading()
        self.stopButton.setEnabled(False)
        self.nextButton.setEnabled(False)
        self.saveSessionButton.setEnabled(False)
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
        if ConnectedT_F == True:
            self.messagesBox.appendHtml('<p style="color:green;">DAQ device: connected.</p>')
            # Only enable Start button if NOT currently monitoring
            if not self.is_monitoring:
                self.startButton.setEnabled(True)
            self.removeDeviceButton.setEnabled(True)
            self.configurationButton.setEnabled(False)
        else:
            self.messagesBox.appendHtml('<p style="color:red;">DAQ device: connection failed!</p>')
        self.daq_connected = ConnectedT_F

    def configure(self):
        '''
        Configure DAQ parameters
        '''
        self.ModuleSelectWin = DaqConfigWindow()
        self.ModuleSelectWin.configSignal.connect(self.cnfg_Sig_Received)
        self.ModuleSelectWin.show()

    def cnfg_Sig_Received(self, cfg):
        '''
        Store DAQ configuration values from the config window (dict payload).
        '''
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
            self.mqtt_publisher.stop()
            self.mqtt_publisher = None
        new_machine_id = str(cfg.get('machine_id', self.machine_id)).strip() or self.machine_id
        if new_machine_id != self.machine_id:
            self.machine_id = new_machine_id
            if self.mqtt_publisher is not None:  # recreated with the new id on next start
                self.mqtt_publisher.stop()
                self.mqtt_publisher = None
        self.min_cycle_s = float(cfg.get('min_cycle_s', self.min_cycle_s))
        self.trigger_mode = cfg.get('trigger_mode', 'None')
        self.trigger_wiring = cfg.get('trigger_wiring', 'digital')
        self.digital_map = dict(cfg.get('digital_map', self.digital_map))
        self.conversion = {k: dict(v) for k, v in cfg.get('conversion', self.conversion).items()}
        self.cycle_mode = (self.trigger_mode != 'None')
        self.nplots = len(self.daq_channels)
        self.sensors = [f'CH{ch}' for ch in self.daq_channels]

        # Update trigger channel index (analog wiring)
        self._update_i_channel_index()

        # Reset plot data structures for new number of channels
        self.plotDataItem_lst = []
        self.ydata_plts = []
        for n in range(self.nplots):
            self.plotDataItem_lst.append([])
            self.ydata_plts.append([])

        logger.info("Configuration applied: channels=%s, types=%s, srate=%dHz, dec=%d, "
                    "trigger=%s, machine_id=%s, mqtt=%s",
                    self.daq_channels, self.channel_types, self.daq_srate, self.daq_dec,
                    self.trigger_mode, self.machine_id, self.mqtt_enabled)
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
        self.messagesBox.appendHtml('<p>Sample rate: %d Hz</p>' % cfg['sample_rate_hz'])
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
        if cfg.get('trigger_mode', 'None') != 'None':
            wiring = cfg.get('trigger_wiring', 'analog')
            if wiring == 'digital':
                dmap = cfg.get('digital_map', {})
                where = f"digital inputs (D4={dmap.get('D4')}, D5={dmap.get('D5')})"
            else:
                where = "an analog channel"
            self.messagesBox.appendHtml('<p style="color:green;">Trigger: %s cycle control via %s</p>'
                                        % (cfg['trigger_mode'], where))
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
        self.startsigrec = False
        self.stopsigrec = False
        self.stopThread = False
        self.sensors = sensors
        self.read_digital = read_digital  # append D4/D5 digital word to each scan
        self.daq_device = None
        self.binary_method = 1

    def ConnectDaq(self):
        '''
        Connect to DAQ device with improved error handling
        '''
        try:
            output_mode = 'binary'
            
            # Create DAQ connection
            self.daq_device = daq.Daq_serial(
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
            self.ConnectSig.emit(True)
            self.IsConnected = True
            return True

        except Exception as e:
            logger.exception("DAQ connection error: %s", e)
            self.ConnectSig.emit(False)
            self.IsConnected = False
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

    @QtCore.pyqtSlot()
    def stop_Thread(self):
        self.stopThread = True
        
    @QtCore.pyqtSlot()
    def disconnectDaq(self):
        if self.IsConnected == True and self.daq_device is not None:
            try:
                self.daq_device.close_serial()
                self.IsConnected = False
            except Exception as e:
                logger.error("Error closing DAQ: %s", e)

    @QtCore.pyqtSlot()
    def stopSignalRec(self):
        self.stopsigrec = True

    @QtCore.pyqtSlot()
    def startSignalRec(self):
        self.start_time = perf_counter()
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
    cycleStartedSig = QtCore.pyqtSignal(int)  # cycle_number
    cycleEndedSig = QtCore.pyqtSignal(int, list, list, float)  # cycle_number, xdata, ydata, cycle start (session-relative s)
    cycleDiscardedSig = QtCore.pyqtSignal(int, float)  # cycle_number, duration_s (too short, dropped as noise)
    cycleWaitingSig = QtCore.pyqtSignal()  # Emitted when waiting for first cycle
    updateXAxisRangeSig = QtCore.pyqtSignal(float, float)  # x_min, x_max for waiting mode

    def __init__(self, dataQueue, sensors, read_period, n_display_points=200, refresh_rate_ms=50, main_window=None, parent=None):
        super(QtCore.QThread, self).__init__()

        self.readQSigRec = False
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
        waiting_start_time = perf_counter()  # Track when waiting started
        last_heartbeat = perf_counter()  # Periodic "still alive" log line
        
        # In cycle mode, emit waiting signal at start
        if self.cycle_mode:
            self.cycleWaitingSig.emit()
        
        while not self.stopThread:  # Changed to check stopThread directly
            # Check stop condition at start of each iteration
            if self.stopThread:
                break
                
            if self.readQSigRec:
                plot_T_F = False
                t1 = perf_counter()
                timer = t1 - t0

                # Process multiple data points at once
                processed_count = 0
                while processed_count < 20 and not self.stopThread:  # Added stopThread check
                    try:
                        self.serData = self.dataQueue.get_nowait()
                        x_time = self.serData[-1]

                        # Split the scan into analog channels (+ optional digital word).
                        # With digital trigger wiring the last pre-timestamp value is
                        # the D4/D5 digital word, not an analog channel.
                        raw_all = self.serData[:-1]
                        n_analog = self.n_sensors
                        digital_word = None
                        if (self.main_window and self.main_window.trigger_wiring == 'digital'
                                and len(raw_all) > n_analog):
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
                                    self.cycleStartedSig.emit(self.current_cycle)
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
                                                               float(self.cycle_start_time))
                            else:
                                # Waiting for next cycle
                                if i_is_high and (x_time - self.last_cycle_end_time) > 2.0:
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
                                    self.cycleStartedSig.emit(self.current_cycle)
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
                    except:
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
                    self.graphUpdateSig.emit(self.xdata_plts, self.ydata_plts)
                    
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

            # Check monitoring time limit (only when not in waiting mode)
            if not self.waiting_for_first_cycle and len(self.xdata) > 0 and self.xdata[-1] > self.read_period:
                self.monitTimeEndSig.emit()
                self.stopThread = True
        
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
                
                # Skip I channel for Y-axis scaling (it's 0/1 digital)
                is_i_channel = (self.main_window and 
                               self.main_window.i_channel_index is not None and 
                               i == self.main_window.i_channel_index)
                
                if not is_i_channel:
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
                # Skip I channel
                is_i_channel = (self.main_window and 
                               self.main_window.i_channel_index is not None and 
                               i == self.main_window.i_channel_index)
                
                if is_i_channel:
                    y_mins.append(0)
                    y_maxs.append(1)
                    continue
                
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
                
                # Skip I channel for Y-axis scaling (it's 0/1 digital)
                is_i_channel = (self.main_window and 
                               self.main_window.i_channel_index is not None and 
                               i == self.main_window.i_channel_index)
                
                if not is_i_channel:
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
                is_i_channel = (self.main_window and 
                               self.main_window.i_channel_index is not None and 
                               i == self.main_window.i_channel_index)
                
                if is_i_channel:
                    y_mins.append(0)
                    y_maxs.append(1)
                    continue
                
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
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.showMaximized()
    app.exec_()
    logger.info("Application closed.")