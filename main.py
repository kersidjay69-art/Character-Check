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
    from ui import styles

    cfg = config.load()
    _start_logging(config.data_dir())
    i18n.set_language(cfg.get("lang"))

    app = QApplication(sys.argv)
    app.setApplicationName("Character Check")
    # Applied before the UI modules read ACCENT, exactly as Jump Planner does.
    app.setStyleSheet(styles.apply_theme(cfg.get("theme", "default")))
    # The window closing must not end the process -- the app lives in the tray.
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # Say it wherever anyone can hear it: a frozen build has no console.
        logging.error("%s", i18n.t("main.no_tray"))
        if sys.stderr is not None:
            print(i18n.t("main.no_tray"))
        return 2

    from ui.tray import TrayApp
    tray = TrayApp(app)
    tray.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
