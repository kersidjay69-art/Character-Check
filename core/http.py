"""Shared HTTP session.

One keep-alive session per process rather than a fresh connection per call.
A local scan is 100-400 requests to the same two hosts, and on the reference
project this exact change measured 127ms -> 45ms per call, most of the saving
being the TLS handshake that no longer repeats.

Hard rules learned from live probing, encoded here so no caller can forget:
  * zKillboard 403s a BLANK User-Agent. Never send one.
  * Accept-Encoding: gzip shrinks a zkb page 8.4x (465 KB -> 55 KB).
  * r2z2.zkillboard.com is a separate, much tighter bucket (15 req/s, ban up
    to an hour). This app never touches it.
"""
from __future__ import annotations

import logging
import threading

import requests

from . import config

log = logging.getLogger("cc.http")

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

# Verified sustained without a single 429 across hundreds of requests.
# A constant, not a setting: the failure mode is an IP ban, so this is not a
# knob the user should be able to turn up.
ZKB_CONCURRENCY = 8

_lock = threading.Lock()
_session: requests.Session | None = None


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def session() -> requests.Session:
    global _session
    with _lock:
        if _session is not None:
            return _session
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=4,
            pool_maxsize=ZKB_CONCURRENCY * 2,
            max_retries=0,          # retries are decided per-caller, not here
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": config.user_agent(),
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
        })
        _session = s
        return s


def refresh_user_agent() -> None:
    """Call after the user edits `contact` in settings."""
    with _lock:
        if _session is not None:
            _session.headers["User-Agent"] = config.user_agent()


def close() -> None:
    global _session
    with _lock:
        if _session is not None:
            _session.close()
            _session = None
