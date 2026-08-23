"""Type icons from CCP's image server, cached on disk.

    icons.get(28646) -> bytes | None      one icon, fetching it if needed
    icons.prefetch(sets)                  the whole known cyno set, in parallel

Qt-free on purpose (invariant 1): this hands back PNG bytes and nothing else.
Turning them into a QIcon is `ui/icon_cache.py`'s job.

Three things were verified live against the image server before this was
written, and none of them should be re-litigated from memory:

  * `/types/{id}/icon` works for BOTH modules and ships. `/render` is a
    ship-only route -- it answers 400 for 21096, 28646 and 52694.
  * Cyno I (21096) and Industrial Cyno (52694) return a BYTE-IDENTICAL icon;
    they share iconID 1444 in the SDE. Only Covert Cyno looks different. The
    UI therefore cannot rely on the artwork alone to tell them apart.
  * There is no icon data in any local SDE dump. `invTypes.iconID` is a
    foreign key into a table those dumps do not ship, and for recon hulls it
    is NULL outright. Downloading is the only route.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging
import os
import time

from . import config
from .http import TIMEOUT, ZKB_CONCURRENCY, session
from .ratelimit import images_bucket

log = logging.getLogger("cc.icons")

BASE = "https://images.evetech.net/types/%d/icon?size=%d"
SIZE = 64

# Same shape as zkb's: three attempts, then give up for this run.
_RETRY_PAUSES = (1.0, 3.0)

# A ceiling, borrowed from Jump Planner's icon cache. EVE has a finite number
# of type ids so growth is bounded anyway; this just keeps the folder tidy.
_DISK_CACHE_MAX = 4000

_MAX_BYTES = 512 * 1024


def icons_dir() -> str:
    d = os.path.join(config.data_dir(), "icons")
    os.makedirs(d, exist_ok=True)
    return d


def _png_path(type_id: int) -> str:
    return os.path.join(icons_dir(), "%d.png" % type_id)


def _miss_path(type_id: int) -> str:
    return os.path.join(icons_dir(), "%d.miss" % type_id)


def read_cached(type_id: int) -> bytes | None:
    """Whatever is already on disk. Never touches the network."""
    try:
        with open(_png_path(type_id), "rb") as fh:
            return fh.read() or None
    except OSError:
        return None


def is_known_miss(type_id: int) -> bool:
    """Has this type already answered "no icon"?

    Jump Planner has no equivalent, and so re-asks the server for every type
    that has no artwork -- on every single repaint.
    """
    return os.path.exists(_miss_path(type_id))


def _write_atomic(path: str, data: bytes) -> None:
    tmp = path + ".part"
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError:
        log.debug("icon write failed: %s", path)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def fetch(type_id: int) -> bytes | None:
    """Download one icon. Returns None for a type that has no artwork."""
    url = BASE % (type_id, SIZE)
    for attempt in range(len(_RETRY_PAUSES) + 1):
        images_bucket.take()
        try:
            # The shared session advertises Accept: application/json for the
            # whole process. Asking for JSON while wanting a PNG is exactly
            # the kind of thing a CDN is entitled to take literally.
            resp = session().get(url, timeout=TIMEOUT,
                                 headers={"Accept": "image/png"})
        except Exception as exc:
            if attempt >= len(_RETRY_PAUSES):
                log.debug("icon %d: %s", type_id, exc)
                return None
            time.sleep(_RETRY_PAUSES[attempt])
            continue
        if resp.status_code == 200:
            data = resp.content
            return data if data and len(data) <= _MAX_BYTES else None
        # 404 and 400 are settled answers: this type has no icon, ever.
        if resp.status_code in (400, 404):
            return None
        if attempt >= len(_RETRY_PAUSES):
            log.debug("icon %d: HTTP %d", type_id, resp.status_code)
            return None
        time.sleep(_RETRY_PAUSES[attempt])
    return None


def get(type_id: int, allow_fetch: bool = True) -> bytes | None:
    """Cached bytes, downloading once if we have never asked."""
    cached = read_cached(type_id)
    if cached is not None:
        return cached
    if is_known_miss(type_id) or not allow_fetch:
        return None
    data = fetch(type_id)
    if data is None:
        _write_atomic(_miss_path(type_id), b"")
        return None
    _write_atomic(_png_path(type_id), data)
    return data


def missing(type_ids) -> list:
    """Which of these we have neither an icon nor a settled "no" for."""
    return [t for t in dict.fromkeys(type_ids)
            if read_cached(t) is None and not is_known_miss(t)]


def prefetch(sets, extra=(), on_progress=None) -> int:
    """Fill the cache for every module and hull we know about.

    Roughly 76 files and half a megabyte on a fresh install, once. Everything
    outside the current cyno set -- the rookie frigates that carried cynos
    before 2018 -- arrives lazily as it shows up in evidence.
    """
    wanted = list(sets.modules) + list(sets.hulls) + list(extra)
    todo = missing(wanted)
    if not todo:
        return 0
    done = 0
    workers = min(ZKB_CONCURRENCY, len(todo))
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for _ in ex.map(get, todo):
            done += 1
            if on_progress is not None:
                on_progress(done, len(todo))
    log.info("icons: fetched %d of %d", done, len(todo))
    return done


def prune(limit: int = _DISK_CACHE_MAX) -> None:
    """Drop the oldest icons if the folder ever outgrows the ceiling."""
    try:
        d = icons_dir()
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if f.endswith(".png")]
        if len(files) <= limit:
            return
        files.sort(key=lambda p: os.stat(p).st_mtime)
        for p in files[:len(files) - limit]:
            try:
                os.unlink(p)
            except OSError:
                pass
    except OSError:
        pass


def stats() -> dict:
    try:
        names = os.listdir(icons_dir())
    except OSError:
        return {"icons": 0, "misses": 0}
    return {"icons": sum(1 for n in names if n.endswith(".png")),
            "misses": sum(1 for n in names if n.endswith(".miss"))}
