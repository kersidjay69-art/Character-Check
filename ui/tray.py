"""Tray icon and the glue between the clipboard watcher and the window.

The watcher runs on its own thread inside core/, which knows nothing about Qt.
It hands text over through a Qt signal, so every scan happens on a worker
thread and only the UI update touches the GUI thread.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import (analyze, cache, chatlog, clipboard, config, cyno_sets,
                  http, i18n, icons, scan)

from . import single_instance, styles
from .about import AboutDialog
from .results_window import ResultsWindow, level_label

log = logging.getLogger("cc.ui")


def _icon(colour: str | None = None) -> QIcon:
    """A drawn cyno beacon, so the app ships without binary assets.

    Defaults to the theme accent, and switches to the verdict colour after a
    scan so the tray itself carries the answer.
    """
    colour = colour or styles.ACCENT
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(colour), 6))
    p.drawEllipse(12, 12, 40, 40)
    p.setPen(QPen(QColor(colour), 5))
    p.drawLine(32, 2, 32, 14)
    p.drawLine(32, 50, 32, 62)
    p.drawLine(2, 32, 14, 32)
    p.drawLine(50, 32, 62, 32)
    p.end()
    return QIcon(pix)


class ScanWorker(QObject):
    """Runs one scan off the GUI thread.

    Three signals rather than one, because a full trade hub takes minutes and
    the window used to show nothing at all until the last pilot was in:

      stage_changed  the pipeline reached a point worth a word on screen
      pilot_ready    one pilot answered; cached ones arrive before any request
      done           the finished result, which redraws the list canonically
    """

    done = Signal(object)
    stage_changed = Signal(str, int)
    pilot_ready = Signal(object)

    def __init__(self):
        super().__init__()
        self._own = ()

    def set_own(self, names) -> None:
        self._own = tuple(names)

    def scan(self, text: str) -> None:
        # Read fresh every time: the search filters live in config.json and
        # the window writes them there, so a copy taken at startup would go on
        # answering the old question after the user changed it.
        cfg = config.load()
        try:
            result = scan.scan_text(
                text, own_names=self._own, cfg=cfg,
                on_result=self.pilot_ready.emit,
                on_stage=self.stage_changed.emit)
        except Exception:
            log.exception("scan failed")
            return
        self.done.emit(result)


class TrayApp(QObject):
    _text_ready = Signal(str)

    def __init__(self, app: QApplication, instance_server=None):
        super().__init__()
        self.app = app
        # Held for the life of the app, not because anything reads it: a
        # QLocalServer that goes out of scope is collected and stops
        # listening, and the next launch would then start a second copy.
        self._instance_server = instance_server
        self.cfg = config.load()
        self.sets = cyno_sets.load()
        cache.connect()

        self.own = chatlog.own_characters(
            log_dir=self.cfg.get("log_dir") or None,
            max_age_h=float(self.cfg.get("chatlog_max_age_h", 72)))
        # The requests leave from THIS machine, so they carry THIS pilot's
        # name -- never the author's. Newest log first, so it is the character
        # actually being played. The refresh is needed because the shared HTTP
        # session may already have built its header.
        config.set_operator(self.own[0] if self.own else None)
        http.refresh_user_agent()

        # 76 icons and half a megabyte on a fresh install, once. Off the GUI
        # thread and fire-and-forget: a missing icon is a blank square, never
        # a reason to hold up the window.
        threading.Thread(target=self._prefetch_icons, name="cc-icons",
                         daemon=True).start()

        self.window = ResultsWindow(self.sets, on_rescan=self.scan_clipboard)

        self._thread = QThread()
        self.worker = ScanWorker()
        self.worker.set_own(self.own)
        self.worker.moveToThread(self._thread)
        self._thread.start()
        self._text_ready.connect(self.worker.scan)
        self.worker.done.connect(self._on_result)
        # Queued across the thread boundary by Qt, so the scan thread never
        # touches a widget.
        self.worker.stage_changed.connect(self._on_stage)
        self.worker.pilot_ready.connect(self.window.add_pilot)

        self.tray = QSystemTrayIcon(_icon(), parent=app)
        self.tray.setToolTip("Character Check")
        self.tray.activated.connect(self._on_tray_click)
        self._menu_ref = self._menu()
        self.tray.setContextMenu(self._menu_ref)
        self.tray.show()

        self.watcher = clipboard.ClipboardWatcher(
            self._on_clipboard,
            poll_ms=int(self.cfg.get("clipboard_poll_ms", 200)))
        self.watcher.start()

        if instance_server is not None:
            # A second launch asks for the window, and gets it -- raised and
            # focused. That is deliberately unlike the start of a scan, which
            # may only `show()`: taking focus away from EVE mid-fight is not
            # acceptable, but an explicit second launch IS the user asking.
            single_instance.listen_for_show(instance_server, self._show_window)

        if not config.contact_is_set(self.cfg):
            # Only when the chat logs gave us nothing either. This was a
            # Windows balloon until 2026-08-23; it is now a line that stands
            # in the window until the first accepted scan.
            self.window.set_notice(
                i18n.t("hint.no_contact"),
                i18n.t("hint.no_contact_tip", config.config_path()))

    def _prefetch_icons(self) -> None:
        try:
            icons.prune()
            got = icons.prefetch(self.sets)
        except Exception:
            log.exception("icon prefetch failed")
            return
        if got:
            log.info("icons: %s", icons.stats())

    def _menu(self) -> QMenu:
        menu = QMenu()
        show = QAction(i18n.t("tray.show"), menu)
        show.triggered.connect(self._show_window)
        menu.addAction(show)

        rescan = QAction(i18n.t("tray.rescan"), menu)
        rescan.triggered.connect(self.scan_clipboard)
        menu.addAction(rescan)
        menu.addSeparator()

        about = QAction(i18n.t("tray.about"), menu)
        about.triggered.connect(self._show_about)
        menu.addAction(about)

        settings = QAction(i18n.t("tray.settings"), menu)
        settings.triggered.connect(self._open_config)
        menu.addAction(settings)
        menu.addSeparator()

        quit_action = QAction(i18n.t("tray.quit"), menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        return menu

    # --- events ----------------------------------------------------------

    def _on_clipboard(self, text: str) -> None:
        """Called on the watcher thread -- hop to the worker via a signal."""
        self._text_ready.emit(text)

    def scan_clipboard(self) -> None:
        text = clipboard.read_text()
        if text:
            self._text_ready.emit(text)

    def _on_stage(self, stage: str, count: int) -> None:
        """Put the window up as the scan starts, not when it finishes.

        `show()` and nothing else: raising or activating here would pull focus
        out of EVE mid-scan. The end of a scan still raises the window, and
        only when something was actually found.
        """
        self.window.show_stage(stage, count)
        if stage == scan.STAGE_SCANNING:
            self.window.show()

    def _on_result(self, result) -> None:
        self.cfg = config.load()
        if not result.accepted:
            # Junk in the clipboard is the normal case; say nothing loudly.
            self.window.show_rejected(result.reason, result.reason_key,
                                      result.reason_args)
            return

        self.window.show_result(result)
        flagged = result.flagged
        top = flagged[0].level if flagged else analyze.LEVEL_NONE
        self.tray.setIcon(_icon(styles.LEVEL_COLORS.get(top)
                                if flagged else None))

        if flagged:
            # The whole notification, as of 2026-08-23: the window comes up
            # and the tray icon takes the verdict's colour. The balloon and
            # the beep were removed on request.
            #
            # ⚠️ Neither reaches a user with EVE in fullscreen -- the game
            # paints over the window, and no amount of asking Windows to
            # raise us changes that.
            # The beep was the one signal that did. That capability is gone
            # deliberately, not by oversight.
            self._show_window()

        # The advice about signing requests has had its chance by now.
        self.window.set_notice()

    def _on_tray_click(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_window()

    def _show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _show_about(self) -> None:
        dlg = AboutDialog(self.window)
        dlg.exec()

    def _open_config(self) -> None:
        path = config.config_path()
        if not __import__("os").path.exists(path):
            config.save(self.cfg)
        try:
            __import__("os").startfile(path)
        except Exception:
            log.exception("could not open %s", path)

    def _quit(self) -> None:
        # Quitting from the tray never fires the window's closeEvent, so the
        # placement would be lost exactly for the people who close it properly.
        self.window.save_geometry()
        self.watcher.stop()
        self._thread.quit()
        self._thread.wait(2000)
        cache.close()
        self.app.quit()
