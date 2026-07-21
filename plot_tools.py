"""
Matplotlib-style interaction tools for the pyqtgraph plots.

ToolViewBox replaces the default ViewBox on every plot the user can interact
with. The built-in mouse interaction (wheel zoom, free drag, right-click menu)
is disabled; instead MainWindow drives a single global tool mode, mirroring
the matplotlib toolbar:

    None     -> mouse does nothing on the plot (live view / no tool selected)
    'pan'    -> left-drag pans the plot (matplotlib hand tool)
    'zoom'   -> left-drag draws a zoom-in rectangle (matplotlib magnifier)
    'cursor' -> clicks place the two measurement time-cursors (t1/t2)

Dual-axis plots stay coherent: the extra ViewBoxes behind the right/second-left
axes are PassThroughViewBox instances - mouse-transparent, so events reach the
main ToolViewBox below - and are registered as "y buddies" of the main view.
When a pan/zoom changes the main Y range, the same fractional change is applied
to each buddy, so every Y axis of the plot moves together like one matplotlib
axes. X follows automatically through the normal pyqtgraph X-link.
"""
from PyQt5 import QtCore, QtGui
import pyqtgraph as pg


class ToolViewBox(pg.ViewBox):
    """Main ViewBox of a plot: modal (pan/zoom/cursor) mouse interaction only."""

    # Shared by every instance; driven by MainWindow.
    tool_mode = None              # None | 'pan' | 'zoom' | 'cursor'
    cursor_click_callback = None  # f(mouse_button, x_data), set by MainWindow

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('enableMenu', False)
        super().__init__(*args, **kwargs)
        self.y_buddies = []  # side-axis ViewBoxes that follow this view's Y changes
        # Matplotlib-style zoom rectangle: thin black outline, no fill. The
        # pyqtgraph default is a translucent yellow-filled box; updateScaleBox
        # only repositions/shows it, so styling it once here persists.
        self.rbScaleBox.setPen(pg.mkPen('k', width=1))
        self.rbScaleBox.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))

    def cancel_active_gesture(self):
        """Hide a half-drawn zoom rectangle (tool cancelled mid-drag)."""
        try:
            self.rbScaleBox.hide()
        except Exception:
            pass

    def _map_y_to_buddies(self, old_y):
        """Apply this view's fractional Y-range change to the buddy viewboxes."""
        new_y = self.viewRange()[1]
        old_span = old_y[1] - old_y[0]
        if not self.y_buddies or old_span == 0 or tuple(new_y) == tuple(old_y):
            return
        f_lo = (new_y[0] - old_y[0]) / old_span
        f_hi = (new_y[1] - old_y[0]) / old_span
        for vb in self.y_buddies:
            b_lo, b_hi = vb.viewRange()[1]
            span = b_hi - b_lo
            vb.setYRange(b_lo + f_lo * span, b_lo + f_hi * span, padding=0)

    def wheelEvent(self, ev, axis=None):
        ev.accept()  # wheel zoom disabled (was broken on the multi-axis plots)

    def mouseDragEvent(self, ev, axis=None):
        mode = ToolViewBox.tool_mode
        if mode not in ('pan', 'zoom') or ev.button() != QtCore.Qt.LeftButton:
            ev.ignore()
            return
        self.setMouseMode(self.PanMode if mode == 'pan' else self.RectMode)
        old_y = tuple(self.viewRange()[1])
        super().mouseDragEvent(ev, axis=axis)
        self._map_y_to_buddies(old_y)

    def mouseClickEvent(self, ev):
        if ToolViewBox.tool_mode == 'cursor' and ToolViewBox.cursor_click_callback is not None:
            x = self.mapSceneToView(ev.scenePos()).x()
            ToolViewBox.cursor_click_callback(ev.button(), x)
            ev.accept()
            return
        ev.ignore()


class PassThroughViewBox(pg.ViewBox):
    """ViewBox backing a secondary (side) Y axis: ignores the mouse entirely.

    Events fall through to the ToolViewBox underneath, which keeps this view
    in sync via the y-buddy mapping (Y) and the regular X-link (X).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('enableMenu', False)
        super().__init__(*args, **kwargs)

    def wheelEvent(self, ev, axis=None):
        ev.ignore()

    def mouseDragEvent(self, ev, axis=None):
        ev.ignore()

    def mouseClickEvent(self, ev):
        ev.ignore()
