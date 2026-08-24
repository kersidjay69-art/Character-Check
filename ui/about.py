"""The About window: what this is, who wrote it, and what it is not.

The author's three contacts live HERE and nowhere else. They are rendered for
a human to read and are never put into a request header -- see the module
docstring of `core/config.py` for why that separation is the whole point, and
`tests/test_distribution.py` for the test that keeps them out of `core/`.

Fleet Manager Online does the same thing: the same three handles sit in a page
footer (`web/index.html`), shown only on the login and setup screens.
"""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
)

from core import clipboard, config, i18n

from . import styles

# Author contacts. Deliberately handles, not an email: an address in public
# source is a spam magnet, and none of these can be harvested into one.
DISCORD = "kersid_jay"
TELEGRAM = "@KersidJay"
TELEGRAM_URL = "https://t.me/KersidJay"
CHARACTER = "Leya Sokard"
CHARACTER_URL = "https://zkillboard.com/character/96931519/"

# The disclaimer lives in core/i18n.py with the rest of the interface
# text ("about.disclaimer"). Only the author's handles are kept here --
# they are the one thing that must exist in exactly one place.


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("about.title"))
        self.setMinimumWidth(520)
        self.setLayout(self._build())

    def _build(self) -> QVBoxLayout:
        title = QLabel("CHARACTER CHECK")
        title.setObjectName("title")

        version = QLabel(i18n.t("about.version", config.VERSION,
                                config.PROJECT_URL))
        version.setObjectName("dim")
        version.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Shown so the user can see what their own copy sends, rather than
        # having to trust a sentence about it.
        ua = QLabel("User-Agent: %s" % config.user_agent())
        ua.setObjectName("dim")
        ua.setWordWrap(True)
        ua.setTextInteractionFlags(Qt.TextSelectableByMouse)

        note = QLabel(i18n.t("about.disclaimer"))
        note.setObjectName("dim")
        note.setWordWrap(True)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:%s;" % styles.BORDER)

        contacts_title = QLabel(i18n.t("about.contact"))
        contacts_title.setObjectName("dim")

        contacts = QHBoxLayout()
        contacts.setSpacing(8)
        # Discord has no per-username link, so the handle goes to the
        # clipboard instead -- the same compromise Fleet Manager Online makes.
        # Here the caption carries the handle and the tooltip says what the
        # click does; the window's own footer is the other way round, because
        # there the caption sets the minimum width and here it does not.
        contacts.addWidget(self._button(
            "Discord: " + DISCORD, lambda: self._copy(DISCORD),
            i18n.t("contact.tip_discord", DISCORD)))
        contacts.addWidget(self._button(
            "Telegram: " + TELEGRAM, lambda: webbrowser.open(TELEGRAM_URL),
            i18n.t("contact.tip_telegram", TELEGRAM)))
        contacts.addWidget(self._button(
            "EVE: " + CHARACTER, lambda: webbrowser.open(CHARACTER_URL),
            i18n.t("contact.tip_eve", CHARACTER)))
        contacts.addStretch(1)

        close = QPushButton(i18n.t("about.close"))
        close.setObjectName("primary")
        close.setToolTip(i18n.t("about.close_tip"))
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(ua)
        layout.addSpacing(4)
        layout.addWidget(note)
        layout.addWidget(line)
        layout.addWidget(contacts_title)
        layout.addLayout(contacts)
        layout.addSpacing(6)
        layout.addLayout(bottom)
        return layout

    def _button(self, text: str, on_click, tip: str = "") -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.clicked.connect(on_click)
        return btn

    def _copy(self, text: str) -> None:
        """Copy a handle and say so in the title bar, then put the title back.

        `clipboard.expect` first: the watcher polls a sequence number and
        cannot tell this write from a paste, so without it the handle comes
        straight back as a scan the user never asked for.
        """
        clipboard.expect(text)
        QApplication.clipboard().setText(text)
        self.setWindowTitle(i18n.t("contact.copied", text))
        QTimer.singleShot(
            2500, lambda: self.setWindowTitle(i18n.t("about.title")))
