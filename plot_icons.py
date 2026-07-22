"""
Matplotlib-style monochrome toolbar icons for the plot tools.

The icons are drawn at runtime with QPainter (vector strokes on a transparent
canvas) so the app needs no image files - the same "no image files needed"
approach already used for the session-control buttons' built-in theme icons.

Each function returns a QIcon rendered in near-black line art, echoing the
matplotlib navigation toolbar: a house (home), a magnifier (zoom), crossed
4-way arrows (pan) and two cursor lines with a measuring arrow (time cursors).
Because a QIcon is returned (not a bare pixmap), Qt derives the greyed-out
"disabled" variant automatically, so the tools dim correctly while the plot is
following live data.
"""
import math

from PyQt5 import QtCore, QtGui

_ICON_PX = 64                          # render canvas; Qt scales it to the button
_COLOR = QtGui.QColor(30, 30, 30)      # near-black, matplotlib-toolbar ink


def _canvas(px=_ICON_PX):
    """A transparent square pixmap plus an antialiased painter over it."""
    pm = QtGui.QPixmap(px, px)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    return pm, p


def _pen(p, px, width_frac=0.07, color=_COLOR):
    """Set a rounded black stroke whose width scales with the canvas size."""
    pen = QtGui.QPen(color)
    pen.setWidthF(px * width_frac)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    p.setPen(pen)
    return pen


def _finish(pm, p):
    p.end()
    return QtGui.QIcon(pm)


def _arrow_head(p, tip, dirx, diry, length, half_width):
    """Draw a filled triangular arrowhead at ``tip`` pointing along (dirx, diry)."""
    bx, by = tip.x() - dirx * length, tip.y() - diry * length
    base1 = QtCore.QPointF(bx - diry * half_width, by + dirx * half_width)
    base2 = QtCore.QPointF(bx + diry * half_width, by - dirx * half_width)
    p.drawPolygon(QtGui.QPolygonF([tip, base1, base2]))


def home_icon():
    """A simple house outline (matplotlib 'home' / reset view)."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s)
    p.setBrush(QtCore.Qt.NoBrush)
    # Roof: eaves wider than the body, peaked in the middle.
    roof = QtGui.QPolygonF([
        QtCore.QPointF(0.14 * s, 0.52 * s),
        QtCore.QPointF(0.50 * s, 0.20 * s),
        QtCore.QPointF(0.86 * s, 0.52 * s),
    ])
    p.drawPolyline(roof)
    # Body and door.
    p.drawRect(QtCore.QRectF(0.24 * s, 0.50 * s, 0.52 * s, 0.30 * s))
    p.drawRect(QtCore.QRectF(0.44 * s, 0.62 * s, 0.14 * s, 0.18 * s))
    return _finish(pm, p)


def zoom_icon():
    """A magnifier with a '+' inside (matplotlib 'zoom to rectangle')."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s)
    p.setBrush(QtCore.Qt.NoBrush)
    cx, cy, r = 0.42 * s, 0.42 * s, 0.24 * s
    p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
    # Handle running off the lens at 45 degrees.
    hx, hy = cx + r * math.cos(math.pi / 4), cy + r * math.sin(math.pi / 4)
    p.drawLine(QtCore.QPointF(hx, hy), QtCore.QPointF(0.82 * s, 0.82 * s))
    # '+' marking zoom-in.
    p.drawLine(QtCore.QPointF(cx - 0.11 * s, cy), QtCore.QPointF(cx + 0.11 * s, cy))
    p.drawLine(QtCore.QPointF(cx, cy - 0.11 * s), QtCore.QPointF(cx, cy + 0.11 * s))
    return _finish(pm, p)


def pan_icon():
    """Crossed four-way arrows (matplotlib 'pan/zoom' move tool)."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s)
    p.setBrush(_COLOR)
    c, a = 0.50 * s, 0.32 * s          # centre and arm half-length
    p.drawLine(QtCore.QPointF(c, c - a), QtCore.QPointF(c, c + a))
    p.drawLine(QtCore.QPointF(c - a, c), QtCore.QPointF(c + a, c))
    d, h = 0.13 * s, 0.11 * s          # arrowhead length and half-width
    _arrow_head(p, QtCore.QPointF(c, c - a), 0, -1, d, h)   # up
    _arrow_head(p, QtCore.QPointF(c, c + a), 0, 1, d, h)    # down
    _arrow_head(p, QtCore.QPointF(c - a, c), -1, 0, d, h)   # left
    _arrow_head(p, QtCore.QPointF(c + a, c), 1, 0, d, h)    # right
    return _finish(pm, p)


def cloud_icon():
    """A simple cloud outline in black edges (send the session to the cloud/MQTT)."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s, width_frac=0.06)
    p.setBrush(QtCore.Qt.NoBrush)
    # Flat bottom with three rounded humps on top, drawn as one closed curve.
    yb = 0.64 * s
    path = QtGui.QPainterPath(QtCore.QPointF(0.26 * s, yb))
    path.quadTo(0.08 * s, yb,           0.15 * s, 0.48 * s)   # left shoulder up
    path.quadTo(0.19 * s, 0.30 * s,     0.41 * s, 0.37 * s)   # left hump
    path.quadTo(0.51 * s, 0.20 * s,     0.65 * s, 0.35 * s)   # centre hump (tallest)
    path.quadTo(0.83 * s, 0.28 * s,     0.85 * s, 0.50 * s)   # right hump
    path.quadTo(0.93 * s, yb,           0.74 * s, yb)         # right shoulder down
    path.closeSubpath()                                        # flat base back to start
    p.drawPath(path)
    return _finish(pm, p)


def save_icon():
    """A monochrome floppy-disk (save), black line art to match the cloud icon."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s, width_frac=0.06)
    p.setBrush(QtCore.Qt.NoBrush)
    # Body with the classic chamfered top-right corner.
    x0, y0, x1, y1 = 0.22 * s, 0.22 * s, 0.78 * s, 0.78 * s
    chamf = 0.14 * s
    body = QtGui.QPainterPath(QtCore.QPointF(x0, y0))
    body.lineTo(x1 - chamf, y0)
    body.lineTo(x1, y0 + chamf)
    body.lineTo(x1, y1)
    body.lineTo(x0, y1)
    body.closeSubpath()
    p.drawPath(body)
    # Top shutter (the metal slider), inset from the body edges.
    p.drawRect(QtCore.QRectF(0.34 * s, y0, 0.28 * s, 0.16 * s))
    # Label area at the bottom.
    p.drawRect(QtCore.QRectF(0.32 * s, 0.50 * s, 0.36 * s, 0.28 * s))
    return _finish(pm, p)


def eye_icon():
    """An open eye (toggles visibility of the faint past-cycle ghost curves)."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s, width_frac=0.06)
    p.setBrush(QtCore.Qt.NoBrush)
    # Almond eye outline: two lids meeting at the left/right corners.
    left = QtCore.QPointF(0.12 * s, 0.50 * s)
    right = QtCore.QPointF(0.88 * s, 0.50 * s)
    path = QtGui.QPainterPath(left)
    path.quadTo(QtCore.QPointF(0.50 * s, 0.20 * s), right)   # upper lid
    path.quadTo(QtCore.QPointF(0.50 * s, 0.80 * s), left)    # lower lid
    p.drawPath(path)
    # Filled pupil in the centre.
    p.setBrush(_COLOR)
    p.drawEllipse(QtCore.QPointF(0.50 * s, 0.50 * s), 0.10 * s, 0.10 * s)
    return _finish(pm, p)


def measure_icon():
    """Two vertical cursor lines with a horizontal measuring arrow between them."""
    s = _ICON_PX
    pm, p = _canvas()
    _pen(p, s, width_frac=0.06)
    x1, x2 = 0.24 * s, 0.76 * s
    top, bot = 0.16 * s, 0.84 * s
    p.drawLine(QtCore.QPointF(x1, top), QtCore.QPointF(x1, bot))
    p.drawLine(QtCore.QPointF(x2, top), QtCore.QPointF(x2, bot))
    y = 0.50 * s
    p.drawLine(QtCore.QPointF(x1, y), QtCore.QPointF(x2, y))
    p.setBrush(_COLOR)
    d, h = 0.12 * s, 0.08 * s
    _arrow_head(p, QtCore.QPointF(x1, y), -1, 0, d, h)     # left head
    _arrow_head(p, QtCore.QPointF(x2, y), 1, 0, d, h)      # right head
    return _finish(pm, p)
