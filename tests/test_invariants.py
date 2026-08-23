"""Two project invariants, executable rather than documented.

Both exist because a comment in a README does not survive contact with a
future change; a failing test does.
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def py_files(*dirs):
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            if "__pycache__" in dirpath:
                continue
            for name in filenames:
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _code_strings(source):
    """Every string literal in the module EXCEPT docstrings.

    A docstring is documentation; a bare literal is what actually gets sent
    somewhere. Only the latter can call an endpoint.
    """
    import ast
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and                     isinstance(body[0].value, ast.Constant) and                     isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


class TestHeadlessCore(unittest.TestCase):
    """Invariant 1: core/ is Qt-free.

    Jump planer paid for this one already -- once GUI imports leak into the
    logic, nothing can be tested or run without a display.
    """

    GUI = re.compile(r"^\s*(?:import|from)\s+(PySide6|PyQt5|PyQt6|tkinter)\b", re.M)

    def test_core_imports_no_gui(self):
        offenders = [os.path.relpath(p, ROOT) for p in py_files("core")
                     if self.GUI.search(read(p))]
        self.assertEqual([], offenders, "GUI import leaked into core/")

    def test_core_is_importable_without_a_display(self):
        import importlib
        for mod in ("core.guard", "core.analyze", "core.cyno_sets",
                    "core.cache", "core.chatlog", "core.config", "core.scan"):
            importlib.import_module(mod)


class TestNoInputAutomation(unittest.TestCase):
    """Invariant 2: the tool never synthesises input into the game client.

    Reading logs, the clipboard and the screen is tolerated by CCP (RIFT is on
    their own community tools list). Sending keystrokes is where a passive tool
    would become one that plays the game for you -- EULA 6.A.3. The copy stays
    a human action.
    """

    BANNED = ("SendInput", "keybd_event", "mouse_event", "PostMessage",
              "SendMessage", "pyautogui", "pydirectinput", "pynput",
              "SetForegroundWindow", "SetCursorPos")

    def test_no_input_synthesis_anywhere(self):
        offenders = []
        for path in py_files("core", "ui", "sde"):
            src = read(path)
            for bad in self.BANNED:
                if bad in src:
                    offenders.append("%s: %s" % (os.path.relpath(path, ROOT), bad))
        self.assertEqual([], offenders)

    def test_clipboard_module_never_writes(self):
        """Reading the clipboard is passive; writing to it is not, and would
        also stomp on whatever the user actually copied."""
        src = read(os.path.join(ROOT, "core", "clipboard.py"))
        for bad in ("SetClipboardData", "EmptyClipboard"):
            self.assertNotIn(bad, src)


class TestRateLimits(unittest.TestCase):
    """The penalty for over-polling zKillboard is an IP ban of up to an hour,
    so the ceiling is a constant, not a user setting."""

    def test_zkb_rate_is_not_configurable(self):
        from core import config, ratelimit
        self.assertLessEqual(ratelimit.zkb_bucket.rate, 10.0)
        self.assertNotIn("zkb_rate", config.DEFAULTS)
        self.assertNotIn("concurrency", config.DEFAULTS)

    FORBIDDEN_URLS = ("r2z2.zkillboard.com", "asearchquery", "/asearch")

    def test_forbidden_endpoints_are_never_called(self):
        """r2z2 is a separate 15 req/s bucket with an hour-long ban, and
        asearch is behind a Cloudflare challenge with an item index that only
        goes back ~18 months -- it answers 'did they ever' wrongly.

        Docstrings are skipped on purpose: both names appear in prose that
        explains why they are avoided, and a check that forbade the
        explanation would push the reasoning out of the code.
        """
        offenders = []
        for path in py_files("core", "ui"):
            for literal in _code_strings(read(path)):
                low = literal.lower()
                for url in self.FORBIDDEN_URLS:
                    if url in low:
                        offenders.append("%s: %s"
                                         % (os.path.relpath(path, ROOT), url))
        self.assertEqual([], offenders)


class TestUserAgent(unittest.TestCase):
    def test_user_agent_is_never_blank(self):
        """zKillboard 403s a blank User-Agent and the failure is opaque."""
        from core import config
        ua = config.user_agent({"contact": ""})
        self.assertTrue(ua.strip())
        self.assertIn("CharacterCheck", ua)
        self.assertIn("me@example.com",
                      config.user_agent({"contact": "me@example.com"}))


if __name__ == "__main__":
    unittest.main()
