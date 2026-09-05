# stats — the numbers GitHub forgets

GitHub's traffic API answers for the **last 14 days only**, and the days that
fall out of that window are gone: there is no deeper history to request, on the
site or through the API. Views and clones are therefore not a report you can
pull later — they are a measurement you either took at the time or did not.

`collect.py` is that measurement. Run it once a day; each run merges the
rolling window into the CSVs here, keyed by date, so re-running on the same day
corrects that day rather than doubling it, and a day recorded once is kept
forever.

```bash
python stats/collect.py
```

| file | columns | what it is |
|---|---|---|
| `views.csv` | date, views, uniques | per day |
| `clones.csv` | date, clones, uniques | per day |
| `downloads.csv` | date, tag, asset, downloads | a **cumulative** counter, sampled |
| `referrers.csv` | date, referrer, count, uniques | GitHub's own 14-day aggregate, sampled |
| `paths.csv` | date, path, count, uniques | the same |
| `repo.csv` | date, stars, watchers, forks | sampled |
| `collect.log` | | one line per run, including failures |

⚠️ Three of those are **snapshots of a running total, not daily figures**. The
release download counter only ever grows, and referrers/paths are what GitHub
aggregates over its own 14 days. A row is meaningful only against another row:
the difference between two dates, never the value on one.

⚠️ **The download counter counts everything** — bots, mirrors, a second click
by the same person. There is no unique-downloaders figure and it cannot be
derived. Clones of the repository are not in it either; that is `clones.csv`.

Authentication is `gh`, already logged in on this machine. **No token is
stored in this repository and none belongs here.** The traffic endpoints
require push access, so this works for the owner of the repository and returns
403 for anyone else — which is the correct answer, not a bug to work around.

**The CSVs are committed** (2026-09-05, reversing the rule that used to be
here). The churn argument was real — a snapshot a day is a commit a day — and
it lost to a simpler fact: this data cannot be re-fetched. Fourteen days after
the event GitHub has no answer to give, so the only copy that exists is the
one on disk, and a copy that exists on exactly one disk is not a record. The
run log stays ignored: it says how a collection went, not what was measured.

⚠️ That makes the CSVs **append-mostly files that two machines must not both
write**. `collect.py` merges by date, so a run corrects its own day rather than
doubling it, but two clones collecting the same day and both committing is an
ordinary merge conflict in a file nobody wants to resolve by hand. One
collector, one machine — the scheduled task below.

## Running it daily

On this machine it is a Windows scheduled task named **Character Check stats**,
firing at 12:00 with *Start the task as soon as possible after a scheduled
start is missed* — a laptop that was closed at noon would otherwise lose that
day for good once it ages past 14.

```powershell
Get-ScheduledTaskInfo -TaskName "Character Check stats"   # last result, next run
Start-ScheduledTask   -TaskName "Character Check stats"   # run it now
Unregister-ScheduledTask -TaskName "Character Check stats" -Confirm:$false
```
