"""Keep the numbers GitHub forgets.

GitHub's traffic API answers only for the **last 14 days** and then drops the
older days for good -- there is no deeper history to ask for, on the site or
through the API. So the history has to be kept here: run this once a day and
each run merges the API's rolling window into files that never lose a day.

    python stats/collect.py

Data lands beside this file, one CSV per question, merged by date rather than
appended: re-running on the same day corrects that day instead of doubling it.
Today's row is always partial and is overwritten by every later run.

    views.csv       date, views, uniques        -- per day
    clones.csv      date, clones, uniques       -- per day
    downloads.csv   date, tag, asset, downloads -- a cumulative counter, sampled
    referrers.csv   date, referrer, count, uniques  -- a 14-day window, sampled
    paths.csv       date, path, count, uniques      -- same
    repo.csv        date, stars, watchers, forks    -- sampled

Two of those are snapshots of a running total, not daily figures: the release
download counter only ever grows, and referrers/paths are what GitHub itself
aggregates over its 14 days. Dating each sample is what makes a difference
between two of them meaningful.

Authentication is `gh`, already logged in on this machine -- no token is stored
in the repository and none belongs there. The traffic endpoints need push
access, so this works for the owner and nobody else.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = "kersidjay69-art/Character-Check"
HERE = Path(__file__).resolve().parent


def gh(path: str):
    """One `gh api` call, parsed. Raises with the CLI's own words on failure."""
    exe = shutil.which("gh")
    if exe is None:
        raise RuntimeError(
            "the GitHub CLI is not on PATH -- install it and run `gh auth login`"
        )
    done = subprocess.run(
        [exe, "api", path], capture_output=True, text=True, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError("gh api %s: %s" % (path, (done.stderr or "").strip()))
    return json.loads(done.stdout)


def merge(name: str, header: list, keys: list, rows: list) -> tuple:
    """Fold `rows` into stats/<name>, keyed by `keys`. Returns (total, new)."""
    path = HERE / name
    have = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                have[tuple(row.get(k, "") for k in keys)] = row
    new = 0
    for row in rows:
        key = tuple(str(row[k]) for k in keys)
        if key not in have:
            new += 1
        have[key] = {h: str(row[h]) for h in header}
    with path.open("w", newline="", encoding="utf-8") as fh:
        out = csv.DictWriter(fh, fieldnames=header)
        out.writeheader()
        for key in sorted(have):
            out.writerow(have[key])
    return len(have), new


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        views = gh("repos/%s/traffic/views" % REPO)
        clones = gh("repos/%s/traffic/clones" % REPO)
        referrers = gh("repos/%s/traffic/popular/referrers" % REPO)
        paths = gh("repos/%s/traffic/popular/paths" % REPO)
        releases = gh("repos/%s/releases" % REPO)
        repo = gh("repos/%s" % REPO)
    except (RuntimeError, json.JSONDecodeError) as exc:
        note("FAILED %s" % exc)
        print(exc, file=sys.stderr)
        return 1

    merge(
        "views.csv",
        ["date", "views", "uniques"],
        ["date"],
        [
            {"date": d["timestamp"][:10], "views": d["count"], "uniques": d["uniques"]}
            for d in views.get("views", [])
        ],
    )
    merge(
        "clones.csv",
        ["date", "clones", "uniques"],
        ["date"],
        [
            {"date": d["timestamp"][:10], "clones": d["count"], "uniques": d["uniques"]}
            for d in clones.get("clones", [])
        ],
    )
    merge(
        "downloads.csv",
        ["date", "tag", "asset", "downloads"],
        ["date", "tag", "asset"],
        [
            {
                "date": today,
                "tag": rel["tag_name"],
                "asset": asset["name"],
                "downloads": asset["download_count"],
            }
            for rel in releases
            for asset in rel.get("assets", [])
        ],
    )
    merge(
        "referrers.csv",
        ["date", "referrer", "count", "uniques"],
        ["date", "referrer"],
        [
            {
                "date": today,
                "referrer": r["referrer"],
                "count": r["count"],
                "uniques": r["uniques"],
            }
            for r in referrers
        ],
    )
    merge(
        "paths.csv",
        ["date", "path", "count", "uniques"],
        ["date", "path"],
        [
            {"date": today, "path": p["path"], "count": p["count"], "uniques": p["uniques"]}
            for p in paths
        ],
    )
    merge(
        "repo.csv",
        ["date", "stars", "watchers", "forks"],
        ["date"],
        [
            {
                "date": today,
                "stars": repo["stargazers_count"],
                "watchers": repo["subscribers_count"],
                "forks": repo["forks_count"],
            }
        ],
    )

    downloads = sum(
        a["download_count"] for rel in releases for a in rel.get("assets", [])
    )
    line = (
        "views %s/%s uniques, clones %s/%s uniques, downloads %s, stars %s"
        % (
            views.get("count", 0),
            views.get("uniques", 0),
            clones.get("count", 0),
            clones.get("uniques", 0),
            downloads,
            repo["stargazers_count"],
        )
    )
    note(line)
    print(line)
    return 0


def note(line: str) -> None:
    """A one-line log. Under the scheduler nothing reads stdout."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    with (HERE / "collect.log").open("a", encoding="utf-8") as fh:
        fh.write("%s  %s\n" % (stamp, line))


if __name__ == "__main__":
    sys.exit(main())
