"""One copy at a time, and a second launch raises the first one's window.

Why this is worth a guard at all: `core.http.ZKB_CONCURRENCY` is 8 and is a
constant rather than a setting because the penalty for exceeding zKillboard's
rate is an IP ban (invariant 3). Two instances make it 16 from one address.

⚠️ The handshake cannot be driven end to end from one process. `signal_existing`
blocks the calling thread, and a server living in that same thread cannot
accept a connection while it is blocked -- so a naive in-process test watches
the handoff report success while the callback never runs, which looks exactly
like a bug and is not one. The tests below therefore drive the socket by hand,
pumping the event loop between the steps. The real two-process case was
verified separately, with a subprocess and a live event loop.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class InstanceCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from ui import single_instance
        cls.si = single_instance
        cls._servers = []

    @classmethod
    def tearDownClass(cls):
        for server in cls._servers:
            server.close()

    def keep(self, server):
        """Hold a server open for the class, and close it at the end."""
        type(self)._servers.append(server)
        return server

    def pump(self, times=20):
        for _ in range(times):
            self.app.processEvents()


class TestServerName(InstanceCase):
    def test_it_is_derived_from_the_data_directory(self):
        """Keyed on data_dir, so CC_DATA_DIR isolates the guard exactly as it
        isolates the cache and the config. A suite run must not be able to
        collide with the user's real running app."""
        a = self.si.server_name(r"C:\one\CharacterCheck")
        b = self.si.server_name(r"C:\two\CharacterCheck")
        self.assertNotEqual(a, b)

    def test_it_is_stable(self):
        path = r"C:\one\CharacterCheck"
        self.assertEqual(self.si.server_name(path), self.si.server_name(path))

    def test_it_survives_being_a_windows_pipe_name(self):
        """A pipe name cannot contain a backslash, and a data directory is
        full of them -- hence the hash."""
        name = self.si.server_name(r"C:\Users\Someone\AppData\CharacterCheck")
        self.assertNotIn("\\", name)
        self.assertTrue(name.startswith("character-check-"))


class TestClaiming(InstanceCase):
    def test_the_first_launch_gets_a_listening_server(self):
        server = self.keep(self.si.take_or_signal(r"C:\claim-1\CC"))
        self.assertIsNotNone(server)
        self.assertTrue(server.isListening())

    def test_a_second_launch_is_told_to_go_away(self):
        self.keep(self.si.take_or_signal(r"C:\claim-2\CC"))
        self.assertIsNone(self.si.take_or_signal(r"C:\claim-2\CC"))

    def test_a_different_data_directory_is_a_different_app(self):
        """Two checkouts, or the suite beside the real app, must coexist."""
        self.keep(self.si.take_or_signal(r"C:\claim-3a\CC"))
        other = self.keep(self.si.take_or_signal(r"C:\claim-3b\CC"))
        self.assertIsNotNone(other)
        self.assertTrue(other.isListening())

    def test_a_name_left_behind_by_a_crash_is_reclaimed(self):
        """There is no atexit hook and no signal handler in this project --
        `TrayApp._quit` is the only clean exit. Without `removeServer` a single
        crash would stop the app from ever starting again."""
        first = self.si.take_or_signal(r"C:\claim-4\CC")
        first.close()                       # as a crash leaves it
        second = self.keep(self.si.take_or_signal(r"C:\claim-4\CC"))
        self.assertIsNotNone(second)
        self.assertTrue(second.isListening())

    def test_nothing_listening_means_nothing_answers(self):
        self.assertFalse(self.si.signal_existing("character-check-nobody-here"))


class TestShowRequest(InstanceCase):
    def _socket(self):
        from PySide6.QtNetwork import QLocalSocket
        return QLocalSocket()

    def test_the_running_instance_is_asked_to_show_itself(self):
        from PySide6.QtCore import QByteArray
        server = self.keep(self.si.take_or_signal(r"C:\show-1\CC"))
        seen = []
        self.si.listen_for_show(server, lambda: seen.append(1))

        # By hand rather than via signal_existing: see the module docstring.
        # Write BEFORE the server gets a turn, which is what the real sender
        # does: connect, write, flush, then wait. Pumping first would let the
        # server accept and sit in its blocking read while this side has not
        # sent anything yet.
        sock = self._socket()
        sock.connectToServer(self.si.server_name(r"C:\show-1\CC"))
        sock.write(QByteArray(self.si.SHOW))
        sock.flush()
        self.pump()
        self.assertEqual(1, len(seen))
        sock.abort()

    def test_anything_else_is_ignored(self):
        """The socket is a local IPC endpoint; it should act only on the one
        word it knows."""
        from PySide6.QtCore import QByteArray
        server = self.keep(self.si.take_or_signal(r"C:\show-2\CC"))
        seen = []
        self.si.listen_for_show(server, lambda: seen.append(1))

        sock = self._socket()
        sock.connectToServer(self.si.server_name(r"C:\show-2\CC"))
        sock.write(QByteArray(b"quit"))
        sock.flush()
        self.pump()
        self.assertEqual([], seen)
        sock.abort()


if __name__ == "__main__":
    unittest.main()
