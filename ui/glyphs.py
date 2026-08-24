"""Small vector icons for the topbar buttons: chevrons, a pushpin, a funnel,
a circular refresh arrow and a waste bin.

Drawn rather than shipped. Five glyphs do not justify carrying image files
around, and drawing them means they take the palette colour -- the same reason
the tech-tier wedge in `results_window` is painted instead of downloaded.

Text glyphs ("▼", "📌", "⚙") were the obvious alternative and are the wrong one:
their shape depends on whichever font Windows falls back to, and a colour
emoji ignores the stylesheet entirely.

Every glyph is defined on a 16-unit square and scaled, so the proportions hold
at any button size. Pixmaps are rendered at 2x with a device pixel ratio set,
which is what keeps them from going soft on a HiDPI screen.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_UNIT = 16.0
_SCALE = 2       # render factor; the pixmap carries it as its DPR


def _canvas(size: int):
    """A transparent pixmap and a painter already scaled to the 16-unit box."""
    pix = QPixmap(size * _SCALE, size * _SCALE)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(size * _SCALE / _UNIT, size * _SCALE / _UNIT)
    return pix, p


def _finish(pix, painter, size: int) -> QIcon:
    painter.end()
    pix.setDevicePixelRatio(float(_SCALE))
    return QIcon(pix)


def chevron(down: bool, colour: str, size: int = 16) -> QIcon:
    """The same arrow the tree draws next to an expandable row.

    Stroked, not filled: a filled triangle reads as "play", and these two
    buttons have to look like the spoiler markers they drive.
    """
    pix, p = _canvas(size)
    pen = QPen(QColor(colour), 2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    if down:
        path.moveTo(4.0, 6.0)
        path.lineTo(8.0, 10.5)
        path.lineTo(12.0, 6.0)
    else:
        path.moveTo(4.0, 10.5)
        path.lineTo(8.0, 6.0)
        path.lineTo(12.0, 10.5)
    p.drawPath(path)
    return _finish(pix, p, size)


def funnel(colour: str, size: int = 16) -> QIcon:
    """A funnel: the search filters.

    The shape the pin was rejected for. That rejection is the argument FOR it
    here -- a funnel in a toolbar means "filter" so unmistakably that drawing
    one by accident broke a different button. Filled, so it reads as a state
    (these filters are always set to something) rather than an action.
    """
    pix, p = _canvas(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(colour))
    path = QPainterPath()
    path.moveTo(2.5, 3.0)
    path.lineTo(13.5, 3.0)
    path.lineTo(9.3, 8.4)
    path.lineTo(9.3, 13.5)
    path.lineTo(6.7, 12.0)
    path.lineTo(6.7, 8.4)
    path.closeSubpath()
    p.drawPath(path)
    return _finish(pix, p, size)


def pin(colour: str, size: int = 16) -> QIcon:
    """A pin, tilted, the way "pinned" is drawn everywhere.

    Two earlier shapes were tried and rejected on sight at 16px: an upright
    thumbtack with a tapering body read as a FUNNEL, which in a toolbar means
    "filter", and a map-pin teardrop reads as "location". A ball-headed needle
    driven in at an angle says only one thing.
    """
    pix, p = _canvas(size)
    col = QColor(colour)
    # Tilt the whole glyph rather than computing angled coordinates: the shape
    # stays easy to read in the source.
    p.translate(8.0, 8.0)
    p.rotate(-40.0)
    p.translate(-8.0, -8.0)

    p.setPen(Qt.NoPen)
    p.setBrush(col)
    p.drawEllipse(QPointF(8.0, 3.6), 2.5, 2.5)

    shaft = QPen(col, 1.8)
    shaft.setCapStyle(Qt.FlatCap)
    p.setPen(shaft)
    p.drawLine(QPointF(8.0, 5.6), QPointF(8.0, 11.5))

    # The point: a thin triangle, so the needle ends in a tip and not a stub.
    p.setPen(Qt.NoPen)
    tip = QPainterPath()
    tip.moveTo(7.1, 11.5)
    tip.lineTo(8.9, 11.5)
    tip.lineTo(8.0, 15.0)
    tip.closeSubpath()
    p.drawPath(tip)
    return _finish(pix, p, size)


def refresh(colour: str, size: int = 16) -> QIcon:
    """A circular arrow -- the universal "do it again" mark.

    An open arc rather than a closed ring: a full circle reads as a status
    light, and the gap is what makes the arrowhead mean direction. The arc
    stops short of 360 degrees so the head has somewhere to sit.
    """
    pix, p = _canvas(size)
    col = QColor(colour)

    pen = QPen(col, 1.7)
    pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # Qt angles are in 1/16 degree, counter-clockwise from three o'clock.
    p.drawArc(QRectF(3.2, 3.2, 9.6, 9.6), 70 * 16, -290 * 16)

    # The head closes the gap the arc left, pointing clockwise.
    p.setPen(Qt.NoPen)
    p.setBrush(col)
    head = QPainterPath()
    head.moveTo(9.4, 1.4)
    head.lineTo(9.4, 5.4)
    head.lineTo(12.6, 3.4)
    head.closeSubpath()
    p.drawPath(head)
    return _finish(pix, p, size)


def trash(colour: str, size: int = 16) -> QIcon:
    """A waste bin: the lid, the body, and two ribs.

    Stroked like the chevrons rather than filled, so at 16 px it stays a
    recognisable outline instead of a dark blob, and so it takes the dim
    palette colour -- clearing the list is not the button anyone should reach
    for first.
    """
    pix, p = _canvas(size)
    col = QColor(colour)

    pen = QPen(col, 1.4)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    p.drawLine(QPointF(2.6, 4.2), QPointF(13.4, 4.2))      # the lid
    p.drawLine(QPointF(6.4, 4.2), QPointF(6.4, 2.6))       # the handle
    p.drawLine(QPointF(6.4, 2.6), QPointF(9.6, 2.6))
    p.drawLine(QPointF(9.6, 2.6), QPointF(9.6, 4.2))

    body = QPainterPath()                                   # tapered body
    body.moveTo(4.2, 5.6)
    body.lineTo(5.1, 13.6)
    body.lineTo(10.9, 13.6)
    body.lineTo(11.8, 5.6)
    p.drawPath(body)

    p.drawLine(QPointF(6.9, 7.2), QPointF(7.1, 12.0))       # the ribs
    p.drawLine(QPointF(9.1, 7.2), QPointF(8.9, 12.0))
    return _finish(pix, p, size)
