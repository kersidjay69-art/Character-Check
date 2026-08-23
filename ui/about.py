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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
)

from core import config

from . import styles

# Author contacts. Deliberately handles, not an email: an address in public
# source is a spam magnet, and none of these can be harvested into one.
DISCORD = "kersid_jay"
TELEGRAM = "@KersidJay"
TELEGRAM_URL = "https://t.me/KersidJay"
CHARACTER = "Leya Sokard"
CHARACTER_URL = "https://zkillboard.com/character/96931519/"

DISCLAIMER = (
    "Инструмент читает только публичные данные: буфер обмена, заголовки "
    "чатлогов, ESI и zKillboard. Он не связан с CCP hf и не одобрен ею — CCP "
    "не одобряет никакие сторонние приложения. EVE Online и все связанные "
    "материалы — собственность CCP hf.\n\n"
    "Распространяется по лицензии Apache 2.0, без каких-либо гарантий. "
    "Ответственность за использование несёт тот, кто запустил программу."
)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setMinimumWidth(520)
        self.setLayout(self._build())

    def _build(self) -> QVBoxLayout:
        title = QLabel("CHARACTER CHECK")
        title.setObjectName("title")

        version = QLabel("версия %s   ·   %s" % (config.VERSION,
                                                 config.PROJECT_URL))
        version.setObjectName("dim")
        version.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Shown so the user can see what their own copy sends, rather than
        # having to trust a sentence about it.
        ua = QLabel("User-Agent: %s" % config.user_agent())
        ua.setObjectName("dim")
        ua.setWordWrap(True)
        ua.setTextInteractionFlags(Qt.TextSelectableByMouse)

        note = QLabel(DISCLAIMER)
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
        contacts.addWidget(self._button("Discord: " + DISCORD,
                                        lambda: self._copy(DISCORD)))
        contacts.addWidget(self._button("Telegram: " + TELEGRAM,
                                        lambda: webbrowser.open(TELEGRAM_URL)))
        contacts.addWidget(self._button("EVE: " + CHARACTER,
                                        lambda: webbrowser.open(CHARACTER_URL)))
        contacts.addStretch(1)

        close = QPushButton(i18n.t("about.close"))
        close.setObjectName("primary")
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

    def _button(self, text: str, on_click) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(on_click)
        return btn

    def _copy(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.setWindowTitle(i18n.t("about.copied", text))
