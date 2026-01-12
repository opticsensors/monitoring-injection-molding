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
import json
from pathlib import Path
import daq_connectivity as daq  # Import DAQ library
from time import sleep
from time import perf_counter
import queue
import numpy as np

import MainWindow
import help_dialog

# Path to configuration defaults file
CONFIG_DEFAULTS_FILE = Path(__file__).parent / 'daq_config_defaults.json'

def load_config_defaults():
    """Load configuration defaults from JSON file."""
    defaults = {
        "monitoring_time_s": 300,
        "channels": [0, 1, 2, 3, 4],
        "channel_types": ["T", "T", "P", "P", "I"],
        "voltage_ranges": [10, 10, 10, 10, 10],
        "sample_rate_hz": 6000,
        "decimation": 100,
        "display_points": 1600,
        "plot_refresh_rate_ms": 50,
        "separate_plots": False,
        "cycle_mode": True
    }
    
    try:
        if CONFIG_DEFAULTS_FILE.exists():
            loaded = json.loads(CONFIG_DEFAULTS_FILE.read_text())
            defaults.update(loaded)
            print(f"Loaded configuration defaults from: {CONFIG_DEFAULTS_FILE}")
        else:
            print(f"Config file not found at {CONFIG_DEFAULTS_FILE}, using built-in defaults")
    except Exception as e:
        print(f"Error loading config defaults: {e}, using built-in defaults")
    
    return defaults

# Load defaults at startup
CONFIG_DEFAULTS = load_config_defaults()

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
        self.plotDataItem_lst = [] # List for plot data items identifiers
        self.splotlist = [] # List of subplots (initialized)
        
        # Color palettes for temperature (warm) and pressure (cold)
        self.temp_colors = ['#FF0000', '#FF6600', '#FF9900', '#FFCC00']  # Red, Orange, Dark Orange, Gold
        self.pressure_colors = ['#0000FF', '#0099FF', '#00CCFF', '#00FFFF']  # Blue, Light Blue, Cyan, Aqua
        
        # Channel type configuration from defaults
        self.channel_types = CONFIG_DEFAULTS['channel_types'].copy()
        
        # Unit conversion constants
        self.adc_resolution = 2**(16-1)  # 15-bit ADC resolution
        self.voltage_scale = 10  # Voltage range scale
        
        # Temperature conversion: 1V = 100°C
        self.temp_scale = 100  # 100°C per volt
        
        # Pressure conversion: bar
        self.s0 = 2.500
        self.s1 = 2.508
        self.Qmax = 20000
        self.xmax0 = self.Qmax / self.s0  
        self.xmax1 = self.Qmax / self.s1
        
        # Inductive sensor (I channel) configuration
        self.i_channel_index = None  # Index of the I channel in channel_types list
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
        
        # Cycle mode configuration
        self.cycle_mode = False  # If True, I channel controls cycle start/end
        self.current_cycle = 0  # Current cycle number (1-based when active)
        self.cycle_max_x = 0  # Maximum X value seen across all cycles
        self.completed_cycles_data = []  # List of (xdata, ydata) for completed cycles
        self.completed_cycles_plots = []  # List of plot items for completed cycles
        self.cycle_label = None  # Label showing current cycle number
        
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
        
        #LABELS:
        self.x_Label = 'Time [s]'

        # Run configure function when configurationButton is clicked:
        self.configurationButton.clicked.connect(self.configure)
        # Run exit_app_event function when exitButton is clicked:
        self.exitButton.clicked.connect(self.closeEvent)
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

        self.aboutAction = QtWidgets.QAction("&About...", self)
        self.menuHelp.addAction(self.aboutAction)
        self.aboutAction.triggered.connect(self.onAboutTriggered)

        # Initialize plot data structures
        for n in range(self.nplots):
            self.plotDataItem_lst.append([])
        
        # Find I channel index if present in defaults
        self._update_i_channel_index()

        #Initial message:
        self.messagesBox.appendHtml('<p style="color:blue;">DAQ Monitoring System v2.0</p><p></p>')

    def _update_i_channel_index(self):
        """Update the I channel index based on current channel_types configuration."""
        self.i_channel_index = None
        for i, ct in enumerate(self.channel_types):
            if ct == 'I':
                self.i_channel_index = i
                break

    def get_channel_color(self, channel_index):
        """
        Get the appropriate color for a channel based on its type.
        Temperature channels get warm colors, Pressure channels get cold colors.
        I channels don't get plotted as lines.
        """
        if channel_index >= len(self.channel_types):
            return '#808080'  # Gray fallback
        
        channel_type = self.channel_types[channel_index]
        
        if channel_type == 'I':
            return '#00FF00'  # Green for inductive sensor arrows
        
        # Count how many channels of this type come before this one
        type_count = 0
        for i in range(channel_index):
            if i < len(self.channel_types) and self.channel_types[i] == channel_type:
                type_count += 1
        
        if channel_type == 'T':
            return self.temp_colors[type_count % len(self.temp_colors)]
        else:  # 'P'
            return self.pressure_colors[type_count % len(self.pressure_colors)]

    def get_channel_label(self, channel_index):
        """
        Get the label for a channel including its type.
        """
        if channel_index >= len(self.daq_channels):
            return f'CH{channel_index}'
        
        ch_num = self.daq_channels[channel_index]
        
        if channel_index < len(self.channel_types):
            ch_type = self.channel_types[channel_index]
            if ch_type == 'T':
                return f'CH{ch_num} - Temperature'
            elif ch_type == 'P':
                return f'CH{ch_num} - Pressure'
            else:  # 'I'
                return f'CH{ch_num} - Inductive'
        return f'CH{ch_num}'

    def get_y_label(self, channel_index):
        """
        Get the Y-axis label for a channel based on its type.
        """
        if channel_index >= len(self.channel_types):
            return 'Value [V]'
        
        ch_type = self.channel_types[channel_index]
        ch_num = self.daq_channels[channel_index] if channel_index < len(self.daq_channels) else channel_index
        
        if ch_type == 'T':
            return f'Temperature CH{ch_num} [°C]'
        elif ch_type == 'P':
            return f'Pressure CH{ch_num} [bar]'
        else:  # 'I'
            return f'Trigger CH{ch_num}'

    def convert_voltage_to_units(self, voltage_values):
        """
        Convert raw voltage values to physical units based on channel type configuration.
        For I channels, converts to digital 0/1 based on thresholds.
        """
        converted_values = []
        
        for i, voltage in enumerate(voltage_values):
            if i < len(self.channel_types):
                ch_type = self.channel_types[i]
                
                if ch_type == 'T':  # Temperature
                    temp_celsius = voltage * (10 / (2**(16-1))) * 100
                    converted_values.append(temp_celsius)
                elif ch_type == 'P':  # Pressure
                    # Use appropriate pressure scale based on channel position
                    pressure_idx = sum(1 for j in range(i) if self.channel_types[j] == 'P')
                    if pressure_idx % 2 == 0:
                        pressure_bar = voltage * (self.xmax0 / (2**(16-1)))
                    else:
                        pressure_bar = voltage * (self.xmax1 / (2**(16-1)))
                    converted_values.append(pressure_bar)
                else:  # 'I' - Inductive sensor
                    # Convert to digital: 0 if LOW, 1 if HIGH
                    # Raw voltage value is an integer proportional to actual voltage
                    if voltage < self.i_threshold_low:
                        converted_values.append(0)
                    elif voltage > self.i_threshold_high:
                        converted_values.append(1)
                    else:
                        # In the hysteresis zone - keep previous state
                        # For conversion purposes, use the closer threshold
                        mid_point = (self.i_threshold_low + self.i_threshold_high) / 2
                        converted_values.append(0 if voltage < mid_point else 1)
            else:
                converted_values.append(voltage)
        
        return converted_values

    def process_i_channel_transition(self, x_time, raw_value):
        """
        Process a raw value from the I channel and detect transitions.
        Returns the current digital state (0 or 1).
        """
        if self.i_channel_index is None:
            return None
        
        # Determine current state based on thresholds
        if raw_value < self.i_threshold_low:
            new_state = 'LOW'
            digital_value = 0
        elif raw_value > self.i_threshold_high:
            new_state = 'HIGH'
            digital_value = 1
        else:
            # In hysteresis zone - keep previous state
            if self.i_channel_state is not None:
                new_state = self.i_channel_state
                digital_value = 1 if new_state == 'HIGH' else 0
            else:
                # Default to LOW if no previous state
                new_state = 'LOW'
                digital_value = 0
        
        # Detect transitions
        if self.i_channel_state is not None and new_state != self.i_channel_state:
            if self.i_channel_state == 'LOW' and new_state == 'HIGH':
                # Rising edge - UP arrow
                self.i_channel_transitions.append((x_time, 'UP'))
                print(f"I Channel: Rising edge detected at t={x_time:.3f}s")
            elif self.i_channel_state == 'HIGH' and new_state == 'LOW':
                # Falling edge - DOWN arrow
                self.i_channel_transitions.append((x_time, 'DOWN'))
                print(f"I Channel: Falling edge detected at t={x_time:.3f}s")
        
        self.i_channel_state = new_state
        return digital_value

    def check_i_channel_initial_state(self):
        """
        Check if the I channel is in HIGH state before starting monitoring.
        Returns True if OK to proceed, False if HIGH (should not start).
        """
        if self.i_channel_index is None:
            return True  # No I channel configured, OK to proceed
        
        try:
            # Read a single value from the DAQ to check initial state
            if hasattr(self, 'DaqThread') and self.DaqThread.IsConnected:
                values = self.DaqThread.daq_device.collect_data(self.DaqThread.binary_method)
                if values is not None and self.i_channel_index < len(values):
                    raw_value = float(values[self.i_channel_index])
                    if raw_value > self.i_threshold_high:
                        return False  # HIGH state - should not start
        except Exception as e:
            print(f"Error checking I channel initial state: {e}")
        
        return True  # OK to proceed

    def onAboutTriggered(self):
        '''
        Executed when About button is clicked:
        Show help dialog.
        '''
        self.About = help_dialog()
        self.About.show()

    def closeEvent(self, event):
        '''
        Action for when exitButton is clicked.
        1 - emit signal to stop DAQ thread loop.
        2 - A message appears asking if user really wishes to leave.
        3 - Message has 2 buttons: Return and Leave.
        '''
        self.stopThreadSig.emit()

        reply = QtWidgets.QMessageBox.question(self, "Message", 'Are you sure you want to leave? Any unsaved work will be lost.', 
        QtWidgets.QMessageBox.Cancel | QtWidgets.QMessageBox.Close)

        if reply == QtWidgets.QMessageBox.Close:
            app.quit()
        else:
            try:
                event.ignore()
            except:
                pass

    def save_Session(self):
        '''
        Save session dialog:
        Save a csv file with session data (both raw and converted values).
        I channel is saved as 0/1 digital values.
        In cycle mode, includes a Cycle column.
        '''
        fname = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Session Data as:', os.getenv('HOME'), 'CSV(*.csv)')

        if fname[0] != '':
            with open(fname[0], 'w', newline='') as csv_file:
                writer = csv.writer(csv_file, dialect='excel')
                
                # Write header with channel types
                header = []
                if self.cycle_mode and self.cycle_numbers_data:
                    header.append("Cycle")
                header.append("Time(s)")
                for i, ch in enumerate(self.daq_channels):
                    if i < len(self.channel_types):
                        ch_type = self.channel_types[i]
                        if ch_type == 'T':
                            header.append(f"CH{ch}_Temp[°C]")
                        elif ch_type == 'P':
                            header.append(f"CH{ch}_Pressure[bar]")
                        else:  # 'I'
                            header.append(f"CH{ch}_Trigger[0/1]")
                    else:
                        header.append(f"CH{ch}")
                writer.writerow(header)
                
                # Write data
                for i in range(len(self.xdata)):
                    if i < len(self.ydata):
                        row_data = []
                        if self.cycle_mode and self.cycle_numbers_data and i < len(self.cycle_numbers_data):
                            row_data.append(self.cycle_numbers_data[i])
                        row_data.append(self.xdata[i])
                        row_data.extend(self.ydata[i])
                        writer.writerow(row_data)
                
                #Saved session message:
                if self.cycle_mode and self.cycle_numbers_data:
                    self.messagesBox.appendHtml('<p>Session data was saved with cycle numbers (I channel as 0/1).</p>')
                else:
                    self.messagesBox.appendHtml('<p>Session data was saved (I channel as 0/1 digital values).</p>')

    def stopReading(self):
        '''
        To emit the signal to stop reading and enable/disable the buttons accordingly.
        '''
        self.stopSig.emit()
        self.is_monitoring = False  # Add this line
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
        # First, verify DAQ connection is still alive - reconnect if needed
        self.messagesBox.appendHtml('<p>Verifying DAQ connection...</p>')
        
        max_retries = 2
        reconnected = False
        
        for attempt in range(max_retries):
            try:
                # Disconnect existing connection
                self.DaqThread.disconnectDaq()
                sleep(0.5)
                
                # Attempt to reconnect
                reconnected = self.DaqThread.ConnectDaq()
                
                if reconnected:
                    break
                else:
                    if attempt < max_retries - 1:
                        self.messagesBox.appendHtml(f'<p style="color:orange;">Reconnection attempt {attempt + 1} failed, retrying...</p>')
                        sleep(0.5)
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    self.messagesBox.appendHtml(f'<p style="color:orange;">Connection error: {e}, retrying...</p>')
                    sleep(0.5)
                continue
        
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
        
        # Check I channel initial state
        if not self.check_i_channel_initial_state():
            QtWidgets.QMessageBox.warning(self, "Inductive Sensor Warning",
                "The inductive sensor (I channel) is currently in HIGH state.\n\n"
                "The signal must be LOW before starting monitoring.\n\n"
                "Please ensure the trigger/sensor is in its inactive state and try again.")
            self.messagesBox.appendHtml('<p style="color:red;">Cannot start: I channel is HIGH. Must be LOW to start.</p>')
            return
        
        # Proceed with session setup
        self.reset_Data_n_Plot_Vars()
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

        self.stopButton.setEnabled(True)
        #Monitoring message:
        self.messagesBox.appendHtml('<p>Monitoring with unit conversion...</p>')
        self.graphThread.start()
        self.startSig.emit()
        self.is_monitoring = True  # Add this line

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
            # Check I channel initial state
            if not self.check_i_channel_initial_state():
                QtWidgets.QMessageBox.warning(self, "Inductive Sensor Warning",
                    "The inductive sensor (I channel) is currently in HIGH state.\n\n"
                    "The signal must be LOW before starting monitoring.\n\n"
                    "Please ensure the trigger/sensor is in its inactive state and try again.")
                self.messagesBox.appendHtml('<p style="color:red;">Cannot start: I channel is HIGH. Must be LOW to start.</p>')
                return
            
            self.reset_Data_n_Plot_Vars()

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

            self.stopButton.setEnabled(True)
            self.graphThread.start()
            self.startSig.emit()
            self.is_monitoring = True  # Add this line

            #Monitoring message:
            self.messagesBox.appendHtml('<p>Monitoring with unit conversion...</p>')
        else:
            self.startButton.setEnabled(False)
            self.configurationButton.setEnabled(True)
            self.messagesBox.appendHtml('<p style="color:red;">DAQ not connected!</p>')

    def ploter(self, xpoints, ypoints):
        '''
        Plot data points with dual-axis support for temperature and pressure.
        I channel is handled separately with arrows.
        '''
        plot_count = getattr(self, 'plot_count', 0) + 1
        self.plot_count = plot_count
        
        if plot_count % 100 == 0:
            print(f"Ploter called: X points: {len(xpoints)}, Y channels: {len(ypoints)}")
            if ypoints and len(ypoints) > 0:
                print(f"Latest Y values: {[y[-1] if y and len(y) > 0 else 'empty' for y in ypoints]}")
        
        if self.separate_plots:
            # Multiple subplots mode - exclude I channel
            plot_idx = 0
            for i in range(min(len(self.ydata_plts), len(ypoints))):
                # Skip I channel in separate plots mode
                if i < len(self.channel_types) and self.channel_types[i] == 'I':
                    continue
                if plot_idx < len(self.plotDataItem_lst) and len(self.plotDataItem_lst[plot_idx]) > 0:
                    if len(ypoints[i]) > 0 and len(xpoints) > 0:
                        color = self.get_channel_color(i)
                        self.plotDataItem_lst[plot_idx][0].setData(xpoints, ypoints[i], pen=pg.mkPen(color, width=2))
                plot_idx += 1
            
            # Update X-axis range for separate plots
            if len(xpoints) > 0 and len(self.splotlist) > 0:
                if self.cycle_mode:
                    current_max = xpoints[-1]
                    if current_max > self.cycle_max_x:
                        self.cycle_max_x = current_max
                    for sp in self.splotlist:
                        sp.setXRange(0, self.cycle_max_x * 1.05, padding=0)
                else:
                    for sp in self.splotlist:
                        sp.setXRange(xpoints[0], xpoints[-1], padding=0.02)
        else:
            # Dual-axis mode
            if len(self.splotlist) >= 1:
                # Get indices for temperature and pressure channels (exclude I)
                temp_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'T']
                pressure_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'P']
                
                # Plot temperature channels on left axis
                for i in temp_indices:
                    if i < len(ypoints) and i < len(self.plotDataItem_lst) and len(self.plotDataItem_lst[i]) > 0:
                        if len(ypoints[i]) > 0 and len(xpoints) > 0:
                            color = self.get_channel_color(i)
                            self.plotDataItem_lst[i][0].setData(xpoints, ypoints[i], pen=pg.mkPen(color, width=2))
                
                # Plot pressure channels on right axis
                if hasattr(self, 'right_viewbox') and self.right_viewbox is not None:
                    for i in pressure_indices:
                        if i < len(ypoints) and i < len(self.plotDataItem_lst) and len(self.plotDataItem_lst[i]) > 0:
                            if len(ypoints[i]) > 0 and len(xpoints) > 0:
                                color = self.get_channel_color(i)
                                self.plotDataItem_lst[i][0].setData(xpoints, ypoints[i], pen=pg.mkPen(color, width=2))
                
                # Update X-axis range
                if len(xpoints) > 0:
                    if self.cycle_mode:
                        # In cycle mode, start from 0 and expand to max of current cycle or previous max
                        current_max = xpoints[-1]
                        if current_max > self.cycle_max_x:
                            self.cycle_max_x = current_max
                        self.splotlist[0].setXRange(0, self.cycle_max_x * 1.05, padding=0)
                    else:
                        # Normal scrolling mode
                        self.splotlist[0].setXRange(xpoints[0], xpoints[-1], padding=0.02)

    def updateArrows(self, transitions, x_min, x_max):
        """
        Update the arrow display for I channel transitions.
        Shows vertical green lines from top to bottom with arrow heads indicating direction.
        transitions: list of (x_time, 'UP' or 'DOWN') tuples
        """
        if self.i_arrow_scatter is None or len(self.splotlist) == 0:
            return
        
        # Filter transitions to only show those in the current X range
        visible_transitions = [(x, direction) for x, direction in transitions 
                               if x_min <= x <= x_max]
        
        if not visible_transitions:
            self.i_arrow_scatter.setData([], [])
            if hasattr(self, 'i_lines_item') and self.i_lines_item is not None:
                self.i_lines_item.setData([], [])
            return
        
        # Get Y range for the lines and arrows
        if hasattr(self, 'splotlist') and len(self.splotlist) > 0:
            y_range = self.splotlist[0].viewRange()[1]
            y_bottom = y_range[0]
            y_top = y_range[1]
            # Add small margin so arrows don't touch the edges
            y_margin = (y_top - y_bottom) * 0.05
            y_bottom_arrow = y_bottom + y_margin
            y_top_arrow = y_top - y_margin
        else:
            y_bottom = 0
            y_top = 100
            y_bottom_arrow = 5
            y_top_arrow = 95
        
        # Prepare line data (vertical lines from bottom to top, NaN-separated)
        line_x = []
        line_y = []
        
        # Prepare arrow head data
        arrow_x = []
        arrow_y = []
        arrow_symbols = []
        
        for x_time, direction in visible_transitions:
            # Add vertical line segment (with NaN separator for disconnected segments)
            line_x.extend([x_time, x_time, np.nan])
            line_y.extend([y_bottom_arrow, y_top_arrow, np.nan])
            
            # Add arrow head at appropriate end
            arrow_x.append(x_time)
            if direction == 'UP':
                arrow_y.append(y_top_arrow)
                arrow_symbols.append('t1')  # Triangle pointing up
            else:  # DOWN
                arrow_y.append(y_bottom_arrow)
                arrow_symbols.append('t')  # Triangle pointing down
        
        # Update vertical lines (all green)
        if hasattr(self, 'i_lines_item') and self.i_lines_item is not None:
            self.i_lines_item.setData(line_x, line_y)
        
        # Update arrow heads (all green)
        self.i_arrow_scatter.setData(
            x=arrow_x, 
            y=arrow_y, 
            symbol=arrow_symbols, 
            brush=pg.mkBrush('#00FF00'),  # Green
            size=15,
            pen=pg.mkPen(None)
        )

    def onCycleWaiting(self):
        """Handle waiting for first cycle signal."""
        self.messagesBox.appendHtml('<p style="color:orange;">Waiting for I signal to go HIGH to start cycle 1...</p>')
        if self.cycle_label is not None:
            self.cycle_label.setText("Waiting...")

    def onCycleStarted(self, cycle_num):
        """Handle cycle started signal."""
        self.current_cycle = cycle_num
        self.messagesBox.appendHtml(f'<p style="color:green;">Cycle {cycle_num} started</p>')
        if self.cycle_label is not None:
            self.cycle_label.setText(f"Cycle {cycle_num}")

    def onCycleEnded(self, cycle_num, xdata, ydata):
        """
        Handle cycle ended signal.
        Create ghost plots for the completed cycle with transparency.
        """
        self.messagesBox.appendHtml(f'<p>Cycle {cycle_num} ended (duration: {xdata[-1]:.2f}s)</p>' if xdata else f'<p>Cycle {cycle_num} ended</p>')
        
        # Store completed cycle data
        self.completed_cycles_data.append((xdata, ydata))
        
        # Update max X if this cycle was longer
        if xdata and xdata[-1] > self.cycle_max_x:
            self.cycle_max_x = xdata[-1]
            # Update X-axis range
            if len(self.splotlist) > 0:
                self.splotlist[0].setXRange(0, self.cycle_max_x * 1.05, padding=0)
        
        # Create ghost plots for completed cycle
        self.createGhostPlots(xdata, ydata, cycle_num)

    def createGhostPlots(self, xdata, ydata, cycle_num):
        """
        Create semi-transparent plot items for a completed cycle.
        """
        if not xdata or not ydata:
            return
        
        alpha = 80  # Transparency level (0-255, lower = more transparent)
        
        # Get indices for temperature and pressure channels (exclude I)
        temp_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'T']
        pressure_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'P']
        
        ghost_plots = []
        
        if self.separate_plots:
            # Separate plots mode
            plot_idx = 0
            for i in range(len(self.channel_types)):
                if self.channel_types[i] == 'I':
                    continue
                if plot_idx < len(self.splotlist) and i < len(ydata):
                    color = self.get_channel_color(i)
                    # Create color with alpha
                    color_with_alpha = pg.mkColor(color)
                    color_with_alpha.setAlpha(alpha)
                    pen = pg.mkPen(color_with_alpha, width=1)
                    
                    ghost_item = pg.PlotDataItem(xdata, ydata[i], pen=pen)
                    self.splotlist[plot_idx].addItem(ghost_item)
                    ghost_plots.append(ghost_item)
                plot_idx += 1
        else:
            # Dual-axis mode
            if len(self.splotlist) > 0:
                main_plot = self.splotlist[0]
                
                # Add ghost plots for temperature channels
                for i in temp_indices:
                    if i < len(ydata):
                        color = self.get_channel_color(i)
                        color_with_alpha = pg.mkColor(color)
                        color_with_alpha.setAlpha(alpha)
                        pen = pg.mkPen(color_with_alpha, width=1)
                        
                        ghost_item = pg.PlotDataItem(xdata, ydata[i], pen=pen)
                        main_plot.addItem(ghost_item)
                        ghost_plots.append(ghost_item)
                
                # Add ghost plots for pressure channels on right axis
                if hasattr(self, 'right_viewbox') and self.right_viewbox is not None:
                    for i in pressure_indices:
                        if i < len(ydata):
                            color = self.get_channel_color(i)
                            color_with_alpha = pg.mkColor(color)
                            color_with_alpha.setAlpha(alpha)
                            pen = pg.mkPen(color_with_alpha, width=1)
                            
                            ghost_item = pg.PlotDataItem(xdata, ydata[i], pen=pen)
                            self.right_viewbox.addItem(ghost_item)
                            ghost_plots.append(ghost_item)
        
        self.completed_cycles_plots.append(ghost_plots)

    def _updateCycleLabelPosition(self):
        """Update cycle label position to stay in top-right corner of plot."""
        if self.cycle_label is None or len(self.splotlist) == 0:
            return
        try:
            view_range = self.splotlist[0].viewRange()
            x_max = view_range[0][1]
            y_max = view_range[1][1]
            self.cycle_label.setPos(x_max, y_max)
        except:
            pass

    def updateXAxisRange(self, x_min, x_max):
        '''
        Update X-axis range (used during waiting mode in cycle mode).
        '''
        if len(self.splotlist) > 0:
            self.splotlist[0].setXRange(x_min, x_max, padding=0)

    def updateYAxisRanges(self, y_mins, y_maxs):
        '''
        Update Y-axis ranges with separate handling for temperature and pressure axes.
        '''
        if self.separate_plots:
            # Multiple subplots mode
            for i in range(min(len(self.splotlist), len(y_mins), len(y_maxs))):
                if i < len(self.splotlist):
                    self.splotlist[i].setYRange(y_mins[i], y_maxs[i], padding=0)
        else:
            # Dual-axis mode
            if len(self.splotlist) > 0:
                # Get indices for temperature and pressure channels (exclude I)
                temp_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'T']
                pressure_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'P']
                
                # Update left axis (temperature) range
                if temp_indices:
                    temp_mins = [y_mins[i] for i in temp_indices if i < len(y_mins)]
                    temp_maxs = [y_maxs[i] for i in temp_indices if i < len(y_maxs)]
                    if temp_mins and temp_maxs:
                        self.splotlist[0].setYRange(min(temp_mins), max(temp_maxs), padding=0)
                
                # Update right axis (pressure) range
                if hasattr(self, 'right_viewbox') and self.right_viewbox is not None and pressure_indices:
                    pressure_mins = [y_mins[i] for i in pressure_indices if i < len(y_mins)]
                    pressure_maxs = [y_maxs[i] for i in pressure_indices if i < len(y_maxs)]
                    if pressure_mins and pressure_maxs:
                        self.right_viewbox.setYRange(min(pressure_mins), max(pressure_maxs), padding=0)

    def receiveXYData(self, xvals, yvals, yvals_raw, cycle_numbers):
        '''
        Receive DAQ collected data after monitoring stops (both converted and raw).
        '''
        self.xdata = xvals
        self.ydata = yvals
        self.ydata_raw = yvals_raw
        self.cycle_numbers_data = cycle_numbers if cycle_numbers else []

    def reset_Data_n_Plot_Vars(self):
        '''
        Reset data storage variables and plot/subplot related lists.
        '''
        # Properly clear dual-axis plot items before clearing canvas
        if hasattr(self, 'right_viewbox') and self.right_viewbox is not None:
            for item in self.right_viewbox.allChildren():
                if hasattr(item, 'scene') and item.scene() is not None:
                    item.scene().removeItem(item)
            
            if hasattr(self.right_viewbox, 'scene') and self.right_viewbox.scene() is not None:
                self.right_viewbox.scene().removeItem(self.right_viewbox)
            
            self.right_viewbox = None

        # Clear the main canvas
        self.GraphArea.canvas.clear()

        self.xdata = []
        self.ydata = []
        self.ydata_raw = []
        self.cycle_numbers_data = []
        self.splotlist = []
        self.plotDataItem_lst = []
        self.xdata_plts = []
        self.ydata_plts = []
        
        # Reset I channel state
        self.i_channel_state = None
        self.i_channel_transitions = []
        self.i_channel_digital_values = []
        self.i_arrow_scatter = None
        self.i_lines_item = None
        
        # Reset cycle mode state
        self.current_cycle = 0
        self.cycle_max_x = 0
        self.completed_cycles_data = []
        self.completed_cycles_plots = []
        self.cycle_label = None

        for n in range(self.nplots):
            self.ydata_plts.append([])
            self.plotDataItem_lst.append([])

    def SubplotSetup(self):
        '''
        Initialize and setup subplots with dual-axis support for temperature/pressure.
        I channel is displayed as arrows, not as a line plot.
        '''
        # Get indices for temperature and pressure channels (exclude I)
        temp_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'T']
        pressure_indices = [i for i in range(len(self.channel_types)) if self.channel_types[i] == 'P']
        
        has_temp = len(temp_indices) > 0
        has_pressure = len(pressure_indices) > 0
        
        # Count non-I channels for separate plots mode
        non_i_count = len([ct for ct in self.channel_types if ct != 'I'])
        
        if self.separate_plots:
            # Multiple subplots mode - exclude I channel
            rows_cols = [[1,1],[1,2],[2,2],[2,2]]
            if non_i_count > 0:
                idx = min(non_i_count - 1, 3)
                n_rows = rows_cols[idx][0]
                n_cols = rows_cols[idx][1]
            else:
                n_rows = 1
                n_cols = 1
            
            sens_count = 0
            for i in range(n_rows):
                for j in range(n_cols):
                    sens_count += 1
                    if sens_count <= non_i_count:
                        self.splotlist.append(self.GraphArea.canvas.addPlot(i, j))

            plot_idx = 0
            for it in range(len(self.channel_types)):
                # Skip I channel
                if self.channel_types[it] == 'I':
                    continue
                    
                if plot_idx < len(self.splotlist):
                    color = self.get_channel_color(it)
                    self.plotDataItem_lst[plot_idx].append(self.splotlist[plot_idx].plot(pen=pg.mkPen(color, width=2)))
                    self.splotlist[plot_idx].getAxis("bottom").setStyle(tickTextOffset = 5, tickTextHeight = 9)
                    self.splotlist[plot_idx].setLabel('left', self.get_y_label(it))
                    self.splotlist[plot_idx].setLabel('bottom', 'Time [s]')
                    
                    # Add legend for this subplot
                    legend = self.splotlist[plot_idx].addLegend(offset=(10, 10))
                    legend.addItem(self.plotDataItem_lst[plot_idx][0], self.get_channel_label(it))
                    
                    # Disable auto-ranging on Y-axis
                    self.splotlist[plot_idx].enableAutoRange(axis='y', enable=False)
                    
                    # Set initial Y-axis range based on channel type
                    if self.channel_types[it] == 'T':
                        self.splotlist[plot_idx].setYRange(0, 100, padding=0)
                    else:  # P
                        self.splotlist[plot_idx].setYRange(0, 10, padding=0)

                    self.splotlist[plot_idx].enableAutoRange(axis='x', enable=False)
                    self.splotlist[plot_idx].setXRange(0, 10, padding=0)
                    
                    plot_idx += 1
            
            # Add arrow scatter plot and vertical lines to the first subplot for I channel
            if self.i_channel_index is not None and len(self.splotlist) > 0:
                # Vertical lines for transitions
                self.i_lines_item = pg.PlotDataItem(pen=pg.mkPen('#00FF00', width=2), connect='finite')
                self.splotlist[0].addItem(self.i_lines_item)
                # Arrow heads
                self.i_arrow_scatter = pg.ScatterPlotItem()
                self.splotlist[0].addItem(self.i_arrow_scatter)
        else:
            # Dual-axis mode - always create both axes
            main_plot = self.GraphArea.canvas.addPlot(0, 0)
            self.splotlist.append(main_plot)

            # Disable X-axis auto-range and set fixed initial range
            main_plot.enableAutoRange(axis='x', enable=False)
            main_plot.setXRange(0, 10, padding=0)
            
            # Configure left Y-axis (Temperature)
            if has_temp:
                main_plot.setLabel('left', 'Temperature [°C]', color='#FF0000')
                main_plot.getAxis("left").setPen(pg.mkPen('#FF0000', width=2))
            else:
                main_plot.setLabel('left', 'Temperature [°C] (unused)', color='#888888')
                main_plot.getAxis("left").setPen(pg.mkPen('#888888', width=1))
            
            main_plot.setLabel('bottom', 'Time [s]')
            main_plot.getAxis("bottom").setStyle(tickTextOffset = 5, tickTextHeight = 9)
            
            # Create right Y-axis (Pressure)
            self.right_viewbox = pg.ViewBox()
            main_plot.showAxis('right')
            main_plot.scene().addItem(self.right_viewbox)
            main_plot.getAxis('right').linkToView(self.right_viewbox)
            self.right_viewbox.setXLink(main_plot)
            
            if has_pressure:
                main_plot.setLabel('right', 'Pressure [bar]', color='#0000FF')
                main_plot.getAxis("right").setPen(pg.mkPen('#0000FF', width=2))
            else:
                main_plot.setLabel('right', 'Pressure [bar] (unused)', color='#888888')
                main_plot.getAxis("right").setPen(pg.mkPen('#888888', width=1))
            
            # Create legend at top-right (with offset to not touch pressure Y-axis)
            # Note: I channel is excluded from legend
            legend = pg.LegendItem(offset=(-80, 10))
            legend.setParentItem(main_plot.graphicsItem())
            
            # Add temperature plots to left axis
            for i in temp_indices:
                color = self.get_channel_color(i)
                plot_item = main_plot.plot(pen=pg.mkPen(color, width=2), name=self.get_channel_label(i))
                self.plotDataItem_lst[i].append(plot_item)
                legend.addItem(plot_item, self.get_channel_label(i))
            
            # Add pressure plots to right axis
            for i in pressure_indices:
                color = self.get_channel_color(i)
                plot_item = pg.PlotDataItem(pen=pg.mkPen(color, width=2), name=self.get_channel_label(i))
                self.right_viewbox.addItem(plot_item)
                self.plotDataItem_lst[i].append(plot_item)
                legend.addItem(plot_item, self.get_channel_label(i))
            
            # Add scatter plot and vertical lines for I channel arrows (no legend, no Y axis)
            if self.i_channel_index is not None:
                # Vertical lines for transitions
                self.i_lines_item = pg.PlotDataItem(pen=pg.mkPen('#00FF00', width=2), connect='finite')
                main_plot.addItem(self.i_lines_item)
                # Arrow heads
                self.i_arrow_scatter = pg.ScatterPlotItem()
                main_plot.addItem(self.i_arrow_scatter)
            
            # Function to update right viewbox geometry
            def updateViews():
                self.right_viewbox.setGeometry(main_plot.vb.sceneBoundingRect())
                self.right_viewbox.linkedViewChanged(main_plot.vb, self.right_viewbox.XAxis)
            
            updateViews()
            main_plot.vb.sigResized.connect(updateViews)
            
            # Set initial ranges
            main_plot.enableAutoRange(axis='y', enable=False)
            main_plot.setYRange(0, 100, padding=0)  # Temperature range
            self.right_viewbox.enableAutoRange(axis='y', enable=False) 
            self.right_viewbox.setYRange(0, 10, padding=0)  # Pressure range

        # Add cycle label if in cycle mode
        if self.cycle_mode and len(self.splotlist) > 0:
            self.cycle_label = pg.TextItem(text="", anchor=(1, 0), color='#666666')
            self.cycle_label.setFont(QtGui.QFont('Arial', 9))
            self.splotlist[0].addItem(self.cycle_label)
            # Position will be updated when plot range changes
            self.cycle_label.setPos(0, 0)
            # Connect to view range change to update label position
            self.splotlist[0].sigRangeChanged.connect(self._updateCycleLabelPosition)

        self.show()

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

        self.DaqThread = DaqThread(self.daq_channels, self.voltage_ranges, 
                                   self.daq_dec, self.daq_deca, self.daq_srate, 
                                   self.dataQueue, self.sensors[:self.nplots])
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

    def cnfg_Sig_Received(self, timeint, channels, voltage_ranges, channel_types, srate, dec, n_points, refresh_rate, separate_plots, cycle_mode):
        '''
        Store DAQ configuration values
        '''
        self.time_lim = timeint
        self.daq_channels = channels
        self.voltage_ranges = voltage_ranges
        self.channel_types = channel_types
        self.daq_srate = srate
        self.daq_dec = dec
        self.n_display_points = n_points
        self.plot_refresh_rate = refresh_rate
        self.separate_plots = separate_plots
        self.cycle_mode = cycle_mode
        self.nplots = len(channels)
        self.sensors = [f'CH{ch}' for ch in channels]
        
        # Update I channel index
        self._update_i_channel_index()
        
        # Reset plot data structures for new number of channels
        self.plotDataItem_lst = []
        self.ydata_plts = []
        for n in range(self.nplots):
            self.plotDataItem_lst.append([])
            self.ydata_plts.append([])
        
        self.config_message(timeint, channels, voltage_ranges, channel_types, srate, dec, n_points, refresh_rate, separate_plots, cycle_mode)
        self.findDeviceButton.setEnabled(True)

    def config_message(self, timeint, channels, voltage_ranges, channel_types, srate, dec, n_points, refresh_rate, separate_plots, cycle_mode):
        '''
        Display configuration message
        '''
        self.messagesBox.appendHtml('<p>Configuration:</p>')
        self.messagesBox.appendHtml('<p>Operation mode: DAQ monitoring with unit conversion</p>')
        self.messagesBox.appendHtml('<p>Monitoring time: %ds</p>' %timeint)
        self.messagesBox.appendHtml('<p>Channels: %s</p>' %channels)
        self.messagesBox.appendHtml('<p>Channel types: %s</p>' %channel_types)
        self.messagesBox.appendHtml('<p>Voltage ranges: %s</p>' %voltage_ranges)
        self.messagesBox.appendHtml('<p>Sample rate: %d Hz</p>' %srate)
        self.messagesBox.appendHtml('<p>Decimation: %d</p>' %dec)
        self.messagesBox.appendHtml('<p>Display points: %d</p>' %n_points)
        self.messagesBox.appendHtml('<p>Plot refresh rate: %.1f ms</p>' %refresh_rate)
        
        # Count channel types
        temp_count = sum(1 for t in channel_types if t == 'T')
        pressure_count = sum(1 for t in channel_types if t == 'P')
        inductive_count = sum(1 for t in channel_types if t == 'I')
        
        plot_mode = "Separate plots" if separate_plots else f"Dual-axis ({temp_count} Temp, {pressure_count} Pressure)"
        if inductive_count > 0:
            plot_mode += f" + {inductive_count} Inductive"
        self.messagesBox.appendHtml('<p>Plot layout: %s</p>' %plot_mode)
        self.messagesBox.appendHtml('<p>Unit conversion: T→°C, P→bar, I→0/1</p>')
        
        if cycle_mode:
            self.messagesBox.appendHtml('<p style="color:green;">Cycle mode: ENABLED (I signal controls cycles)</p>')


# DAQ thread: ############################################################################
##########################################################################################
class DaqThread(QtCore.QThread):
    ConnectSig = QtCore.pyqtSignal(bool)
    readQueueSig = QtCore.pyqtSignal()
    readErrorSig = QtCore.pyqtSignal()

    def __init__(self, channels, voltage_ranges, dec, deca, srate, dataQueue, sensors, parent = None):
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
                output_mode=output_mode
            )
            
            # Configure the DAQ
            self.daq_device.config_daq()
            
            # Record connection time and reset counters
            self.connection_time = perf_counter()
            self.last_keepalive = perf_counter()
            self.reconnect_attempts = 0
            
            print("DAQ connected successfully")
            self.ConnectSig.emit(True)
            self.IsConnected = True
            return True
            
        except Exception as e:
            print(f"DAQ connection error: {e}")
            self.ConnectSig.emit(False)
            self.IsConnected = False
            return False

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
                    print(f"DAQ thread error: {e}")
                    self.readErrorSig.emit()
                    break
                
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
                print(f"Error closing DAQ: {e}")

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
                
                return ydata_lst
            else:
                return None
                
        except Exception as e:
            print(f"DAQ read error: {e}")
            raise


# DAQ Configuration Window with Table-based Channel Selection
class DaqConfigWindow(QtWidgets.QDialog):
    configSignal = QtCore.pyqtSignal(float, list, list, list, int, int, int, float, bool, bool)
    
    def __init__(self, parent=None):
        super(DaqConfigWindow, self).__init__(parent)
        self.setWindowTitle("DAQ Configuration")
        self.setModal(True)
        
        # Fixed channels: CH0 to CH4
        self.available_channels = [0, 1, 2, 3, 4]
        self.num_channels = len(self.available_channels)
        
        # Storage for table widgets
        self.channel_checkboxes = {}
        self.channel_type_combos = {}
        self.voltage_range_edits = {}
        
        self.setupUi()
        self.loadDefaults()
        
        # Adjust window size to fit content
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def setupUi(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)
        
        # ============== DAQ Settings (on top) ==============
        daq_group = QtWidgets.QGroupBox("DAQ Settings")
        daq_layout = QtWidgets.QGridLayout()
        
        # Row 0: Monitoring Time
        daq_layout.addWidget(QtWidgets.QLabel("Monitoring Time (s):"), 0, 0)
        self.timeEdit = QtWidgets.QLineEdit()
        self.timeEdit.setToolTip("Duration of monitoring session in seconds")
        daq_layout.addWidget(self.timeEdit, 0, 1)
        
        # Row 1: Sample Rate
        daq_layout.addWidget(QtWidgets.QLabel("Sample Rate (Hz):"), 1, 0)
        self.srateEdit = QtWidgets.QLineEdit()
        self.srateEdit.setToolTip("Sampling rate in Hz")
        daq_layout.addWidget(self.srateEdit, 1, 1)
        
        # Row 2: Decimation
        daq_layout.addWidget(QtWidgets.QLabel("Decimation (dec):"), 2, 0)
        self.decEdit = QtWidgets.QLineEdit()
        self.decEdit.setToolTip("Decimation factor for data reduction")
        daq_layout.addWidget(self.decEdit, 2, 1)
        
        daq_group.setLayout(daq_layout)
        layout.addWidget(daq_group)
        
        # ============== Channel Configuration Table ==============
        channel_group = QtWidgets.QGroupBox("Channel Configuration")
        channel_layout = QtWidgets.QVBoxLayout()
        
        # Create the table
        self.channelTable = QtWidgets.QTableWidget()
        self.channelTable.setRowCount(3)  # Enable, Type, Voltage Range
        self.channelTable.setColumnCount(self.num_channels)
        
        # Set column headers (channel numbers)
        headers = [f"CH {ch}" for ch in self.available_channels]
        self.channelTable.setHorizontalHeaderLabels(headers)
        
        # Set row headers
        self.channelTable.setVerticalHeaderLabels(["Enable", "Type", "Voltage Range"])
        
        # Populate the table
        for col, ch_num in enumerate(self.available_channels):
            # Row 0: Checkbox for channel enable
            checkbox_widget = QtWidgets.QWidget()
            checkbox_layout = QtWidgets.QHBoxLayout(checkbox_widget)
            checkbox_layout.setAlignment(QtCore.Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox = QtWidgets.QCheckBox()
            checkbox.setToolTip(f"Enable/disable channel {ch_num}")
            checkbox_layout.addWidget(checkbox)
            self.channelTable.setCellWidget(0, col, checkbox_widget)
            self.channel_checkboxes[ch_num] = checkbox
            
            # Row 1: ComboBox for channel type (T, P, I)
            combo_widget = QtWidgets.QWidget()
            combo_layout = QtWidgets.QHBoxLayout(combo_widget)
            combo_layout.setAlignment(QtCore.Qt.AlignCenter)
            combo_layout.setContentsMargins(2, 2, 2, 2)
            combo = QtWidgets.QComboBox()
            combo.addItems(["T", "P", "I"])
            combo.setToolTip("T=Temperature, P=Pressure, I=Inductive (trigger)")
            combo_layout.addWidget(combo)
            self.channelTable.setCellWidget(1, col, combo_widget)
            self.channel_type_combos[ch_num] = combo
            
            # Row 2: LineEdit for voltage range
            edit_widget = QtWidgets.QWidget()
            edit_layout = QtWidgets.QHBoxLayout(edit_widget)
            edit_layout.setAlignment(QtCore.Qt.AlignCenter)
            edit_layout.setContentsMargins(2, 2, 2, 2)
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(50)
            edit.setToolTip(f"Voltage range for channel {ch_num}")
            edit_layout.addWidget(edit)
            self.channelTable.setCellWidget(2, col, edit_widget)
            self.voltage_range_edits[ch_num] = edit
        
        # Adjust table appearance - fit to content without scrollbars
        self.channelTable.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.channelTable.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.channelTable.verticalHeader().setDefaultSectionSize(30)
        self.channelTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.channelTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        # Calculate exact height needed for the table (header + 3 rows + frame)
        header_height = self.channelTable.horizontalHeader().height()
        row_height = 30  # Fixed row height
        total_rows = 3
        frame_margin = 4
        self.channelTable.setFixedHeight(header_height + (row_height * total_rows) + frame_margin)
        
        channel_layout.addWidget(self.channelTable)
        channel_group.setLayout(channel_layout)
        layout.addWidget(channel_group)
        
        # ============== Display Settings ==============
        display_group = QtWidgets.QGroupBox("Display Settings")
        display_layout = QtWidgets.QGridLayout()
        
        # Points to Display
        display_layout.addWidget(QtWidgets.QLabel("Points to Display:"), 0, 0)
        self.pointsEdit = QtWidgets.QLineEdit()
        self.pointsEdit.setToolTip(
            "Number of data points visible on the plot\n"
            "• Higher values = longer time window\n"
            "• Lower values = shorter time window\n"
            "• Typical range: 50-500"
        )
        display_layout.addWidget(self.pointsEdit, 0, 1)
        
        # Plot Refresh Rate
        display_layout.addWidget(QtWidgets.QLabel("Plot Refresh Rate (ms):"), 1, 0)
        self.refreshEdit = QtWidgets.QLineEdit()
        self.refreshEdit.setToolTip(
            "How often the plot updates in milliseconds\n"
            "• Lower values = smoother animation\n"
            "• Higher values = lower CPU usage\n"
            "• Typical range: 25-100 ms"
        )
        display_layout.addWidget(self.refreshEdit, 1, 1)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # ============== Plot Layout Options (includes cycle mode) ==============
        plot_group = QtWidgets.QGroupBox("Plot Layout")
        plot_layout = QtWidgets.QVBoxLayout()
        
        self.dualAxisRadio = QtWidgets.QRadioButton("Dual-axis plot (Temperature on left, Pressure on right)")
        self.dualAxisRadio.setToolTip(
            "All channels in one plot with two Y-axes:\n"
            "• Left Y-axis: Temperature channels (warm colors)\n"
            "• Right Y-axis: Pressure channels (cold colors)\n"
            "• I channel: Arrows for trigger events"
        )
        
        self.separatePlotsRadio = QtWidgets.QRadioButton("Separate plots for each channel")
        self.separatePlotsRadio.setToolTip(
            "Each channel in its own subplot\n"
            "(I channel excluded, shown as arrows on first plot)"
        )
        
        # Cycle mode checkbox inside plot layout group
        self.cycleModeCheckbox = QtWidgets.QCheckBox("Use I signal for cycle control")
        self.cycleModeCheckbox.setToolTip(
            "When enabled, the I channel controls data acquisition cycles:\n"
            "• Plot starts when I goes LOW→HIGH (cycle 1 begins)\n"
            "• Data acquisition pauses when I goes LOW\n"
            "• Each new LOW→HIGH transition starts a new cycle\n"
            "• All cycles overlay on the same plot (X resets to 0)\n"
            "• Previous cycles shown with transparency\n"
            "• Data saved with cycle number column"
        )
        
        plot_layout.addWidget(self.dualAxisRadio)
        plot_layout.addWidget(self.separatePlotsRadio)
        plot_layout.addWidget(self.cycleModeCheckbox)
        plot_group.setLayout(plot_layout)
        layout.addWidget(plot_group)
        
        # ============== Buttons ==============
        button_layout = QtWidgets.QHBoxLayout()
        self.okButton = QtWidgets.QPushButton("OK")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self.okButton)
        button_layout.addWidget(self.cancelButton)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signals
        self.okButton.clicked.connect(self.accept_config)
        self.cancelButton.clicked.connect(self.close)

    def loadDefaults(self):
        """Load default values from CONFIG_DEFAULTS into the UI."""
        # DAQ Settings
        self.timeEdit.setText(str(CONFIG_DEFAULTS['monitoring_time_s']))
        self.srateEdit.setText(str(CONFIG_DEFAULTS['sample_rate_hz']))
        self.decEdit.setText(str(CONFIG_DEFAULTS['decimation']))
        
        # Display Settings
        self.pointsEdit.setText(str(CONFIG_DEFAULTS['display_points']))
        self.refreshEdit.setText(str(CONFIG_DEFAULTS['plot_refresh_rate_ms']))
        
        # Plot Layout
        if CONFIG_DEFAULTS['separate_plots']:
            self.separatePlotsRadio.setChecked(True)
        else:
            self.dualAxisRadio.setChecked(True)
        
        # Channel Configuration from defaults
        default_channels = CONFIG_DEFAULTS['channels']
        default_types = CONFIG_DEFAULTS['channel_types']
        default_voltages = CONFIG_DEFAULTS['voltage_ranges']
        
        # First, set all channels to unchecked and default values
        for ch_num in self.available_channels:
            self.channel_checkboxes[ch_num].setChecked(False)
            self.channel_type_combos[ch_num].setCurrentText("T")
            self.voltage_range_edits[ch_num].setText("10")
        
        # Then, enable and configure channels from defaults
        for i, ch_num in enumerate(default_channels):
            if ch_num in self.channel_checkboxes:
                self.channel_checkboxes[ch_num].setChecked(True)
                
                # Set channel type
                if i < len(default_types):
                    ch_type = default_types[i].upper()
                    if ch_type in ['T', 'P', 'I']:
                        self.channel_type_combos[ch_num].setCurrentText(ch_type)
                
                # Set voltage range
                if i < len(default_voltages):
                    self.voltage_range_edits[ch_num].setText(str(default_voltages[i]))
        
        # Cycle mode
        self.cycleModeCheckbox.setChecked(CONFIG_DEFAULTS.get('cycle_mode', True))

    def accept_config(self):
        """Validate and emit configuration signal."""
        try:
            # Get DAQ settings
            timeint = float(self.timeEdit.text())
            srate = int(self.srateEdit.text())
            dec = int(self.decEdit.text())
            
            # Get display settings
            n_points = int(self.pointsEdit.text())
            refresh_rate = float(self.refreshEdit.text())
            
            # Get selected channels and their configuration
            channels = []
            channel_types = []
            voltage_ranges = []
            i_count = 0
            
            for ch_num in self.available_channels:
                if self.channel_checkboxes[ch_num].isChecked():
                    channels.append(ch_num)
                    
                    ch_type = self.channel_type_combos[ch_num].currentText()
                    channel_types.append(ch_type)
                    
                    if ch_type == 'I':
                        i_count += 1
                    
                    try:
                        voltage = float(self.voltage_range_edits[ch_num].text())
                        voltage_ranges.append(voltage)
                    except ValueError:
                        QtWidgets.QMessageBox.warning(
                            self, "Error",
                            f"Invalid voltage range for CH{ch_num}.\n"
                            "Please enter a valid number."
                        )
                        return
            
            # Validation: At least one channel must be selected
            if len(channels) == 0:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "No channels selected!\n\n"
                    "Please select at least one channel to monitor."
                )
                return
            
            # Validation: Only one I channel allowed
            if i_count > 1:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    f"Only ONE Inductive (I) channel is allowed.\n\n"
                    f"You have selected {i_count} I channels.\n\n"
                    "Please change the type for some channels."
                )
                return
            
            # Validation: Display points range
            if n_points < 10 or n_points > 2000:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Points to display must be between 10 and 2000."
                )
                return
            
            # Validation: Refresh rate range
            if refresh_rate < 10 or refresh_rate > 1000:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Refresh rate must be between 10 and 1000 ms."
                )
                return
            
            # Validation: Number of channels
            if len(channels) > 8:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Maximum 8 channels can be selected."
                )
                return
            
            # Get other settings
            separate_plots = self.separatePlotsRadio.isChecked()
            cycle_mode = self.cycleModeCheckbox.isChecked()
            
            # Validation: Cycle mode requires I channel
            if cycle_mode and i_count == 0:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Cycle mode requires an Inductive (I) channel.\n\n"
                    "Please set one channel to type 'I' to use cycle control,\n"
                    "or disable cycle mode."
                )
                return
            
            # Emit configuration
            self.configSignal.emit(
                timeint, channels, voltage_ranges, channel_types,
                srate, dec, n_points, refresh_rate, separate_plots, cycle_mode
            )
            self.close()
            
        except ValueError as e:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                f"Please enter valid numeric values.\n\nError: {e}"
            )


# Enhanced GraphThread class with unit conversion and I channel support
class GraphThread(QtCore.QThread):
    graphEndSig = QtCore.pyqtSignal(list, list, list, list)  # Added cycle_numbers
    monitTimeEndSig = QtCore.pyqtSignal()
    graphUpdateSig = QtCore.pyqtSignal(list, list)
    updateYAxisSig = QtCore.pyqtSignal(list, list)
    updateArrowsSig = QtCore.pyqtSignal(list, float, float)  # transitions, x_min, x_max
    cycleStartedSig = QtCore.pyqtSignal(int)  # cycle_number
    cycleEndedSig = QtCore.pyqtSignal(int, list, list)  # cycle_number, xdata, ydata
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
        
        # I channel tracking
        self.i_channel_transitions = []  # List of (x_time, 'UP' or 'DOWN')
        
        # Cycle mode tracking
        self.cycle_mode = main_window.cycle_mode if main_window else False
        self.current_cycle = 0
        self.cycle_active = False  # True when I is HIGH and we're collecting data
        self.cycle_start_time = 0  # Absolute time when current cycle started
        self.cycle_xdata = []  # X data for current cycle (relative to cycle start)
        self.cycle_ydata = []  # Y data for current cycle
        self.cycle_numbers = []  # Cycle number for each data point (for saving)
        self.waiting_for_first_cycle = True if self.cycle_mode else False
        
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

                        # Extract raw voltage values
                        ypoints_raw = []
                        for i in range(len(self.serData) - 1):
                            ypoints_raw.append(self.serData[i])
                        
                        # Check I channel state for cycle mode
                        i_is_high = False
                        if self.main_window and self.main_window.i_channel_index is not None:
                            i_idx = self.main_window.i_channel_index
                            if i_idx < len(ypoints_raw):
                                raw_i_value = ypoints_raw[i_idx]
                                # Determine if HIGH or LOW
                                if raw_i_value > self.main_window.i_threshold_high:
                                    i_is_high = True
                                elif raw_i_value < self.main_window.i_threshold_low:
                                    i_is_high = False
                                else:
                                    # In hysteresis - keep previous state
                                    i_is_high = self.cycle_active
                                
                                # Process transitions (for arrow display in non-cycle mode)
                                self.main_window.process_i_channel_transition(x_time, raw_i_value)
                                self.i_channel_transitions = self.main_window.i_channel_transitions.copy()
                        
                        # Convert to physical units
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
                                    # Start first cycle
                                    self.waiting_for_first_cycle = False
                                    self.cycle_active = True
                                    self.current_cycle = 1
                                    self.cycle_start_time = x_time
                                    self.cycle_xdata = []
                                    self.cycle_ydata = []
                                    self.cycleStartedSig.emit(self.current_cycle)
                                    print(f"Cycle {self.current_cycle} started at t={x_time:.3f}s")
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
                                    print(f"Cycle {self.current_cycle} ended at t={x_time:.3f}s, duration={x_time - self.cycle_start_time:.3f}s")
                                    self.last_cycle_end_time = x_time  # Record end time for debounce
                                    # Emit signal with cycle data for creating ghost plot
                                    self.cycleEndedSig.emit(self.current_cycle, 
                                                           self.cycle_xdata.copy(), 
                                                           [list(y) for y in zip(*self.cycle_ydata)] if self.cycle_ydata else [])
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
                                    print(f"Cycle {self.current_cycle} started at t={x_time:.3f}s")
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
                    print(f"GraphThread processed: {processed_count} points this cycle, Total: {len(self.xdata)} points")
                
                # Only update the actual plot display based on timer
                if timer >= self.update_interval:
                    t0 = perf_counter()
                    plot_T_F = True

                if plot_T_F and len(self.xdata_plts) > 0:
                    self.graphUpdateSig.emit(self.xdata_plts, self.ydata_plts)
                    
                    # Update arrows for I channel (only in non-cycle mode)
                    if not self.cycle_mode and self.i_channel_transitions:
                        x_min = self.xdata_plts[0] if self.xdata_plts else 0
                        x_max = self.xdata_plts[-1] if self.xdata_plts else 0
                        self.updateArrowsSig.emit(self.i_channel_transitions, x_min, x_max)
                    
                self.readQSigRec = False

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
                    # Default range based on channel type
                    if self.main_window and i < len(self.main_window.channel_types):
                        if self.main_window.channel_types[i] == 'T':
                            y_min_with_margin = 0
                            y_max_with_margin = 100
                        elif self.main_window.channel_types[i] == 'P':
                            y_min_with_margin = 0
                            y_max_with_margin = 10
                        else:  # I
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
                    if self.main_window and i < len(self.main_window.channel_types):
                        if self.main_window.channel_types[i] == 'T':
                            y_min_with_margin = 0
                            y_max_with_margin = 100
                        elif self.main_window.channel_types[i] == 'P':
                            y_min_with_margin = 0
                            y_max_with_margin = 10
                        else:
                            y_min_with_margin = 0
                            y_max_with_margin = 1
                    else:
                        y_min_with_margin = 0
                        y_max_with_margin = 100
                
                y_mins.append(y_min_with_margin)
                y_maxs.append(y_max_with_margin)
            
            self.updateYAxisSig.emit(y_mins, y_maxs)


# Keep existing dialog classes
class help_dialog(QtWidgets.QDialog, help_dialog.Ui_aboutDialog):
    def __init__(self, parent = None):
        super(help_dialog, self).__init__(parent)
        self.setupUi(self)


pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.showMaximized()
    app.exec_()