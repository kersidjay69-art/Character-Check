"""The results window: one row per pilot, expandable into the evidence.

Styled to match Jump Planner -- same dark EVE palette, same topbar/panel
idiom, same object names (`topbar`, `title`, `dim`, `primary`). See ui/styles.

Qt lives only under ui/. Everything shown here comes from plain data produced
by core/, which never imports Qt (CLAUDE.md invariant 1).
"""
from __future__ import annotations

import bisect
import time
import webbrowser

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QPainter, QPen,
                           QPixmap, QPolygon)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMenu, QPushButton, QSizePolicy, QSlider, QStyle,
    QStyledItemDelegate, QStyleOptionViewItem, QToolTip, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core import analyze, clipboard, config, i18n, scan

from . import assets, glyphs, styles
# The author's handles, from the one module allowed to hold them. Imported
# rather than retyped: invariant 7 by import instead of by convention.
from .about import CHARACTER, CHARACTER_URL, DISCORD, TELEGRAM, TELEGRAM_URL
from .icon_cache import get_icon_cache

def level_label(level: str) -> str:
    """"cyno" -> "CYNO". The key itself is protocol and never shown."""
    return i18n.t("level." + level)


def _count_tip(level: str) -> str:
    """What one coloured number in the header means.

    Set from two places -- `_label_widgets` once, and `_set_counts` on every
    update -- so it has to be a function. Two copies of the same format string
    is exactly how they drift apart.
    """
    return i18n.t("tip.count", level_label(level))


def kind_label(kind: str) -> str:
    return i18n.t("kind." + kind)


def short_kind_label(kind: str) -> str:
    """The evidence label as the window says it: "fitted", not "cyno in a high
    slot".

    What set the name column's width was never the names -- 99% of a trade hub
    fits in 125 px and the longest of 1402 was 152 -- it was this label sitting
    next to a date underneath them. The console keeps the long form; a terminal
    has room and no column to widen.
    """
    return i18n.t("short." + kind)
MODULE_LABEL = {21096: "Cyno", 28646: "Covert Cyno", 52694: "Industrial Cyno"}
_KIND_ORDER = {"fitted": 0, "cargo": 1, "hull_lost": 2, "hull_flown": 3}
_LEVEL_ORDER = (analyze.LEVEL_CYNO, analyze.LEVEL_HULL,
                analyze.LEVEL_INDY, analyze.LEVEL_SEEN, analyze.LEVEL_NONE)

_COL_NAME, _COL_MODULES, _COL_SHIPS = 0, 1, 2

# The lowest window opacity the slider offers, in percent. Anything less
# and the text goes dim along with the background.
_OPACITY_MIN = 50

# config key -> i18n suffix, in menu order. The window never spells a filter's
# name; it only knows which setting each line drives.
_FILTER_KEYS = {
    "find_potential": "potential",
    "find_industrial": "industrial",
    "stop_at_first": "stop_first",
}

_ROLE_URL = Qt.UserRole + 1
# The pilot name used to be read back out of column 1 by the copy handler.
# Carrying it in a role instead means the columns can be rearranged without
# silently breaking Ctrl+C.
_ROLE_NAME = Qt.UserRole + 2
# [(type_id, underline_colour_or_None), ...] for the icon delegate.
_ROLE_ICONS = Qt.UserRole + 3


def _get(f, key, default=None):
    """Findings arrive either as dataclasses (fresh) or dicts (from cache).

    `default` matters for `n`, which only grouped rows carry.
    """
    if hasattr(f, "kind"):
        return getattr(f, key, default)
    return f[key] if key in f else default


class IconRowDelegate(QStyledItemDelegate):
    """Paints a row of EVE type icons inside one cell.

    A Qt item carries exactly one icon, and a pilot can have three modules and
    a fistful of hulls, so the cell is painted by hand. Jump Planner solves the
    same problem with a QHBoxLayout of QLabels per row -- fine for one widget,
    far too heavy for a tree several hundred rows long.

    Modules get a coloured underline because Cyno I and Industrial Cyno ship a
    byte-identical icon (both iconID 1444); the artwork alone cannot tell the
    red case from the blue one.
    """

    # Space between the icon and its frame, on every side.
    INSET = 3
    # Artwork size, derived from the row height rather than set beside it: a
    # 20px icon in a 30px row left four pixels of dead space above and below,
    # which reads on screen as gaps between the rows. `cell` now equals
    # styles.ROW_H exactly, and a test holds them together.
    ICON = styles.ROW_H - 2 * INSET
    # The frame's stroke. One pixel disappears against the panel border.
    BORDER = 2
    # Space between neighbouring icons. Modules need it: each is framed in a
    # 2px colour and two frames touching would read as one wide box, so the
    # gap can never drop below 2*BORDER.
    GAP = 4
    # Ships carry no frame, so nothing has to hold them apart -- and INSET
    # already leaves 2*3 px of air between two pieces of artwork. Zero here is
    # not "no space", it is "no space beyond what the cells already have".
    GAP_TIGHT = 0
    # Class attribute as well as an instance one: the geometry test builds a
    # delegate with __new__ and never runs __init__.
    gap = GAP
    # HORIZONTAL only. The row should start where the icons start: no dead
    # margin on either side of the cell. It must not enter the height.
    PAD = 1

    @property
    def cell(self) -> int:
        """Full footprint of one icon: artwork plus its frame."""
        return self.ICON + 2 * self.INSET

    @classmethod
    def width_for(cls, count: int, gap: int | None = None) -> int:
        """How wide a column has to be to show `count` icons and no "+N".

        Computed, never a number typed next to the delegate. It was one once:
        the column was 96 px, then the icon grew with the row height and three
        modules needed 100, so every pilot carrying all three drew two of them
        and a "+1". Nothing in the suite noticed, because nothing knew the two
        numbers were related.
        """
        # The trailing +1 is QRect.right(), which is INCLUSIVE: a rect of
        # width W spans left..left+W-1, and `_slots` compares against it. One
        # pixel short and the last icon is dropped for a "+1" -- which is
        # exactly how the old hand-typed 96 failed, only quieter.
        gap = cls.GAP if gap is None else gap
        return (count * (cls.ICON + 2 * cls.INSET)
                + max(0, count - 1) * gap + 2 * cls.PAD + 1)

    # Side of the tech-tier wedge, in pixels of the drawn icon.
    BADGE = 9

    def __init__(self, cache, name_of, meta_of, parent=None, gap=None):
        super().__init__(parent)
        self._cache = cache
        self._name_of = name_of
        self._meta_of = meta_of
        self._scaled: dict[int, QPixmap] = {}
        if gap is not None:
            self.gap = int(gap)

    def forget(self, type_id: int) -> None:
        """An icon just arrived; drop the stale scaled copy."""
        self._scaled.pop(type_id, None)

    def _pixmap(self, type_id: int):
        """The icon at drawing size, exactly as CCP ships it.

        A white wash was tried here to lift the darker hulls out of the panel
        and rejected at both 22% and 10%: it flattens the artwork more than it
        helps. The icons stay untouched.
        """
        pix = self._scaled.get(type_id)
        if pix is not None:
            return pix
        raw = self._cache.get(type_id)
        if raw is None:
            return None
        pix = raw.scaled(self.ICON, self.ICON, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
        self._scaled[type_id] = pix
        return pix

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        # Exactly the cell, with nothing added: any slack here comes back as a
        # gap between rows.
        if size.height() < self.cell:
            size.setHeight(self.cell)
        return size

    def _slots(self, option, spec):
        """Where each icon cell lands, and how many did not fit."""
        out = []
        x = option.rect.left() + self.PAD
        right = option.rect.right() - self.PAD
        for type_id, colour in spec:
            if x + self.cell > right:
                break
            out.append((x, type_id, colour))
            x += self.cell + self.gap
        return out, x

    def paint(self, painter, option, index):
        spec = index.data(_ROLE_ICONS)
        if not spec:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Let the style paint the background and the selection, but not text:
        # the cell's content is icons.
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        slots, x = self._slots(opt, spec)
        top = opt.rect.top() + max(0, (opt.rect.height() - self.cell) // 2)

        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, False)
        for left, type_id, colour in slots:
            frame = QRect(left, top, self.cell, self.cell)
            box = frame.adjusted(self.INSET, self.INSET,
                                 -self.INSET, -self.INSET)
            pix = self._pixmap(type_id)
            if pix is not None:
                painter.drawPixmap(box, pix)
            else:
                # Still downloading: hold the space so nothing jumps sideways
                # when the icon lands.
                painter.fillRect(box, QColor(styles.BG_CARD))
            self._draw_badge(painter, box, type_id)
            if colour:
                # drawRect strokes centred on the path, so shrink by half the
                # pen width or the frame bleeds outside its own cell.
                painter.setPen(QPen(QColor(colour), self.BORDER))
                half = self.BORDER // 2
                painter.drawRect(frame.adjusted(half, half, -half - 1,
                                                -half - 1))
        # Whatever did not fit, or -- on the evidence rows -- the ship's
        # name sitting next to its icon.
        tail = ("+%d" % (len(spec) - len(slots)) if len(slots) < len(spec)
                else index.data(Qt.DisplayRole) or "")
        if tail:
            colour = index.data(Qt.ForegroundRole)
            painter.setPen(colour.color() if colour is not None
                           else QColor(styles.TEXT_DIM))
            painter.drawText(
                QRect(x + 2, opt.rect.top(), opt.rect.right() - x - 2,
                      opt.rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft, tail)
        painter.restore()

    def _draw_badge(self, painter, box, type_id) -> None:
        """Tech tier as a wedge in the icon's top-left corner.

        Painted unconditionally, on top of whatever the image server did:
        twelve of the Tech II hulls already carry CCP's own badge there, and
        drawing ours only where theirs is missing would give those twelve two
        badges. Ours is opaque and covers it.

        No "II"/"III" lettering -- at a 20px icon the wedge is 8px across and
        any glyph inside it is mud. The colour carries the tier and the
        tooltip carries the ship's name.
        """
        colour = styles.META_COLORS.get(self._meta_of(type_id))
        if not colour:
            return
        n = self.BADGE
        left, top = box.left(), box.top()
        wedge = QPolygon([QPoint(left, top),
                          QPoint(left + n, top),
                          QPoint(left, top + n)])
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(colour))
        painter.drawPolygon(wedge)
        painter.restore()

    def helpEvent(self, event, view, option, index):
        """Name the icon under the cursor -- otherwise they are just pictures."""
        spec = index.data(_ROLE_ICONS)
        if not spec:
            return super().helpEvent(event, view, option, index)
        slots, _ = self._slots(option, spec)
        for left, type_id, _colour in slots:
            if left <= event.pos().x() <= left + self.cell:
                QToolTip.showText(event.globalPos(), self._name_of(type_id),
                                  view)
                return True
        QToolTip.hideText()
        return True


class ResultsWindow(QMainWindow):
    def __init__(self, sets, on_rescan=None):
        super().__init__()
        self._sets = sets
        self._on_rescan = on_rescan
        self._notice = ""
        self._notice_tip = ""
        self._said = ""
        self._copy_token = None
        self.tree = None
        self._reset_stream()
        self.setWindowTitle("Character Check")
        self.resize(1000, 660)

        self.setCentralWidget(self._build())
        self._restore_geometry()

    # --- window placement -------------------------------------------------

    def _restore_geometry(self) -> None:
        """Put the window back where it was left, including on another screen.

        Qt otherwise centres it on the primary monitor every launch, which is
        the wrong monitor for anyone who keeps the game there.
        """
        cfg = config.load()
        # Set before the window is first shown, so the flag does not need the
        # re-show dance below.
        if cfg.get("window_on_top"):
            self.on_top_btn.setChecked(True)
        rect = cfg.get("window_rect") or []
        if len(rect) == 4 and all(isinstance(v, (int, float)) for v in rect):
            x, y, w, h = (int(v) for v in rect)
            # Halved along with the layout minimum: refusing to restore a
            # rectangle the user is allowed to drag to would snap the window
            # back to 1000x660 on every launch, which reads as "it forgot".
            if w >= 200 and h >= 150 and self._on_a_screen(x, y, w, h):
                self.setGeometry(x, y, w, h)
        if cfg.get("window_maximized"):
            self.showMaximized()
        opacity = cfg.get("window_opacity", 100)
        if isinstance(opacity, (int, float)):
            value = max(_OPACITY_MIN, min(100, int(opacity)))
            # blockSignals: setValue emits valueChanged, and without the block
            # the window would save a preference merely because it had read
            # one -- the same trap `_sync_filters` documents.
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(value)
            self.opacity_slider.blockSignals(False)
            self._apply_opacity(value)

    @staticmethod
    def _on_a_screen(x, y, w, h) -> bool:
        """Is this rectangle still somewhere a user could see it?

        Guards the monitor that was unplugged since last run: restoring blindly
        would drop the window onto a screen that no longer exists, and it would
        look like the app failed to start.
        """
        wanted = QRect(x, y, w, h)
        for screen in QApplication.screens():
            if screen.availableGeometry().intersects(wanted):
                return True
        return False

    def _set_on_top(self, on: bool) -> None:
        """Toggle the always-on-top hint and remember the choice.

        Windows will not pick the flag up on a window that is already visible,
        so it has to be shown again -- which is also why this is a no-op while
        the window is still hidden.

        ⚠️ Both locals are load-bearing, and both were learned the hard way:

        * `setWindowFlag` HIDES a visible widget as a side effect, so asking
          `isVisible()` afterwards always answers False and the window is
          never shown again. It simply vanished, which reads exactly like a
          crash.
        * the flag change destroys and recreates the native window, and the
          new one is placed by its client rectangle -- so the window crept up
          the screen by the height of its own title bar on every single click.
        """
        was_visible = self.isVisible()
        where = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on))
        if was_visible:
            self.setGeometry(where)
            self.show()
        try:
            cfg = config.load()
            if bool(cfg.get("window_on_top")) != bool(on):
                cfg["window_on_top"] = bool(on)
                config.save(cfg)
        except Exception:
            pass

    def _apply_opacity(self, percent: int) -> None:
        """Live while the slider moves; the clamp is not decoration.

        A hand-edited 0 in config.json would otherwise produce an invisible
        window that cannot be found to be fixed.
        """
        percent = max(_OPACITY_MIN, min(100, int(percent)))
        self.setWindowOpacity(percent / 100.0)

    def _save_opacity(self) -> None:
        try:
            cfg = config.load()
            value = int(self.opacity_slider.value())
            if value != cfg.get("window_opacity"):
                cfg["window_opacity"] = value
                config.save(cfg)
        except Exception:
            # Same rule as the geometry: losing a preference must never take
            # the app down with it.
            pass

    def save_geometry(self) -> None:
        """Remember the placement. Cheap, so it is safe to call on every hide."""
        try:
            cfg = config.load()
            maximized = bool(self.isMaximized())
            # normalGeometry() is the un-maximized rectangle, which is what we
            # want to come back to if the user un-maximizes later.
            g = self.normalGeometry() if maximized else self.geometry()
            rect = [g.x(), g.y(), g.width(), g.height()]
            if rect == cfg.get("window_rect") and maximized == cfg.get(
                    "window_maximized"):
                return
            cfg["window_rect"] = rect
            cfg["window_maximized"] = maximized
            config.save(cfg)
        except Exception:
            # Losing the placement must never take the app down with it.
            pass

    # --- construction ----------------------------------------------------

    @staticmethod
    def _let_it_shrink(widget) -> None:
        """Stop this widget from setting the window's minimum width.

        Qt derives a window's minimum from its layout, and a QLabel reports
        the full width of its text -- so the title and the bottom hint were
        holding the window at 516 px whether or not anyone wanted it that
        wide. Here they are allowed to be squeezed and clipped instead; the
        tree is what the window is actually for, and it shrinks happily.

        ⚠️ This was `Ignored` with a minimum of 0 until 2026-08-23, and that
        combination is a trap: an Ignored widget's size hint is not "used when
        there is room", it is *discarded*, so beside a stretch it gets nothing
        at all. The title, the hint and the old "Check clipboard" button were
        0 px wide at every window size -- permanently invisible, not merely
        squeezed. That is what "bring the button back" turned out to mean.

        `Preferred` keeps the size hint, and the minimum of ONE pixel is what
        lets the window shrink past it: `qSmartMinSize` only honours an
        explicit minimum when it is greater than zero, so a minimum of 0 is
        silently ignored and the label's own hint becomes the floor again.
        """
        widget.setSizePolicy(QSizePolicy.Preferred,
                             widget.sizePolicy().verticalPolicy())
        widget.setMinimumWidth(1)

    def _build(self) -> QWidget:
        # The logo, if we have one. A missing file means no widget at all
        # rather than an empty label eating the spacing around it.
        self.logo = None
        pix = assets.logo_pixmap(styles.LOGO_H)
        if pix is not None:
            self.logo = QLabel()
            self.logo.setPixmap(pix)
            self.logo.setFixedSize(pix.size() / pix.devicePixelRatio())

        title = QLabel("CHARACTER CHECK")
        title.setObjectName("title")
        self.title = title
        self._let_it_shrink(title)

        # The tally, as bare coloured numbers. No words: the colour is the
        # same one the pilot names wear two pixels below, so the mapping is
        # already on screen, and the tooltip names each one for anybody who
        # wants it spelled out.
        self.counts_row = QHBoxLayout()
        self.counts_row.setSpacing(12)
        self.counts_row.setContentsMargins(0, 0, 0, 0)
        self._count_labels = {}
        for level in _LEVEL_ORDER:
            lbl = QLabel("")
            lbl.setStyleSheet("color:%s; font-weight:bold; font-size:15px;"
                              % styles.LEVEL_COLORS[level])
            lbl.hide()
            self._count_labels[level] = lbl
            self.counts_row.addWidget(lbl)

        # The two buttons that DO something, both square glyphs.
        #
        # "Check clipboard" used to be a wide text button carrying an Ignored
        # size policy, so that the window could still shrink to 230 px -- and
        # the consequence was that below ~350 px the button was squeezed out
        # of existence. A 28 px square never has to disappear, which is the
        # better answer to the same problem.
        self.rescan_btn = self._square_button(
            glyphs.refresh(styles.ACCENT),
            lambda: self._on_rescan and self._on_rescan())
        # Dim, not accent: emptying the list is not what anyone should reach
        # for first, and the colour is the whole ranking.
        self.clear_btn = self._square_button(glyphs.trash(styles.TEXT_DIM),
                                             self.clear)

        # Three glyph buttons. Their captions became tooltips: the words cost
        # more width than they were worth, and the chevrons say the same thing
        # as the spoiler markers they drive.
        self.expand_btn = self._icon_button(
            glyphs.chevron(True, styles.TEXT_DIM), self.tree_expand_all)
        self.collapse_btn = self._icon_button(
            glyphs.chevron(False, styles.TEXT_DIM),
            lambda: self.tree.collapseAll())

        # A funnel, which is exactly the shape the pin had to be redrawn to
        # stop looking like. Here it is right: these are the search filters.
        self.filters_btn = self._icon_button(glyphs.funnel(styles.TEXT_DIM),
                                             self._show_filters)
        self.filters_menu = QMenu(self)
        self.filter_actions = {}
        for key in _FILTER_KEYS:
            act = QAction("", self)
            act.setCheckable(True)
            act.toggled.connect(
                lambda on, k=key: self._set_filter(k, on))
            self.filters_menu.addAction(act)
            self.filter_actions[key] = act
        self._sync_filters()

        self.on_top_btn = self._icon_button(glyphs.pin(styles.TEXT_DIM), None)
        self.on_top_btn.setCheckable(True)
        self.on_top_btn.toggled.connect(self._sync_pin_icon)
        self.on_top_btn.toggled.connect(self._set_on_top)

        top = QHBoxLayout()
        top.setContentsMargins(12, 6, 12, 6)
        top.setSpacing(10)
        if self.logo is not None:
            top.addWidget(self.logo)
        top.addWidget(title)
        top.addSpacing(6)
        top.addLayout(self.counts_row)
        top.addStretch(1)
        # Right to left: the two that change the view, then the two that act.
        # The primary action stays rightmost, where the eye ends up.
        top.addWidget(self.filters_btn)
        top.addWidget(self.on_top_btn)
        top.addWidget(self.expand_btn)
        top.addWidget(self.collapse_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.rescan_btn)

        self.topbar = QFrame()
        self.topbar.setObjectName("topbar")
        self.topbar.setLayout(top)
        topbar = self.topbar

        self.tree = QTreeWidget()
        # Three columns and no verdict column: the pilot's name wears the
        # threat colour, and the header already carries the per-level counts.
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["PILOT", "MODULES", "SHIPS"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setIndentation(14)
        self.tree.itemDoubleClicked.connect(self._open_link)

        self._icons = get_icon_cache()
        # Two delegates, one per icon column, differing only in the gap.
        # Modules are framed in 2px of colour and their frames must not touch;
        # ships are unframed, so nothing has to hold them apart and the row
        # fits more of them. See IconRowDelegate.GAP_TIGHT.
        self._delegate = IconRowDelegate(self._icons, self._type_name,
                                         self._sets.meta_group, self.tree)
        self._ship_delegate = IconRowDelegate(
            self._icons, self._type_name, self._sets.meta_group, self.tree,
            gap=IconRowDelegate.GAP_TIGHT)
        self._delegates = (self._delegate, self._ship_delegate)
        self.tree.setItemDelegateForColumn(_COL_MODULES, self._delegate)
        self.tree.setItemDelegateForColumn(_COL_SHIPS, self._ship_delegate)
        self._icons.icon_ready.connect(self._on_icon_ready)

        head = self.tree.header()
        head.setSectionResizeMode(_COL_NAME, QHeaderView.Interactive)
        head.setSectionResizeMode(_COL_MODULES, QHeaderView.Fixed)
        # Ships take the slack: a pilot can have a dozen hulls, and modules
        # never exceed three.
        head.setSectionResizeMode(_COL_SHIPS, QHeaderView.Stretch)
        head.setStretchLastSection(False)
        # Fits the longest name measured in a 1402-pilot hub paste (152 px)
        # and the short evidence label under it (133 px in Russian). It used to
        # be 250, held there by the LONG label -- see `short_kind_label`. The
        # 90 px handed back go to the ships column, which now shows 13 hulls
        # instead of 9.
        self.tree.setColumnWidth(_COL_NAME, 168)
        # Every cyno module in the game, side by side, from the delegate's own
        # geometry. Never a literal: see IconRowDelegate.width_for.
        self.tree.setColumnWidth(_COL_MODULES,
                                 IconRowDelegate.width_for(
                                     len(analyze.ALL_CYNO)))
        # The three headings said nothing the icons do not: a name is a name,
        # and the two icon columns are told apart by their frames.
        head.hide()

        self._backdrop = assets.background_pixmap()
        self._backdrop_scaled = None
        self._backdrop_size = None
        self.tree.viewport().installEventFilter(self)

        body = QVBoxLayout()
        body.setContentsMargins(6, 6, 6, 4)
        body.setSpacing(0)
        body.addWidget(self.tree)
        body_frame = QWidget()
        body_frame.setLayout(body)

        # The only status surface left. The line under the title used to carry
        # the pilot count and the elapsed time; both were noise, and the
        # messages that shared that line moved down here.
        self.hint = QLabel(i18n.t("status.idle"))
        self.hint.setObjectName("dim")
        self._let_it_shrink(self.hint)
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(12, 0, 12, 8)
        hint_row.addWidget(self.hint)
        hint_row.addStretch(1)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(topbar)
        layout.addWidget(body_frame, 1)
        layout.addLayout(hint_row)
        layout.addWidget(self._contacts_row())

        central = QWidget()
        central.setObjectName("central")
        central.setLayout(layout)

        self.copy_action = QAction(i18n.t("action.copy_names"), self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.triggered.connect(self._copy_selected)
        self.addAction(self.copy_action)
        self._label_widgets()
        return central

    # --- the backdrop -----------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self.tree.viewport() and event.type() == QEvent.Paint:
            self._paint_backdrop()
            # False, not True: the tree must still paint its rows, on top of
            # what we just put down.
            return False
        return super().eventFilter(obj, event)

    def _paint_backdrop(self) -> None:
        """The viewport's own base colour, and the picture when idle.

        The base is painted here rather than in the QSS because a QSS
        background belongs to the widget and is painted after this filter --
        it would cover the picture. `test_ui_window.TestBackground` is what
        holds this honest: no part of the window may end up unpainted.

        The picture is drawn only when the list is empty. That is the whole
        feature -- what an idle window shows instead of a flat rectangle --
        and it means no pilot's name is ever read against artwork.
        """
        view = self.tree.viewport()
        painter = QPainter(view)
        painter.fillRect(view.rect(), QColor(styles.BG_PANEL))
        if self._backdrop is not None and self.tree.topLevelItemCount() == 0:
            painter.drawPixmap(0, 0, self._cover(view.width(), view.height()))
        painter.end()

    def _cover(self, w: int, h: int) -> QPixmap:
        """The backdrop scaled to fill `w` x `h`, cropped, and remembered.

        Cached on the size: a repaint happens on every scroll and every hover,
        and rescaling a 1440x760 pixmap each time is real work for a picture
        that has not changed.
        """
        if self._backdrop_size != (w, h):
            grown = self._backdrop.scaled(w, h, Qt.KeepAspectRatioByExpanding,
                                          Qt.SmoothTransformation)
            self._backdrop_scaled = grown.copy((grown.width() - w) // 2,
                                               (grown.height() - h) // 2, w, h)
            self._backdrop_size = (w, h)
        return self._backdrop_scaled

    def _icon_button(self, icon, on_click) -> QPushButton:
        """A square, borderless button carrying one drawn glyph."""
        btn = QPushButton()
        btn.setObjectName("icon_btn")
        btn.setIcon(icon)
        btn.setFixedSize(26, 26)
        if on_click is not None:
            btn.clicked.connect(on_click)
        return btn

    def _square_button(self, icon, on_click) -> QPushButton:
        """The same glyph, but framed: a button that acts, not one that views.

        Two pixels larger than `_icon_button` because the border eats one on
        each side and the glyph inside has to stay the same size.
        """
        btn = QPushButton()
        btn.setObjectName("square_btn")
        btn.setIcon(icon)
        btn.setFixedSize(28, 28)
        if on_click is not None:
            btn.clicked.connect(on_click)
        return btn

    def _contacts_row(self) -> QFrame:
        """The author's three handles, at the foot of the window.

        The handles themselves live in `ui/about.py` and are imported, never
        retyped: invariant 7 says they exist in exactly one place, and an
        import is the only version of that rule a refactor cannot quietly
        break. Only `ui/` may see them -- `core/` is where the networking is,
        and a handle there would end up signing a stranger's traffic.

        Short captions with the handle in the tooltip. "Discord: kersid_jay"
        across three buttons sets the window's minimum width at ~455 px, which
        is most of what the narrow-window work bought back.
        """
        self.discord_btn = QPushButton(i18n.t("contact.discord"))
        # Discord has no per-user link, so the handle goes to the clipboard --
        # the same compromise the About dialog makes.
        self.discord_btn.clicked.connect(lambda: self._copy_contact(DISCORD))
        self.telegram_btn = QPushButton(i18n.t("contact.telegram"))
        self.telegram_btn.clicked.connect(
            lambda: webbrowser.open(TELEGRAM_URL))
        self.eve_btn = QPushButton(i18n.t("contact.eve"))
        self.eve_btn.clicked.connect(lambda: webbrowser.open(CHARACTER_URL))

        # Transparency, on the right of the footer where PySpy puts it too --
        # a window that sits beside the game client is more useful when it can
        # be seen through. The slider is the whole control; there is no number,
        # because the number is not the point and the effect is visible while
        # dragging.
        self.opacity_slider = QSlider(Qt.Horizontal)
        # Wide when there is room, squeezed to nothing when there is not --
        # the same treatment the title and the hint get. A fixed 90 px here
        # pushed the window's minimum width from 318 to 420, which the
        # minimum-width test caught immediately.
        self.opacity_slider.setMaximumWidth(90)
        self._let_it_shrink(self.opacity_slider)
        # 50 is the floor and it is not arbitrary: setWindowOpacity dims the
        # text along with everything else, and below half the pilot names stop
        # being readable.
        self.opacity_slider.setRange(_OPACITY_MIN, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._apply_opacity)
        # Saved on release, not on every tick: a single drag emits dozens of
        # values and each one would rewrite config.json.
        self.opacity_slider.sliderReleased.connect(self._save_opacity)

        row = QHBoxLayout()
        row.setContentsMargins(12, 5, 12, 5)
        row.setSpacing(6)
        row.addWidget(self.discord_btn)
        row.addWidget(self.telegram_btn)
        row.addWidget(self.eve_btn)
        row.addStretch(1)
        row.addWidget(self.opacity_slider)

        frame = QFrame()
        frame.setObjectName("footer")
        frame.setLayout(row)
        return frame

    def _copy_contact(self, text: str) -> None:
        """Put a handle on the clipboard and say so, briefly.

        `clipboard.expect` is not optional. The watcher polls the clipboard
        sequence number and cannot tell our own write from a paste, so without
        it this handle comes back ~200 ms later as a scan, the guard refuses
        it, and the refusal lands in the very label this confirmation is
        written to.
        """
        clipboard.expect(text)
        QApplication.clipboard().setText(text)
        self._say(i18n.t("contact.copied", text))
        # A token rather than a flag: any other message clears it (see _say),
        # so a scan that starts in the meantime is not overwritten when the
        # timer fires.
        self._copy_token = token = object()
        QTimer.singleShot(2500, lambda: self._restore_hint(token))

    def _restore_hint(self, token) -> None:
        if self._copy_token is token:
            self._say(i18n.t("status.idle"))

    def _show_filters(self) -> None:
        self.filters_menu.exec(
            self.filters_btn.mapToGlobal(self.filters_btn.rect().bottomLeft()))

    def _sync_filters(self) -> None:
        """Put the menu and the funnel in step with what is actually stored.

        Signals are blocked while the boxes are ticked: `setChecked` fires
        `toggled`, and letting that through would save the config and kick off
        a rescan every time the window merely read its own settings -- once at
        construction, before there is anything to rescan.
        """
        cfg = config.load()
        changed = False
        for key, act in self.filter_actions.items():
            on = bool(cfg.get(key, config.DEFAULTS.get(key)))
            act.blockSignals(True)
            act.setChecked(on)
            act.blockSignals(False)
            if on != bool(config.DEFAULTS.get(key)):
                changed = True
        # Accented while the search differs from the defaults, so a scan that
        # is quietly narrower -- or twice as slow -- says so from the topbar.
        self.filters_btn.setIcon(glyphs.funnel(
            styles.ACCENT if changed else styles.TEXT_DIM))

    def _set_filter(self, key: str, on: bool) -> None:
        """Store one filter and re-ask the question with it.

        Rescanning is the point: the list on screen was produced under the old
        filter, so leaving it there would show an answer to a question nobody
        is asking any more.
        """
        try:
            cfg = config.load()
            if bool(cfg.get(key)) != bool(on):
                cfg[key] = bool(on)
                config.save(cfg)
        except Exception:
            pass
        self._sync_filters()
        if self._on_rescan:
            self._on_rescan()

    def _sync_pin_icon(self, on: bool) -> None:
        """A pressed pin is accented. `icon_btn:hover` recolours text, not
        icons, so the state has to be redrawn rather than restyled."""
        self.on_top_btn.setIcon(
            glyphs.pin(styles.ACCENT if on else styles.TEXT_DIM))

    def _say(self, text: str) -> None:
        """Put one line in the hint, with the standing notice beside it.

        The tooltip repeats the whole thing: the hint carries an Ignored size
        policy so the window can shrink, which means it really is clipped at
        narrow widths and there would otherwise be no way to read it.
        """
        self._said = text
        self._copy_token = None      # any message cancels a pending revert
        full = "%s   ·   %s" % (text, self._notice) if self._notice else text
        self.hint.setText(full)
        self.hint.setToolTip(self._notice_tip or full)

    def set_notice(self, text: str = "", tip: str = "") -> None:
        """A standing line beside the hint. Empty arguments take it away.

        This is startup advice, not live state. The only user is the "your
        requests go out unsigned" warning, which used to be a Windows balloon
        at launch: it stands through the idle period and the first scan, then
        goes. Repeating it under every scan would be the nagging the balloon
        was removed to stop; dropping it silently would lose the one place the
        user is told the setting exists. About still says it permanently, in
        the User-Agent line.
        """
        self._notice, self._notice_tip = text, tip
        self._say(self._said)

    def tree_expand_all(self) -> None:
        self.tree.expandAll()

    # --- captions ---------------------------------------------------------

    def _label_widgets(self) -> None:
        """The ONE place a caption or a tooltip is set.

        There is no language to switch any more, so this runs once, from
        `_build`. It stays a separate function for the discipline it enforces:
        a new button gets its tooltip HERE, where the whole set can be read at
        a glance, instead of three lines after its own constructor where the
        next reader will not find it.

        Every widget it touches has to be held on `self` -- a local in
        `_build` cannot be reached from here. That trap outlived the language
        switch it was written for.
        """
        # The glyph buttons carry no text at all, so their label IS the
        # tooltip -- without one they are four unexplained shapes.
        self.rescan_btn.setToolTip(i18n.t("tip.rescan"))
        self.clear_btn.setToolTip(i18n.t("tip.clear"))
        self.expand_btn.setToolTip("%s   ·   %s" % (
            i18n.t("btn.expand"), i18n.t("btn.expand_tip")))
        self.collapse_btn.setToolTip("%s   ·   %s" % (
            i18n.t("btn.collapse"), i18n.t("btn.collapse_tip")))
        self.on_top_btn.setToolTip("%s   ·   %s" % (
            i18n.t("btn.on_top"), i18n.t("btn.on_top_tip")))
        self.filters_btn.setToolTip("%s\n\n%s" % (i18n.t("btn.filters"),
                                                  i18n.t("filter.tip")))
        for key, act in self.filter_actions.items():
            act.setText(i18n.t("filter." + _FILTER_KEYS[key]))
        self.copy_action.setText(i18n.t("action.copy_names"))
        for level, lbl in self._count_labels.items():
            lbl.setToolTip(_count_tip(level))
        # The handle is in the tooltip rather than the caption: a caption
        # reading "Discord: kersid_jay" would set the window's minimum width.
        self.discord_btn.setToolTip(i18n.t("contact.tip_discord", DISCORD))
        self.telegram_btn.setToolTip(i18n.t("contact.tip_telegram", TELEGRAM))
        self.eve_btn.setToolTip(i18n.t("contact.tip_eve", CHARACTER))
        self.opacity_slider.setToolTip(i18n.t("tip.opacity"))
        self._say(i18n.t("status.idle"))

    def _type_name(self, type_id: int) -> str:
        """Tooltip text for one icon: modules first, then any ship."""
        if type_id in MODULE_LABEL:
            return MODULE_LABEL[type_id]
        if self._sets.is_module(type_id):
            return self._sets.module_name(type_id)
        return self._sets.hull_name(type_id)

    def _on_icon_ready(self, type_id: int) -> None:
        # Both delegates: each keeps its own scaled-pixmap cache, and the one
        # that was not told would go on drawing the old scale forever.
        for delegate in self._delegates:
            delegate.forget(type_id)
        self.tree.viewport().update()

    # --- population ------------------------------------------------------

    def _set_counts(self, counts: dict) -> None:
        for level, lbl in self._count_labels.items():
            n = counts.get(level, 0)
            if n:
                lbl.setText(str(n))
                lbl.setToolTip(_count_tip(level))
                lbl.show()
            else:
                lbl.hide()

    def show_scanning(self, count: int) -> None:
        self._say(i18n.t("status.scanning", count))
        self.rescan_btn.setEnabled(False)

    def show_stage(self, stage: str, count: int) -> None:
        """A word about where the pipeline is, before any verdict exists."""
        if stage == scan.STAGE_RESOLVING:
            self.rescan_btn.setEnabled(False)
            self._say(i18n.t("status.resolving", count))
        elif stage == scan.STAGE_SCANNING:
            self.begin_scan(count)

    def begin_scan(self, total: int) -> None:
        """Empty the tree and start filling it as answers arrive.

        The window used to appear only once the whole scan was over, which on
        a full trade hub is minutes of nothing. Cached pilots -- and only
        pilots caught with a cyno are cached -- land here before a single
        request leaves the machine, so the dangerous names are on screen
        immediately and the rest fill in underneath them.
        """
        self._reset_stream(total)
        self.rescan_btn.setEnabled(False)
        self._say(i18n.t("status.scanning", self._stream_total))

    def _reset_stream(self, total: int = 0) -> None:
        """Back to an empty list. Shared by a new scan and by Clear.

        Also called from `__init__`, so that `add_pilot` cannot meet a missing
        attribute: a `pilot_ready` arriving without a preceding
        STAGE_SCANNING would otherwise raise on `self._stream_done`.
        """
        self._last_result = None
        self._stream_keys = []
        self._stream_counts = {}
        self._stream_total = max(0, int(total))
        self._stream_done = 0
        if getattr(self, "tree", None) is not None:
            self.tree.clear()
            self._set_counts({})

    def clear(self) -> None:
        """Empty the list and go back to waiting.

        ⚠️ The tray icon keeps the colour of the last verdict. That is
        deliberate: the tray means "the last answer this session", the window
        means "what is on screen", and resetting it would need a callback from
        the window into TrayApp -- the exact coupling that went away with the
        language switch.
        """
        self._reset_stream(0)
        self.rescan_btn.setEnabled(True)
        self._say(i18n.t("status.idle"))

    def add_pilot(self, p) -> None:
        """One pilot's answer, dropped into the place it will end up in.

        The insertion point comes from `scan.pilot_sort_key`, the same function
        the final render sorts by. Two copies of that rule would let the list
        reshuffle itself when the scan finished, which looks like a bug even
        when both orders are defensible.
        """
        self._stream_done += 1
        self._stream_counts[p.level] = self._stream_counts.get(p.level, 0) + 1
        self._set_counts(self._stream_counts)
        if p.level != analyze.LEVEL_NONE:
            key = scan.pilot_sort_key(p)
            at = bisect.bisect_left(self._stream_keys, key)
            self._stream_keys.insert(at, key)
            self.tree.insertTopLevelItem(at, self._pilot_item(p))
            self._icons.warm(dict.fromkeys(self._icons_wanted(p)))
        if self._stream_total:
            self._say(i18n.t("status.progress", self._stream_done,
                             self._stream_total))

    def show_rejected(self, reason: str, key: str = "", args=()) -> None:
        """`reason` is the English text; `key` lets us say it in the UI language."""
        said = i18n.t(key, *args) if key else reason
        self._say(i18n.t("status.rejected", said))
        self.rescan_btn.setEnabled(True)

    def show_result(self, result) -> None:
        """The canonical render. Streaming builds the same tree row by row;
        this one rebuilds it once from the finished result, so the two can
        never drift apart over a long scan."""
        self.rescan_btn.setEnabled(True)
        self._last_result = result
        # Repainting 200 rows one at a time is a visible flicker right at the
        # end of a scan, and there is nothing to see until it is done.
        self.tree.setUpdatesEnabled(False)
        try:
            self._render(result)
        finally:
            self.tree.setUpdatesEnabled(True)

    def _render(self, result) -> None:
        self.tree.clear()

        counts = {}
        for p in result.pilots:
            counts[p.level] = counts.get(p.level, 0) + 1
        self._set_counts(counts)

        bits = [i18n.t("hint.bottom")]
        if result.own_seen:
            bits.append(i18n.t("status.own") + ", ".join(result.own_seen))
        if result.unresolved:
            bits.append(i18n.t("status.unresolved", len(result.unresolved)))
        self._say("   ·   ".join(bits))

        flagged = result.flagged
        for p in flagged:
            self.tree.addTopLevelItem(self._pilot_item(p))
        # Deliberately never auto-expanded: the collapsed row already answers
        # the question, and the killmail list is for when you want to argue
        # with the answer. "Развернуть" is one click away.

        # Ask for every icon this screen needs in one go, so the downloads
        # overlap instead of trickling in one repaint at a time.
        wanted: list = []
        for p in flagged:
            wanted.extend(self._icons_wanted(p))
        self._icons.warm(dict.fromkeys(wanted))

    @staticmethod
    def _icons_wanted(p) -> list:
        """Every type id one pilot's row and its expansion will draw.

        The evidence rows can name hulls the summary leaves out -- a pilot
        flagged on a module may have died in something that never earns a ship
        icon of its own.
        """
        wanted = list(p.modules) + list(p.ships)
        for f in p.findings:
            for key in ("ship_type_id", "module_type_id"):
                tid = _get(f, key)
                if tid:
                    wanted.append(tid)
        return wanted

    def _pilot_item(self, p) -> QTreeWidgetItem:
        item = QTreeWidgetItem([p.name, "", ""])
        colour = QBrush(QColor(styles.LEVEL_COLORS.get(p.level, styles.TEXT)))
        item.setForeground(0, colour)

        if p.level == analyze.LEVEL_CYNO:
            bold = QFont()
            bold.setBold(True)
            item.setFont(0, bold)

        # Modules carry an underline in their own colour; ships do not, so the
        # eye reads one row of "what he had" and one of "what he flew".
        item.setData(1, _ROLE_ICONS,
                     [(m, styles.MODULE_COLORS.get(m)) for m in p.modules])
        item.setData(2, _ROLE_ICONS, [(sh, None) for sh in p.ships])

        item.setData(0, _ROLE_URL,
                     "https://zkillboard.com/character/%d/" % p.character_id)
        item.setData(0, _ROLE_NAME, p.name)
        # A cached row says when it was last checked: the cache never expires
        # a positive, so without the date there is no way to tell an answer
        # from this minute apart from one from last month.
        when = getattr(p, "checked_at", 0.0) or 0.0
        if getattr(p, "from_cache", False) and when:
            item.setToolTip(0, i18n.t(
                "tip.checked", level_label(p.level),
                time.strftime("%Y-%m-%d", time.localtime(when))))
        else:
            item.setToolTip(0, i18n.t("tip.pilot", level_label(p.level)))

        for f in sorted(p.findings,
                        key=lambda x: (_KIND_ORDER.get(_get(x, "kind"), 9),
                                       -_get(x, "km_time"))):
            item.addChild(self._finding_item(f))
        return item

    def _finding_item(self, f) -> QTreeWidgetItem:
        kind = _get(f, "kind")
        ship = _get(f, "ship_type_id")
        mod = _get(f, "module_type_id")
        when = time.strftime("%Y-%m-%d", time.gmtime(_get(f, "km_time")))
        # Ship and module share one column: the parent row uses column 3 for a
        # count, so putting a module name there too made the header a lie and
        # truncated "Industrial Cyno".
        # The ship keeps its name -- one row, one hull, and the name is the
        # thing you actually read here. The module does not: its icon and
        # frame already say which of the three it was, and the parent row
        # spells it out anyway.
        # One row now stands for every killmail of its kind on that hull, so
        # it has to say how many. See analyze.group_findings for why: without
        # grouping, a pilot who flies one hull daily buried every other piece
        # of his own evidence.
        n = _get(f, "n", 1) or 1
        what = self._sets.hull_name(ship) if ship else ""
        if n > 1:
            what = "%s  x%d" % (what, n) if what else "x%d" % n
        child = QTreeWidgetItem(
            ["%s   %s" % (when, short_kind_label(kind)), "", what])

        child.setForeground(0, QBrush(QColor(styles.TEXT_DIM)))
        child.setForeground(2, QBrush(QColor(styles.TEXT_DIM)))
        if mod:
            child.setData(_COL_MODULES, _ROLE_ICONS,
                          [(mod, styles.MODULE_COLORS.get(mod))])
        if ship:
            child.setData(_COL_SHIPS, _ROLE_ICONS, [(ship, None)])
        child.setData(0, _ROLE_URL, "https://zkillboard.com/kill/%d/"
                      % _get(f, "killmail_id"))
        child.setToolTip(0, i18n.t("tip.killmail"))
        return child

    # --- interaction -----------------------------------------------------

    def _open_link(self, item, _column) -> None:
        url = item.data(0, _ROLE_URL)
        if url:
            webbrowser.open(url)

    def _copy_selected(self) -> None:
        # Read the name from its role, not from a column index: the columns
        # have been rearranged once already.
        names = [i.data(0, _ROLE_NAME) for i in self.tree.selectedItems()
                 if i.parent() is None and i.data(0, _ROLE_NAME)]
        if names:
            text = "\n".join(names)
            # Without this the watcher reads our own write and rescans the
            # very pilots that were just copied.
            clipboard.expect(text)
            QApplication.clipboard().setText(text)

    def showEvent(self, event):
        super().showEvent(event)
        # Deferred by one turn of the event loop: inside showEvent the native
        # window is still being set up, and reaching for its handle there can
        # force a second, re-entrant creation.
        QTimer.singleShot(0, self._dark_titlebar)

    def _dark_titlebar(self) -> None:
        """Ask Windows for the dark caption bar.

        Qt styles the client area only, so a white system title bar sat on top
        of a black window. DWMWA_USE_IMMERSIVE_DARK_MODE is the supported way
        to ask for the other one; it is attribute 20 from build 18985 onward
        and 19 before that, and asking with the wrong number simply fails.

        Runs on every show, not once at construction: there is no HWND before
        the first show, and toggling always-on-top recreates the native window
        with a fresh one.

        ctypes here does not touch invariant 1 -- that forbids Qt inside
        `core/`, not the platform inside `ui/`.
        """
        try:
            import ctypes
            handle = self.windowHandle()
            if handle is None:
                return
            # windowHandle().winId(), never self.winId(): the latter CREATES
            # the native window if it is missing, which is the last thing to
            # do from a deferred callback.
            hwnd = ctypes.c_void_p(int(handle.winId()))
            on = ctypes.c_int(1)
            for attribute in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, ctypes.c_uint(attribute), ctypes.byref(on),
                        ctypes.sizeof(on)) == 0:
                    return
        except Exception:
            # Not Windows, or a build that has never heard of the attribute.
            pass

    def closeEvent(self, event):
        """Closing hides to tray rather than quitting -- the app's job is to
        sit there and answer when you paste."""
        self.save_geometry()
        event.ignore()
        self.hide()
