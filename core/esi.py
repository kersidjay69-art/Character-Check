"""ESI, used for exactly one thing: turning pasted names into character ids.

This is also the guard's final arbiter. Character names in EVE are unique and
real; arbitrary text is not. A line that does not resolve to a character is
dropped silently, so junk that slipped past the mask costs nothing visible.

Verified behaviour of POST /universe/ids/ (probed live):
  * Hard cap 500 names; 501 -> 400. 500 intermittently 504s. 150 is the
    comfortable chunk.
  * DUPLICATES ARE A HARD 400 ("'names' items are not all unique"). The paste
    must be de-duplicated first -- core.guard.normalize already does it, but
    this module de-dupes again because a 400 here loses the whole scan.
  * Matching is FUZZY across entity kinds: ["Jita"] came back with the alliance
    "Jita Holding Inc." and the corporation "jion ss Corp". Only the
    `characters` array is read, and each returned name is re-checked against
    the input.
  * Names that do not exist are simply omitted -- no error, no placeholder.
    All-garbage input returns {} with HTTP 200.
"""
from __future__ import annotations

import logging

from .http import TIMEOUT, HttpError, session

log = logging.getLogger("cc.esi")

BASE = "https://esi.evetech.net/latest"
# Omitting this header silently pins you to compatibility date 2020-01-01.
COMPAT_DATE = "2026-08-18"
CHUNK = 150
MAX_CHUNK = 500


def _post_ids(names: list[str]) -> dict:
    resp = session().post(
        BASE + "/universe/ids/",
        params={"datasource": "tranquility"},
        json=names,
        headers={"X-Compatibility-Date": COMPAT_DATE,
                 "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise HttpError("universe/ids returned %d: %s"
                        % (resp.status_code, resp.text[:200]), resp.status_code)
    return resp.json() or {}


def resolve_names(names) -> dict:
    """names -> {casefolded name: (character_id, canonical name)}.

    Only genuine characters come back. Unknown names are absent from the
    result, which is what the caller uses to stay quiet.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for n in names:
        n = (n or "").strip()
        key = n.casefold()
        if not n or key in seen:
            continue
        seen.add(key)
        ordered.append(n)
    if not ordered:
        return {}

    wanted = {n.casefold() for n in ordered}
    out: dict[str, tuple] = {}

    for i in range(0, len(ordered), CHUNK):
        chunk = ordered[i:i + CHUNK]
        try:
            payload = _post_ids(chunk)
        except HttpError as exc:
            # One bad chunk must not lose the rest of a 200-pilot local.
            log.warning("name chunk %d-%d failed: %s", i, i + len(chunk), exc)
            continue
        for ent in payload.get("characters") or ():
            name = ent.get("name") or ""
            cid = ent.get("id")
            key = name.casefold()
            # Guard against the fuzzy matching described above.
            if cid and key in wanted:
                out[key] = (int(cid), name)
    return out
