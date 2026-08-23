"""The safety catch: decide whether clipboard text is a list of EVE pilot
names (or a single name) before spending a single network request on it.

Pure functions, no I/O, no imports beyond the stdlib.

The character rules below are NOT guesses -- they were derived from 331
distinct sender names harvested from this machine's own EVE chat logs, and
three plausible-sounding rules died against that sample:

  * "names are Latin"      -- 93 of 331 (28%) are CJK: 冰喵, 幻华 琉璃, 躺着看.
                              A Latin-only mask throws away a quarter of the
                              real pilots in local.
  * "no repeated quotes"   -- Io ''Midnight'' Shadow exists.
  * "a digit run is junk"  -- 599847624 is a real character name.

What the sample DID confirm: no name contains . , _ " / \\ or any bracket;
none starts or ends with punctuation; every name is 1-3 words; observed
lengths run 2..26 against EVE's documented 37 limit.

Cyrillic is deliberately excluded from the allowed set. EVE has never issued
Cyrillic character names, and Russian prose is by far the most common junk in
this user's clipboard -- leaving it out makes a pasted paragraph fail the mask
naturally, with no special rule.

The mask is intentionally the WEAK half of this design. The strong signals are
(a) seeing one of your own characters in the list, and (b) ESI, which is the
final arbiter in core/scan.py: a name that does not resolve to a character is
silently dropped, so junk that slips past the mask still costs nothing visible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import i18n

MAX_NAME_LEN = 37       # CCP's documented limit
MIN_NAME_LEN = 2        # observed: 冰喵
MAX_WORDS = 3           # observed: 1, 2 or 3 words, never more
# Jita local genuinely reaches four figures. A cap of 250 rejected a real
# 1100-name paste outright, which is exactly the situation where the tool is
# most useful, so the ceiling is set above the busiest hub rather than at a
# comfortable scan size. Depth, not breadth, is what keeps a big paste quick.
MAX_LINES = 1500
MAX_CHARS = 60_000
MIN_MASK_RATIO = 0.90   # share of lines that must look like names

_URL = re.compile(r"https?://|www\.", re.I)

# Whitelist by script rather than "anything alphanumeric": str.isalnum() is
# True for Cyrillic, Arabic and Greek too, which would defeat the point.
_CJK_RANGES = (
    (0x2E80, 0x9FFF),    # CJK radicals through unified ideographs
    (0x3040, 0x30FF),    # hiragana + katakana
    (0xAC00, 0xD7AF),    # hangul syllables
    (0xF900, 0xFAFF),    # CJK compatibility ideographs
    (0x20000, 0x2FA1F),  # extensions B..F
)
_PUNCT_OK = " '-"


def _is_name_char(ch: str) -> bool:
    if ch in _PUNCT_OK:
        return True
    if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
        return True
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _is_alnum_char(ch: str) -> bool:
    return _is_name_char(ch) and ch not in _PUNCT_OK


def looks_like_name(line: str) -> bool:
    """Does one line have the shape of an EVE character name?"""
    n = len(line)
    if n < MIN_NAME_LEN or n > MAX_NAME_LEN:
        return False
    if line.count(" ") > MAX_WORDS - 1:
        return False
    if not _is_alnum_char(line[0]) or not _is_alnum_char(line[-1]):
        return False
    return all(_is_name_char(c) for c in line)


@dataclass(frozen=True)
class GuardResult:
    accepted: bool
    mode: str                  # "list" | "single" | "rejected"
    names: tuple = ()
    reason: str = ""           # English, for the log
    own_seen: tuple = ()       # your own characters found in the paste
    reason_key: str = ""       # the same refusal, for i18n.t()
    reason_args: tuple = ()

    def __bool__(self) -> bool:
        return self.accepted


def normalize(text: str) -> list[str]:
    """Stage 0: split, strip, drop blanks and the odd BOM, de-duplicate while
    preserving order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.replace("﻿", "").strip()
        if not line:
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _reject(key: str, *args) -> GuardResult:
    """Refuse the paste, carrying BOTH a translation key and English text.

    The English string stays because it is what goes into the log, where a
    Russian message would be worse than useless. The key is what the window
    translates for the person reading it.
    """
    return GuardResult(False, "rejected", (), i18n.en(key, *args),
                       reason_key=key, reason_args=args)


def inspect(text: str, own_names=()) -> GuardResult:
    """Stages 1-3. Returns the candidate names, or why the text was refused.

    `own_names` are your own characters, discovered for free from the
    `Listener:` header of recent chat logs. Finding one in the paste is proof
    it came from a local member list.
    """
    if not text or not text.strip():
        return _reject("reason.empty")
    if len(text) > MAX_CHARS:
        return _reject("reason.too_long", len(text))
    if "\t" in text:
        # D-Scan, inventory and EFT exports are tab-separated; names are not.
        return _reject("reason.tabs")
    if _URL.search(text):
        return _reject("reason.url")

    lines = normalize(text)
    if not lines:
        return _reject("reason.empty_after_normalise")
    if len(lines) > MAX_LINES:
        return _reject("reason.too_many_lines", len(lines))

    good = [ln for ln in lines if looks_like_name(ln)]
    ratio = len(good) / len(lines)

    own_lc = {n.casefold() for n in own_names or ()}
    own_seen = tuple(ln for ln in good if ln.casefold() in own_lc)

    # Stage 3: your own character in the paste settles it, even if some other
    # line is malformed (a truncated copy, a stray status line).
    if own_seen:
        candidates = tuple(ln for ln in good if ln.casefold() not in own_lc)
        if not candidates:
            return _reject("reason.only_own")
        return GuardResult(True, "list", candidates, "", own_seen)

    if ratio < MIN_MASK_RATIO:
        return _reject("reason.mask_ratio", len(good), len(lines))

    if len(good) == 1:
        # A single word is the weakest possible signal. Accept it, but the mode
        # tells scan.py to stay silent when ESI does not know the name.
        return GuardResult(True, "single", tuple(good))

    return GuardResult(True, "list", tuple(good))
