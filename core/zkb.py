"""zKillboard REST client -- the only source of a pilot's full history.

Why this and not the advanced search: /asearchquery/ can filter by fitted item
and returns 151 bytes instead of 529 KB, but it sits behind a Cloudflare
managed challenge, its CORS is pinned to zkillboard.com, it is undocumented,
and -- decisively -- cron/6.itemcleanup.php keeps only the last 100000
killmails per item type (~18 months). On a real pilot it returned 14 cyno
losses where a full REST scan found 16. For an "ever?" question that is a
silent false negative, so this module walks the documented API instead.

Verified limits (probed live):
  * 200 killmails per page, page cap 100 -> 20000 killmails reachable.
  * Full ESI bodies inline: victim.items with flags AND attackers[] with
    ship_type_id and character_id. One download answers all three questions.
  * Blank User-Agent -> 403.  Accept-Encoding: gzip -> 8.4x smaller.
  * Comma-separated ids, /no-items/ and /no-attackers/ are all disabled.
  * pastSeconds is capped at 7 days, so it is useless for history.
  * ~0.8s and ~48 KB gzipped per page; 8 concurrent workers sustained with
    zero 429s across 231 requests.
"""
from __future__ import annotations

import logging
import time

from .http import TIMEOUT, HttpError, session
from .ratelimit import zkb_bucket

log = logging.getLogger("cc.zkb")

BASE = "https://zkillboard.com/api"
PER_PAGE = 200
MAX_PAGE = 100          # hard cap enforced by zKillboard itself

KIND_LOSSES = "losses"
KIND_KILLS = "kills"

_RETRY_PAUSES = (1.0, 3.0)


def _get(url: str) -> list:
    last: Exception | None = None
    for attempt in range(len(_RETRY_PAUSES) + 1):
        # Bound the rate globally, not per worker: a pool of 8 threads was
        # measured producing 20 req/s because short pages return fast.
        zkb_bucket.take()
        try:
            resp = session().get(url, timeout=TIMEOUT)
        except Exception as exc:            # network blip
            last = exc
        else:
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "error" in data:
                    raise HttpError("zkb error: %s" % data["error"], 200)
                return data if isinstance(data, list) else []
            if resp.status_code in (429, 502, 503, 504):
                last = HttpError("zkb %d" % resp.status_code, resp.status_code)
                if resp.status_code == 429:
                    log.warning("zkb rate limited on %s -- backing off", url)
            else:
                raise HttpError("zkb %d for %s" % (resp.status_code, url),
                                resp.status_code)
        if attempt < len(_RETRY_PAUSES):
            time.sleep(_RETRY_PAUSES[attempt])
    raise HttpError("zkb failed after retries: %s" % last)


def page_url(character_id: int, kind: str, page: int) -> str:
    return "%s/characterID/%d/%s/page/%d/" % (BASE, character_id, kind, page)


def fetch_page(character_id: int, kind: str, page: int = 1) -> list:
    """One page of full killmails. An empty list means there is no more."""
    if page < 1 or page > MAX_PAGE:
        return []
    return _get(page_url(character_id, kind, page))


def iter_killmails(character_id: int, kind: str, max_pages: int = 1,
                   start_page: int = 1, stop=None):
    """Yield killmails page by page.

    Stops early on a short page -- a page with fewer than PER_PAGE entries is
    the last one, which saves a request on the ~59% of pilots who never fill
    page 1. `stop` is an optional callable checked between pages so a scan can
    abandon a pilot the moment the worst verdict is already proven.
    """
    pages = min(max_pages, MAX_PAGE - start_page + 1)
    for offset in range(pages):
        page = start_page + offset
        batch = fetch_page(character_id, kind, page)
        if not batch:
            return
        yield from batch
        if len(batch) < PER_PAGE:
            return
        if stop is not None and stop():
            return
