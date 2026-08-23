"""Discover the user's own EVE characters from chat log headers.

This is the whole job of this module. The tool needs to know your pilots for
two reasons: seeing one in a paste proves it came from a local member list
(guard stage 3), and your own characters must never be scanned or alarmed on.
Getting them from the logs means the user configures nothing.

Verified against this machine's logs (5446 files):

  * Encoding is UTF-16LE with a b'\\xff\\xfe' BOM, and a stray \\ufeff also
    appears at the start of message lines, not only at the top of the file.
  * The header block appears exactly ONCE, at the top -- verified across the
    largest logs on disk, including a 408 KB one. (An earlier note in the plan
    claimed it repeats; that was a misreading of a 13-line file whose head and
    tail overlapped.) A new file is started per session rather than the header
    being re-emitted, so reading the first 4 KB is enough.
  * Channel names are LOCALISED -- this client is Russian and writes
    "Локальный", "Корп", "Альянс". Never match the literal "Local".
    `Channel ID: local` is the language-independent marker.
  * Filenames carry a trailing character id: Локальный_20260702_182828_96931519.txt
    Older parsers that slice filename[:-20] (Vintel) get this wrong.

Reading is deliberately read-only and passive: no file is written, no input is
ever synthesised into the client. See CLAUDE.md invariant 2.
"""
from __future__ import annotations

import os
import re
import time

DEFAULT_MAX_AGE_H = 72
_HEAD_BYTES = 4096          # the header block sits well inside this
_LISTENER = re.compile(r"^\s*Listener:\s*(.+?)\s*$", re.M)
_CHANNEL_ID = re.compile(r"^\s*Channel ID:\s*(.+?)\s*$", re.M)

# Pseudo-senders EVE uses for server messages. They look like names but are
# not pilots, and the Russian and Chinese clients each spell them differently.
PSEUDO_SENDERS = frozenset({
    "EVE System", "Система EVE", "EVE系统", "Message", "Сообщение",
})


def default_log_dir() -> str:
    """Documents\\EVE\\logs\\Chatlogs, resolved through the Windows known
    folder so OneDrive redirection does not silently break it."""
    docs = None
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # CSIDL_PERSONAL = 5, SHGFP_TYPE_CURRENT = 0
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
            docs = buf.value
    except Exception:
        docs = None
    if not docs:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs, "EVE", "logs", "Chatlogs")


def _read_head(path: str) -> str:
    with open(path, "rb") as fh:
        raw = fh.read(_HEAD_BYTES)
    if raw[:2] == b"\xff\xfe":
        raw = raw[2:]
    if len(raw) % 2:
        raw = raw[:-1]
    return raw.decode("utf-16-le", errors="replace").replace("﻿", "")


def recent_log_files(log_dir: str | None = None,
                     max_age_h: float = DEFAULT_MAX_AGE_H) -> list[str]:
    """Log files touched recently, newest first.

    The age filter is not an optimisation, it is what makes this usable: the
    directory holds thousands of files and reading them all costs seconds.
    """
    d = log_dir or default_log_dir()
    if not os.path.isdir(d):
        return []
    cutoff = time.time() - max_age_h * 3600.0
    out = []
    with os.scandir(d) as it:
        for entry in it:
            if not entry.is_file() or not entry.name.lower().endswith(".txt"):
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                out.append((mtime, entry.path))
    out.sort(reverse=True)
    return [p for _m, p in out]


FALLBACK_MAX_AGE_H = 24 * 365


def own_characters(log_dir: str | None = None,
                   max_age_h: float = DEFAULT_MAX_AGE_H,
                   limit_files: int = 600) -> list[str]:
    """Names from the `Listener:` header of recent logs, newest first.

    Every channel's log names its own listener, so this picks up every client
    the user has run recently, not just the ones with a local window open.

    If the recent window is empty the search widens to a year. Measured on a
    real install: the newest log was 48 days old, so the default 72h window
    found nothing and the guard silently lost its strongest signal. Widening
    costs 0.15s across 2463 files, and a stale name is still your name.
    """
    names = _scan_listeners(log_dir, max_age_h, limit_files)
    if not names and max_age_h < FALLBACK_MAX_AGE_H:
        names = _scan_listeners(log_dir, FALLBACK_MAX_AGE_H, limit_files)
    return names


def _scan_listeners(log_dir, max_age_h, limit_files) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for path in recent_log_files(log_dir, max_age_h)[:limit_files]:
        try:
            head = _read_head(path)
        except OSError:
            continue
        m = _LISTENER.search(head)
        if not m:
            continue
        name = m.group(1)
        key = name.casefold()
        if key in seen or name in PSEUDO_SENDERS:
            continue
        seen.add(key)
        names.append(name)
    return names


def is_local_log(path: str) -> bool:
    """Language-independent: the header says `Channel ID: local` regardless of
    what the localised channel name happens to be."""
    try:
        head = _read_head(path)
    except OSError:
        return False
    m = _CHANNEL_ID.search(head)
    return bool(m) and m.group(1).strip().casefold() == "local"
