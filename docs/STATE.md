# Project state

Snapshot: **2026-08-23**. Update this file at the end of a session rather than
starting a second one.

`CLAUDE.md` is the project map and the invariants, and is read automatically.
This file holds only what is not in it: what is done, what is next, and what
was abandoned and why.

---

## Done

| Phase | What | Where |
|---|---|---|
| 0 | cyno sets derived from the SDE | `sde/build_cyno_sets.py` → `sde/cyno_sets.json` |
| 1 | Qt-free core + console | `core/`, `python -m core.console` |
| 2 | tray, results window, Jump Planner styling | `ui/` |
| 3 | icons instead of text, tightened evidence rules, console-less start | `core/icons.py`, `ui/icon_cache.py`, `ui/results_window.py`, `start.cmd` |
| 3.1 | pre-rebalance fits, tech-tier badge, RU/EN, always-on-top | `core/i18n.py`, `sde/build_cyno_sets.py`, `core/analyze.py` |
| 3.2 | evidence grouping, the `seen` level, tally as bare numbers, dark caption | `core/analyze.py`, `core/cache.py`, `ui/glyphs.py` |
| 3.3 | three search filters, cache beside the exe, streamed results | `core/scan.py`, `core/cache.py`, `core/config.py`, `ui/results_window.py` |
| 3.4 | published to GitHub, CI build with provenance, English docs | `.github/workflows/ci.yml`, `README.md` |
| — | publication prep: two identities in the UA, LICENSE, About window | `core/config.py`, `ui/about.py`, `tests/test_distribution.py` |

287 tests, none of them touching the network:
`python -m unittest discover -s tests`.

Verified live: 60 hub names in both modes (8.6 s / 15.3 s, the reds match), 12
known cyno pilots (12/12 under the default filters, 6.5 s → 0.58 s from cache),
a 49-name paste, a 1402-name stress run.

### Antivirus and code signing (2026-08-20, continued 2026-08-23)

**Detections.** VirusTotal, two rounds:

| file | detections |
|---|---|
| onefile | Bkav Pro `W32.Malware.98C1BF1C` |
| onedir zip | Bkav Pro `W32.Malware.5A27CA41` + Zillya `Backdoor.XWorm.Win32.3294` |

⚠️ **The first round did not move the counter — it got worse, not better.**
The bet was on onedir ("self-extraction into `%TEMP%` looks like a dropper"),
and it did not pay off. The reports are not strictly comparable (different
files), but 1 → 2. Recorded so that this argument is not put forward as the
main one again.

**The second hypothesis — the bootloader — did not hold either.** The reasoning
was factually correct: the wheel ships a prebuilt binary, and slices of the
stock `runw.exe` really are inside our exe verbatim (5 of 5). But **rebuilding
from source changes nothing**: the same MSVC produces byte-identical code, 64
differing bytes and every one of them metadata (Rich header, TimeDateStamp,
checksum). Numbers in `CLAUDE.md`.

So the popular advice "just rebuild the bootloader" is useless on a matching
toolchain, and it cost a Build Tools install to find that out. That is exactly
why it is written down.

⚠️ **Two plausible hypotheses in a row turned out to be wrong.** What they had
in common: both explained a mechanism, and neither was tested before being
adopted. There must be no third hypothesis without a way to test it.

**What was done**, all in `build.py`:

1. **`--onedir` instead of `--onefile` by default.** No effect on detections
   (above); kept for the cold start, **1.6 s → 0.71 s** — those one and a half
   seconds *were* the unpacking. The price is 133 MB spread over files instead
   of 55 MB in one.
2. **A version resource.** It was entirely blank — every field of the Details
   tab. Generated from `core.config`, no hand-maintained file.
3. **`--noupx`, explicitly.** Changes nothing today (UPX is not on PATH); it is
   there for the machine where it is installed, because PyInstaller picks it up
   silently and a UPX-packed binary is flagged by a dozen engines.
4. **A bootloader guard** (`build.report_bootloader`): prints the sha256 of the
   bootloader going into the build and says `custom` / `STOCK` /
   `unknown-version`. Without it, `pip install --upgrade pyinstaller` would put
   the stock one back silently. The hash table is keyed by PyInstaller version:
   after an upgrade the key is absent, and the check has to admit it rather
   than stay quiet.

Filing false-positive reports with Bkav and Zillya is left to the user — an
outward action. It is the only thing that removes **those two** detections
rather than dodging them.

**The machine's own antivirus** (worth remembering next time): ESET Security
with real-time protection on, and it never touched the build across a whole
session. Windows Defender is disabled, so it is useless as a signal. In other
words the engines that actually block things are silent; the two that complain
are from the tail.

**Signing.** There is none, and there is exactly one free option:

| Option | Price | Real trust | Requires |
|---|---|---|---|
| **SignPath Foundation** | 0 | **yes**, a real OV cert | public repository + CI |
| GitHub Artifact Attestations | 0 | provenance, not Authenticode | public repository |
| Self-signed | 0 | **no** | — |
| Azure Trusted Signing | $9.99/mo | yes | — |
| Certum Open Source | ~€25/yr | yes | — |

⚠️ **Self-signed does not count** — written down so it is not re-litigated.
Windows still says "unknown publisher"; SmartScreen and antivirus engines
ignore an untrusted signature. It costs exactly as much as having none, while
looking like a closed question.

⚠️ **And signed ≠ no warning on day one.** SmartScreen reputation accrues to a
certificate as downloads happen; only an EV certificate grants it instantly,
and that is free nowhere.

Both prerequisites for SignPath Foundation now exist (public repo, CI that
builds). Applying is the remaining step. Apache-2.0 is already in place.

**State of this topic as of 2026-08-23.** The toolchain and the PyInstaller
sources have been removed; the installed PyInstaller is the stock wheel. Only
the useful parts remain in the code: the bootloader guard, the version
resource, `--noupx`, onedir. Open:

1. false-positive reports to Bkav and Zillya — **the user's to send**, the only
   thing that clears those two detections;
2. a SignPath Foundation application, now unblocked;
3. further work on the VirusTotal counter — **do not start without a way to
   test the hypothesis.** Two plausible ones in a row were wrong; a third
   without a test will cost the same and yield the same.

### Phase 3.4 (2026-08-23)

**Published**: <https://github.com/kersidjay69-art/Character-Check>, public,
Apache-2.0. `PROJECT_URL` in the User-Agent no longer points at a 404, which
had been an open question for days.

**CI** (`.github/workflows/ci.yml`) runs the suite on Windows against Python
3.11 and 3.14, then builds the executable and, on tags, attaches a build
provenance attestation. The app is unsigned, so "built in the open from this
exact source" is the strongest honest claim available until a certificate
exists.

⚠️ **CI found a real defect on its first run**, not a CI quirk:
`TestBootloaderGuard` imported PyInstaller, which `requirements.txt`
deliberately omits — it is a build tool, not a dependency. Anyone who only
wanted to run the program and then ran the tests got four errors. `build.py`
now treats a missing PyInstaller as a normal answer and the two tests that
need it skip. Verified both ways: 287 pass with it installed, 287 pass with the
import blocked.

**Minimum window width 516 → 230 px.** Qt derives a window's minimum from its
layout, and a QLabel reports the full width of its text — the title, the bottom
hint and the "Check clipboard" button were setting the floor between them.
They now shrink and clip. The saved-geometry sanity check was halved to match
(400 → 200), or the window would snap back to 1000×660 on every launch and read
as "it forgot".

⚠️ Below roughly 350 px the title and the "Check clipboard" button are squeezed
out entirely. Rescanning is still available from the tray menu. That is the
price of the halving and it was accepted deliberately.

**The exe has a real logo** — `assets/icon.png`, the first and only binary
asset in the repository. See `CLAUDE.md` for what had to be done to the source
image and why the icon is unreadable at 16 px.

**Documentation is English**; the Russian README is kept alongside as
`README.ru.md`.

### Phase 3.3 (2026-08-20)

**The product answers a different question by default.** It used to be "cyno,
and failing that, has he flown anything cyno-capable". Now "potential cyno" is
off and a pilot without a module never appears. Three filters
(`find_potential`, `find_industrial`, `stop_at_first`) live in the config and
are edited from the funnel in the header.

**A 2× speedup, and not a heuristic one.** Module evidence is read only from
`victim.items`, i.e. only from a pilot's own losses; the `/kills/` feed
physically cannot yield anything but `hull_flown`. With "potential" off that
request cannot change a single row on screen — so it is not made.

| | requests | 60 hub names | 1400 names |
|---|---:|---:|---:|
| both feeds | 2 per pilot | 15.3 s | ~350 s |
| "potential" off | **1 per pilot** | **8.6 s** | **~175 s** |

Both runs from an empty cache. `cyno` 4 and `indy` 1 match by name in both; the
entire difference is 12 pilots at the `hull` level. Narrowing costs not one
piece of module evidence.

**The cache moved and shrank.** Now `<app folder>\cache\cache.db`, while
settings stay in `%APPDATA%` — a portable copy carries its answers with it.
**Only pilots with a cyno module are stored**: 10.5% of those encountered,
~56 MB per million names. There is no negative cache any more, and that is a
deliberate price: pasting the same local twice is no longer instant. Measured
on 12 cyno pilots: 6.5 s → 0.58 s. The legacy import ran live: 78 pilots with a
module out of 696.

**`scan_bits`.** A cache row remembers which question it answered and is
compared for equality. Verified: turning "potential" on forced a rescan of all
12; running again with the same filter served 12 of 12 from cache.

**Streaming.** `stage_changed` / `pilot_ready` / `done`. Cached pilots are
handed over before the first network request. Insertion order and final sort
are one function, `scan.pilot_sort_key`.

**The "+1" on modules — a phase 3.2 regression, closed.** Column width is
computed from the delegate's geometry rather than a hard-coded 96 px. Plus
`QRect.right()` is inclusive — that is the exact pixel that was being missed.

**Name column 250 → 168 px** thanks to short evidence labels (`short.*`). The
row now fits 13 ships instead of 9.

### Phase 3.2 (2026-08-20)

**Evidence is grouped.** Found on a live pilot: his row drew a Marshal and a
Redeemer, his expansion showed fifty identical Legions. The cause was not the
PRIMARY KEY (nothing collapsed: 62 findings = 62 distinct killmails) but
`ORDER BY km_time DESC LIMIT 50` — the pilot flew 52 killmails on one hull in
four days and took every slot. Now one row per `(kind, ship, module)` with
`×N`. Raising the limit would not have helped: the problem was sameness, not
size.

**Covert Ops and T3 with no module → the new `seen` level.** The pilot stays in
the list, greyed, at the bottom. Cost measured on 1712 pilots: 104 moved
`hull → seen`, 4 `hull → indy`. Hub shares: `hull` 27.5% → 20.9%, `seen` 6.4%.

**Bare industrial hulls are no longer recorded as evidence at all** — 3263 rows
out of 16444 (20%) were exactly that. Changes no levels; it cleans up the
expanded list.

**A latent bug:** `cache.save_pilot` recomputed `modules_csv`/`ships_csv`
without `sets`, although `scan_pilot` had already computed them correctly a
line earlier. Without the SDE, `_hull_rank` cannot tell a recon from a hauler,
so a freshly scanned pilot got a flat, wrong ship order that only a migration
ever fixed. The lists are now passed as parameters.

**GUI:** row height and icon size tied to one constant `ROW_H` (the gaps
between rows disappeared), the header became bare coloured numbers with no
status line, the expand/collapse/on-top buttons became glyphs, the system
caption went dark.

⚠️ **The always-on-top button lost the window** and it reached the user:
`setWindowFlag` hides a visible widget, so an `isVisible()` check after it is
always false and `show()` never ran. The window also crept up by the height of
its own title bar per click. Closed by three tests.

### Phase 3.1 (2026-08-20)

**Pre-rebalance fits are no longer evidence** — the main change, and it
reverses an earlier decision. A module counts only if the hull can mount that
exact one under the current SDE (`CynoSets.can_fit`). Measured on 1712 pilots:
727 of 1493 findings removed, 53 pilots moved down, 13 of them losing their
only evidence. Hub shares: `cyno` 9.8% → 6.5%, `hull` 25.5% → 27.5%, `indy`
0.9% → 1.2%, `none` 63.8% → 64.8%. Migration
`drop_prerebalance_module_findings`, idempotent, verified on a copy of the live
database.

**The T2/T3 tier badge** is drawn from `metaGroupID` because
images.evetech.net composites it onto only 12 of 37 T2 hulls. The cause was
found in Fleet Manager and reproduced here across all 73 hulls.

**Order** — modules covert → regular → industrial; ships recon → Covert Ops →
HIC → other combat → industrial; pilots with modules above pilots without.

**RU/EN** with English as the default, 62 strings in `core/i18n.py`, instant
switching. **Always-on-top** — a header button, state in the config. Spoilers
no longer expand by themselves; the tree header is gone.

Lightening the ship icons was tried at 22% and 10% — **rejected**, it flattens
the artwork more than it helps. The icons stay as CCP ships them.

### Phase 3 (2026-08-20)

**Evidence rules tightened, shares recomputed on the hub (1402 pilots):**

| Level | Was | Became |
|---|---:|---:|
| `cyno` | 10.6% | 9.8% |
| `hull` | 23.2% | 25.5% |
| `indy` | 17.6% | **0.9%** |
| `none` | 48.6% | 63.8% |

Two new rules: a stowed cyno counts only on a combat cyno hull, and a bare
industrial hull stopped being evidence at all. Checked name by name on 1705
cached pilots — 289 transitions, **all downward**, not one promotion:
`indy→none` 264 (miners), `cyno→hull` 17, `cyno→none` 7 (freighters with a cyno
in the hold), `cyno→indy` 1. Migration `levels_cargo_and_indy_hulls`,
idempotent, verified on a copy of the live database.

**Icons.** `images.evetech.net` is the third and last network host. Its own
token bucket, a disk cache in `%APPDATA%\CharacterCheck\icons\`, misses
remembered by a `.miss` file. 76 files, 530 KB, 8.2 s on first run.

**Starting without a console.** `main.pyw` + `start.cmd`. Why the console kept
appearing: `python` on PATH is the Store stub `WindowsApps\python.exe`, which
always creates a console window and relaunches the real interpreter as a child.
There are no `.py`/`.pyw` associations on the system, so `.pyw` alone does not
solve it — `start.cmd` finds `pythonw.exe` itself.

**Window geometry** is remembered in `config.window_rect`. Verified on three
monitors: the window returns to the same screen, negative coordinates included.

---

## Abandoned — do not revisit without new data

These are not "we ran out of time", they are verified dead ends. Each cost a
live experiment.

**Writing corporation contacts through ESI.** The project's original idea. The
route does not exist: `POST /corporations/{id}/contacts` → 405 `Allow: GET`,
there is no `esi-corporations.write_contacts.v1` scope, and ESI ticket #751 has
been open since 2018. Personal contacts can be written, but the limit is ~1024
and labels do not apply to an offline character (issue #171, since 2016). The
product was rebuilt around this.

**A local database of every killmail, and a log watchdog.** Cancelled by the
user: the volume is not justified. Also, a local chat log contains only lines
people typed — no roster, no join/leave — so a watchdog cannot see a silent
cyno at all.

**zKillboard's `/asearch/`.** Rejected on the merits, not because of
Cloudflare: `cron/6.itemcleanup.php` keeps `$keepPerItem = 100000`, so the item
index covers roughly 18 months. On a real pilot it returned 14 cyno losses
where a full scan found 16 — a silent false negative for an "ever?" question.

**EVE SSO for signing requests.** Discussed 2026-08-20, cancelled by the user.
It would work technically: native/PKCE with no client secret, zero scopes, and
`name` and `sub` arrive in the JWT anyway. But the character name is already
free from `chatlog.own_characters()`, while SSO would add a refresh token on
disk, a browser trip on first run, and the look of "a tool for reading public
killboards wants an EVE login". Nobody verifies the UA signature — paying for
that with an OAuth subsystem is a bad trade.

**RedisQ** was switched off on 2026-05-31; **r2z2** and any killmail stream are
not needed — see invariant 5.

**Being a directory of every name ever seen.** Discussed 2026-08-20, cancelled
by the user on the numbers: EVE creates ~30 000 characters a day. A million
names with all their evidence is 750 MB, 260 MB with grouping. The cache stays
but keeps only pilots with a cyno module found (10.5%, ~56 MB per million
encountered).

**Posing as several clients to get around the zKillboard limit.** Asked
directly: "can we parallelise as if it were two different applications". No.
zKillboard counts by IP; two User-Agents from one machine is one IP. There is
no gain, and invariant 3 breaks. A pool of 8 threads already produces 20 req/s
on its own — the bucket throttles it to 8 on purpose.

**Cutting off at the rebalance patch date.** Measured: 10.8% of findings
predate October 2019, and 21 of 227 flagged pilots rest on those alone. At a
depth of one page the saving is 0% — there is one page already, nothing to cut.

**A cyno alt who lit one and did not die.** Leaves no trace in principle:
zKillboard knows only deaths. Decided by the user: "there is nothing we can do
here, so we do nothing".

---

## Next

**Speed.** Streaming into the table and a progress line were done in phase 3.3;
background page top-up was not, and after `single_full_history` was retired it
is a separate "ever?" question rather than an optimisation. `core/evekill.py`
(`POST /characters/analyze`, 250 ids in 0.53 s) was in the plan but is **not
written**: its window is 90 days, and on 129 pilots it reported
`cyno_probability = 0` for six whom a full scan found cyno deaths for. Good
only for an instant provisional highlight, never as the answer.

**OCR of the local list.** A large topic of its own. It must default to off:
screen capture is precedentially thinner than reading logs (see the EULA
section).

**An in-game overlay.** ⚠️ The only thing ever considered here that runs
straight into EULA 6.A.2 ("modify any content appearing within the Game
environment"). A separate window beside the client is safe; drawing over the
client is not.

**Phase 4, optional:** exporting the list, scan history, typing a name into the
window, a hotkey.

**`docs/MANUAL_TESTS.md`** — the plan called for it, the file was never
written. It should collect what the automated tests cannot cover: the
copy-from-game round trip, sound behaviour in fullscreen, verdict accuracy on
pilots with a known history.

---

## Open questions

1. **⚠️ `app.log` contains 429s from zKillboard — invariant 3 denies this.**
   Found 2026-08-20 while checking a new build.
   `%APPDATA%\CharacterCheck\app.log` for 17:32–17:34 holds **426 `zkb rate
   limited` warnings** and 8 pilots whose kills pass failed outright (`zkb 429`
   after every retry). Not a spike: 112 / 306 / 8 by minute, i.e. a minute and
   a half straight. Every URL is `/kills/page/1/`.

   `CLAUDE.md` invariant 3 says: "8 req/s verified across hundreds of requests
   with not one 429". One of the two facts is stale and I do not know which.
   Untested hypotheses: zKillboard tightened the limit; or that measurement was
   a hundred-request run and this one was a full hub (~2800); or the bucket
   leaks with 8 threads. **The invariant was left alone** — changing a rate
   constant on the strength of one log is exactly the case where the price of
   being wrong is an IP ban.

   Later runs (60 + 60 + 12 + 49 names) produced zero 429s. Incidentally,
   `find_potential=False` halves the request count and so reduces exposure —
   but that is a side effect, not a fix.

   What to do next time: run the whole hub with both filter settings and count
   429s against elapsed time; if they reproduce, measure the real ceiling
   rather than tuning the constant to taste.

2. **Faction hulls (meta 4, 16 of them) get no tier badge.** The mechanism is
   ready — add a colour to `styles.META_COLORS`, one line. The original task
   mentioned only T2.

---

## EULA — summary of the review (2026-08-20)

The EULA text is only reachable from the Steam mirror;
`support.eveonline.com` returns 403 to anything that is not a browser:
<https://store.steampowered.com/eula/8500_eula_0>

The explicit prohibitions are **not** breached: 6.A.3 (macros/input emulation)
— zero input synthesis; 6.A.2 (modifying game content) — the client is not
touched; 6.A.1 (load on "the System") — a scan sends `ceil(N/150)` requests to
ESI; 9.C (reverse engineering, packet sniffing) — what is read is the clipboard
and files the client writes itself.

The grey area worth remembering: the ToS contains the blanket phrase "nor will
they try to create or use any third party add-ons, extras or tools for the
game", which forbids literally everything, Pyfa and EVEMon included. And CCP
endorses nothing as a matter of policy: "any use of third party tools is done
entirely at your own risk". There is no whitelist, so "does not violate" will
never become "permitted". The disclaimer for this is in `ui/about.py` and in
the README.

---

## Loose ends from earlier sessions

- The transcript of the session in which the project was written lives under
  the **old** key:
  `C:\Users\Kersid Jay\.claude\projects\f--123-Auto-Cyno-Marker\*.jsonl`.
  The project memory has already been copied under the new key
  `f--123-Character-Check`.
- The original plan (`docs/PLAN.md`, Russian, 2026-08-18) was removed from the
  repository in phase 3.4: this file superseded it and it was outdated in
  places. It remains in git history at the initial commit.
