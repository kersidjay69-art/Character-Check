"""Windows GUI entry point -- the same app as main.py, without a console.

`python main.py` opens a console window and keeps it there for the life of the
tray app. `.pyw` is the extension Windows reserves for GUI programs: launched
through pythonw.exe it has no console at all.

Kept as a two-line shim rather than a copy so there is exactly one main().
See start.cmd for a launcher that does not depend on file associations.
"""
import sys

from main import main

if __name__ == "__main__":
    sys.exit(main())
