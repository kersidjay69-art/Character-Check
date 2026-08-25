"""EVE-themed dark stylesheet, matching the look of Jump Planner.

The neutral greys are copied verbatim from `f:/123/Jump planer/ui/styles.py`,
so the two apps look like one family. Three things are this project's own:

  * QTreeWidget/QTreeView rules -- Jump Planner styles QTableWidget and
    QListWidget but never a tree, and this app's whole window is a tree.
  * Verdict colours, mapped onto the palette's existing status colours rather
    than inventing new ones.
  * The accent. Jump Planner's is `#4fc3f7`; this one is amber, taken from the
    project's own logo -- the only artwork it owns, and the one thing that
    should not look borrowed. Chosen by measurement rather than by eye: 8.2:1
    against BG_PANEL (the blue managed 8.9), and 22.9 / 19.6 degrees of hue
    away from the `cyno` red and the `hull` yellow, which it must never be
    mistaken for.

Themes only swap the accent; the dark base stays, as in EVE's Photon UI.
"""
from __future__ import annotations

# -- Palette (neutral grey, identical to Jump Planner) ----------------------
BG_DEEP = "#0c0c0e"
BG_PANEL = "#17171a"
BG_CARD = "#1c1c20"
BG_HEADER = "#131316"
BORDER = "#32323a"
BORDER_LT = "#4a4a55"
ACCENT = "#ff944d"
ACCENT2 = "#00bcd4"
TEXT = "#d4d4d8"
TEXT_DIM = "#8e8e98"
SELECT_BG = "#2c2c34"
PRIMARY_BG = "#26262e"
PRIMARY_BG_HOVER = "#34343e"

YELLOW = "#f0c040"
ORANGE = "#ff9800"
RED = "#ef5350"
GREY = "#6e6e76"
# Same Material row as RED and ORANGE. Deliberately NOT `ACCENT`: that one is
# rewritten per faction theme, and an industrial verdict must not change colour
# because the user picked Amarr.
BLUE = "#42a5f5"
PURPLE = "#ba68c8"

# Verdict -> colour, and the pilot's name is what wears it. Red is a combat
# cyno, blue an industrial one, yellow a combat cyno hull with nothing aboard,
# grey a pilot who is no threat. ORANGE is no longer a verdict colour.
LEVEL_COLORS = {
    "cyno": RED,
    "indy": BLUE,
    "hull": YELLOW,
    # Cyno-capable hull and nothing else. Deliberately a LIGHTER grey than
    # `none`: the two never meet in the tree (clean pilots are not listed at
    # all) but they stand side by side as numbers in the topbar, where two
    # identical greys would be unreadable.
    "seen": TEXT_DIM,
    "none": GREY,
}

# Each module gets its own framed colour. This is not decoration: Cyno I and
# Industrial Cyno ship a BYTE-IDENTICAL icon (both are iconID 1444 in the SDE),
# so without the frame the red case and the blue one look the same. Covert
# takes purple, which also separates it from plain Cyno at a glance -- their
# artwork does differ, but not enough to read at 20 pixels.
MODULE_COLORS = {
    21096: RED,        # Cynosural Field Generator I
    28646: PURPLE,     # Covert Cynosural Field Generator I
    52694: BLUE,       # Industrial Cynosural Field Generator
}

# Tech tier -> corner wedge on a ship icon, keyed by SDE metaGroupID.
# Drawn by us rather than taken from the image server: of the 37 Tech II cyno
# hulls, 25 come back from images.evetech.net with no badge at all, while
# Jaguar, Redeemer and every Tech III hull have one. Since there is no pattern,
# we paint our own over the top for all of them.
META_COLORS = {
    2: ORANGE,         # Tech II
    14: RED,           # Tech III
}

# Height of one tree row, in pixels, and the single source of truth for it.
# The icon cell is sized FROM this (see IconRowDelegate), so artwork fills the
# row edge to edge. They used to be set independently -- a 30px row around a
# 26px cell -- which read on screen as gaps between the rows.
ROW_H = 30

# The logo beside the title in the topbar. Deliberately small: it is the same
# picture the taskbar shows, and at this size it is decoration -- the radar
# dial does not read below about 32 px. Larger would make the topbar taller
# for no information gained.
LOGO_H = 22

THEME_PRESETS = [
    {"id": "default", "name": "Default", "accent": "#ff944d", "accent2": "#e07b39"},
    {"id": "amarr", "name": "Amarr Empire", "accent": "#e0b347", "accent2": "#caa030"},
    {"id": "gallente", "name": "Gallente Federation", "accent": "#34c79a",
     "accent2": "#26a37d"},
    {"id": "caldari", "name": "Caldari State", "accent": "#5b9bd5",
     "accent2": "#3f7fc0"},
    {"id": "ore", "name": "Outer Ring Excavations", "accent": "#e8c020",
     "accent2": "#c9a514"},
    {"id": "minmatar", "name": "Minmatar Republic", "accent": "#d4623a",
     "accent2": "#b54a28"},
    {"id": "soe", "name": "Sisters of EVE", "accent": "#c9d36b", "accent2": "#aab84d"},
    {"id": "coal", "name": "Coal", "accent": "#b8c4cc", "accent2": "#90a0aa"},
    {"id": "photon", "name": "Photon Mode", "accent": "#4a90e2", "accent2": "#5b9bd5"},
]
THEMES = {p["id"]: p for p in THEME_PRESETS}


_QSS_TEMPLATE = """
QMainWindow {{
    background: {BG_DEEP};
}}

/* The central widget, painted explicitly. `QWidget` below is transparent so
   that panels and rows can sit on whatever is under them -- but the strips
   that belong to no widget at all (the margin around the tree, the row the
   hint sits in) then paint nothing whatsoever, which grabs as fully
   transparent pixels rather than as the window's dark background. */
QWidget#central {{
    background: {BG_DEEP};
}}

QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 12px;
}}

QFrame#panel {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}

QFrame#topbar {{
    background: {BG_PANEL};
    border-top: 1px solid {ACCENT};
    border-bottom: 1px solid {ACCENT};
}}

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 11px;
}}

QLabel#title {{
    color: {ACCENT};
    font-size: 14px;
    font-weight: bold;
    letter-spacing: 2px;
}}

QLabel#accent {{
    color: {ACCENT};
    font-weight: bold;
}}

QPushButton {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 10px;
    font-size: 12px;
    text-align: center;
}}

QPushButton:hover {{
    background: {BORDER};
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton:pressed {{
    background: {BORDER_LT};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

QPushButton#primary {{
    background: {PRIMARY_BG};
    color: {ACCENT};
    border: 1px solid {ACCENT};
    font-weight: bold;
    font-size: 13px;
    /* Snug to the label rather than a fixed width: this rule is shared, and
       a width that suits one caption clips another. */
    padding: 6px 12px;
}}

QPushButton#primary:hover {{
    background: {PRIMARY_BG_HOVER};
}}

QPushButton#icon_btn {{
    background: transparent;
    border: none;
    padding: 2px 4px;
    color: {TEXT_DIM};
    font-size: 14px;
}}

QPushButton#icon_btn:hover {{
    color: {ACCENT};
}}

/* Square glyph buttons -- the two that DO something (check the clipboard,
   empty the list), as opposed to the borderless ones that only change what is
   already on screen. The border is the whole difference: an action needs to
   look like a button, not like a mark floating in the bar. */
QPushButton#square_btn {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 0px;
}}

QPushButton#square_btn:hover {{
    background: {BORDER};
    border-color: {ACCENT};
}}

QPushButton#square_btn:pressed {{
    background: {BORDER_LT};
}}

QPushButton#square_btn:disabled {{
    background: {BG_PANEL};
    border-color: {BORDER};
}}

/* The contacts row at the foot of the window. BORDER, not ACCENT: the topbar
   already owns two accent lines, and a third at the bottom would compete for
   the eye with the least important row on screen. */
QFrame#footer {{
    background: {BG_PANEL};
    border-top: 1px solid {BORDER};
}}

QLineEdit, QComboBox {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    selection-background-color: {SELECT_BG};
}}

QLineEdit:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {SELECT_BG};
}}

/* Trees are this app's main surface; Jump Planner only styles tables, so
   these rules mirror its QTableWidget look one to one. */
QTreeWidget, QTreeView {{
    /* Transparent, and the viewport paints its own base instead -- see
       `ResultsWindow._paint_backdrop`. A background set here would be painted
       AFTER the event filter and would cover the backdrop picture entirely. */
    background: transparent;
    alternate-background-color: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    outline: none;
}}

QTreeWidget::item, QTreeView::item {{
    /* No vertical padding: the icon cell IS the row height. Any padding here
       reappears as a gap between rows. */
    padding: 0px 2px;
    border: none;
    min-height: {ROW_H}px;
}}

/* Translucent, because the artwork is behind the rows now. Opaque here
   would black out a strip of the picture under the cursor. */
QTreeWidget::item:hover, QTreeView::item:hover {{
    background: {HOVER_RGBA};
}}

/* Background only. Recolouring the text here would repaint the pilot's name
   in the accent colour, and the name's colour IS the verdict. */
QTreeWidget::item:selected, QTreeView::item:selected {{
    background: {SELECT_RGBA};
}}

QTreeWidget::branch:hover {{
    background: {HOVER_RGBA};
}}

QHeaderView::section {{
    background: {BG_HEADER};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 5px 8px;
    font-size: 11px;
    font-weight: bold;
}}

QHeaderView::section:hover {{
    background: {BG_CARD};
    color: {TEXT};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QProgressBar {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 3px;
    text-align: center;
    color: {TEXT};
    height: 8px;
    font-size: 10px;
}}

QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}

QToolTip {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 4px 8px;
    border-radius: 3px;
}}

QMenu {{
    background: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QMenu::item {{
    padding: 4px 18px;
}}

QMenu::item:selected {{
    background: {SELECT_BG};
    color: {ACCENT};
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

QDialog {{
    background: {BG_PANEL};
    color: {TEXT};
}}

QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    background: {BG_PANEL};
    border-radius: 2px;
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
"""


def rgba(colour: str, alpha: float) -> str:
    """`#rrggbb` plus an alpha, as CSS. Qt style sheets accept rgba().

    Needed because the results tree now sits on a picture: an opaque row
    background blanks a strip of it, and hover and selection still have to
    read as feedback.
    """
    c = colour.lstrip("#")
    return "rgba(%d, %d, %d, %.2f)" % (
        int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha)


# What sits behind a label drawn over the backdrop. ⚠️ Measured, not chosen:
# composited over the brightest pixel the artwork actually contains --
# (152, 119, 76), in the station's wireframe -- BG_DEEP at 0.80 leaves the
# tightest of the tree's colours, RED `cyno`, at 4.55:1. The others land at
# 4.89 (TEXT_DIM), 6.00 (BLUE), 9.31 (YELLOW) and 10.74 (TEXT). Below 0.80 the
# red drops under 4.5 and the scrim stops doing its job. `GREY` is not in that
# list on purpose: it is the `none` level and clean pilots are never listed.
SCRIM = BG_DEEP
SCRIM_ALPHA = 0.80


def _build_qss() -> str:
    return _QSS_TEMPLATE.format(
        BG_DEEP=BG_DEEP, BG_PANEL=BG_PANEL, BG_CARD=BG_CARD, BG_HEADER=BG_HEADER,
        BORDER=BORDER, BORDER_LT=BORDER_LT, ACCENT=ACCENT, ACCENT2=ACCENT2,
        TEXT=TEXT, TEXT_DIM=TEXT_DIM, SELECT_BG=SELECT_BG,
        HOVER_RGBA=rgba(BG_CARD, 0.55), SELECT_RGBA=rgba(SELECT_BG, 0.80),
        PRIMARY_BG=PRIMARY_BG, PRIMARY_BG_HOVER=PRIMARY_BG_HOVER,
        ROW_H=ROW_H,
    )


def apply_theme(theme_id: str) -> str:
    """Apply a colour scheme: mutate the accent and rebuild MAIN_QSS.

    Call before the UI modules read ACCENT, i.e. at startup.
    """
    global ACCENT, ACCENT2, MAIN_QSS
    t = THEMES.get(theme_id, THEMES["default"])
    ACCENT = t["accent"]
    ACCENT2 = t["accent2"]
    MAIN_QSS = _build_qss()
    return MAIN_QSS


MAIN_QSS = _build_qss()
