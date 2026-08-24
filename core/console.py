"""Phase 1 runner: no Qt, no tray, just the working product.

    python -m core.console

Copy a local member list in game (click a name in the member list, Ctrl+A,
Ctrl+C) and the verdicts print here. Also accepts a single name.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from . import (analyze, cache, chatlog, clipboard, config, cyno_sets,
               i18n, scan)

def level_label(level: str) -> str:
    return i18n.t("level." + level)


def kind_label(kind: str) -> str:
    return i18n.t("kind." + kind)


def _fmt_finding(f, sets) -> str:
    kind = f.kind if hasattr(f, "kind") else f["kind"]
    ship = f.ship_type_id if hasattr(f, "kind") else f["ship_type_id"]
    mod = f.module_type_id if hasattr(f, "kind") else f["module_type_id"]
    when = f.km_time if hasattr(f, "kind") else f["km_time"]
    km_id = f.killmail_id if hasattr(f, "kind") else f["killmail_id"]
    # Findings arrive grouped, so one line can stand for many killmails; the
    # id is the newest of them. Silent when there is only one, so the common
    # case reads exactly as it always did.
    n = (f.get("n", 1) if isinstance(f, dict) else 1) or 1
    parts = [time.strftime("%Y-%m-%d", time.gmtime(when)),
             kind_label(kind)]
    if ship:
        parts.append(sets.hull_name(ship))
    if mod:
        parts.append(sets.module_name(mod))
    if n > 1:
        parts.append("x%d" % n)
    return "%s  https://zkillboard.com/kill/%d/" % ("  ".join(parts), km_id)


_KIND_SEVERITY = {"fitted": 0, "cargo": 1, "hull_lost": 2, "hull_flown": 3}
MODULE_LABEL = {21096: "Cyno", 28646: "Covert Cyno", 52694: "Industrial Cyno"}


def _by_severity(findings):
    """Strongest evidence first, then newest.

    Cached findings come back ordered by date, which buried the one line that
    justifies a red verdict under older, weaker ones.
    """
    def key(f):
        kind = f.kind if hasattr(f, "kind") else f["kind"]
        when = f.km_time if hasattr(f, "kind") else f["km_time"]
        return (_KIND_SEVERITY.get(kind, 9), -when)
    return sorted(findings, key=key)


def report(result, sets, show_clean: bool = False, cfg: dict | None = None) -> None:
    if not result.accepted:
        print(i18n.t("console.skipped",
                     i18n.t(result.reason_key, *result.reason_args)
                     if result.reason_key else result.reason))
        return

    min_level = (cfg or {}).get("min_level", "indy")
    flagged = result.at_least(min_level)
    counts = {}
    for p in result.pilots:
        counts[p.level] = counts.get(p.level, 0) + 1
    print(i18n.t("console.scanned", len(result.pilots), result.elapsed))
    print("    " + "   ".join(
        "%s %d" % (level_label(lv), counts[lv])
        for lv in ("cyno", "hull", "indy", "seen", "none") if counts.get(lv)))

    if result.own_seen:
        print(i18n.t("console.own_in_list", ", ".join(result.own_seen)))
    if result.unresolved:
        print(i18n.t("console.not_found", len(result.unresolved),
                     ", ".join(result.unresolved[:8])))

    if not flagged:
        print(i18n.t("console.nothing"))
    for p in flagged:
        cached = i18n.t("console.cached") if p.from_cache else ""
        mods = ", ".join(MODULE_LABEL.get(m, sets.module_name(m))
                         for m in p.modules)
        print("\n  %-12s %s%s" % (level_label(p.level), p.name, cached))
        if mods:
            print(i18n.t("console.modules", mods))
        print("           https://zkillboard.com/character/%d/" % p.character_id)
        for f in _by_severity(p.findings)[:8]:
            print("           - %s" % _fmt_finding(f, sets))

    if show_clean:
        clean = [p for p in result.pilots if not p.is_flagged]
        if clean:
            print(i18n.t("console.clean",
                         ", ".join(sorted(p.name for p in clean))))
    errs = [p for p in result.pilots if p.error]
    if errs:
        print(i18n.t("console.errors", len(errs), errs[0].error))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=i18n.t("console.desc"))
    ap.add_argument("--once", metavar="FILE",
                    help=i18n.t("console.arg_once"))
    ap.add_argument("--show-clean", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    # The three search filters, so a live run can be compared against the
    # window without editing config.json between them.
    ap.add_argument("--potential", action="store_true",
                    help=i18n.t("console.arg_potential"))
    ap.add_argument("--no-industrial", action="store_true",
                    help=i18n.t("console.arg_no_industrial"))
    ap.add_argument("--all-cyno", action="store_true",
                    help=i18n.t("console.arg_all_cyno"))
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = config.load()
    # Overrides only -- an absent flag leaves the stored setting alone, so the
    # console and the window answer the same question by default.
    if args.potential:
        cfg["find_potential"] = True
    if args.no_industrial:
        cfg["find_industrial"] = False
    if args.all_cyno:
        cfg["stop_at_first"] = False
    sets = cyno_sets.load()
    cache.connect()

    own = chatlog.own_characters(
        log_dir=cfg.get("log_dir") or None,
        max_age_h=float(cfg.get("chatlog_max_age_h", 72)))
    # This machine's traffic gets this machine's name in the User-Agent,
    # so the detection has to happen before anything is warned about.
    config.set_operator(own[0] if own else None)

    if not config.contact_is_set(cfg):
        print(i18n.t("console.no_contact", config.config_path()))
    print(i18n.t("console.sets_built", sets.built_at or "?",
                 len(sets.modules), len(sets.hulls)))
    print(i18n.t("console.own_chars", len(own),
                 (" (" + ", ".join(own[:4]) + "…)") if own else ""))
    print(i18n.t("console.cache", cache.stats()))
    print(i18n.t("console.filters", analyze.Filters.from_config(cfg)))

    if args.once:
        with open(args.once, encoding="utf-8") as fh:
            text = fh.read()
        result = scan.scan_text(text, own_names=own, cfg=cfg,
                                use_cache=not args.no_cache)
        report(result, sets, args.show_clean, cfg)
        return 0

    print(i18n.t("console.waiting"))

    def on_text(text: str) -> None:
        result = scan.scan_text(text, own_names=own, cfg=cfg,
                                use_cache=not args.no_cache)
        if result.accepted or args.verbose:
            report(result, sets, args.show_clean, cfg)

    watcher = clipboard.ClipboardWatcher(
        on_text, poll_ms=int(cfg.get("clipboard_poll_ms", 200)))
    watcher.start()
    try:
        while watcher.is_alive():
            watcher.join(0.5)
    except KeyboardInterrupt:
        print(i18n.t("console.exit"))
        watcher.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
