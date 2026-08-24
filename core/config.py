"""Configuration, stored as JSON in %APPDATA%\\CharacterCheck\\config.json.

Everything has a working default, so a fresh install runs with no setup.

TWO IDENTITIES, NEVER MIXED
---------------------------
The User-Agent has to say who to contact, and this project is published on
GitHub, so "who" has two different answers that must not collapse into one:

  * PROJECT_URL -- the SOFTWARE. Identical in every copy, a repository rather
    than a person. If the tool as a whole ever misbehaves the complaint lands
    on a public issue tracker instead of the author's private messages.
  * the operator -- the HUMAN whose IP the requests actually leave from.
    Filled in per installation, never committed. zKillboard bans by address,
    so this is the only name that should carry the blame for one machine's
    traffic.

Baking the author's own handle in here would make every download attribute
someone else's traffic to the author. The author's contacts live in
`ui/about.py`, are shown to a human and are never sent anywhere -- the same
place Fleet Manager Online keeps its three (web/index.html, page footer).
"""
from __future__ import annotations

import json
import os
import sys
import threading

APP_NAME = "CharacterCheck"
VERSION = "0.2"

# The software's identity, the same in every copy. zKillboard's own example
# UA allows a website ("your name, email, website etc."), and a repository is
# the one contact that survives a fork and cannot be spammed.
PROJECT_URL = "https://github.com/kersidjay69-art/Character-Check"

DEFAULTS = {
    # WHO IS RUNNING THIS COPY -- your EVE character, Discord handle or email.
    # Sent only in the User-Agent to ESI and zKillboard. Blank on purpose: it
    # belongs on the machine that makes the requests, and a value committed
    # here would put one person's name on everybody else's traffic. If blank,
    # the character name found in your own chat logs is used instead.
    "contact": "",

    # Lowest verdict worth listing: cyno | hull | indy | seen.
    # Read by the CONSOLE only -- the window always goes through
    # `ScanResult.flagged`, which starts at `seen`. Left at "indy" so the
    # console stays terse: "seen" adds every pilot ever spotted in a Covert
    # Ops or a T3, which is most of a trade hub.
    "min_level": "indy",
    # Colour scheme, same preset ids as Jump Planner: default | amarr |
    # gallente | caldari | ore | minmatar | soe | coal | photon.
    "theme": "default",

    # WHAT TO LOOK FOR. These three decide both what the window shows and how
    # many requests a scan costs -- see `scan.scan_pilot`.
    #
    # A cyno-capable hull with nothing aboard: the `hull` and `seen` verdicts.
    # Off by default, and the default is the expensive one to change: module
    # evidence is read only from the pilot's own losses, so with this off the
    # `/kills/` feed cannot produce a single displayed row and is not fetched
    # at all. That is 1 request per pilot instead of 2.
    "find_potential": False,
    # The industrial cyno module (52694). Off makes a pilot whose only
    # evidence was industrial disappear from the list entirely.
    "find_industrial": True,
    # Give up on a pilot as soon as a combat cyno is proven, instead of
    # reading his page out. Applied only to a mass paste -- see
    # `scan.STOP_AT_FIRST_MIN`.
    "stop_at_first": True,

    # Pages per pilot, everywhere -- a single pasted name included. 200
    # killmails deep, one request. See CLAUDE.md for what this costs: the
    # answer is "in the last 200 losses", not "ever".
    "list_pages": 1,
    "negative_ttl_days": 7,
    # Cache ceiling in megabytes. A safety valve, not a mechanism: reaching it
    # takes roughly 1.8 million distinct cyno pilots.
    "cache_limit_mb": 100,
    "clipboard_poll_ms": 200,
    "chatlog_max_age_h": 72,
    "log_dir": "",                # blank -> auto-detect via Documents

    # Where the results window was last left: [x, y, width, height] in virtual
    # desktop coordinates, so a second monitor above or left of the primary
    # one is negative. Empty means "wherever Qt wants". Stored as plain
    # numbers rather than Qt's saveGeometry() blob so the file stays something
    # a human can read and fix by hand.
    "window_rect": [],
    "window_maximized": False,
    # Window transparency, percent. 100 is opaque. Clamped to 50 at both ends
    # of its journey -- opacity applies to the text as well as the background,
    # and below roughly half the pilot names stop being readable, which reads
    # as a broken window rather than a subtle one.
    "window_opacity": 100,
    # Keep the results window above other windows. Worth having because EVE
    # in fullscreen paints over everything else.
    "window_on_top": False,
}


def data_dir() -> str:
    """Where settings, the icon cache and the log file live: %APPDATA%.

    Roams with the Windows profile, survives moving the executable, and is
    writable without asking. `CC_DATA_DIR` overrides it -- that is what the
    test suite runs on.
    """
    base = os.environ.get("CC_DATA_DIR")
    if not base:
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def config_path() -> str:
    return os.path.join(data_dir(), "config.json")


def app_dir() -> str:
    """The folder the application itself was started from.

    Frozen by PyInstaller, `sys.executable` IS the application; from sources
    it is the interpreter, which says nothing, so the project root is used
    instead.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write-test")
        with open(probe, "w") as fh:
            fh.write("1")
        os.remove(probe)
        return True
    except OSError:
        return False


# Named rather than a literal because `build.py` has to know it too: a rebuild
# copied over an existing folder must step around this one directory. Two
# copies of the string "cache" is how a build starts deleting a user's data.
CACHE_FOLDER = "cache"


def cache_dir() -> str:
    """Where the killboard cache lives: a folder beside the application.

    Beside it rather than in %APPDATA% so a copy on a stick carries its own
    answers -- the cache is the expensive thing to rebuild, and it is the one
    piece of state worth travelling with the executable.

    `CC_DATA_DIR` still wins outright; after that, an unwritable folder (an
    exe dropped into Program Files) falls back to %APPDATA% rather than
    refusing to start.
    """
    base = os.environ.get("CC_DATA_DIR")
    if base:
        os.makedirs(base, exist_ok=True)
        return base
    beside = os.path.join(app_dir(), CACHE_FOLDER)
    if _writable(beside):
        return beside
    return data_dir()


_lock = threading.Lock()
_cache: dict | None = None


def load(force: bool = False) -> dict:
    global _cache
    with _lock:
        if _cache is not None and not force:
            return dict(_cache)
        cfg = dict(DEFAULTS)
        try:
            with open(config_path(), "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                # Unknown keys are kept: a downgrade must not silently drop a
                # newer version's settings.
                cfg.update(stored)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            # A corrupt config must never stop the app from starting.
            pass
        _cache = cfg
        return dict(cfg)


def save(cfg: dict) -> None:
    global _cache
    path = config_path()
    tmp = path + ".part"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, path)
        _cache = dict(cfg)


# Who is running THIS copy. Set once at startup from the chat logs, so a fresh
# download identifies its own operator without the user configuring anything.
# Module state rather than a parameter because the single shared HTTP session
# builds the header long before any scan has a name to hand it.
_operator: str | None = None


def set_operator(name: str | None) -> None:
    """Record the character running this copy; None clears it."""
    global _operator
    _operator = (name or "").strip() or None


def operator(cfg: dict | None = None) -> str | None:
    """An explicit `contact` always wins: the user typed it, we detected the
    other one."""
    typed = ((cfg or load()).get("contact") or "").strip()
    return typed or _operator


def user_agent(cfg: dict | None = None) -> str:
    """`CharacterCheck/0.1 (+repo; operator)`.

    Never blank -- zKillboard 403s an empty User-Agent and the failure is
    completely opaque. The repository is always there; the operator is added
    when we know who it is. Both parts matter and they are not interchangeable:
    the first says what the software is, the second says whose traffic this is.
    """
    who = operator(cfg)
    tail = "; %s" % who if who else "; operator not identified"
    return "%s/%s (+%s%s)" % (APP_NAME, VERSION, PROJECT_URL, tail)


def contact_is_set(cfg: dict | None = None) -> bool:
    """True once the requests can be attributed to somebody -- typed in, or
    picked up from the chat logs. Only a machine with neither should be
    nagged."""
    return bool(operator(cfg))
