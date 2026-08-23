"""Type icons as QPixmaps, fetched off the GUI thread.

Modelled on f:/123/Jump planer/ui/icon_cache.py -- same memory dict, same
`_pending` guard against duplicate in-flight requests, same `icon_ready`
signal that tells the view to repaint one row. Two deliberate differences:

  * the bytes come from `core.icons`, not from a QNetworkAccessManager here.
    All network in this project lives in `core/` (invariant 1), and that is
    also what gives the download a rate limit and a negative cache.
  * a type that has no artwork is remembered as a miss, so it is asked for
    once rather than on every repaint.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, QRunnable, Signal
from PySide6.QtGui import QPixmap

from core import icons


class _Job(QRunnable):
    """One download, on the pool. Emits nothing itself -- the signal lives on
    the cache, because a QRunnable is not a QObject."""

    def __init__(self, cache, type_id: int):
        super().__init__()
        self._cache = cache
        self._type_id = type_id

    def run(self) -> None:
        data = None
        try:
            data = icons.get(self._type_id)
        except Exception:
            data = None
        self._cache._delivered.emit(self._type_id, data or b"")


class IconCache(QObject):
    icon_ready = Signal(int)            # this type_id can now be drawn
    _delivered = Signal(int, bytes)     # worker -> GUI thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mem: dict[int, QPixmap] = {}
        self._pending: set[int] = set()
        self._pool = QThreadPool(self)
        # Same width as the killboard pool. The image CDN has its own token
        # bucket, so this only bounds how many threads sit waiting on it.
        self._pool.setMaxThreadCount(4)
        self._delivered.connect(self._on_delivered)

    def get(self, type_id: int) -> QPixmap | None:
        """The pixmap if we have it, else None and a fetch is started."""
        if type_id in self._mem:
            pix = self._mem[type_id]
            return pix if not pix.isNull() else None
        data = icons.read_cached(type_id)
        if data:
            return self._store(type_id, data)
        if icons.is_known_miss(type_id) or type_id in self._pending:
            return None
        self._pending.add(type_id)
        self._pool.start(_Job(self, type_id))
        return None

    def warm(self, type_ids) -> None:
        """Pull whatever is already on disk into memory, fetch the rest."""
        for t in type_ids:
            self.get(t)

    def _store(self, type_id: int, data: bytes) -> QPixmap | None:
        pix = QPixmap()
        if not pix.loadFromData(data):
            # Remember the failure so a corrupt file is not decoded per repaint.
            pix = QPixmap()
        self._mem[type_id] = pix
        return pix if not pix.isNull() else None

    def _on_delivered(self, type_id: int, data: bytes) -> None:
        self._pending.discard(type_id)
        if self._store(type_id, data) is not None:
            self.icon_ready.emit(type_id)


_instance: IconCache | None = None


def get_icon_cache() -> IconCache:
    global _instance
    if _instance is None:
        _instance = IconCache()
    return _instance
