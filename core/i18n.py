"""Interface text, English only.

    i18n.t("btn.expand")            -> "Expand"
    i18n.t("status.unresolved", 3)  -> "not found in ESI: 3"

Keys rather than strings, so a caption is written once and the console and the
window cannot disagree about it. Qt-free on purpose: `core/console.py` says the
same sentences as the results window without importing anything from `ui/`.

There was a Russian table here until 2026-08-23. It was removed on request --
the project is published on GitHub, the documentation is English, and a second
table is a second thing to keep in step. `README.ru.md` stays: that is
documentation for players, not interface text.

What is deliberately NOT here, and must never be added:

* "Character Check" -- the product name.
* Module and ship names ("Covert Cyno", "Falcon"). They are what the game
  calls them, in every client language.
* Level and evidence KEYS (`cyno`, `fitted`, ...). Those are protocol: they
  sit in the SQLite cache and in config.json. Only their labels are here.
* Log messages and zKillboard URLs.
"""
from __future__ import annotations

EN = {
    # --- verdict levels ------------------------------------------------
    "level.cyno": "CYNO",
    "level.hull": "cyno hull",
    "level.indy": "industrial",
    # A cyno-capable hull and nothing else. Not a warning: everybody flies
    # a Covert Ops or a T3.
    "level.seen": "seen",
    "level.none": "clean",

    # --- kinds of evidence ---------------------------------------------
    "kind.fitted": "cyno in a high slot",
    "kind.cargo": "cyno in the hold",
    "kind.hull_lost": "died in a cyno hull",
    "kind.hull_flown": "flew a cyno hull",

    # The same four for the window, which puts them in the name column next
    # to a date. The long forms need 164 px there and the names themselves
    # need 125, so the sentence was setting the column width; these need 124.
    # The console keeps the long ones -- a terminal has room.
    "short.fitted": "fitted",
    "short.cargo": "in hold",
    "short.hull_lost": "lost",
    "short.hull_flown": "flew",

    # --- results window ------------------------------------------------
    "status.idle": "copy the local member list in game -- "
                   "click a name, Ctrl+A, Ctrl+C",
    "status.resolving": "looking up %d names...",
    "status.scanning": "checking %d pilots...",
    "status.progress": "checked %d of %d",
    "status.rejected": "skipped: %s",
    "status.own": "yours: ",
    "status.unresolved": "not found in ESI: %d",
    "btn.rescan": "Check clipboard",
    "btn.expand": "Expand",
    "btn.expand_tip": "Open the evidence under every pilot",
    "btn.collapse": "Collapse",
    "btn.collapse_tip": "Close every pilot's evidence",
    "btn.clear": "Clear",
    "btn.filters": "Search filters",
    "filter.potential": "Potential cyno -- hulls with no module",
    "filter.industrial": "Industrial cyno",
    "filter.stop_first": "Stop at the first combat cyno",
    "filter.tip": "What to look for. With \"potential cyno\" off a scan asks\n"
                  "zKillboard once per pilot instead of twice, because module\n"
                  "evidence only ever comes from the pilot's own losses.",
    "btn.ignore": "Ignore list",
    "btn.ignore_one": "Ignore %s",
    "btn.ignore_selected": "Ignore the %d selected",
    "btn.ignore_checked": "Ignore all %d just checked",
    "btn.ignore_clear": "Clear the ignore list (%d)",
    "btn.ignore_empty": "Nothing ignored",
    "ignore.tip": "Pilots to leave out of every scan -- your own fleet,\n"
                  "usually. They cost no requests at all while ignored,\n"
                  "and the list is forgotten when the application exits.\n"
                  "It survives closing the window to the tray.",
    "status.ignored": "%d ignored",
    "status.all_ignored": "all %d pilots are on the ignore list",
    "btn.on_top": "Always on top",
    "btn.on_top_tip": "Keep this window above the others. EVE in fullscreen "
                      "paints over everything,\nso this only helps in "
                      "windowed or borderless mode.",
    "action.copy_names": "Copy names",
    "hint.no_contact": "requests go out unsigned",
    "hint.no_contact_tip": "No chat logs found and «contact» is empty, so "
                           "requests are signed with nobody's name.\n"
                           "Put your character or handle in «contact» in %s",
    "hint.bottom": "double-click opens the pilot or the killmail on "
                   "zKillboard   ·   Ctrl+C copies the selected names",
    "tip.pilot": "%s   ·   double-click to open on zKillboard",
    "tip.checked": "%s   ·   from the cache, checked %s   ·   "
                   "double-click to open on zKillboard",
    "tip.killmail": "Double-click to open the killmail",
    "tip.rescan": "Check the names in the clipboard now",
    "tip.clear": "Empty the list and go back to waiting",
    "tip.count": "pilots whose verdict is: %s",
    "tip.opacity": "See through this window -- useful with EVE beside it",

    # --- tray ----------------------------------------------------------
    "tray.show": "Show results",
    "tray.rescan": "Check the clipboard",
    "tray.about": "About",
    "tray.settings": "Open the settings file",
    "tray.quit": "Quit",

    # --- about ---------------------------------------------------------
    "about.title": "About",
    "about.version": "version %s   ·   %s",
    "about.contact": "Contact the author",
    "about.close": "Close",
    "about.close_tip": "Close this window",
    "about.disclaimer":
        "This tool reads public data only: the clipboard, chat log headers, "
        "ESI and zKillboard. It is not affiliated with CCP hf and is not "
        "endorsed by them -- CCP endorses no third-party application. EVE "
        "Online and all related material are the property of CCP hf.\n\n"
        "Distributed under the Apache 2.0 licence, with no warranty of any "
        "kind. Whoever runs the program answers for how it is used.",

    # --- the author's contacts -------------------------------------------
    # The handles themselves are NOT here: they live in ui/about.py and
    # nowhere else (invariant 7). These are only the captions around them.
    # Short captions on purpose -- a caption carrying the handle itself
    # set the window's minimum width at ~455 px. The handle is in the tooltip.
    "contact.discord": "Discord",
    "contact.telegram": "Telegram",
    "contact.eve": "EVE",
    "contact.tip_discord": "Copy the author's Discord handle -- %s",
    "contact.tip_telegram": "Open the author's Telegram in a browser -- %s",
    "contact.tip_eve": "Open the author's character on zKillboard -- %s",
    "contact.copied": "copied: %s",

    # --- console -------------------------------------------------------
    "console.desc": "Character Check (console)",
    "console.arg_once": "check the text in a file and exit (for tests)",
    "console.skipped": "[skipped] %s",
    "console.scanned": "\n=== scanned %d pilots in %.1f s ===",
    "console.own_in_list": "own characters in the list: %s",
    "console.not_found": "not found in ESI (%d): %s",
    "console.nothing": "No cyno found.",
    "console.cached": " [cached]",
    "console.modules": "           modules: %s",
    "console.clean": "\nclean: %s",
    "console.errors": "\nerrors on %d pilots (first: %s)",
    "console.sets_built": "Cyno sets built %s: %d modules, %d hulls",
    "console.own_chars": "Own characters from the chat logs: %d%s",
    "console.cache": "Cache: %s",
    "console.filters": "Looking for: %s",
    "console.arg_potential": "also flag cyno-capable hulls with no module",
    "console.arg_no_industrial": "ignore the industrial cyno module",
    "console.arg_all_cyno": "read every page, do not stop at the first combat cyno",
    "console.no_contact": "WARNING: no chat logs found and «contact» is empty --\n"
                          "         requests will go out unsigned. Put yourself in %s\n",
    "console.waiting": "\nWatching the clipboard. Copy a local member list "
                       "(Ctrl+A, Ctrl+C in\nthe member list) or a single name. "
                       "Ctrl+C to quit.\n",
    "console.exit": "\nexit",
    "main.no_tray": "No system tray available. Use python -m core.console",
    "main.already_running": "Character Check is already running -- the window of the copy that was already there has been raised.",

    # --- why a paste was refused ---------------------------------------
    "reason.empty": "empty",
    "reason.too_long": "too long (%d chars)",
    "reason.tabs": "contains tabs (D-Scan or inventory, not names)",
    "reason.url": "contains a URL",
    "reason.empty_after_normalise": "empty after normalisation",
    "reason.too_many_lines": "too many lines (%d)",
    "reason.only_own": "only your own characters",
    "reason.mask_ratio": "only %d/%d lines look like names",
    "reason.no_name_resolved": "no name resolved to a character",
}



def t(key: str, *args) -> str:
    """Look a key up. Never raises.

    A missing key returns the key itself, which shows up in the interface as
    an obvious `btn.expand` rather than an empty button. A bad format string
    does the same instead of taking the window down.
    """
    text = EN.get(key)
    if text is None:
        return key
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return text
