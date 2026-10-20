"""Shared plot construction and interaction for live and recorded-cycle views."""
import logging
import numpy as np
from PyQt5 import QtCore, QtGui
import pyqtgraph as pg
from sensor_types import sensor_category, sensor_label, sensor_unit
from plot_tools import ToolViewBox, PassThroughViewBox
from rheology import apparent_viscosity, cross_section_mm2
logger = logging.getLogger(__name__)


class PlotViewMixin:
    def _notify_plot_toolbar(self):
        callback = getattr(self, '_plot_toolbar_changed', None)
        if callback is not None:
            callback(self)

    _COORD_TAGS = {'T_futaba': 'T', 'T_typeK': 'T', 'T_typeJ': 'T', 'P_kistler': 'P', 'P_machine': 'P',
                   'vel_screw': 'vel', 'pos_screw': 'pos'}
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


    def _set_plot_live(self, live):
        """Enter/leave the live (auto-following) plot state.

        The Home/Zoom/Pan/Cursors tools and the x/y coordinate readout are only
        usable while the plot is still. Entering live mid-interaction cancels
        the active tool, hides a half-drawn zoom rectangle and the readout, and
        snaps the view back to the default ranges so the plot follows the
        incoming data again.
        """
        self.plot_is_live = live
        has_plots = bool(self.splotlist or self.machine_splotlist)
        enable = (not live) and has_plots
        if live:
            # No mouse-move arrives while the cursor sits still, so a label left
            # over from the previous still plot has to be cleared here.
            self._hide_coord_readouts()
            # Remember the Cursors tool so the capture only interrupts it: the
            # lines are hidden for the cycle and put back when it ends.
            self._cursor_tool_was_on = self.tool_mode == 'cursor'
            if self.tool_mode is not None:
                self._on_tool_toggled(self.tool_mode, False)
            for vb in self._tool_viewboxes:
                vb.cancel_active_gesture()
            self.resetPlotView()
        elif enable and self._cursor_tool_was_on:
            # Cycle captured: restore the cursors the operator had placed, where
            # they were. ΔP and η recompute against the curve now on screen.
            self._cursor_tool_was_on = False
            self._on_tool_toggled('cursor', True)
        self._notify_plot_toolbar()


    def _on_tool_toggled(self, name, checked):
        """Keep Zoom/Pan/Cursors mutually exclusive within this plot view."""
        if checked:
            self.tool_mode = name
        elif self.tool_mode == name:
            self.tool_mode = None
        # The Cursors tool owns its lines: they are only drawn, draggable and
        # measured while it is active. Switching to Zoom/Pan also hides them.
        self._set_cursor_lines_shown(self.tool_mode == 'cursor')


    def _on_hide_ghosts_toggled(self, hide):
        """Eye toggle: show/hide every faint past-cycle ghost curve at once."""
        self._ghosts_hidden = hide
        for ghost_plots in self.completed_cycles_plots:
            for item in ghost_plots:
                item.setVisible(not hide)
        self._notify_plot_toolbar()


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


    def _cursor_subplots(self):
        """Subplots the time cursors live on: the Mold-sensors tab only.

        Δt is read against the Futaba/Kistler traces and ΔP against the cavity
        pressures, so the lines belong on that tab. The Machine-data tab shares
        the same X range but nothing there is measured, so drawing them on it
        would only add clutter.
        """
        return list(self.splotlist)


    def _on_cursor_click(self, button, x):
        """Place/move a time cursor: left -> t1, right -> t2, middle -> clear."""
        if self.plot_is_live or self.tool_mode != 'cursor':
            return
        # The cursors are a Mold-sensors tool: a click on the Machine tab must
        # not move lines that are not drawn there (see _cursor_subplots).
        if self.plotTabs.currentWidget() is not self.GraphArea:
            return
        if button == QtCore.Qt.LeftButton:
            self._place_cursor('t1', x)
        elif button == QtCore.Qt.RightButton:
            self._place_cursor('t2', x)
        elif button == QtCore.Qt.MiddleButton:
            self._clear_cursor_lines()
        self._update_cursor_readout()


    def _place_cursor(self, key, x):
        """Create the key's line on every Mold-tab subplot (first use) or move it.

        The same time position is mirrored across those subplots, since every X
        axis shows the same time range.
        """
        if self.cursor_lines[key]:
            self._move_cursor_lines(key, x)
            return
        pen = self.cursor_pens[key]
        hover = pg.mkPen(pen.color(), width=4)
        label_pos = 0.95 if key == 't1' else 0.88  # keep the two labels apart
        for sp in self._cursor_subplots():
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


    def _set_cursor_lines_shown(self, shown):
        """Show/hide the t1-t2 lines and refresh the readout to match.

        Hiding keeps the line objects and their positions, so switching the
        Cursors tool back on brings them back exactly where they were, still
        draggable - unlike a middle-click, which deletes them for good.
        """
        for key in ('t1', 't2'):
            for _, line in self.cursor_lines[key]:
                line.setVisible(shown)
                line.setMovable(shown)
        self._update_cursor_readout()


    def _cursor_x(self, key):
        entries = self.cursor_lines[key]
        return entries[0][1].value() if entries else None


    def _update_cursor_readout(self):
        """Refresh the Δt / ΔP / η labels from the cursor lines and on-screen curves.

        The rheology follows the same inputs as ΔP, so it is recomputed here -
        i.e. on every cursor placement, drag and clear - and never goes stale
        against the two numbers it is derived from.

        All three read '--' whenever the lines are not on the plot, whether
        they were never placed or the Cursors tool is off: a measurement with no
        visible lines behind it has nothing the operator can check it against.
        """
        shown = self.tool_mode == 'cursor'
        x1 = self._cursor_x('t1') if shown else None
        x2 = self._cursor_x('t2') if shown else None
        dt_txt = dp_txt = eta_txt = '--'
        rheo = None
        if x1 is not None and x2 is not None:
            t_lo, t_hi = sorted((x1, x2))
            dt = t_hi - t_lo
            dt_txt = f'{dt:.3f} s'
            dp = self._pressure_drop_at(t_hi)
            if dp is not None:
                dp_txt = f'{dp:.1f} bar'
                rheo = apparent_viscosity(dt, dp, self.visc_L_mm, self.visc_Rc_mm)
                if rheo is not None:
                    eta_txt = f'{rheo.eta:,.1f} Pa·s'
        self._cursor_readout = (f'Δt: {dt_txt}', f'ΔP: {dp_txt}', f'η: {eta_txt}',
                                self._viscosity_tooltip(rheo))
        self._notify_plot_toolbar()


    def _viscosity_tooltip(self, rheo):
        """Full breakdown behind the η reading: Q, τ, γ̇a and the geometry used."""
        head = (f'Apparent viscosity from Δt and ΔP, for a runner of '
                f'L = {self.visc_L_mm:g} mm and Rc = {self.visc_Rc_mm:g} mm '
                f'(A = {cross_section_mm2(self.visc_Rc_mm):.5f} mm²).')
        if rheo is None:
            return (f'{head}\n\nNeeds both cursor lines placed and at least two '
                    f'cavity-pressure curves on screen.')
        return (f'{head}\n\n'
                f'Q  = {rheo.Q:,.1f} mm³/s\t(flow rate, A·Δx/Δt)\n'
                f'τ  = {rheo.tau:,.0f} Pa\t(wall shear stress, ΔP·Rc/2L)\n'
                f'γ̇a = {rheo.gamma_dot:,.1f} 1/s\t(apparent shear rate, 4Q/πRc³)\n'
                f'η  = {rheo.eta:,.1f} Pa·s\t(τ/γ̇a)')


    def _session_cycle(self, cycle_num):
        """Session-relative cycle number: 1 for the first cycle of this session.

        Derived from the global counter (cycle_num - the cycle_id the session
        started from) instead of being tracked as a second counter, so the two
        can never drift: a discarded cycle reuses its global number, so the
        relative one is reused for free. A falsy cycle_num (continuous mode, or
        before the first cycle) stays 0, exactly like cycle_id.

        The session boundary is where session_id is minted - Start and Next -
        so Stop alone does not reset it: the finished session's data is still
        in memory and savable until Next/Start replaces it.
        """
        if not cycle_num:
            return 0
        return cycle_num - self.session_cycle_base


    def _cycle_label(self, cycle_num):
        """'3 (#1487)' - session-relative number first, global cycle_id after it.

        Used by the message log so it reads the same way as the toolbar readout.
        """
        return f'{self._session_cycle(cycle_num)} (#{cycle_num})'


    def _set_cycle_readout(self, cycle_num):
        """Show the cycle number in the toolbar readout box.

        Replaces the old light-grey TextItem that used to sit in the corner of
        the plot; the number now lives beside the Δt / ΔP readings. Shows the
        session-relative number (what the operator reads and writes on a sample
        bag) with the global cycle_id after it as '#1487', so the database
        number stays visible for finding the cycle in Grafana. A falsy
        cycle_num (0 / None, e.g. before the first cycle or in continuous mode)
        shows a placeholder.
        """
        self._cycle_readout_text = (
            f'Cycle: {self._session_cycle(cycle_num)}  (#{cycle_num})'
            if cycle_num else 'Cycle: --')
        self._notify_plot_toolbar()


    def _coord_tag(self, ch_type):
        """Short axis tag for the coordinate readout (T / P / pos / vel)."""
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


    def _hide_coord_readouts(self, which=None):
        """Hide the x/y readouts of one tab, or of both when `which` is None."""
        groups = ([self._coord_readouts.get(which, ())] if which
                  else self._coord_readouts.values())
        for entries in groups:
            for e in entries:
                e['item'].hide()


    def _update_coord_readouts(self, which, scene_pos):
        """Refresh the x/y readout under the cursor for one tab (mold/machine).

        Silent while the plot is live: during a cycle the curves move under the
        cursor, so the numbers would be read off a point that is already gone.
        The readout comes back as soon as the cycle is captured and the plot
        stands still (same rule as the Home/Zoom/Pan/Cursor tools).
        """
        if self.plot_is_live:
            self._hide_coord_readouts(which)
            return
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
            value = float(np.interp(t, x[:n], y[:n]))
            if not np.isfinite(value):
                return None
            values.append(value)
        return max(values) - min(values)


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
            ghost_item.setVisible(not getattr(self, '_ghosts_hidden', False))
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
        self._session_streamed = False  # fresh session: allow a manual cloud send again
        self.completed_cycles_data = []
        self.completed_cycles_plots = []
        self.cycle_labels = []
        self.cycle_label = None

        # Reset plot-tool state (the line items died with canvas.clear())
        self._tool_viewboxes = []
        self.cursor_lines = {'t1': [], 't2': []}
        self._cursor_tool_was_on = False   # nothing left to restore next cycle
        self._last_plot_x = []
        self._last_plot_y = []
        self._default_x_range = None
        self._default_y_ranges = []
        self._update_cursor_readout()  # back to 'Δt: -- | ΔP: -- | η: --'

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
        sp = canvas.addPlot(row, col, viewBox=ToolViewBox(interaction=self), enableMenu=False)
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
            pos_idx = [i for i in machine_idx if self.channel_types[i] == 'pos_screw']
            spd_idx = [i for i in machine_idx if self.channel_types[i] == 'vel_screw']
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
            col_pos = self.machine_colors['pos_screw']
            if pos_idx:
                main_plot.setLabel('left', f"{sensor_label('pos_screw')} [{sensor_unit('pos_screw')}]", color=col_pos)
                main_plot.getAxis("left").setPen(pg.mkPen(col_pos, width=2))
            else:
                main_plot.setLabel('left', f"{sensor_label('pos_screw')} (unused)", color='#888888')
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
                col_spd = self.machine_colors['vel_screw']
                extra_ax.setLabel(f"{sensor_label('vel_screw')} [{sensor_unit('vel_screw')}]", color=col_spd)
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
                coord_axes.append(('pos', sensor_unit('pos_screw'), main_plot.vb))
            if spd_idx and self.machine_left2_viewbox is not None:
                coord_axes.append(('vel', sensor_unit('vel_screw'), self.machine_left2_viewbox))
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


