"""Character Check -- tray application.

    python main.py

Sits in the tray. Copy a local member list in game (click a name in the member
list, Ctrl+A, Ctrl+C) and the results window shows who has a cyno history.
"""
from __future__ import annotations

import logging
import os
import sys

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _start_logging(data_dir: str) -> None:
    """Warnings to the console, or to a file when there is no console.

    A windowed frozen build has no stderr at all -- PyInstaller leaves it as
    None -- and logging's default StreamHandler would raise on the first
    warning it ever tried to write. Running from source this is a no-op.
    """
    if sys.stderr is None:
        try:
            logging.basicConfig(
                level=logging.WARNING, format=FORMAT,
                handlers=[logging.FileHandler(
                    os.path.join(data_dir, "app.log"), encoding="utf-8")])
            return
        except OSError:
            # An unwritable data directory must not stop the app from starting.
            logging.basicConfig(level=logging.WARNING, handlers=[
                logging.NullHandler()])
            return
    logging.basicConfig(level=logging.WARNING, format=FORMAT)


def main() -> int:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from core import config, i18n
    from ui import assets, single_instance, styles

    cfg = config.load()
    _start_logging(config.data_dir())

    app = QApplication(sys.argv)
    app.setApplicationName("Character Check")
    # Set on the application, not per window: it covers the results window,
    # the About dialog and the taskbar in one line. A missing asset yields an
    # empty QIcon, and setting an empty icon is a no-op.
    app.setWindowIcon(assets.logo_icon())
    # Applied before the UI modules read ACCENT, exactly as Jump Planner does.
    app.setStyleSheet(styles.apply_theme(cfg.get("theme", "default")))
    # The window closing must not end the process -- the app lives in the tray.
    app.setQuitOnLastWindowClosed(False)

    # One copy at a time. Two would make 16 requests a second at zKillboard
    # from one address, against a limit that exists because the penalty is an
    # IP ban, and would share one SQLite cache while both ran eviction on it.
    # A second launch is not an error, though: it is somebody asking for the
    # window, so the running copy shows itself and this process leaves quietly.
    server = single_instance.take_or_signal(config.data_dir())
    if server is None:
        logging.info("%s", i18n.t("main.already_running"))
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # Say it wherever anyone can hear it: a frozen build has no console.
        logging.error("%s", i18n.t("main.no_tray"))
        if sys.stderr is not None:
            print(i18n.t("main.no_tray"))
        return 2

    from ui.tray import TrayApp
    tray = TrayApp(app, instance_server=server)
    tray.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
