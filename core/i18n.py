"""Interface text in English and Russian.

    i18n.set_language("ru")
    i18n.t("btn.rescan")            -> "Проверить буфер"
    i18n.t("status.unresolved", 3)  -> "не найдено в ESI: 3"

English is the default: the project is published on GitHub and most of the
people who find it there do not read Russian. The choice lives in
`config.lang` next to `theme`.

Qt-free on purpose, so the console speaks the same language as the window and
neither owns the strings.

What is deliberately NOT here, and must never be added:

* "Character Check" -- the product name.
* Module and ship names ("Covert Cyno", "Falcon"). They are what the game
  calls them, in every client language.
* Level and evidence KEYS (`cyno`, `fitted`, ...). Those are protocol: they
  sit in the SQLite cache and in config.json. Only their labels are here.
* Log messages and zKillboard URLs.
"""
from __future__ import annotations

import threading

DEFAULT = "en"
LANGUAGES = ("en", "ru")

_lock = threading.Lock()
_lang = DEFAULT

EN = {
    # --- verdict levels ------------------------------------------------
    "level.cyno": "CYNO",
    "level.hull": "cyno hull",
    "level.indy": "industrial",
    # A cyno-capable hull and nothing else. Not a warning: everybody flies
    # a Covert Ops or a T3.
    "level.seen": "seen",
    "level.none": "clean",

    # --- kinds of evidence ---------------------------------------------
    "kind.fitted": "cyno in a high slot",
    "kind.cargo": "cyno in the hold",
    "kind.hull_lost": "died in a cyno hull",
    "kind.hull_flown": "flew a cyno hull",

    # The same four for the window, which puts them in the name column next
    # to a date. The long forms need 164 px there and the names themselves
    # need 125, so the sentence was setting the column width; these need 124.
    # The console keeps the long ones -- a terminal has room.
    "short.fitted": "fitted",
    "short.cargo": "in hold",
    "short.hull_lost": "lost",
    "short.hull_flown": "flew",

    # --- results window ------------------------------------------------
    "status.idle": "copy the local member list in game -- "
                   "click a name, Ctrl+A, Ctrl+C",
    "status.resolving": "looking up %d names...",
    "status.scanning": "checking %d pilots...",
    "status.progress": "checked %d of %d",
    "status.rejected": "skipped: %s",
    "status.own": "yours: ",
    "status.unresolved": "not found in ESI: %d",
    "btn.rescan": "Check clipboard",
    "btn.expand": "Expand",
    "btn.collapse": "Collapse",
    "btn.filters": "Search filters",
    "filter.potential": "Potential cyno -- hulls with no module",
    "filter.industrial": "Industrial cyno",
    "filter.stop_first": "Stop at the first combat cyno",
    "filter.tip": "What to look for. With \"potential cyno\" off a scan asks\n"
                  "zKillboard once per pilot instead of twice, because module\n"
                  "evidence only ever comes from the pilot's own losses.",
    "btn.on_top": "Always on top",
    "btn.on_top_tip": "Keep this window above the others. EVE in fullscreen "
                      "paints over everything,\nso this only helps in "
                      "windowed or borderless mode.",
    "action.copy_names": "Copy names",
    "hint.bottom": "double-click opens the pilot or the killmail on "
                   "zKillboard   ·   Ctrl+C copies the selected names",
    "tip.pilot": "%s   ·   double-click to open on zKillboard",
    "tip.checked": "%s   ·   from the cache, checked %s   ·   "
                   "double-click to open on zKillboard",
    "tip.killmail": "Double-click to open the killmail",

    # --- tray ----------------------------------------------------------
    "tray.show": "Show results",
    "tray.rescan": "Check the clipboard",
    "tray.about": "About",
    "tray.settings": "Open the settings file",
    "tray.quit": "Quit",
    "tray.no_contact": "No chat logs found -- put yourself in «contact» so\n"
                       "requests are signed with your name instead of nobody's.\n",

    # --- about ---------------------------------------------------------
    "about.title": "About",
    "about.version": "version %s   ·   %s",
    "about.contact": "Contact the author",
    "about.close": "Close",
    "about.copied": "About -- copied: %s",

    # --- console -------------------------------------------------------
    "console.desc": "Character Check (console)",
    "console.arg_once": "check the text in a file and exit (for tests)",
    "console.skipped": "[skipped] %s",
    "console.scanned": "\n=== scanned %d pilots in %.1f s ===",
    "console.own_in_list": "own characters in the list: %s",
    "console.not_found": "not found in ESI (%d): %s",
    "console.nothing": "No cyno found.",
    "console.cached": " [cached]",
    "console.modules": "           modules: %s",
    "console.clean": "\nclean: %s",
    "console.errors": "\nerrors on %d pilots (first: %s)",
    "console.sets_built": "Cyno sets built %s: %d modules, %d hulls",
    "console.own_chars": "Own characters from the chat logs: %d%s",
    "console.cache": "Cache: %s",
    "console.filters": "Looking for: %s",
    "console.arg_potential": "also flag cyno-capable hulls with no module",
    "console.arg_no_industrial": "ignore the industrial cyno module",
    "console.arg_all_cyno": "read every page, do not stop at the first combat cyno",
    "console.no_contact": "WARNING: no chat logs found and «contact» is empty --\n"
                          "         requests will go out unsigned. Put yourself in %s\n",
    "console.waiting": "\nWatching the clipboard. Copy a local member list "
                       "(Ctrl+A, Ctrl+C in\nthe member list) or a single name. "
                       "Ctrl+C to quit.\n",
    "console.exit": "\nexit",
    "main.no_tray": "No system tray available. Use python -m core.console",

    # --- why a paste was refused ---------------------------------------
    "reason.empty": "empty",
    "reason.too_long": "too long (%d chars)",
    "reason.tabs": "contains tabs (D-Scan or inventory, not names)",
    "reason.url": "contains a URL",
    "reason.empty_after_normalise": "empty after normalisation",
    "reason.too_many_lines": "too many lines (%d)",
    "reason.only_own": "only your own characters",
    "reason.mask_ratio": "only %d/%d lines look like names",
    "reason.no_name_resolved": "no name resolved to a character",
}

RU = {
    "level.cyno": "ЦИНО",
    "level.hull": "цино-хулл",
    "level.indy": "индастриал",
    "level.seen": "замечен",
    "level.none": "чисто",

    "kind.fitted": "цино в хай-слоте",
    "kind.cargo": "цино в трюме",
    "kind.hull_lost": "погиб на цино-хулле",
    "kind.hull_flown": "летал на цино-хулле",

    "short.fitted": "в фите",
    "short.cargo": "в трюме",
    "short.hull_lost": "потерян",
    "short.hull_flown": "летал",

    "status.idle": "скопируйте список локала в игре — "
                   "клик по нику, Ctrl+A, Ctrl+C",
    "status.resolving": "ищу %d имён…",
    "status.scanning": "проверяю %d пилотов…",
    "status.progress": "проверено %d из %d",
    "status.rejected": "пропущено: %s",
    "status.own": "свои: ",
    "status.unresolved": "не найдено в ESI: %d",
    "btn.rescan": "Проверить буфер",
    "btn.expand": "Развернуть",
    "btn.collapse": "Свернуть",
    "btn.filters": "Фильтры поиска",
    "filter.potential": "Потенциальное цино — хулл без модуля",
    "filter.industrial": "Индастриал цино",
    "filter.stop_first": "Останавливаться на первом боевом цино",
    "filter.tip": "Что искать. Пока «потенциальное цино» выключено, скан\n"
                  "делает один запрос на пилота вместо двух: улики на модуль\n"
                  "бывают только на собственных лоссах пилота.",
    "btn.on_top": "Поверх окон",
    "btn.on_top_tip": "Держать окно поверх других. EVE в полноэкранном режиме "
                      "перекрывает всё,\nтак что это помогает только в "
                      "windowed/borderless.",
    "action.copy_names": "Копировать ники",
    "hint.bottom": "двойной клик открывает пилота или килмейл на "
                   "zKillboard   ·   Ctrl+C копирует выделенные ники",
    "tip.pilot": "%s   ·   двойной клик — открыть на zKillboard",
    "tip.checked": "%s   ·   из кэша, проверен %s   ·   "
                   "двойной клик — открыть на zKillboard",
    "tip.killmail": "Двойной клик — открыть килмейл",

    "tray.show": "Показать результаты",
    "tray.rescan": "Проверить буфер обмена",
    "tray.about": "О программе",
    "tray.settings": "Открыть файл настроек",
    "tray.quit": "Выход",
    "tray.no_contact": "Чатлоги не найдены — впишите себя в «contact», чтобы\n"
                       "запросы были подписаны вашим именем, а не анонимными.\n",

    "about.title": "О программе",
    "about.version": "версия %s   ·   %s",
    "about.contact": "Связаться с автором",
    "about.close": "Закрыть",
    "about.copied": "О программе — скопировано: %s",

    "console.desc": "Character Check (консоль)",
    "console.arg_once": "проверить текст из файла и выйти (для тестов)",
    "console.skipped": "[пропуск] %s",
    "console.scanned": "\n=== просканировано %d пилотов за %.1f с ===",
    "console.own_in_list": "свои персонажи в списке: %s",
    "console.not_found": "не найдены в ESI (%d): %s",
    "console.nothing": "Цино не найдено.",
    "console.cached": " [из кэша]",
    "console.modules": "           модули: %s",
    "console.clean": "\nчисто: %s",
    "console.errors": "\nошибки у %d пилотов (первая: %s)",
    "console.sets_built": "Наборы цино собраны %s: %d модулей, %d хуллов",
    "console.own_chars": "Свои персонажи из чатлогов: %d%s",
    "console.cache": "Кэш: %s",
    "console.filters": "Ищем: %s",
    "console.arg_potential": "помечать и цино-способные хуллы без модуля",
    "console.arg_no_industrial": "не считать индустриальный цино-модуль",
    "console.arg_all_cyno": "читать все страницы, не останавливаться на первом боевом цино",
    "console.no_contact": "ВНИМАНИЕ: чатлоги не найдены, и «contact» не заполнен — запросы\n"
                          "          уйдут неподписанными. Впишите себя в %s\n",
    "console.waiting": "\nЖду буфер обмена. Скопируйте список локала (Ctrl+A, "
                       "Ctrl+C в\nсписке участников) или один ник. "
                       "Ctrl+C для выхода.\n",
    "console.exit": "\nвыход",
    "main.no_tray": "Системный трей недоступен. Используйте python -m core.console",

    "reason.empty": "пусто",
    "reason.too_long": "слишком длинно (%d символов)",
    "reason.tabs": "есть табуляции (это D-Scan или инвентарь, не имена)",
    "reason.url": "есть ссылка",
    "reason.empty_after_normalise": "после очистки ничего не осталось",
    "reason.too_many_lines": "слишком много строк (%d)",
    "reason.only_own": "только ваши собственные персонажи",
    "reason.mask_ratio": "на имена похожи только %d строк из %d",
    "reason.no_name_resolved": "ни одно имя не нашлось в ESI",
}

TABLES = {"en": EN, "ru": RU}


def set_language(lang: str | None) -> str:
    """Switch the active language. Anything unknown falls back to English."""
    global _lang
    with _lock:
        _lang = lang if lang in TABLES else DEFAULT
        return _lang


def language() -> str:
    return _lang


def t(key: str, *args) -> str:
    """Look a key up in the active language, then in English, then give up.

    Never raises: a missing key returns the key itself, which shows up in the
    interface as an obvious `btn.rescan` rather than an empty button. A bad
    format string does the same instead of taking the window down.
    """
    text = TABLES.get(_lang, EN).get(key) or EN.get(key)
    if text is None:
        return key
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return text


def en(key: str, *args) -> str:
    """The English text regardless of the active language -- for logs."""
    text = EN.get(key)
    if text is None:
        return key
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return text
