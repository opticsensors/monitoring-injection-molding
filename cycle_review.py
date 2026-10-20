"""Recorded-cycle view, using exactly the live plot construction/tools."""
import re
from collections import Counter
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore
from graphswidget import GraphsWidget
from plot_view import PlotViewMixin
from sensor_types import sensor_unit


class CycleReview(PlotViewMixin, QtWidgets.QWidget):
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.records = records
        first = records[0]
        c = first["capture"]
        cfg = c.get("config_snapshot", {})
        # Plot the union of recorded fields. Never use today's DAQ calibration.
        fields = list(dict.fromkeys(f for r in records for f in r["waveform"]["fields"]))
        for record in records:
            recorded = record["capture"].get("config_snapshot", {})
            for field, unit in zip(recorded.get("field_names", []), recorded.get("field_units", [])):
                if unit != sensor_unit(field.split("_", 1)[1]):
                    raise ValueError(f"Recorded unit for {field} differs from this viewer: {unit}")
        self.daq_channels, self.channel_types = [], []
        for name in fields:
            match = re.fullmatch(r"CH(\d+)_(.+)", name)
            if not match:
                raise ValueError(f"Unknown recorded channel: {name}")
            self.daq_channels.append(int(match[1]))
            self.channel_types.append(match[2])
        if len(set(self.daq_channels)) != len(self.daq_channels):
            raise ValueError("These recordings use different sensor types on the same channel. Open them in separate tabs.")
        self.plot_channels = list(self.daq_channels)
        self.nplots = len(fields)
        self.sensors = [f"CH{i}" for i in self.daq_channels]
        self.temp_colors = ['#FF0000', '#FF6600', '#FF9900', '#FFCC00']
        self.pressure_colors = ['#0000FF', '#0099FF', '#00CCFF', '#00FFFF']
        self.machine_colors = {'pos_screw': '#8E44AD', 'vel_screw': '#16A085', 'P_machine': '#E67E22'}
        self.separate_plots = cfg.get("separate_plots", False)
        self.machine_layout = cfg.get("machine_layout", "shared")
        self.trigger_mode = "None"
        self.digital_map = {}
        self.cycle_mode = True
        self.session_cycle_base = c["cycle_id"] - (c.get("session_cycle") or c["cycle_id"])
        geometry = cfg.get("viscosity", {})
        self.visc_L_mm = geometry.get("L_mm", 0)
        self.visc_Rc_mm = geometry.get("Rc_mm", 0)
        self.plot_is_live = False
        self.tool_mode = None
        self._extra_viewboxes = []
        self._cursor_sync_guard = False
        self.cursor_pens = {
            't1': pg.mkPen('#E91E63', width=2, style=QtCore.Qt.DotLine),
            't2': pg.mkPen('#212121', width=2, style=QtCore.Qt.DotLine)}
        layout = QtWidgets.QVBoxLayout(self)
        toolbar = QtWidgets.QHBoxLayout()
        self.focus = QtWidgets.QComboBox()
        labels = [f"Cycle {r['capture']['cycle_id']} · {r['capture']['machine_id']}" for r in records]
        duplicates, occurrences = Counter(labels), Counter()
        for record in records:
            capture = record["capture"]
            label = f"Cycle {capture['cycle_id']} · {capture['machine_id']}"
            occurrences[label] += 1
            suffix = f" ({occurrences[label]})" if duplicates[label] > 1 else ""
            self.focus.addItem(label + suffix)
            self.focus.setItemData(self.focus.count() - 1,
                f"{label}\nSession: {capture['session_id']}", QtCore.Qt.ToolTipRole)
        self.focus.setAccessibleName("Cycle used for measurements")
        self.focus.setFixedSize(170, 30)
        toolbar.addWidget(self.focus)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        self.plotTabs = QtWidgets.QTabWidget()
        self.GraphArea, self.GraphAreaMachine = GraphsWidget(), GraphsWidget()
        self.plotTabs.addTab(self.GraphArea, "Mold sensors")
        self.plotTabs.addTab(self.GraphAreaMachine, "Machine data")
        layout.addWidget(self.plotTabs, 1)
        self._coord_readouts = {'mold': [], 'machine': []}
        self.GraphArea.canvas.scene().sigMouseMoved.connect(lambda p: self._update_coord_readouts('mold', p))
        self.GraphAreaMachine.canvas.scene().sigMouseMoved.connect(lambda p: self._update_coord_readouts('machine', p))
        self.reset_Data_n_Plot_Vars()
        self.SubplotSetup()
        styles = [QtCore.Qt.SolidLine, QtCore.Qt.DashLine, QtCore.Qt.DotLine, QtCore.Qt.DashDotLine]
        self._review_lines = []
        self._prepared = []
        for index, record in enumerate(records):
            waveform = record["waveform"]
            x = np.asarray(waveform["time_s"], dtype=float)
            y = [np.asarray(waveform["values"].get(f, np.full(len(x), np.nan)), dtype=float) for f in fields]
            self._prepared.append((x, y))
            lines = []
            for i, values in enumerate(y):
                target = self.item_target.get(i)
                if target is None:
                    continue
                item = pg.PlotDataItem(x, values, connect="finite",
                    pen=pg.mkPen(self.get_channel_color(i), width=2, style=styles[index % len(styles)]))
                target.addItem(item)
                lines.append(item)
            self._review_lines.append(lines)
        maximum = max(float(x[-1]) for x, _ in self._prepared if len(x))
        for setter, indices in self.y_axis_groups:
            all_values = [values[i][np.isfinite(values[i])] for _, values in self._prepared for i in indices]
            present = [v for v in all_values if len(v)]
            if present:
                lo, hi = min(float(v.min()) for v in present), max(float(v.max()) for v in present)
                padding = max((hi-lo)*.06, .1)
                setter.setYRange(lo-padding, hi+padding, padding=0)
        self._snapshot_default_ranges()
        self._default_x_range = (0, max(maximum * 1.03, .01), 0)
        self.resetPlotView()
        self.focus.currentIndexChanged.connect(self._focus_cycle)
        self._focus_cycle(0)
        self._set_plot_live(False)

    def _focus_cycle(self, index):
        x, y = self._prepared[index]
        self._last_plot_x, self._last_plot_y = x.tolist(), [v.tolist() for v in y]
        capture = self.records[index]["capture"]
        cfg = capture.get("config_snapshot", {})
        geometry = cfg.get("viscosity", {})
        self.visc_L_mm, self.visc_Rc_mm = geometry.get("L_mm", 0), geometry.get("Rc_mm", 0)
        self.session_cycle_base = capture["cycle_id"] - (capture.get("session_cycle") or capture["cycle_id"])
        self._set_cycle_readout(capture["cycle_id"])
        self.focus.setToolTip("Cycle used for Δt, ΔP and viscosity.\n" +
                             self.focus.itemData(index, QtCore.Qt.ToolTipRole))
        self._update_review_visibility()
        self._update_cursor_readout()

    def _update_review_visibility(self):
        index = self.focus.currentIndex()
        for n, lines in enumerate(self._review_lines):
            for line in lines:
                line.setOpacity(1.0 if n == index else .4)
                line.setVisible(n == index or not getattr(self, "_ghosts_hidden", False))

    def _on_hide_ghosts_toggled(self, hide):
        self._ghosts_hidden = hide
        self._update_review_visibility()
        self._notify_plot_toolbar()

    def _viscosity_tooltip(self, rheo):
        if not self.visc_L_mm or not self.visc_Rc_mm:
            return "Recorded geometry unavailable; viscosity cannot be calculated."
        return super()._viscosity_tooltip(rheo)

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout_canvas(self.GraphArea.canvas)
        self._relayout_canvas(self.GraphAreaMachine.canvas)
        self._resync_side_axes()
