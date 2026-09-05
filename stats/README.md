# stats — a closed record

GitHub's traffic API answers for the **last 14 days only**. The days that fall
out of that window are gone: there is no deeper history to request, on the site
or through the API. So these CSVs are not a report that could be regenerated —
they are measurements that were taken at the time, between **2026-08-10 and
2026-09-05**, covering the project's publication and its first three releases.

⚠️ **The collector was removed on 2026-09-05, on request.** Nothing writes to
this folder any more, and the daily Windows task that used to run it has been
unregistered. What is here is frozen: it will neither grow nor be corrected.
Reading a date later than 2026-09-05 into these files is a mistake.

| file | columns | what it is |
|---|---|---|
| `views.csv` | date, views, uniques | per day |
| `clones.csv` | date, clones, uniques | per day |
| `downloads.csv` | date, tag, asset, downloads | a **cumulative** counter, sampled |
| `referrers.csv` | date, referrer, count, uniques | GitHub's own 14-day aggregate, sampled |
| `paths.csv` | date, path, count, uniques | the same |
| `repo.csv` | date, stars, watchers, forks | sampled |

⚠️ Three of those are **snapshots of a running total, not daily figures**. The
release download counter only ever grows, and referrers/paths are what GitHub
aggregates over its own 14 days. A row is meaningful only against another row:
the difference between two dates, never the value on one.

⚠️ **The download counter counts everything** — bots, mirrors, a second click
by the same person. There is no unique-downloaders figure and it cannot be
derived. Clones of the repository are not in it either; that is `clones.csv`.

## What the record says

At the close, over the whole period: **66 views / 14 unique**, **82 clones /
24 unique**, **8 release downloads** (v0.2 — 5, v0.1 — 1, v0.3 — 1, plus one
`SHA256SUMS.txt`), **0 stars**. Traffic is one spike on 2026-08-23–25, the days
the project was published and v0.2 was tagged, and near-silence afterwards.
Referrers were GitHub itself and Bing.

## If it is ever wanted back

`stats/collect.py` is in git history — it authenticated through `gh`, merged
the rolling window into these files by date, and appended a line per run to
`stats/collect.log`:

```bash
git log --diff-filter=D --oneline -- stats/collect.py   # the commit that removed it
git show <commit>^:stats/collect.py > stats/collect.py  # bring it back
```

It ran here as a Windows scheduled task named **Character Check stats**, daily
at 12:00, `pythonw.exe stats\collect.py` with the project root as the working
directory and *Start the task as soon as possible after a scheduled start is
missed* set — a laptop closed at noon would otherwise lose that day for good
once it aged past 14. The traffic endpoints require push access, so it worked
for the owner of the repository and answered 403 to anyone else, which is
correct rather than a bug to work around. No token was ever stored here and
none belongs here.

⚠️ If it does come back: collect from **one machine only**. It merges by date,
so a re-run corrects its own day instead of doubling it, but two clones
committing the same day is a CSV merge conflict resolved by hand.
