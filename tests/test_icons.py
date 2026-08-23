"""Icon cache behaviour. No network -- the fetcher is always stubbed out."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import icons  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"fake pixels"


class _Fetcher:
    """Stands in for the image server and counts how often it was asked."""

    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def __call__(self, type_id):
        self.calls.append(type_id)
        return self.answers.get(type_id)


class IconsTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._old = os.environ.get("CC_DATA_DIR")
        os.environ["CC_DATA_DIR"] = self.dir
        self._real_fetch = icons.fetch

    def tearDown(self):
        icons.fetch = self._real_fetch
        if self._old is None:
            os.environ.pop("CC_DATA_DIR", None)
        else:
            os.environ["CC_DATA_DIR"] = self._old
        shutil.rmtree(self.dir, ignore_errors=True)

    def stub(self, answers=None):
        icons.fetch = _Fetcher(answers)
        return icons.fetch


class TestDiskCache(IconsTestCase):
    def test_icon_is_fetched_once_then_read_from_disk(self):
        fetcher = self.stub({28646: PNG})
        self.assertEqual(PNG, icons.get(28646))
        self.assertEqual(PNG, icons.get(28646))
        self.assertEqual(PNG, icons.get(28646))
        self.assertEqual([28646], fetcher.calls)

    def test_bytes_survive_a_cold_start(self):
        self.stub({28646: PNG})
        icons.get(28646)
        # Nothing in memory: a brand-new process would see exactly this.
        self.assertEqual(PNG, icons.read_cached(28646))

    def test_a_type_without_artwork_is_never_asked_twice(self):
        """The gap in Jump Planner's cache: it re-asks on every repaint."""
        fetcher = self.stub({})
        self.assertIsNone(icons.get(999999))
        self.assertTrue(icons.is_known_miss(999999))
        self.assertIsNone(icons.get(999999))
        self.assertIsNone(icons.get(999999))
        self.assertEqual([999999], fetcher.calls)

    def test_allow_fetch_false_never_reaches_the_fetcher(self):
        fetcher = self.stub({28646: PNG})
        self.assertIsNone(icons.get(28646, allow_fetch=False))
        self.assertEqual([], fetcher.calls)

    def test_read_cached_does_not_fetch(self):
        fetcher = self.stub({28646: PNG})
        self.assertIsNone(icons.read_cached(28646))
        self.assertEqual([], fetcher.calls)

    def test_no_partial_files_are_left_behind(self):
        self.stub({28646: PNG})
        icons.get(28646)
        leftovers = [n for n in os.listdir(icons.icons_dir())
                     if n.endswith(".part")]
        self.assertEqual([], leftovers)


class TestMissingAndPrefetch(IconsTestCase):
    def test_missing_ignores_both_hits_and_settled_misses(self):
        self.stub({1: PNG})
        icons.get(1)          # -> cached
        icons.get(2)          # -> settled miss
        self.assertEqual([3], icons.missing([1, 2, 3]))

    def test_missing_deduplicates(self):
        self.stub({})
        self.assertEqual([7], icons.missing([7, 7, 7]))

    def test_prefetch_covers_modules_and_hulls_once(self):
        class Sets:
            modules = {21096: "a", 28646: "b", 52694: "c"}
            hulls = {11957: {}, 648: {}}

        fetcher = self.stub({t: PNG for t in (21096, 28646, 52694, 11957, 648)})
        self.assertEqual(5, icons.prefetch(Sets()))
        self.assertEqual(5, len(fetcher.calls))
        # Second pass has nothing left to do and touches no network at all.
        self.assertEqual(0, icons.prefetch(Sets()))
        self.assertEqual(5, len(fetcher.calls))

    def test_stats_counts_hits_and_misses(self):
        self.stub({1: PNG})
        icons.get(1)
        icons.get(2)
        self.assertEqual({"icons": 1, "misses": 1}, icons.stats())


class TestUrl(unittest.TestCase):
    def test_icon_route_is_used_for_everything(self):
        """`/render` is ship-only -- it answers 400 for all three modules."""
        self.assertIn("/icon", icons.BASE)
        self.assertNotIn("/render", icons.BASE)

    def test_size_is_pinned(self):
        self.assertEqual(64, icons.SIZE)
