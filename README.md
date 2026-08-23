# Character Check

[![build](https://github.com/kersidjay69-art/Character-Check/actions/workflows/ci.yml/badge.svg)](https://github.com/kersidjay69-art/Character-Check/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

*[Русская версия](README.ru.md)*

Paste a local member list from EVE Online — find out which of those pilots
have lit a cyno.

The app watches the clipboard. When you copy a local member list (click a name
in the member list, `Ctrl+A`, `Ctrl+C`) or a single name, it checks each
pilot's killboard and shows you the ones with cyno history.

## What counts as evidence

| Verdict | What was found | Share of a trade hub |
|---|---|---|
| **CYNO** (red) | a covert or regular cyno generator was on the pilot's ship | 6.5% |
| **industrial** (blue) | an industrial cyno module | 1.4% |
| **cyno hull** (yellow) | died in, or killed from, a combat hull that can carry such a cyno (Falcon, Purifier, Black Ops) — but no cyno was aboard | 20.9% |
| **seen** (grey) | only a Covert Ops or a T3 — a cyno fits, but everyone flies those | 6.4% |
| clean | none of the above | 64.8% |

**By default only the first two are looked for** — the pilots who actually had
a cyno in their hands. The yellow and grey ones are switched on by the
"potential cyno" filter (the funnel in the header), and it is off for a
reason: without it a scan runs **twice as fast**. Module evidence exists only
on a pilot's own losses, so the second request to the killboard — the one that
asks what he was flying in other people's killmails — cannot change a single
row on screen while that filter is off, and is simply never made.

Evidence counts only if the ship can carry that exact cyno **today**. Before
the rebalance, cynos were fitted to rookie frigates and stealth bombers
carried the non-covert one; those killmails are real, but they say nothing
about what the pilot can do now.

Priority comes from the **module type**, not from whether it was fitted or
stowed: a covert cyno in the hold is the same threat one undock later. The
industrial cyno ranks below even a bare combat hull, because it bridges
nothing but jump freighters and the Rorqual.

For each pilot you get **which cyno** was found, the ships involved with
dates, and links to the individual killmails.

## Filters

The funnel in the header, three switches:

* **Potential cyno** — the yellow and grey verdicts. Off by default; turning
  it on doubles the time a scan takes.
* **Industrial cyno** — on. Turn it off and a pilot who had nothing but an
  industrial module disappears from the list entirely.
* **Stop at the first combat cyno** — on. Once a covert or regular cyno is
  found, stop digging into that pilot. Applied only to a mass paste (more
  than 10 names): a single name takes a fraction of a second either way.

Flipping any of them restarts the check immediately.

## What it cannot tell you

It checks the pilot's **last 200 losses** — one page of the killboard. For a
typical local that is his whole history; for someone who loses a ship daily it
is the last few weeks. The honest phrasing is "in the last 200 losses", not
"ever". Depth is set by `list_pages` in the config.

The tool sees only what reached a killboard. A cyno alt who has never lost a
ship and never appeared in someone else's killmail is **invisible**. What you
are getting is "known cyno alts", not "cyno alts".

The reverse holds too: "cyno hull" ≠ guilty. Half of all active PvP pilots
have flown a Force Recon, and Ventures and haulers get lost by everyone. That
is why the levels are separate rather than collapsed into one flag.

## Install and run

Needs Python 3.11+.

```bash
pip install -r requirements.txt
```

Then `start.cmd`. It locates `pythonw.exe` and starts the app **without a
console window**; double-clicking a `.pyw` is not reliable, because Windows
often has no association registered for `.py`/`.pyw` at all.

```bash
start.cmd        # normal start, no console
python main.py   # the same, with a console -- when you want the logs
```

Or build a standalone copy that needs no Python:

```bash
pip install pyinstaller
python build.py                       # -> dist/CharacterCheck/
python build.py --dest "C:/somewhere/CC"
python build.py --onefile             # one file instead of a folder
```

A folder by default: no console, window up in 0.7 s. Settings live in
`%APPDATA%\CharacterCheck\`, shared with a source checkout. **The cache sits
next to the application itself**, in `cache\` — so a copy on a USB stick
carries its answers with it.

`--onefile` packs everything into a single exe. Handier to pass around, but it
unpacks itself into a temp folder on every launch, which makes it start three
times slower and looks suspicious to antivirus heuristics (see below).

### If your antivirus complains

It happens, and it is a false positive. Python apps are packaged with
PyInstaller, which puts the same startup code into every executable it makes —
identical across every program on earth, including the ones not written with
good intentions. Some engines react to that, not to the contents.

As of 2026-08-20 two engines out of seventy flagged it on VirusTotal — Bkav
Pro and Zillya, both reliably near the top of the false-positive rankings.
The engines that actually block things (Defender, ESET, Kaspersky,
BitDefender) are silent.

The build is **not code-signed**: the free certificate for open-source
projects requires a public repository and a CI build, which now exist, so this
may change. A self-signed certificate is deliberately not used — Windows would
still say "unknown publisher", and it would create a false impression of being
vetted.

Instead of taking any of that on faith:

* build it yourself — the whole program is here, and `python build.py`
  produces exactly the same thing;
* take a build from [Releases](https://github.com/kersidjay69-art/Character-Check/releases):
  GitHub Actions builds it from that exact commit, on a machine nobody here
  owns, and attaches a provenance attestation. Verify with
  `gh attestation verify CharacterCheck-win64.zip -R kersidjay69-art/Character-Check`.
  That is not a code signature — Windows will still say "unknown publisher" —
  but it is a checkable claim about where the file came from.

The app minimises to the tray and waits. Copy a local member list in game and
the results window comes up on its own.

A pilot's row shows: the name in the colour of its verdict, icons for the cyno
modules found, and icons for the ships he was seen in. The row expands into
the evidence — one line per "what happened + ship + module", with the date of
the most recent one and a count; a double-click opens the pilot or the
killmail on zKillboard.

Icons are fetched from CCP's image server on first run — about 76 files and
half a megabyte, once.

Pilots appear as they are checked, not all at once at the end. Anyone found
before shows up instantly — before the first network request; hover a name to
see when it was last checked.

The window remembers its position and size, including on a second or third
monitor. The pin button keeps it above the game in windowed/borderless mode.

The interface is English and Russian — the **RU/EN** button in the header
switches instantly. English by default.

**EVE in fullscreen paints over the window.** Keep the game in
windowed/borderless, or put the app on a second monitor.

The same engine without a GUI, if a console suits you better:

```bash
python -m core.console
```

A one-shot check of a file of names, without watching the clipboard:

```bash
python -m core.console --once names.txt --show-clean
```

The same filters exist there — `--potential`, `--no-industrial`,
`--all-cyno`. A flag overrides the stored setting for that run only.

## Configuration

`%APPDATA%\CharacterCheck\config.json` is created on first run. You do not
have to configure anything.

```json
{
  "contact": "",
  "min_level": "indy",
  "sound": true,
  "find_potential": false,
  "find_industrial": true,
  "stop_at_first": true,
  "list_pages": 1,
  "cache_limit_mb": 100,
  "negative_ttl_days": 7
}
```

### Who your requests are signed by

CCP asks third-party tools to identify themselves in the `User-Agent`, and
zKillboard answers 403 to an empty one outright. The header is assembled from
**two different things**:

```
CharacterCheck/0.1 (+https://github.com/kersidjay69-art/Character-Check; Leya Sokard)
                     |                                                    |
                     the software, same in every copy                      who is running this one
```

The repository link is identical in every copy — it is the address for
complaints about the tool itself. The second part is you: the name is filled
in automatically from your chat log headers, and needs no setup. The `contact`
field is only for when there are no chat logs, or you want to give something
else — Discord, an email, anything.

That split is not cosmetic. zKillboard bans by IP, so whoever's machine makes
the traffic is who answers for it. The author's own contacts live in the About
window and are never sent anywhere — `tests/test_distribution.py` enforces it.

## The guard

The app must not hit the network every time you copy something. So clipboard
text passes four stages, and the first three are free:

1. quick rejections — URLs, tabs (D-Scan, fits, inventory), Cyrillic, lines
   that are too long, bodies that are too large;
2. the EVE name mask — verified against 329 real names from chat logs,
   including Chinese ones (`冰喵`), all-digit ones (`599847624`) and ones with
   apostrophes (`Io ''Midnight'' Shadow`);
3. **your own character in the list** — if he is there, this is certainly a
   local roster. Your pilots' names are taken from the chat logs
   automatically. The app never checks you;
4. ESI, the final arbiter: a name that does not resolve to a character is
   dropped without a word.

Copy a snippet of code, a link or a paragraph of prose and the app stays
silent, without making a single request.

## Speed

Requests to zKillboard are capped at 8 per second. That is not a setting: the
price of exceeding it is an IP ban for an hour. Everything else follows from
it — scan time is essentially the number of requests divided by eight.

With the default filters a pilot costs **one** request: fifty names take seven
seconds, a full trade hub about three minutes. Turn on "potential cyno" and it
becomes two per pilot, with everything that implies.

Only pilots **who were found to have a cyno** are cached: the evidence is
monotone (die with a cyno once and it is forever), so that verdict is kept
permanently and the pilot is never fetched again. Clean ones are not stored at
all — EVE creates about thirty thousand characters a day, and this program
does not try to be a directory of every name ever seen. So pasting the same
local twice is not instant: the reds and blues appear immediately, the rest
are computed again.

The cache is capped at 100 MB (`cache_limit_mb`); on overflow the least
recently checked go first. That is a safety valve, not a mechanism: reaching
it takes about two million distinct cyno pilots.

## Boundaries

The app only reads: log files and the clipboard. It does **not** press keys in
the game, read client memory, touch the cache or intercept traffic. Copying
stays your action — that is what separates a passive tool from prohibited
automation.

For developers: `CLAUDE.md` is the project map and the list of invariants.

## Licence and liability

Apache License 2.0 — see `LICENSE`. No warranty (§7) and no liability for the
author (§8). Forks may not use the original project's name to promote their
own builds (§6).

This application is not affiliated with or endorsed by CCP hf. CCP endorses no
third-party tools as a matter of policy: "any use of third party tools is done
entirely at your own risk". EVE Online and all related material are the
property of CCP hf.
