# Project state

Snapshot: **2026-09-05**. Update this file at the end of a session rather than
starting a second one.

`CLAUDE.md` is the project map and the invariants, and is read automatically.
This file holds only what is not in it: what is done, what is next, and what
was abandoned and why.

---

## Right now (2026-08-25)

**0.3 is released.** `git tag v0.3` was pushed, CI built it and published the
archive with a provenance attestation. `config.VERSION` is `"0.3"`. The working
tree is clean, `main` is pushed, and a built copy also sits in the author's
`Desktop\CC\CharacterCheck\` (rebuilt with `build.py --dest`, 5 633 811
bytes, version resource verified as 0.3 in Explorer's Details tab).

What 0.3 added, both on request and both described in `CLAUDE.md`:

- **the session ignore list** (3.7) — a circled-minus menu in the topbar and a
  right-click on a pilot. It is applied in `scan.scan_text` before the cache
  read, so an ignored pilot costs no lookup and no request; nothing writes it
  down, because the requirement was that it clear itself on exit;
- **the backdrop stays behind the results** (3.8) — the reversal of a rule this
  file and `CLAUDE.md` both used to state the other way round. Every label now
  sits on its own translucent panel, `SCRIM_ALPHA = 0.80`, measured against the
  brightest pixel the artwork contains rather than chosen by eye.

**Three things are closed and must not be reopened without new data.** Each
cost a live experiment, and the detail is further down this file:

1. the antivirus counter — three measured failures: distribution format,
   bootloader bytes, and now the packager;
2. zKillboard `/stats/` screening — measured on 167 pilots; it cannot pay, and
   the version that would save anything silently clears real cyno pilots;
3. a second interface language — removed on request, and `README.ru.md` is
   documentation rather than interface.

**Three open actions, all the author's rather than the code's:**

- report the Microsoft false positive (`Trojan:Win32/Wacatac.C!ml`) at
  <https://www.microsoft.com/en-us/wdsi/filesubmission>. It is the only engine
  that matters — it is on every Windows machine by default — and it is the one
  the pynsist experiment failed to shift;
- apply to **SignPath Foundation**. After three failed packaging hypotheses a
  signature is the only lever left, and both of its prerequisites (a public
  repository, a CI build) have existed since 3.4;
- send the enquiry in `Desktop\CC\CCP-запрос\` — written, never sent. See
  open question 4 at the foot of this file for why a support ticket is the
  only channel that yields a written answer.

**Traffic collection is over.** `stats/*.csv` was committed on request
(2026-09-05) and the collector removed in the same breath: the numbers run
2026-08-10 to 2026-09-05 and stop. The files stay because GitHub's traffic API
forgets anything older than 14 days, so not one row in them could be
regenerated — they are a closed record. The daily Windows task
**Character Check stats** was unregistered; `stats/collect.py` is recoverable
from git history and `stats/README.md` says how, along with the trap that
matters if it ever comes back (collect from one machine, or two clones
committing the same day is a CSV merge by hand). ⚠️ It was removed because it
was no longer wanted, not because it broke — do not rewrite it unprompted.

⚠️ **The 0.3 executable has not been scanned.** The two-engine figure quoted
throughout this file is the 0.2 build, and a detection count is only worth
something when both files are measured on the same day with the engines named
(`CLAUDE.md`, the build section). Nothing about the packaging changed in 0.3,
so there is no reason to expect movement — but the number has not been
re-measured and must not be quoted as if it had. Scan the **exe**, never the
zip.

**Open questions worth reading before touching anything** are at the bottom of
this file: the 429s in `app.log` versus invariant 3 (still not the experiment
that would settle it), the CCP → Fenris Creations rename in the disclaimer
(legal-entity suffix unverified — **do not guess it**), and how to ask them
whether this is allowed at all.

---

## Done

| Phase | What | Where |
|---|---|---|
| 0 | cyno sets derived from the SDE | `sde/build_cyno_sets.py` → `sde/cyno_sets.json` |
| 1 | Qt-free core + console | `core/`, `python -m core.console` |
| 2 | tray, results window, Jump Planner styling | `ui/` |
| 3 | icons instead of text, tightened evidence rules, console-less start | `core/icons.py`, `ui/icon_cache.py`, `ui/results_window.py`, `start.cmd` |
| 3.1 | pre-rebalance fits, tech-tier badge, RU/EN (removed in 3.5), always-on-top | `core/i18n.py`, `sde/build_cyno_sets.py`, `core/analyze.py` |
| 3.2 | evidence grouping, the `seen` level, tally as bare numbers, dark caption | `core/analyze.py`, `core/cache.py`, `ui/glyphs.py` |
| 3.3 | three search filters, cache beside the exe, streamed results | `core/scan.py`, `core/cache.py`, `core/config.py`, `ui/results_window.py` |
| 3.4 | published to GitHub, CI build with provenance, English docs | `.github/workflows/ci.yml`, `README.md` |
| 3.5 | English only, no notifications, contacts footer, window logo, square action buttons | `core/i18n.py`, `ui/tray.py`, `ui/assets.py`, `ui/results_window.py` |
| 3.6 | amber accent, window transparency, one instance only, the idle backdrop | `ui/styles.py`, `ui/single_instance.py`, `assets/make_background.py` |
| — | version 0.2, released by tag | `core/config.py`, `.github/workflows/ci.yml` |
| 3.7 | session ignore list, tighter topbar cluster | `core/scan.py`, `ui/results_window.py`, `ui/glyphs.py` |
| 3.8 | right-click to ignore, the list drawn over the backdrop | `ui/results_window.py`, `ui/styles.py` |
| — | version 0.3, released by tag | `core/config.py`, `README.md`, `README.ru.md` |
| — | publication prep: two identities in the UA, LICENSE, About window | `core/config.py`, `ui/about.py`, `tests/test_distribution.py` |

380 tests, none of them touching the network:
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

#### The third hypothesis, and this one is built (2026-08-24)

Outside evidence rather than plausibility: PySpy's CHANGELOG 0.5.6 says
*"Switch pynsist for installation to avoid bogus virus warnings"* — a
comparable Python/Windows EVE tool, our exact problem, and the thing it changed
was the **packager**, not the bootloader and not the distribution format.

`build_pynsist.py` is a **parallel** build path; `build.py` is untouched and
remains how the program ships.

**The premise is confirmed and it cost no upload at all.** Searching for five
4 KB slices of the stock `runw.exe` inside each artifact:

| | slices found | size | installed |
|---|---:|---:|---:|
| `dist/CharacterCheck/CharacterCheck.exe` | **5 of 5** | 5.6 MB | 141 MB, 207 files |
| `build/nsis/CharacterCheck_Installer.exe` | **0 of 5** | 44.6 MB | 148 MB, 665 files |

sha256 `d2a4bd48…` and `95dbe692…` respectively.

⚠️ **The size objection turned out to be wrong, and it was mine.** pynsist was
expected to cost 2–3× because it takes whole wheels and cannot tree-shake. It
has `exclude`, whose patterns are rooted at `pkgs/`, and with `PySide6-Essentials`
in place of the `PySide6` meta-package (which drags in the 168 MB Addons wheel)
the installer is **44.6 MB against our 55 MB zip** — smaller, not larger.

Verified running, not merely built: Qt 6.11.1 loads out of the bundled
embeddable CPython 3.12.10, `cyno_sets` loads 73 hulls from `pkgs/sde`, the
window and tray come up, and a second launch hands off and exits 0 exactly as
under PyInstaller.

**Three traps, all of them silent:**

- ⚠️ pynsist resolves relative paths against **the directory of the config
  file**, not the working directory. The config is generated into `build/`, so
  a relative `assets/icon.png` sends it hunting for `build/assets/icon.png` and
  dies with a bare `FileNotFoundError: [WinError 2]` naming no path. Every path
  in the generated config is absolute.
- ⚠️ `nsist.configreader.read_extra_files` reads `files` with a bare
  `.splitlines()` — unlike `packages` and `pypi_wheels`, which it strips first
  — and turns every line without a `>` into a path. A leading blank line
  becomes the file `''` and pynsist dies in `shutil.copy2` with
  `[WinError 3]`, again naming nothing. The first entry therefore goes on the
  key's own line.
- ⚠️ The data files must land **inside `pkgs/`**. Both
  `cyno_sets._artifact_path` and `ui.assets._asset` fall back to two
  directories above their own module when `sys._MEIPASS` is absent, and under
  pynsist that is `pkgs/`. In `$INSTDIR` the app cannot find its own cyno sets,
  which is a hard failure by design.

**What is NOT settled.**

⚠️ The comparison is not strict, and no number should be read off it without
this sentence. Our detections were on `CharacterCheck.exe`; pynsist's artifact
is an **NSIS installer stub** — a different binary with its own detection
profile, and NSIS is itself a format malware is packed with. A fall from 2
engines to 1 could be that and not the missing bootloader.

⚠️ Portability. pynsist produces an installer, not a folder. `config.cache_dir`
puts the cache beside the executable precisely so a copy on a USB stick carries
its answers with it. Where pynsist actually installs, and whether that location
is writable, was **not** verified — the run above was from the assembled tree,
laid out by hand as the installer would.

⚠️ **Do not switch the default build on one sample.** Two engines is a small
number and VirusTotal results drift on their own; 2 → 1 could be noise. If it
looks like a win, re-run both a week later before touching
`.github/workflows/ci.yml` or the README.

#### The answer (VirusTotal, 2026-08-24) — the third hypothesis is wrong too

Both artifacts uploaded within a minute of each other.

| | verdict | engines that flagged it |
|---|---|---|
| `CharacterCheck.exe` (PyInstaller) | **2 / 71** | Microsoft `Trojan:Win32/Wacatac.C!ml`, SecureAge `Malicious` |
| `CharacterCheck_Installer.exe` (pynsist) | **1 / 69** | Microsoft `Trojan:Win32/Wacatac.C!ml` |

⚠️ **Microsoft flags the pynsist artifact too, and that settles it.** That
binary contains **0 of 5** slices of the PyInstaller bootloader — verified by
byte search before either upload. The hypothesis was "remove those bytes and
the detections stop". The bytes are gone and the detection that matters is
still there. Removing the packager bought exactly one engine: SecureAge.

⚠️ **And Defender is the one that matters.** Bkav Pro and Zillya are obscure;
Microsoft Defender is on every Windows machine by default. Going from
"2 engines nobody runs" to "Defender says trojan" is not an improvement to
celebrate, and the pynsist build does not fix it.

⚠️ **The 2026-08-20 baseline turned out to be unusable, and this is the most
useful thing measured here.** Then: Bkav Pro + Zillya. Now: Microsoft +
SecureAge — and Bkav Pro reports **Undetected** on both files. The count is
"2 then, 2 now" while not one engine is the same engine. Verdicts on this file
drift on their own between engine-roster updates, so **no conclusion may be
drawn from a count alone**, only from named engines measured on the same day.
That is why both files were uploaded together rather than comparing today's
pynsist number against August's PyInstaller number.

**What the two artifacts actually have in common**, now that the packager has
been eliminated as the variable: an unsigned PE with a large appended overlay
and a Python payload inside. `Wacatac.C!ml` is Defender's generic
machine-learning bucket, and both files carry VirusTotal's `overlay` tag.
Nothing about how the overlay got there appears to matter.

⚠️ One thing is NOT isolated: our exe changed between the two measurements
(amber accent, `background.png`), so "Defender is new since August" cannot be
attributed to drift rather than to the new build. It does not affect the
conclusion — Defender flags the pynsist binary as well, which shares none of
those bytes.

#### Confirmed the same evening, on a second independent build

The v0.2 release archive was scanned, then the executable inside it separately.

| file | verdict | engines |
|---|---|---|
| `CharacterCheck-win64.zip` (`8d66e646…`) | **0 / 66** | none |
| `CharacterCheck.exe` from inside it (`89b2c5f6…`) | **2 / 70** | Microsoft `Trojan:Win32/Wacatac.B!ml`, SecureAge `Malicious` |

⚠️ **Scanning the archive is not a measurement of the program.** A clean sheet
on the zip means only that the engines judged a container; unpack it and the
same two vendors flag the same file. Anyone reporting "VirusTotal says 0/66"
about this project is quoting the wrong artifact. Always extract and scan the
PE.

**But the exe result is the useful part, and it is the strongest data point
yet.** This build came off a GitHub runner, not the author's machine, with
different package versions — 4 945 788 bytes against the local build's
5 625 092, so it is a genuinely different binary from a different environment.
It draws **exactly the same two engines**. That rules out anything peculiar to
one machine and confirms the detection is keyed on the shape of the artifact.
It also settles the drift question the other way: Bkav Pro and Zillya changed
their minds over four days, but Microsoft and SecureAge agree with themselves
across two builds on the same day.

(`Wacatac.B!ml` here against `Wacatac.C!ml` in the morning is a variant label
inside one generic machine-learning family, not a different finding.)

⚠️ **A crowdsourced YARA rule fired: `PyInstaller`, from bartblaze's public
ruleset**, with its own note that matching it "does NOT necessarily mean the
detected file is malicious". It is not what causes the Microsoft verdict, but
it is direct confirmation of the claim in `CLAUDE.md` that a PyInstaller
binary is trivially identifiable from public signatures — the shape is
recognised by rules anybody can read.

**Consequences.**

1. `build_pynsist.py` stays as a recorded experiment. **The default build does
   not change.** It buys one obscure engine and costs portability, and the
   cache-beside-the-executable property is worth more than SecureAge.
2. Code signing is the only lever left that plausibly moves Defender, which
   puts the SignPath Foundation application back at the top rather than as one
   item among three.
3. ⚠️ **Do not propose a fourth packaging change.** Three hypotheses have now
   been measured — distribution format, bootloader bytes, packager — and all
   three were wrong. The variable is not how the Python gets into the PE.
4. The false-positive report to send is now **Microsoft's**, not Bkav's:
   <https://www.microsoft.com/en-us/wdsi/filesubmission>. Still the user's to
   send.

### Phase 3.8 (2026-08-24) — the list sits on the picture now

**Right-click a pilot → Ignore**, beside the topbar menu shipped an hour
earlier. Reaching for the header to dismiss the pilot you are looking at is the
wrong distance.

⚠️ Two rules, both about not surprising anyone: a click inside the current
selection means the whole selection, a click outside it means that one row —
and neither moves the selection. `_ignore_target` holds the decision, split out
of the menu because the menu ends in `exec()` and a modal popup cannot be
driven from a test.

**The backdrop stays visible while results are on screen**, and this reverses a
decision recorded in `CLAUDE.md` in as many words: *"a name must never be read
against artwork"*. It now reads "never against **bare** artwork" — every label
in the tree is painted on a rounded translucent panel. The old rule cost the
picture the moment anything was found, which in practice meant never seeing it.

⚠️ **The alpha was measured, not chosen.** Composited against the brightest
pixel the artwork contains, `(152, 119, 76)` in the station's wireframe,
`BG_DEEP` at 0.80 leaves `RED` — the tightest of the tree's colours — at
**4.55:1**, with `TEXT_DIM` 4.89, `BLUE` 6.00, `YELLOW` 9.31, `TEXT` 10.74.
At 0.75 the red falls to 4.21 and misses. `GREY` was excluded on purpose: it is
the `none` level and clean pilots never enter the tree, so measuring against it
would have forced a darker scrim for text that cannot appear.

⚠️ **Four things carry text over the picture, not one** — the name, the
evidence line, the hull name beside an evidence icon, and the `+N` overflow
marker. The first two are a new `NameDelegate` on column 0; the last two are
the `tail` inside `IconRowDelegate`. Missing any one of them makes expanding a
pilot produce an unreadable list.

**Three settings had to give way**, all of which paint an opaque row
background: `alternatingRowColors` is off for good, and hover and selection in
the QSS became `rgba()`. Over a picture, stripes are a venetian blind and a
hover is a black bar.

⚠️ `test_ui_window` had a test named
`test_rows_get_a_flat_panel_and_not_artwork` enforcing the old rule. It was
**inverted rather than deleted**, and its docstring now says which way round it
used to be — so the next reader meets the reversal instead of guessing at it.

369 → 380 tests.

### Phase 3.7 (2026-08-24) — the session ignore list

Your own fleet is not the threat. Paste it once, press ignore, and those pilots
are out of every scan until the list is cleared or the application exits.

**It is applied inside `scan.scan_text`, before the cache read**, not by hiding
rows — an ignored pilot costs no cache lookup and no zKillboard request. The
progress line counts what will actually be scanned.

**Nothing anywhere may write it down.** Session state only: not `config.json`,
not `cache.db`. That is not a detail, it is the requirement — the user asked
for a list that clears itself, and the guarantee is the absence of any code
that could persist it. A test asserts that saving the config after ignoring
adds no key. Closing the window only hides it to the tray, so the list
survives that and dies with the process.

**One button with a menu, not two buttons.** The width argument for this was
wrong and is worth recording as such: at 4 px spacing two buttons come to 305,
under the 325 floor set by the contacts footer, so width never decided it. The
menu earns its place because the action has two scopes — the selected rows and
everyone the last paste checked — and two unlabelled glyphs cannot say which is
which.

**The topbar buttons moved into their own layout at 4 px.** Measured: seven
buttons at 4 px come to the same 283 px as six at 10, so the new button was
free. The outer 10 px stays for the logo and the title.

⚠️ **The eye glyph was measured and rejected.** "Hidden" is normally an eye
with a stroke through it, and at 16 px it does not survive — four variants were
rendered at actual size and all three eyes collapsed into a smudge with a
diagonal on it. A circled minus reads instantly. A circle with a *diagonal* bar
reads just as well and was rejected for what it says: these pilots were checked
and set aside, not forbidden.

⚠️ **A note for whoever edits this project through a shell.** Three separate
times this session a newline escape written inside a heredoc reached the file
as a real newline and produced an unterminated string literal — and the fourth
time was this very paragraph, which had to be repaired after describing the
problem. Build such escapes with `chr(92)`, or use an editing tool. Do not put
backslash escapes in a heredoc here.

351 → 369 tests.

### Phase 3.6 (2026-08-24) — the app's own colours, and one measured refusal

**Amber, chosen by measurement.** `ACCENT` was `#4fc3f7`, inherited wholesale
from Jump Planner, while the one piece of artwork the project owns is amber.
It is now `#ff944d`: contrast **8.2:1** against `BG_PANEL` (the blue managed
8.9), and hue distances of **22.9°** from `RED` (the `cyno` verdict), **19.6°**
from `YELLOW` (`hull`) and **11.8°** from `ORANGE` (the Tech II wedge). Set in
two places — the module constant *and* the `default` theme preset — because
`build._beacon_png` reads the constant at build time with `apply_theme` never
called, so changing one would have shipped a blue `.ico`. Rendered the tray
beacon at 16 px beside a `hull` beacon to check the two nearby hues still read
apart. `TEXT_LINK`, `GREEN` and `RED_DARK` were unreferenced and are gone.

**Window transparency**, the one control worth taking from PySpy outright: a
slider in the footer, 50–100%, saved on `sliderReleased` rather than per tick.
⚠️ Clamped at 50 on write *and* on read — opacity applies to text too, and a
hand-edited `0` in `config.json` must not produce an invisible window.

⚠️ It also broke the minimum width the moment it was added: `setFixedWidth(90)`
pushed the window's floor from 318 px to 420, and `TestMinimumWidth` — written
one phase earlier for a different bug — caught it. `setMaximumWidth` plus
`_let_it_shrink` restored 318.

**One instance at a time** (`ui/single_instance.py`, a `QLocalServer` named
after a sha1 of `data_dir`). Not tidiness: `ZKB_CONCURRENCY` is 8 and is a
constant *because* the price of exceeding zKillboard's rate is an IP ban, and
two copies make it 16 from one address. A second launch asks the first to show
itself and exits 0. `removeServer` before `listen` because a crash otherwise
leaves the name behind and the app would refuse to start ever again; a failing
`listen` logs and starts anyway, as `config.load` and `_start_logging` do.

⚠️ **The handshake cannot be tested from one process** and this cost an hour
of chasing a bug that was not there. `signal_existing` blocks the calling
thread, and a server living in that same thread cannot accept while it is
blocked — so an in-process test watches the handoff report success while the
callback never fires. Verified with two real processes instead; the tests drive
the socket by hand without blocking, and the trap is written into both files.

**The idle backdrop.** `assets/background.png`, produced by a committed
generator (`assets/make_background.py`, the `sde/build_cyno_sets.py` pattern):
light denoise (luma 3, chroma 10 — the artefact is red/green speckle in the
sky, and heavier luma smoothing eats the thin wireframe lines and the faint
stars), 2× Lanczos, crop, dimming baked in so the app does no per-repaint work.
472 KB.

⚠️ **The first version cropped a landscape band around the planet, and it was
wrong.** The crop was chosen from renders at 900x560 and 700x420 — and the
window is used **tall and narrow**. `config.json` had held the answer the whole
time: `window_rect` is 552x1374, a viewport of about 538x1260. In that window
the landscape crop is magnified some 2.6x and shows one enormous soft fragment
of the planet's limb.

**The fix was to stop cropping.** The source composition is aspect 0.495 and
the real viewport is 0.434 — the artwork already fits the window it is actually
used in, and cover-scaling now trims only a sliver off the top and bottom. The
stored file is 720x1456, the source's own width, so nothing is stored upscaled;
the 2x Lanczos pass exists to break up the JPEG's 8x8 blocks and coming back
down to 720 is what removes them. 973 KB, which is the most this repository
should carry forever — 900 wide costs 1.35 MB for detail that is dimmed to 60%
and sits behind an empty list.

⚠️ **The lesson is not about aspect ratios.** Four renders were made and looked
at, which is the right instinct, and every one of them was at a size the window
is never used at. Measuring the wrong configuration carefully is not
measurement. The app's own saved geometry is the first place to look for what
"the window's size" means.

It is painted by an event filter on the tree's viewport that fills the base
colour, draws the pixmap **only when the list is empty**, and returns `False`
so the tree still paints its rows. The QSS tree background had to become
transparent — a background set there belongs to the widget and is painted
*after* the filter, covering the picture. No pilot's name is ever read against
artwork.

⚠️ A first version toggled `alternatingRowColors` off when the tree was empty,
on the theory that QTreeView carries its stripes down past the last row and
would show the picture through a venetian blind. **Measured: it does not.** The
mechanism was removed rather than kept with a false justification, and a test
now covers the case it was invented for.

328 → 351 tests.

### Phase 3.5 (2026-08-23) — the window, on request

Six changes asked for in one go, all of them about the window rather than the
logic. Two of them turned up defects that were already shipped.

**English only.** The `RU` table, `set_language`, `language`, `en()`,
`config.lang` and the RU/EN button are gone. `retranslate()` survived under a
new name, `_label_widgets()`: it is the only place seven widgets are ever
labelled, and one function means the whole caption-and-tooltip set can be read
at a glance. `README.ru.md` stays — documentation, not interface.

**No notifications.** Both `showMessage` balloons and the `winsound` beep are
gone, and `config.sound` with them. What announces a finding is the window
coming up plus the tray icon taking the verdict's colour. ⚠️ Neither reaches a
user with EVE in fullscreen; the beep was the one that did. Accepted knowingly.
The startup "your requests are unsigned" balloon became
`ResultsWindow.set_notice()`, a standing line beside the hint that clears after
the first accepted scan.

**Square action buttons.** "Check clipboard" is a 28 px square with a drawn
circular arrow, and a bin beside it clears the list. Six glyphs now, two of
them framed: the framed ones *do* something, the borderless ones only change
what is on screen.

⚠️ **The disappearing button was not what it looked like.** `_let_it_shrink`
set an `Ignored` size policy, whose hint is discarded rather than deferred, so
beside a stretch the widget got zero width — the title, the hint and that
button were invisible at **every** window size, and phase 3.4 recorded it as
"squeezed out below 350 px" because nobody measured a wide one. Fixed with
`Preferred` plus a minimum of one pixel (zero is silently ignored by
`qSmartMinSize`). Minimum width measured after: **318 px**, set by the contacts
row; the topbar needs 283.

**Contacts in the window.** A footer with Discord / Telegram / EVE, handles
imported from `ui/about.py` — invariant 7 now holds by import rather than by
convention. Short captions with the handle in the tooltip: full ones would put
the minimum width at ~455 px.

⚠️ **Two live bugs found while building it.**
`ui/about.py` called `i18n.t()` without importing `i18n`, so the About window
raised `NameError` — in the released 0.1. Nothing constructed the dialog in the
suite, and `test_distribution` reads that file with `ast` rather than importing
it, so everything stayed green over a window that could not open. There is a
`tests/test_about.py` now.
And `core/clipboard` handed the app its own writes back: Ctrl+C on selected
pilots started a fresh scan of those same pilots. `clipboard.expect()` closes
it, and the contacts row could not work without that fix.

**Tighter ship rows.** Two delegate instances, ships at gap 0, modules still at
4 — their 2 px coloured frames must not touch. ~13% more hulls per row.

**The logo at runtime.** `ui/assets.py` loads `assets/icon.png` for the window,
the taskbar and a 22 px copy in the topbar; `build.data_files()` puts it in the
bundle. ⚠️ The committed PNG already carries its alpha channel — verified by
decoding it — so nothing cuts a circle at load time. `CLAUDE.md` said otherwise
and was corrected.

287 → 328 tests.

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

⚠️ **This entry was wrong, and 3.5 corrected it.** The measurement was never
taken on a *wide* window. `_let_it_shrink` used an `Ignored` size policy, which
does not mean "use the hint when there is room" — it discards the hint, so
beside a stretch the widget gets nothing. The title, the hint and the "Check
clipboard" button were **0 px wide at every size**, not merely below 350. The
real minimum is now 318 px, set by the contacts row, and the widgets are
visible again. Details in `CLAUDE.md`; held by `tests/test_ui_window.py`.

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

**RU/EN** with English as the default, instant switching — **removed in 3.5**,
see below. `core/i18n.py` is now one English table of 92 keys.
**Always-on-top** — a header button, state in the config. Spoilers no longer
expand by themselves; the tree header is gone.

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

**Screening pilots with zKillboard's `/stats/` endpoint (measured 2026-08-24).**
PySpy fetches `api/stats/characterID/<id>/`, a small aggregate whose `groups`
block carries `shipsLost` per ship group. The hypothesis was: a pilot with no
losses in any cyno-capable group cannot have module or hull evidence, so the
expensive killmail page need not be fetched. Probed live on **167 real pilots**
(the 78 in the local cache plus 89 hub names resolved through ESI), 334
requests, cold:

| | median bytes | median time |
|---|---:|---:|
| `/stats/characterID/<id>/` | 11 652 | 0.31 s |
| `/losses/characterID/<id>/page/1/` | 103 664 | 0.27 s |

**It fails on cost, and structurally rather than marginally.** `/stats/` is 9×
smaller and *exactly as slow*, because the binding constraint is not bandwidth
— 334 requests took 40.5 s, i.e. 8.2 req/s, which is the token bucket doing its
job. The bucket charges one token per request regardless of size, so a screen
turns N requests into N + N(1−f) and is **never** fewer than N for any clearing
rate f. There is no value of f that makes it pay.

**And the version that would have saved anything also lies.** Screening on the
9 `hull_groups` ids keeps 78% of pilots and produces **5 false negatives out of
our 65 module-carrying pilots** — it silently clears pilots who demonstrably
have a cyno, because Venture, Etana and Rabisu reach cyno capability through
`canFitShipType` and sit in groups 25, 832 and 1283 alongside every other T1
frigate and logistics ship. Adding those three groups removes every false
negative and keeps 90% of pilots, saving essentially nothing. A silent false
negative is precisely the failure that made this project reject `/asearch/`
(invariant 5).

P2 — whether `/stats/` shares the same rate bucket — was **not run**, and
deliberately: it was the one probe whose failure mode is an IP ban, and the
idea was already dead on P1 and P3. Partial evidence in passing: the 167
`/stats/` requests above went through the shared bucket interleaved with the
losses pass and returned 334/334 HTTP 200.

**zKillboard already publishes a per-character cyno summary — and it cannot be
used.** The same `/stats/` body carries `cyno: {count, standard, covert,
industrial}`. It is present for only **41 of 167** pilots (25%), and it is
silent about **37 of our 65** pilots who demonstrably carried a cyno module.
Re-requesting does not populate it, so it is not lazily computed on demand.
It is a partially-filled background job, not an index — and it would in any
case still be one request per pilot, replacing one request per pilot, while
discarding the hull, the date and the killmail that make a verdict explainable.

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

**Looked at in PySpy and not taken this round** (so they are not re-derived
from scratch): corporation and alliance columns with a count of how many of
that corp are in the paste; zKillboard deep links that know which column was
clicked; a once-a-day GitHub release check. The temporary "NPSI fleet" ignore
list was on this list and **was built in 3.7**. None was rejected on merit — they are simply not what was asked for.
⚠️ PySpy's central backend is the one thing deliberately **not** taken: it
requires a server, its data is a nightly dump about a day stale, and its
original host answers 404 today. A mini-app that depends on somebody's VPS
stops working when that VPS does.

**`docs/MANUAL_TESTS.md`** — the plan called for it, the file was never
written. It should collect what the automated tests cannot cover: the
copy-from-game round trip and verdict accuracy on pilots with a known history.
⚠️ Not sound in fullscreen: as of 3.5 there is no sound and no toast, and
nothing the app does reaches a user whose EVE is fullscreen. That was measured
against and accepted, not left to be tested.

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

   ⚠️ **2026-08-24, another clean data point and still not the experiment.**
   The `/stats/` probe made 334 requests through the same bucket in 40.5 s
   (8.2 req/s, mixed `/stats/` and `/losses/`) for **334/334 HTTP 200**. That
   is the fifth run in a row without a 429 — and it is 334 requests, not the
   ~2800 of the run that produced 426 of them. The size of the run remains the
   untested variable, which is exactly what the paragraph above says to
   measure. Do not read this as the invariant being confirmed.

   What to do next time: run the whole hub with both filter settings and count
   429s against elapsed time; if they reproduce, measure the real ceiling
   rather than tuning the constant to taste.

2. **Faction hulls (meta 4, 16 of them) get no tier badge.** The mechanism is
   ready — add a colour to `styles.META_COLORS`, one line. The original task
   mentioned only T2.

3. **CCP Games is now Fenris Creations** (renamed 2026-05-06). The app's
   disclaimer (`i18n.EN["about.disclaimer"]`) and both READMEs still say
   "CCP hf.". ⚠️ The legal-entity suffix of the new name is **not verified**
   and must not be guessed — a disclaimer naming a company that does not exist
   is worse than a stale one. Proposed wording once confirmed: "Fenris
   Creations (formerly CCP Games)".

4. **How to ask them whether this is allowed.** There is **no approval to
   obtain**: the Third Party Policies state they will not authorize or sanction
   third-party software, and the developer documentation names no vetting
   process. So the question can only be "is *this specific behaviour*
   acceptable", never "please approve my app". ⚠️ The EVE Discord's
   `#3rd-party-dev-blog` is an RSS feed and cannot be posted to; the writable
   developer channel, if it still exists, is behind an opt-in role under
   "Channels & Roles". A support ticket is the only channel that yields a
   written answer. Not started.

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

- ⚠️ **`ui/icon_cache.py` can print a traceback on shutdown.** Noticed
  2026-08-24 while rendering the scrim, and it is **not** new -- that file has
  not changed since 0.1. `_IconJob.run` ends in
  `self._cache._delivered.emit(...)`, and if the QObject has been torn down
  while a fetch is still in flight Qt raises `RuntimeError: Signal source has
  been deleted`. Harmless -- the process is ending anyway -- but a user who
  quits from the tray mid-scan gets a traceback in `app.log`, which looks like
  a crash to whoever reads it. One guard in `run` fixes it. Not done, because
  it was not what the session was asked for.

- The transcript of the session in which the project was written lives under
  the **old** key:
  `C:\Users\Kersid Jay\.claude\projects\f--123-Auto-Cyno-Marker\*.jsonl`.
  The project memory has already been copied under the new key
  `f--123-Character-Check`.
- The original plan (`docs/PLAN.md`, Russian, 2026-08-18) was removed from the
  repository in phase 3.4: this file superseded it and it was outdated in
  places. It remains in git history at the initial commit.
