"""One copy of the app at a time, and a second launch raises the first.

Not tidiness. `core.http.ZKB_CONCURRENCY` is 8 and it is a constant rather
than a setting because the price of exceeding zKillboard's rate is an IP ban
of up to an hour (invariant 3) -- and two instances make it 16 requests a
second from one address, which is exactly the thing that constant exists to
prevent. Two instances also share one SQLite cache and would both run
`enforce_limit` and `PRAGMA incremental_vacuum` against it, and both write
config.json last-writer-wins.

The mechanism is a `QLocalServer` named after the data directory. Qt lives
only under `ui/` (invariant 1), which is why this file is here and not in
`core/`, even though nothing in it is about the interface.
"""
from __future__ import annotations

import hashlib
import logging

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger("cc.instance")

# What a second launch sends. One word, because it is the only thing it can
# ever mean: the user started the app again, so they want to see it.
SHOW = b"show"

_CONNECT_MS = 300
_WRITE_MS = 1000


def server_name(data_dir: str) -> str:
    """A socket name derived from the data directory.

    Hashed rather than used literally: a Windows pipe name cannot contain a
    backslash, and the path is full of them.

    Keying it on `config.data_dir()` -- which honours CC_DATA_DIR -- means the
    guard isolates itself exactly as everything else in this project does. The
    test suite points that variable at a temp directory, so a suite run cannot
    collide with the user's real running app, and neither can a second
    checkout.
    """
    digest = hashlib.sha1(data_dir.encode("utf-8", "replace")).hexdigest()
    return "character-check-" + digest[:12]


def signal_existing(name: str) -> bool:
    """Ask a running instance to show itself. True if one answered."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(_CONNECT_MS):
        return False
    socket.write(QByteArray(SHOW))
    socket.flush()
    socket.waitForBytesWritten(_WRITE_MS)
    socket.disconnectFromServer()
    # `socket` is a local, so returning destroys it, and a QLocalSocket
    # destroyed before the peer has accepted the connection can take the
    # buffered bytes with it. Waiting for the orderly disconnect means the
    # other instance has been through its event loop and read us.
    socket.waitForDisconnected(_WRITE_MS)
    return True


def take_or_signal(data_dir: str) -> QLocalServer | None:
    """Become the one instance, or tell the one that already is.

    Returns the listening server on success -- **the caller must keep it
    alive**, or Python collects it and the next launch sees no listener.
    Returns None when another instance answered and this one should exit.
    """
    name = server_name(data_dir)
    if signal_existing(name):
        return None

    # Nobody answered. On Windows a crashed instance can leave the name behind,
    # and `listen` would then fail forever -- the app would refuse to start
    # ever again, for the rest of the machine's life, because of one crash.
    # Removing a name nothing is listening on is safe, and we only get here
    # after the connect above found nothing.
    QLocalServer.removeServer(name)

    server = QLocalServer()
    if not server.listen(name):
        # Do not stop the app. An unwritable or unusable data directory has
        # never been allowed to prevent startup in this project (see
        # `main._start_logging` and `config.load`), and a guard that refuses
        # to run the program is worse than the problem it guards against.
        log.warning("single-instance guard unavailable: %s",
                    server.errorString())
        return server
    return server


def listen_for_show(server: QLocalServer, on_show) -> None:
    """Call `on_show()` whenever another launch asks for the window.

    The read is synchronous. The sender writes four bytes and disconnects at
    once, so waiting on `readyRead` can miss them -- the message is one word
    from a process that has already flushed it, and a short blocking wait is
    both cheap and the version that actually fires.

    ⚠️ None of this can be exercised from a single process. `signal_existing`
    blocks the calling thread, and a server in that same thread cannot accept
    a connection while it is blocked -- so an in-process test sees the handoff
    succeed and the callback never run, which looks exactly like a bug and is
    not one. `tests/test_single_instance.py` drives the socket by hand without
    blocking, and the real two-process case was verified separately.
    """
    def _accept() -> None:
        socket = server.nextPendingConnection()
        if socket is None:
            return
        try:
            if socket.bytesAvailable() or socket.waitForReadyRead(_WRITE_MS):
                if bytes(socket.readAll()).strip() == SHOW:
                    on_show()
        finally:
            socket.disconnectFromServer()
            socket.deleteLater()

    server.newConnection.connect(_accept)
