"""Chat log parsing, against byte-for-byte copies of this machine's real logs.

The fixtures are genuine Russian-client logs, which is what makes them useful:
they carry the localised channel name, the trailing character id in the
filename, the UTF-16LE BOM, the per-line \\ufeff, and the header block repeated
at the tail of the file.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import chatlog  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
LOCAL = os.path.join(FIX, "chatlog_local_ru.txt")
CORP = os.path.join(FIX, "chatlog_corp_ru.txt")


class TestEncoding(unittest.TestCase):
    def test_fixture_is_utf16le_with_bom(self):
        with open(LOCAL, "rb") as fh:
            self.assertEqual(b"\xff\xfe", fh.read(2))

    def test_head_decodes_and_strips_bom(self):
        head = chatlog._read_head(LOCAL)
        self.assertNotIn("﻿", head)
        self.assertIn("Channel ID:", head)

    def test_odd_byte_tail_does_not_crash(self):
        """_read_head slices a fixed byte count, which can land mid-codepoint."""
        import tempfile
        with open(LOCAL, "rb") as fh:
            raw = fh.read()
        path = os.path.join(tempfile.mkdtemp(), "odd.txt")
        with open(path, "wb") as fh:
            fh.write(raw[:-1])          # force an odd length
        self.assertIn("Channel ID:", chatlog._read_head(path))


class TestChannelDetection(unittest.TestCase):
    def test_local_detected_by_channel_id_not_by_name(self):
        """The channel is named 'Локальный' on this client. Matching the
        literal 'Local' would find nothing."""
        self.assertTrue(chatlog.is_local_log(LOCAL))
        head = chatlog._read_head(LOCAL)
        self.assertNotIn("Channel Name:    Local\n", head)

    def test_corp_channel_is_not_local(self):
        self.assertFalse(chatlog.is_local_log(CORP))

    def test_missing_file_is_not_local(self):
        self.assertFalse(chatlog.is_local_log(os.path.join(FIX, "nope.txt")))


class TestListener(unittest.TestCase):
    def test_listener_extracted(self):
        head = chatlog._read_head(LOCAL)
        m = chatlog._LISTENER.search(head)
        self.assertIsNotNone(m)
        self.assertEqual("Leya Sokard", m.group(1))

    def test_header_appears_exactly_once(self):
        """Verified across every log on disk including a 408 KB one: EVE
        writes the header once per file and starts a new file per session.
        Reading the first 4 KB is therefore sufficient."""
        with open(LOCAL, "rb") as fh:
            whole = fh.read().decode("utf-16-le", errors="replace")
        self.assertEqual(1, whole.count("Channel ID:"))


class TestOwnCharacters(unittest.TestCase):
    def test_reads_listeners_from_a_directory(self):
        names = chatlog.own_characters(log_dir=FIX, max_age_h=chatlog.FALLBACK_MAX_AGE_H)
        self.assertIn("Leya Sokard", names)

    def test_no_duplicates(self):
        names = chatlog.own_characters(log_dir=FIX,
                                       max_age_h=chatlog.FALLBACK_MAX_AGE_H)
        self.assertEqual(len(names), len({n.casefold() for n in names}))

    def test_widens_the_window_when_nothing_is_recent(self):
        """Measured on a real install: the newest log was 48 days old, so a
        72h window returned nothing and the guard lost its strongest signal."""
        self.assertEqual([], chatlog._scan_listeners(FIX, 0.0001, 600))
        self.assertIn("Leya Sokard", chatlog.own_characters(log_dir=FIX,
                                                            max_age_h=0.0001))

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual([], chatlog.own_characters(log_dir=os.path.join(FIX, "nope")))

    def test_pseudo_senders_are_known(self):
        for name in ("EVE System", "Система EVE", "EVE系统"):
            self.assertIn(name, chatlog.PSEUDO_SENDERS)


if __name__ == "__main__":
    unittest.main()
