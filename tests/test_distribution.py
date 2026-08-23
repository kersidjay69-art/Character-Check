"""What has to stay true once this repository is public.

The threat here is not malice, it is drift. Somebody downloads the tool, runs
it hard, and zKillboard sees a User-Agent. Whose name is in it decides who
answers for that traffic. These tests keep that boundary in place, because a
paragraph in a README does not survive a refactor.
"""
import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import config  # noqa: E402


def _reset():
    config.set_operator(None)


class TestOperatorIdentity(unittest.TestCase):
    """The User-Agent names the software AND the person running this copy."""

    def setUp(self):
        _reset()

    tearDown = setUp

    def test_shipped_defaults_carry_nobody(self):
        """A committed `contact` would sign every download with one name."""
        self.assertEqual("", config.DEFAULTS["contact"])

    def test_user_agent_always_names_the_project(self):
        for cfg in ({"contact": ""}, {"contact": "someone@example.com"}):
            self.assertIn(config.PROJECT_URL, config.user_agent(cfg))

    def test_project_url_is_a_repository_not_a_person(self):
        """A repo takes a public issue; a handle takes a private complaint and
        a lot of spam."""
        self.assertTrue(config.PROJECT_URL.startswith("https://"))
        self.assertNotIn("@", config.PROJECT_URL)

    def test_detected_operator_fills_a_blank_contact(self):
        config.set_operator("Leya Sokard")
        self.assertIn("Leya Sokard", config.user_agent({"contact": ""}))

    def test_typed_contact_beats_the_detected_one(self):
        """The user typed one on purpose; we only guessed the other."""
        config.set_operator("Leya Sokard")
        ua = config.user_agent({"contact": "me@example.com"})
        self.assertIn("me@example.com", ua)
        self.assertNotIn("Leya Sokard", ua)

    def test_user_agent_is_never_blank_and_never_bare(self):
        ua = config.user_agent({"contact": ""})
        self.assertTrue(ua.strip())
        self.assertIn(config.APP_NAME, ua)

    def test_unidentified_copy_says_so_instead_of_borrowing_a_name(self):
        ua = config.user_agent({"contact": ""})
        self.assertIn("not identified", ua)

    def test_nag_is_silent_once_the_logs_identified_someone(self):
        self.assertFalse(config.contact_is_set({"contact": ""}))
        config.set_operator("Leya Sokard")
        self.assertTrue(config.contact_is_set({"contact": ""}))


class TestAuthorContactsStayOffTheWire(unittest.TestCase):
    """The author's handles are shown to a human, never sent to a server.

    `core/` is everything that talks to ESI and zKillboard. If a handle ever
    appears there it is one refactor away from a request header, and then the
    author is answering for a stranger's traffic.
    """

    def _core_sources(self):
        base = os.path.join(ROOT, "core")
        for dirpath, _dirs, files in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8") as fh:
                        yield os.path.relpath(path, ROOT), fh.read()

    @staticmethod
    def _author_handles():
        """Read the constants out of ui/about.py without importing it.

        Importing would drag PySide6 into a suite that otherwise runs with
        neither Qt nor a display -- invariant 1 cuts both ways.
        """
        path = os.path.join(ROOT, "ui", "about.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        wanted = {"DISCORD", "TELEGRAM", "TELEGRAM_URL", "CHARACTER",
                  "CHARACTER_URL"}
        found = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value,
                                                           ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in wanted:
                        found[target.id] = node.value.value
        missing = wanted - set(found)
        assert not missing, "ui/about.py lost %s" % sorted(missing)
        return tuple(found.values())

    def test_no_author_contact_channel_anywhere_in_core(self):
        """The repository URL is exempt, and only it.

        A GitHub URL necessarily carries the owner's account name, and that is
        the one identifier meant to be here: it points at an issue tracker,
        not at a person's inbox. Blanking it out first keeps the check from
        firing on the very thing it is supposed to allow.
        """
        handles = self._author_handles()
        offenders = []
        for rel, src in self._core_sources():
            low = src.lower().replace(config.PROJECT_URL.lower(), "")
            for handle in handles:
                if handle.lower().lstrip("@") in low:
                    offenders.append("%s: %s" % (rel, handle))
        self.assertEqual([], offenders)

    def test_core_never_imports_the_about_window(self):
        offenders = []
        for rel, src in self._core_sources():
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "about" in node.module:
                        offenders.append(rel)
                elif isinstance(node, ast.Import):
                    offenders += [rel for a in node.names if "about" in a.name]
        self.assertEqual([], offenders)


class TestRedistribution(unittest.TestCase):
    """Open source without a licence is open source nobody may legally use,
    and a licence without a liability clause is one the author pays for."""

    def test_licence_is_present_and_disclaims_liability(self):
        path = os.path.join(ROOT, "LICENSE")
        self.assertTrue(os.path.exists(path), "LICENSE is missing")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Apache License", text)
        self.assertIn("Limitation of Liability", text)
        self.assertIn("Disclaimer of Warranty", text)
        self.assertNotIn("[name of copyright owner]", text)


class TestVersionResource(unittest.TestCase):
    """What Explorer's Details tab says about the executable we hand out.

    It said nothing at all until 2026-08-20 -- every field blank. A nameless
    unsigned binary is a heuristic signal on its own, and the first thing a
    suspicious user checks after an antivirus warning is exactly this tab.
    """

    @classmethod
    def setUpClass(cls):
        import build
        cls.build = build
        cls.text = build.VERSION_TEMPLATE % {
            "vers": build._version_tuple(config.VERSION),
            "version": config.VERSION, "name": "CharacterCheck",
            "filename": "CharacterCheck.exe", "product": "Character Check",
            "company": config.PROJECT_URL, "description": "d",
            "copyright": "Apache License 2.0 -- see LICENSE", "comments": "c",
        }

    def test_it_is_valid_python_pyinstaller_can_evaluate(self):
        """PyInstaller eval()s this file. A syntax error here surfaces as a
        failed build minutes in, with the traceback pointing at their code."""
        ast.parse(self.text)

    def test_no_field_is_left_blank(self):
        for field in ("CompanyName", "FileDescription", "FileVersion",
                      "ProductName", "LegalCopyright", "OriginalFilename"):
            self.assertIn(field, self.text)
        self.assertNotIn("''", self.text)

    def test_the_author_is_not_in_the_binary(self):
        """Invariant 7. The exe goes to strangers, so the only identity in it
        is the project's -- `ui/about.py` is where a human is named."""
        import re
        contacts = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", self.text)
        self.assertEqual([], contacts)
        self.assertIn(config.PROJECT_URL, self.text)

    def test_the_translation_matches_the_string_table(self):
        """040904B0 and [1033, 1200] are the same locale written two ways.
        Disagree, and Explorer shows an empty Details tab -- silently."""
        self.assertIn("040904B0", self.text)
        self.assertIn("[1033, 1200]", self.text)


class TestBootloaderGuard(unittest.TestCase):
    """The bootloader is the part antivirus engines actually recognise.

    The PyPI wheel ships it prebuilt, so the code that starts every frozen app
    is byte-identical everywhere -- measured on our own build, a 4 KB slice
    from the middle of the stock runw.exe was present verbatim inside
    CharacterCheck.exe. Rebuilding it from source makes it unique; this guard
    is what notices when `pip install --upgrade pyinstaller` puts the stock one
    back, which would otherwise surface months later on a VirusTotal report.
    """

    @classmethod
    def setUpClass(cls):
        import build
        cls.build = build

    def test_the_installed_version_is_one_we_have_hashes_for(self):
        """Fails deliberately after a PyInstaller upgrade: the new stock
        hashes have to be recorded, or the guard cannot tell stock from
        custom and quietly says nothing."""
        import PyInstaller
        self.assertIn(PyInstaller.__version__, self.build.STOCK_BOOTLOADERS,
                      "add this version's stock hashes to STOCK_BOOTLOADERS")

    def test_an_unknown_version_is_reported_as_unknown_not_as_custom(self):
        """The failure mode that would turn this into decoration: a check that
        passes on everything it has not seen before."""
        saved = dict(self.build.STOCK_BOOTLOADERS)
        self.build.STOCK_BOOTLOADERS.clear()
        try:
            status, digest = self.build.check_bootloader()
            self.assertEqual("unknown-version", status)
            self.assertTrue(digest, "the hash is still worth reporting")
        finally:
            self.build.STOCK_BOOTLOADERS.update(saved)

    def test_the_windowed_bootloader_is_the_one_checked(self):
        """--windowed embeds runw, not run. Checking the console one would
        pass while shipping the stock binary."""
        self.assertEqual("runw.exe", self.build.WINDOWED_BOOTLOADER)
        self.assertIn("runw.exe", self.build.bootloader_path())

    def test_recorded_hashes_are_full_sha256(self):
        """A truncated hash silently matches nothing and reads as "custom"."""
        for version, files in self.build.STOCK_BOOTLOADERS.items():
            for name, digest in files.items():
                self.assertEqual(64, len(digest), (version, name))
                int(digest, 16)

    def test_reporting_never_raises(self):
        """A build must not die over provenance -- the stock bootloader still
        produces a working program, just a more suspicious one."""
        self.assertIn(self.build.report_bootloader(),
                      ("stock", "custom", "unknown-version"))


class TestVersionParsing(unittest.TestCase):
    """`config.VERSION` is a human string; the resource needs four numbers."""

    def parse(self, text):
        import build
        return build._version_tuple(text)

    def test_the_shipped_version_parses(self):
        self.assertEqual((0, 1, 0, 0), self.parse(config.VERSION))

    def test_it_pads_and_truncates_to_four(self):
        self.assertEqual((1, 2, 3, 0), self.parse("1.2.3"))
        self.assertEqual((1, 2, 3, 4), self.parse("1.2.3.4.5"))

    def test_a_prerelease_suffix_does_not_change_the_number(self):
        """Stripping every non-digit instead of stopping at the first one
        spliced "0-rc1" into "01" and shipped 1.0-rc1 as version 1.1."""
        self.assertEqual((1, 0, 0, 0), self.parse("1.0-rc1"))
        self.assertEqual((0, 9, 1, 0), self.parse("0.9.1beta"))

    def test_junk_builds_rather_than_raises(self):
        """A build must not be the thing that discovers a typo in VERSION."""
        for junk in ("", None, "junk", "..."):
            self.assertEqual((0, 0, 0, 0), self.parse(junk), junk)


if __name__ == "__main__":
    unittest.main()
