# Character Check — project map

A desktop app: you paste a list of names from EVE's local chat and it tells you
which of them have lit a cyno. No server, no database of every killmail.

## Running it

```bash
python main.py                               # tray app, with a console
start.cmd                                    # the same without one -- normal start
python -m core.console                       # the same without Qt, output in the terminal
python -m core.console --once FILE.txt       # one-shot check of a file
python -m core.console --once F --show-clean --no-cache -v
python -m core.console --once F --potential  # filters: see "What is searched for"
python -m core.console --once F --no-industrial --all-cyno
python sde/build_cyno_sets.py                # rebuild the cyno sets from the SDE
python -m unittest discover -s tests         # 287 tests, none touching the network
python build.py --dest "C:/somewhere"        # build -> dist/CharacterCheck/
python build.py --onefile                    # one file instead of a folder
```

Settings, icons and `app.log` live in `%APPDATA%\CharacterCheck\`
(`config.data_dir`). **The cache lives separately, beside the application**:
`<exe folder>\cache\cache.db`, or `<project root>\cache\` when run from source
(`config.cache_dir`). A portable copy therefore carries its answers with it;
the cache is the only thing that is expensive to rebuild. If that folder is not
writable (an exe dropped into Program Files) it falls back to `%APPDATA%`
silently, because otherwise a portable copy simply would not start.
`CC_DATA_DIR` overrides both — that is what the tests run on.

On first run in a new location, pilots with a module are carried over from the
old `%APPDATA%\CharacterCheck\cache.db` (measured: 78 of 696). The old file is
left where it is: it is the user's data, and deleting it would be a favour
nobody asked for.

## Building the exe

`build.py` — PyInstaller, `--onedir --windowed --noupx`. Needs
`pip install pyinstaller`; it is deliberately absent from `requirements.txt` —
it is a build tool, not a dependency of the program.

| | size | build | cold start |
|---|---:|---:|---:|
| `--onedir` (default) | 133 MB, 203 files | 46 s | **0.71 s** |
| `--onefile` | 54.8 MB, one file | 53 s | 1.6 s |

**A folder by default.** `--onefile` is a stub that unpacks itself into
`%TEMP%` and runs what it just wrote; onedir has no extraction stage at all.
Those 1.6 s of cold start **were** the unpacking.

The price is 133 MB spread over files instead of 55 MB in one; it ships as a
zip (~55 MB). `--onefile` remains a flag: one file is handier locally.

⚠️ **Moving to onedir did nothing for antivirus detections, and that needs to
be known before proposing it again.** Measured: onefile — 1 engine (Bkav Pro),
onedir — **2** (Bkav Pro + Zillya `Backdoor.XWorm.Win32`). The reports are not
strictly comparable (different files), but the counter did not fall. The
argument "self-extraction looks like a dropper" sounds convincing and turned
out not to be what engines look at. What onedir really bought is 0.71 s instead
of 1.6 s, and that alone justifies the default.

Four things the build breaks quietly without:

**`sde/cyno_sets.json` must reach the bundle** (`--add-data`). Without it
`cyno_sets.load()` raises — and that is correct: an empty set would declare the
whole galaxy clean. The artifact path asks `sys._MEIPASS` directly
(`cyno_sets._artifact_path`) rather than deriving it from `__file__`: going two
directories up lands in the same place today, but that is a detail of how
PyInstaller names frozen modules, not a contract.

**`--windowed` means `sys.stderr` is `None`.** A plain `logging.basicConfig()`
would set up a `StreamHandler(None)` and the first warning would take the app
down. `main._start_logging` writes to `%APPDATA%\CharacterCheck\app.log` in
that case. From source it behaves as before, on the console.

**The exe icon is `assets/icon.png`**, the only binary asset in the repository.
Until 2026-08-23 it was drawn by code too (the beacon from `ui.tray._icon`) and
the "nothing binary in the repository" rule held completely; the user supplied
a finished logo, and artwork cannot be derived from code. Everything else is
still drawn: the tray icon, the header glyphs (`ui/glyphs.py`), the tier wedge.

⚠️ If the file is missing the build **does not fail**, it falls back to the
drawn beacon (`build._logo_png` returns `None`). A missing picture is no reason
to stop somebody building the program.

It is assembled into a multi-size `.ico` (16…256, PNG entries), each size
scaled from the 512px master separately. One size is not enough: Windows picks
different ones for the taskbar, the title bar and Explorer's large view, and a
single downscaled bitmap looks soft in at least two of the three.

⚠️ **At 16 and 24 px this logo is unreadable** — the dense radar dial becomes
an orange blob and only the circle is distinguishable. From 32 px up it is
fine. Checked by eye on light and dark backgrounds. The only fix is a different
picture for the small sizes, not code.

⚠️ The source image arrived **with no alpha channel**: its transparency was a
checkerboard painted into the pixels (a typical Gemini export). Colour keying
is impossible — the checkerboard grey matches grey on the ship's hull (found at
a radius of 12 px from the centre). So it is cut geometrically: a circle with a
soft edge, opaque to r=308, transparent from r=320, at a crop radius of 327.

**The version resource is generated** (`build.make_version_file`) from
`core.config` — it is not a file kept by hand. Before 2026-08-20 there was none
at all and Explorer's Details tab was entirely blank: a nameless unsigned
binary is a heuristic signal in itself, and the Details tab is the first place
a worried user looks.

⚠️ **The author is not in the exe and must not be** (invariant 7):
`CompanyName` is `PROJECT_URL`, the project's one public identity, and
`LegalCopyright` names the licence rather than a person. The author's contacts
live in `ui/about.py`, and the exe is handed to strangers. Enforced by
`tests/test_distribution.py`.

⚠️ `040904B0` in the `StringTable` and `[1033, 1200]` in `Translation` are the
same locale written two ways. If they diverge, Explorer shows an empty Details
tab, silently.

⚠️ `config.VERSION` is a human string (`"0.1"`) and the resource wants a tuple
of four numbers. `_version_tuple` takes the **leading** digits of each part
rather than every digit: dropping non-digits spliced `"1.0-rc1"` into `01` and
shipped it as 1.1. It does not raise on junk — a build must not be the thing
that discovers a typo in the version.

**Code signing.** There is none. There is exactly one free option — SignPath
Foundation for open-source projects — and it requires a public repository and a
CI build, both of which now exist; applying is the remaining step. A
self-signed certificate is not acceptable: Windows still says "unknown
publisher", and SmartScreen and antivirus engines ignore an untrusted
signature — it costs as much as having none while looking like a solved
problem.

## The bootloader: what antivirus engines actually recognise

The PyInstaller wheel from PyPI ships **prebuilt** bootloader binaries
(`PyInstaller/bootloader/Windows-64bit-intel/` — `run.exe`, `runw.exe` and
their debug twins; no sources). So the code that starts every frozen
application is byte-identical the world over — including the malware whose
authors pack it with the same PyInstaller. Generic engines' signatures sit on
those bytes.

Measured on our build, 2026-08-20:

```
runw.exe from the 6.20.0 wheel     279 552 bytes
our CharacterCheck.exe           5 447 990 bytes
common prefix                          270 bytes   (then our icon and version)
4 KB slices of runw.exe inside our exe:  YES
```

Hence the conclusion about onedir: neither the distribution format, nor the
version resource, nor `--noupx` touch those bytes at all.

### ⚠️ "Just rebuild the bootloader" DOES NOT WORK — verified

That is the standard advice, on the internet and in PyInstaller's own tracker.
We followed it completely (installed MSVC Build Tools, downloaded the 6.20.0
sdist, ran `waf distclean all --target-arch=64bit`) and **measured the
result**:

```
stock runw.exe        279 552 bytes
rebuilt               279 552 bytes   -- the same size
differing bytes            64        (0.02%)
longest identical run  247 298 bytes
4 KB slices of the stock inside the new one:  5 of 5
```

All 64 bytes are metadata, not one byte of code:

```
0x000080-0x0000ef   Rich header (compiler versions)
0x000110-0x000113   PE TimeDateStamp
0x000160-0x000161   checksum
0x03c764            debug directory timestamp
```

The reason is simple: PyInstaller builds the bootloader reproducibly, and the
same MSVC with the same flags emits **byte-identical machine code**. Any
signature keyed on code matches as if nothing had happened.

To change the code you have to change code generation. The only flag that did
so in testing was `/GS-` (size moved by 2048 bytes, 0 of 5 slices).
**Rejected:** that disables stack protection, i.e. weakens the binary for the
sake of not resembling a signature. `/O1` did not help — `wscript` appends
`/O2` after our `CFLAGS`, and with MSVC the last flag wins.

Conclusion: the road is not a dead end, but it is not free either, and above
all **there is no evidence the detection is keyed on bootloader bytes at all.**
It may be keyed on the PyInstaller archive structure (the `MEI` cookie), on the
embedded `python3xx.dll`, or simply on "a PE with Python inside". Before
spending time on this again, get a way to test the hypothesis rather than
another plausible argument.

The toolchain and sources were removed afterwards; the installed PyInstaller is
the **stock wheel** — `pip install .` was never run.

**The guard** — `build.report_bootloader()` prints the sha256 of the bootloader
that will go into the build and says `custom` or `STOCK`. Without it the first
`pip install --upgrade pyinstaller` would put the stock one back silently, and
we would find out six months later from another VirusTotal report.

⚠️ `STOCK_BOOTLOADERS` is a dictionary **by version**, not a single hash. After
an upgrade the key is absent and the check has to say "I do not know this
version" rather than stay quiet: a check that passes on everything it has not
seen is decoration. Held by
`tests/test_distribution.py::TestBootloaderGuard`.

⚠️ PyInstaller may be absent entirely — it is a build tool and is not in
`requirements.txt`. `build._pyinstaller()` returning `None` is a normal answer,
and the tests that need it skip. CI caught this on its first run.

## Layout

```
core/            Qt-free core (invariant 1)
  guard.py       THE GUARD: game text or junk. Pure functions, zero I/O
  analyze.py     pure A/B/C evidence logic for one killmail
  cyno_sets.py   loads sde/cyno_sets.json
  chatlog.py     your own characters, from the Listener: header
  clipboard.py   ctypes, GetClipboardSequenceNumber
  esi.py         POST /universe/ids/ -- and the guard's final arbiter
  icons.py       type icons from images.evetech.net, disk cache + misses
  i18n.py        EN/RU, keys rather than strings; EN by default
  zkb.py         zKillboard REST, pagination
  ratelimit.py   token bucket, 8 req/s
  http.py        one shared keep-alive session
  cache.py       SQLite: verdicts and evidence
  scan.py        the orchestrator
  console.py     running without Qt
assets/          icon.png -- the only binary asset (the exe logo)
sde/             build_cyno_sets.py -> cyno_sets.json (artifact, committed)
ui/              Qt lives only here
  styles.py      palette and QSS -- the same as Jump Planner's
  tray.py        tray icon, scan thread, notifications
  results_window.py  result tree, expansion into evidence, icon delegate
  icon_cache.py  PNG -> QPixmap, fetching off the GUI thread, icon_ready
  glyphs.py      chevron, pin, funnel -- drawn, not shipped as files
  about.py       the author's contacts -- the only place (invariant 7)
tests/           fixtures are real logs and real local pastes
```

Flow: `guard → ESI → cache → zKillboard → analyze → verdict`.

## Evidence

**One filter runs through all of it: `sets.can_fit(hull, module)`.** A module
counts only if the hull can carry that exact one under the current SDE. Neither
`fitted` nor `cargo` gets past it.

| Code | What | How it is decided |
|---|---|---|
| A `fitted` | died with a cyno in a high slot | `can_fit` AND `item_type_id ∈ modules` AND `27 ≤ flag ≤ 34` AND `depth == 0` |
| A' `cargo` | a cyno was aboard but not in a high slot | `can_fit`, same type_id, any other flag/depth. Counts as evidence **only on a combat cyno hull** |
| B `hull_lost` | died in a cyno-capable hull | `victim.ship_type_id ∈ hulls` AND the hull is **not** industrial |
| C `hull_flown` | took part in a kill in such a hull | `attackers[].ship_type_id` for his own `character_id`, same filter |

A bare industrial hull (Venture, Badger, Noctis) is not recorded as evidence at
all — not "level none", there is no row in the database: it only produced noise
in the expanded list (`analyze._hull_is_evidence`). A module on the same hull is
untouched.

## What is searched for — three filters

The filters decide not "what to show" but **what to extract in the first
place**. Evidence that is switched off is never created, never stored and never
reaches the verdict. That is not pedantry: it is exactly why a request can be
**not made** rather than made and thrown away. They live in `config.DEFAULTS`,
are read through `analyze.Filters.from_config`, and are edited from the window
(the funnel in the header) and from the console.

| Key | Default | What it switches off |
|---|---|---|
| `find_potential` | **off** | bare cyno hulls: the `hull` and `seen` levels |
| `find_industrial` | on | the industrial cyno module 52694 |
| `stop_at_first` | on | early exit on the first combat cyno |

⚠️ **The main consequence: with `find_potential` off the kills pass is not made
at all.** Module evidence (`fitted`, `cargo`) is read only from `victim.items`,
i.e. only from the pilot's own losses. The `/kills/` feed returns killmails
where the pilot is an attacker, so nothing but `hull_flown` can physically come
out of it. That means the second request cannot affect a single row on screen —
and `scan.feeds_for` does not order it. **1 request per pilot instead of 2.**

Measured live on 60 hub names, both runs from an empty cache:

| | time | verdicts |
|---|---:|---|
| default | **8.6 s** | `cyno` 4, `indy` 1, 55 clean |
| `--potential` | 15.3 s | `cyno` 4, `indy` 1, `hull` 12, 43 clean |

The reds and blues **match by name** — narrowing costs not one piece of module
evidence, it removes only the maybes. On 1400 names that is ~175 s against
~350 s. No other measure comes close: an early exit on the verdict would be
worth about 3%.

`find_industrial` off — a pilot who had nothing but an industrial cyno becomes
`none` and **disappears from the list** rather than sinking to the bottom.

`stop_at_first` applies only when `len(pilots) > STOP_AT_FIRST_MIN` (10). One
pilot takes a fraction of a second, so there is nothing to save, and a complete
answer to a deliberately typed name is worth more. It stops at the `cyno`
level, not at `fitted`: an industrial cyno is not what is being looked for, and
exiting on one would leave a red pilot reported as blue (`scan._proven`).

⚠️ **Depth is one page everywhere, a single name included** (`list_pages`).
`single_full_history` was retired: 25 s → 0.25 s. The price is honest and must
be remembered — the product stopped answering "ever?" and answers "in the last
200 losses". A silent false negative on "ever" is precisely what made the
project reject `/asearch/` (invariant 5). The same trade is now made
deliberately and by our own hand rather than inherited from somebody else's
cron job.

## Verdict priority

The product answers "cyno — and if so, which". Priority is set by the **module
type**, but the **hull decides whether a module counts at all**.

| Level | Meaning | Name colour | Share of a hub (1402 pilots) |
|---|---|---|---|
| `cyno` | covert or regular cyno (21096 / 28646) | red | 6.5% |
| `hull` | died or killed in a combat cyno hull, no module | yellow | 20.9% |
| `indy` | an industrial cyno **module** (52694) | blue | 1.4% |
| `seen` | only a "quiet" hull: Covert Ops or T3 | grey | 6.4% |
| `none` | nothing | — | 64.8% |

Those shares are with **all** filters on. By default `hull` and `seen` cannot
arise at all, and only reds and blues remain in the list: 7.9%.

The full rule table lives in the `analyze.Finding.level` docstring. Three
places where it is not obvious:

**A cyno in the hold counts as fitted only on a combat cyno hull.** The pilot
may have unfitted it one undock ago — but that is true of a recon, not of a
freighter hauling a crate of cynos to market. Same module, same `kind`; the
difference is entirely the hull.

**Covert Ops and T3 with no module are "seen", not a warning.**
Buzzard/Helios/Anathema/Cheetah are explorers' frigates and
Legion/Loki/Tengu/Proteus are the general-purpose cruiser. A cyno fits in them,
but everybody flies them, and yellow on that basis is a false alarm. Such a
pilot stays in the list, greyed and at the very bottom: he is not a threat, but
dropping him silently would hide the fact that he was checked at all. Measured
on 1712 pilots: **104 moved `hull → seen`**, another 4 `hull → indy` (they had
an industrial module that a quiet hull used to outrank). The list of quiet
groups is `analyze._QUIET_HULL_GROUPS`, exactly two.

**An industrial hull with no module is not evidence at all.** A lost Venture or
Badger with nothing in it is a miner. In the hub run there were 842 of those
out of 1547 flags, i.e. more than half the list was noise. `indy` now means
exactly "an industrial cyno module", not "an industrial ship", and its share
fell from 17.6% to 0.9%.

A level is an opinion about the evidence, and the evidence is fact. So when the
rules change the levels are **recomputed** from `findings` (migrations
`levels_with_yellow`, `levels_by_module`, `levels_cargo_and_indy_hulls` in
`cache.py`) rather than guessed. A migration must touch pilots **without**
evidence too, or they keep a level name from the old scheme forever and vanish
from every count.

## The icon summary is stored, not derived

`pilots.modules_csv` and `pilots.ships_csv` are what gets drawn in the row.
Deriving them from `findings` on read is **not allowed**: that table has
`PRIMARY KEY (character_id, killmail_id, kind)`, so a death with two different
cynos aboard stores one row out of two, and reads are bounded besides.
`findings` remains the source for the expanded evidence list, and for that
only.

Which ships get into the row: combat cyno hulls always; industrial ones only if
a cyno was actually **fitted** on them. Otherwise every lost Venture would earn
an icon. Quiet hulls (Covert Ops, T3) get in but sit **after** the industrial
ones: an industrial in the row means a fitted cyno, i.e. evidence, while a
Legion means nothing.

⚠️ **The icon row and the expanded list must say the same thing.** They diverged
once and it looked like lying: a pilot's row drew a Marshal and a Redeemer while
his expansion showed fifty identical Legions and nothing else. The icons were
right. The list was read with `ORDER BY km_time DESC LIMIT 50`, and the pilot
had flown 52 killmails on one hull in four days — all fifty slots went to them.
Raising the limit does not help, because the problem is sameness, not size.

So evidence is **grouped by `(kind, ship_type_id, module_type_id)`**: one row
per "what this was", the date of the most recent, the count as `×N`
(`analyze.group_findings`, and in SQL the `GROUP BY` in `cache.get_findings`).
Every icon now has a guaranteed corresponding row.

⚠️ In that query `killmail_id` and `system_id` are bare columns beside
`MAX(km_time)`. SQLite guarantees they come from the row `MAX` picked; that
guarantee is what makes a double-click open the newest killmail of the group
rather than an arbitrary one. It must not be rewritten as a plain aggregate.

## INVARIANTS — do not break

**1. `core/` does not import Qt.** Enforced by `tests/test_invariants.py`. Jump
Planner already paid for this: the moment the GUI leaks into the logic, nothing
can be tested or run without a display.

**2. No input emulation.** CCP tolerates reading logs, the clipboard and the
screen (RIFT is on their own tool list). Sending keystrokes is playing for the
player, EULA 6.A.3. Copying stays a human action. The forbidden calls are
listed in the test. Also forbidden: reading memory, scraping the client cache,
sniffing packets (EULA 9.C).

**3. The zKillboard rate is a constant, not a setting.** The price of exceeding
it is an IP ban for up to an hour. 8 req/s was verified across hundreds of
requests with not one 429. Measured: a pool of 8 threads on its own produced
**20 req/s**, because short pages return fast — which is why the bucket is
mandatory and a narrow pool is not enough.

**4. An empty `User-Agent` is a 403 on zKillboard.** The error is completely
opaque when it happens. The UA is never empty (`config.user_agent`).

**5. Do not touch `r2z2.zkillboard.com` or `/asearch/`.** r2z2 is a separate
bucket with a 15 req/s limit and an hour-long ban. asearch sits behind a
Cloudflare challenge, its CORS is pinned to its own domain, it is undocumented,
and — decisively — **it lies about "alltime"**: `cron/6.itemcleanup.php` sets
`$keepPerItem = 100000`, so the item index keeps only the last 100k kills per
type (~18 months). On a real pilot it returned 14 cyno losses against 16 from a
full scan. For an "ever?" question that is a silent false negative. Enforced by
a test over string literals (the docstring is skipped — the explanation belongs
in the code).

⚠️ And right here, so it does not look like a forgotten contradiction: **we
made the same trade ourselves** by retiring `single_full_history` (see "What is
searched for"). The difference is not honesty but whose choice it is and
whether it is visible. `/asearch/` lies silently: it answers "found nothing"
where the data simply is not there, and from outside that is indistinguishable
from a clean pilot. One page is our own ceiling, written down here: "in the
last 200 losses". If "ever" is ever needed, that is `list_pages`, not a new
endpoint.

**6. The cyno sets are derived from the SDE, not hard-coded.** The `canFit*`
attributes are resolved **by name**: there are 32 of them
(`canFitShipGroup01..20`, `canFitShipType1..12`) with non-consecutive
numbering. Hard-coding the range 1298–1300 silently loses T3 cruisers (for
28646 those are attributes 1301, 1872, 1879).

**7. Two identities in the `User-Agent`, never merged.** The project is public,
so the header is assembled from `PROJECT_URL` (the software, identical in every
copy) and `operator` (the human at this particular machine, from a chat log or
from `contact`). zKillboard bans by IP — so the signature must belong to
whoever's traffic it is. The author's contacts live only in `ui/about.py` and
must never appear in `core/`, where all the networking is.
`DEFAULTS["contact"]` must stay empty: a name written there would sign somebody
else's traffic. Enforced by `tests/test_distribution.py`.

## Three traps in the classification

Each was found in real data and closed by a named test.

1. **`depth == 0` is required for A.** Nested items inherit high-slot flags: an
   assembled ship in a Ship Maintenance Bay yields flag 28 at depth 1. Without
   the check, a freighter hauling a fitted recon reads as "cyno fitted".
2. **A flag is not unique per slot.** Charges carry their module's flag — one
   flag 27 can hold both a module and 52 rockets. It is decided by the pair
   (type_id ∈ modules) AND (flag range), never by the flag alone.
3. **Do not mix groups and types.** Venture is group 25 "Frigate"; Etana and
   Rabisu are group 832 "Logistics". Expanding a type back into its group would
   flag every T1 frigate and every logistics ship in the game.

## Facts verified live (do not change from memory)

- **ESI cannot write corporation contacts.** `POST /corporations/{id}/contacts`
  → 405, the `esi-corporations.write_contacts.v1` scope does not exist, ESI
  ticket #751 has been open since 2018. The original contacts idea was dropped
  entirely because of this.
- **`POST /universe/ids/`**: 500 names maximum (501 → 400), 500 sometimes gives
  504, a working chunk is 150. **Duplicates are a hard 400.** Matching is
  fuzzy: `["Jita"]` returned the alliance "Jita Holding Inc." and the
  corporation "jion ss Corp" — read only the `characters` array and compare the
  name with what was asked for.
- **zKillboard REST** returns full ESI bodies: `victim.items` with flags AND
  `attackers[]` with `ship_type_id` and `character_id`. One download answers
  all three questions. 200 kills per page, a 100-page ceiling. `/no-items/` and
  `/no-attackers/` are disabled permanently, commas in ids are unsupported,
  `pastSeconds` is capped at 7 days.
- **A chat log header appears exactly ONCE**, verified on a 408 KB file. (The
  plan wrongly recorded that it repeats — that was an artefact of reading the
  first 14 and last 8 lines of a 13-line file.) EVE starts a new file per
  session, so the first 4 KB is enough.
- **`Channel ID: local`** is the language-independent marker. The channel name
  is localised, and the file name carries a `_<charID>` tail.
- **Character names**: 329 live names were collected from these logs. 28% are
  CJK (`冰喵`, `幻华 琉璃`); there is a name made entirely of digits
  (`599847624`) and doubled apostrophes (`Io ''Midnight'' Shadow`). A Latin-only
  mask would cut a quarter of local. There is no Cyrillic in names — it is
  deliberately outside the allowed set so that Russian text in the clipboard is
  rejected by itself.
- **Cynos were not always restricted by hull — and that is NO LONGER
  evidence.** Before `canFitShipGroup` existed they were fitted to rookie
  frigates: real 2014–2018 kills include Velator, Ibis, Impairor, Reaper,
  Magnate. Stealth bombers carried the regular cyno instead of the covert one.
  The killmails are genuine, but they predict nothing: the pilot cannot repeat
  such a fit today.

  The project used to count them. **The decision was reversed on 2026-08-20**
  because on live data it turned out to be 727 findings out of 1493 (49%), and
  the ship rows carried Velators and Myrmidons for pilots incapable of lighting
  a cyno at all. The price was measured: 53 pilots of 1712 moved down, 13 of
  them losing their only evidence and becoming clean. If CCP ever puts cynos
  back on other hulls — rebuild the SDE and rescan; no separate code needed.

  `ship_names` (423 entries) stays: `is_ship()` protection against MTU and
  structure killmails rests on it.

## The cache

Evidence is **monotone**: die with a cyno once and it is forever. So a positive
verdict is cached permanently and that pilot is never fetched again.

⚠️ **Only pilots with a cyno module found get into the cache.** EVE creates
about thirty thousand characters a day — this file cannot and must not be a
directory of every name ever seen. A clean verdict is cheap to obtain again and
pointless to keep. Measured: **10.5%** of those encountered have a module, each
with 5.8 grouped evidence rows. Per million names encountered that is ~105 000
records and **56 MB** — a size that lives comfortably beside the exe and
travels with it.

The price is honest and must be known: **there is no negative cache any more.**
Pasting the same local again does not answer in a second — the reds and blues
appear instantly, the rest are computed afresh. Measured on 12 known cyno
pilots: first run 6.5 s, second **0.58 s** (ESI only).

**A row remembers which question it answered** — `pilots.scan_bits`, the
two-bit summary from `analyze.Filters.as_bits`. It is compared for **equality,
not containment**. A narrow row is unfit for a wide question in the obvious
way: the pilot simply has no hull evidence, because nobody looked for it. But a
wide row is unfit for a narrow question too: its `ships_csv` holds ships the
narrow question never asked about, while the evidence list beneath is filtered
on read — the icons and the expansion would diverge, which is exactly the
mistake this project has already paid for once. Verified live: turning
"potential cyno" on forced a rescan (0 of 12 from cache); running again with it
served 12 of 12.

⚠️ **`findings` must be filtered on read** (`cache.get_findings(...,
filters=)`). The table is append-only and is therefore the UNION of every
question ever asked about that pilot; a hull row left over from an older, wider
scan would otherwise surface under a row whose icons were computed without it.

**The 100 MB limit** (`cache_limit_mb`) is a safety valve, not a mechanism:
reaching it takes ~1.8 million distinct cyno pilots. Eviction goes **by
proportion, not row by row**: space is only returned by the vacuum at the end,
so a loop that re-measured the size after each delete would never terminate.
`PRAGMA auto_vacuum=INCREMENTAL` is set **when the file is created** — on an
existing database the pragma silently does nothing, and then rows would be
deleted forever while the file never shrank.

## GUI

The styling is taken from `f:/123/Jump planer/ui/styles.py` one for one: the
same dark palette (`BG_DEEP #0c0c0e`, `BG_PANEL #17171a`, `BORDER #32323a`,
`ACCENT #4fc3f7`, `TEXT #d4d4d8`), the same Segoe UI, the same object names
(`topbar`, `title`, `dim`, `primary`) and the same faction theme presets
(`config.theme`). Rules for `QTreeWidget` were added — Jump Planner styles only
tables and lists, whereas here the whole window is a tree.

A pilot's row is **name, module icons, ship icons**, all on one line with no
header: three column titles said nothing the icons do not. The expansion works
the same way — a module icon, a ship icon and its name, so the eye reads the
spoiler the way it read the row above it; plus `×N` when a row stands for
several killmails.

**The module column's width is computed from the delegate's geometry**
(`IconRowDelegate.width_for`) and set from the **number of cyno types in the
game** (`analyze.ALL_CYNO`) rather than a three somebody remembered. There was
a hard-coded number there once: 96 px; then the icon grew with the row height,
three modules needed 100, and a pilot with the full set drew two modules and a
"+1". Not one test noticed, because nobody knew the two numbers were related.

⚠️ There is a `+1` in `width_for` and it is not cosmetic: `QRect.right()` is an
**inclusive** boundary, a rectangle of width W spans `left…left+W-1`, and
`_slots` compares against exactly that. That is the pixel that was being
missed. The test asks `_slots` itself rather than repeating the formula:
repeating the formula is precisely how numbers drift apart.

**The name column is 168 px, not 250.** What held it was not the names (99% of
a hub ≤ 125 px, the longest of 1402 was 152 px) but the evidence label beneath
them: `2026-05-03  died in a cyno hull` is 164 px, 184 in Russian. So the
window uses short labels — the `short.*` keys (`fitted` / `in hold` / `lost` /
`flew`), which need 124/133 px. The console `kind.*` strings stay long: a
terminal has no column to widen. The 90 px freed went to ships — the row fits
13 instead of 9.

**Row height is one constant, `styles.ROW_H`**, and the icon is derived from it
(`ICON = ROW_H − 2×INSET`) rather than set beside it. A 20-pixel icon used to
live in a 30-pixel row, and the four spare pixels read on screen as gaps
between rows. A test holds `IconRowDelegate.cell == ROW_H`: they would drift
apart silently.

**The minimum window width is 230 px.** It was 516 — Qt derives a window's
minimum from its layout, and a QLabel reports the full width of its text, so
the title, the bottom hint and the "Check clipboard" button were setting the
floor between them. `ResultsWindow._let_it_shrink` gives those three an
`Ignored` horizontal policy so they can be squeezed and clipped; the tree,
which is what the window is for, shrinks happily.

⚠️ Below roughly 350 px the title and the "Check clipboard" button are squeezed
out entirely. Rescanning is still available from the tray menu. That is the
price of the halving and it was accepted deliberately.

⚠️ The saved-geometry sanity check in `_restore_geometry` was halved to match
(400 → 200). Refusing to restore a rectangle the user is allowed to drag to
would snap the window back to 1000×660 on every launch, which reads as "it
forgot".

Order within a row is by decreasing danger. Modules: covert, regular,
industrial (`_MODULE_RANK`, not by type_id — 21096 sorts before 28646 and that
is backwards). Ships: Force Recon, Heavy Interdictor, other combat,
industrial, and dead last the quiet ones (`_HULL_GROUP_RANK` + `is_quiet`).

⚠️ `is_quiet` is a property of the **finding, not the ship**. A Buzzard that had
a covert cyno in it is not quiet; the same Buzzard bare is. One `ship_type_id`
therefore arrives with two different keys, and the sort must collapse them into
a `dict` keyed by ship, keeping the louder one: a set of tuples would draw the
icon twice and one of them in the wrong place.

A pilot with modules always ranks above a pilot without one, even when the
latter's level is formally higher: `indy` has rank 2 and `hull` has 3, and
without that correction a blue pilot holding a cyno ended up below a yellow one
holding nothing.

The threat is carried by the name colour: `cyno` = RED `#ef5350`, `indy` = BLUE
`#42a5f5`, `hull` = YELLOW `#f0c040`, `seen` = TEXT_DIM `#8e8e98`, `none` =
GREY `#6e6e76`. `ORANGE` remains in the palette but is no longer a level.
`BLUE` is deliberately not `ACCENT`: that one is overridden by the theme
presets, and the blue would move with the faction choice. `seen` and `none` are
deliberately **different** greys: they never meet in the tree (there are no
clean pilots there), but they stand side by side as numbers in the header.

The header holds the name and bare coloured numbers, one per level. No words:
the colour is the same one a pilot's name wears two pixels below, and a tooltip
says what the number means. The "N pilots in X s" line is gone; everything that
used to live under the title (scanning…, guard refusal, own characters, not
found in ESI) moved to the hint at the bottom.

The buttons are glyphs drawn in `ui/glyphs.py`: chevron down/up, a pin and a
funnel. Not files and not text "▼"/"📌" — those depend on whichever font
Windows substitutes and take no palette colour. Their captions became tooltips.

⚠️ The pin had to be redrawn: the first version (a flat head and a body
tapering downward) read at 16 px as a **funnel**, and a funnel in a toolbar
means "filter". A tilted pin with a ball head is unambiguous. That very funnel
is now drawn separately and stands where it belongs — it is the search-filters
button; the pin's rejection is the argument for it.

**Filters are a menu under the funnel, not three buttons in a row.** Three
abstract 16×16 glyphs would repeat the pin's mistake, and three text captions
would eat half the header. A menu gives full phrases for free. The funnel is
tinted `ACCENT` when the set differs from the defaults: a scan that has become
twice as slow, or quieter, must say so from the header. Flipping a filter
restarts the check immediately — the list on screen was produced under the old
filter and answers a question nobody is asking any more.

⚠️ `_sync_filters` ticks the boxes with `blockSignals`: `setChecked` emits
`toggled`, and without the block the window would save the config and start a
scan merely because it had read its own settings — including at construction
time, when there is nothing to scan yet.

Every module is framed with a 2px border in its own colour: Cyno red, Covert
Cyno purple `#ba68c8`, Industrial Cyno blue.

⚠️ The frame is not decorative. **Cyno I and Industrial Cyno return a
byte-identical icon** — a shared `iconID 1444`, matching `sha1` at both sizes.
Without the frame the red case and the blue one look the same. Covert Cyno has
its own artwork, but at 20 pixels the difference does not read, so all three
got a colour.

⚠️ **The server draws the tier badge only sometimes.** Of 37 T2 hulls, 25
arrive without one (Falcon, Rapier, Onyx, Widow, every Blockade Runner and
DST), while Jaguar, Redeemer and all four T3s have it. There is no pattern. So
the wedge is drawn here from `metaGroupID` (`meta_groups` in the SDE artifact)
and **always over the server's** — otherwise those 25 would have no badge and
12 would have two. There is no "II"/"III" lettering: on a 20px icon the wedge
is 8px across and any glyph inside it is mud.

Icons come from `images.evetech.net/types/{id}/icon?size=64` — the project's
third and last network host. `/render` is not used: it exists only for ships
and answers 400 for all three modules. Local SDE dumps contain no images at all
(`invTypes.iconID` is a key into a table they do not include), so downloading
is the only route. 76 files, ~530 KB, once; a miss is remembered by a `.miss`
file, or a type with no picture would be re-requested on every repaint (that
hole exists in Jump Planner's cache).

Several icons in one cell are painted by `IconRowDelegate`: Qt gives an item
exactly one icon. Jump Planner solves the same problem with a row of `QLabel`s
in a `QHBoxLayout` — fine for one widget and far too heavy for a tree several
hundred rows long.

`main.py` → `ui/tray.py`. Scanning happens in a `QThread`, the clipboard is
watched by a thread from `core.clipboard`, and hand-off is by Qt signal; the
GUI thread only draws. Closing the window hides it to the tray rather than
ending the process.

**Results arrive as they become available.** `ScanWorker` emits three signals:
`stage_changed` (the guard accepted, ESI answered), `pilot_ready` (one pilot)
and `done` (the finished result). A full hub takes minutes, and the window used
to show nothing for all of it. Cached pilots are handed over **before the first
network request** — and only pilots with a cyno are cached — so the most
dangerous names appear instantly.

⚠️ Insertion order comes from `scan.pilot_sort_key`, and the same function
sorts the final `show_result`. Two copies of that rule would shuffle the list
the moment a scan ended — which looks like a bug even when both orders are
defensible. Verified: the streamed order matches the final one.

⚠️ At the start of a scan the window is raised with `show()` and **only** —
no `raise_()`, no `activateWindow()`. Taking focus from EVE mid-scan is not
acceptable. The end of a scan still raises the window, and only if something
was found.

The interface language is `config.lang`, **`en` by default**: the project is on
GitHub. The strings live in `core/i18n.py` (Qt-free, so the console speaks the
same language), and the RU/EN button in the header switches instantly. A trap
when adding strings: in `_build()` and `_menu()` widgets were created as local
variables, and `retranslate()` can only change what `self` holds a reference to
— a new button has to be both stored and listed in `retranslate()`.
`test_i18n.py` compares the EN and RU key sets and their `%` substitutions: a
forgotten string otherwise surfaces only for the user.

Guard refusal reasons are half-bilingual on purpose: `reason` stays English (it
goes to the log) while `reason_key` + `reason_args` are what the window
translates.

Window position and size are remembered in `config.window_rect` /
`window_maximized` and restored at startup — as plain numbers rather than a
`saveGeometry()` blob, so the config stays something a human can read. On
restore it checks that the rectangle intersects some existing screen:
otherwise a monitor unplugged since last run would drop the window into
nowhere, and it would look like "the app did not start". Geometry is written on
window close **and** on quitting from the tray — quitting bypasses
`closeEvent`.

The system title bar is painted dark through
`DwmSetWindowAttribute(DWMWA_USE_IMMERSIVE_DARK_MODE)` — Qt styles only the
client area, and a white strip sat on top of a black window. The attribute is
20 from build 18985 and 19 before that; the wrong number simply returns an
error.

⚠️ It has to be called **deferred** (`QTimer.singleShot(0, ...)`) and through
`windowHandle().winId()`, never `self.winId()`. Inside `showEvent` the native
window is still being built: `self.winId()` there can trigger a second
creation, and calling it head-on returns `S_OK` and repaints nothing.

⚠️ **`setWindowFlag` hides a visible window** — that is its documented side
effect. So "always on top" must ask `isVisible()` **before** changing the flag
and remember `geometry()`: otherwise the window disappears on the first click
and never returns (which looks exactly like a crash), and the new native window
is placed by its client rectangle and creeps up by the height of its own title
bar per click. Both cases are covered by tests in `test_ui_geometry.py`.

⚠️ EVE in fullscreen paints over the window, and `SetForegroundWindow` does not
help. Keep the game in windowed/borderless, or put the window on a second
monitor. (An in-game overlay is a separate task and is not done.)

## Status

Phases 1 and 2 are complete: the core, the console, the tray and the results
window. The project is published at
<https://github.com/kersidjay69-art/Character-Check> (invariant 7, `LICENSE`,
`ui/about.py`), and CI builds the executable from source with provenance.

Before starting anything, read **`docs/STATE.md`**: what is done, what is next,
the open questions and — above all — the list of **abandoned directions**. Each
of them cost a live experiment, and returning to one without new data is a
wasted session.
