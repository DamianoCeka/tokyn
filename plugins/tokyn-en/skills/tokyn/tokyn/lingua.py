"""Lingua dei messaggi di Tokyn: italiano o inglese.

Ogni messaggio si scrive nelle due lingue nel punto in cui serve, con tr("italiano", "english").
La lingua si sceglie così: la variabile TOKYN_LANG (it o en), poi l'opzione --lang della riga di comando,
poi la lingua del plugin (il lanciatore della Skill), poi quella del sistema (LC_ALL, LC_MESSAGES, LANG,
in quest'ordine, e se mancano tutte la lingua del sistema operativo): italiano se inizia con "it", altrimenti inglese.

Questo file viene incluso anche nei programmi autonomi (tokyn build --standalone): niente import relativi.
"""

import locale
import os

LINGUE = ("it", "en")
_SCELTA = {"opzione": None, "plugin": None}  # impostate da cli.py (--lang) e dal lanciatore della Skill


def _normalizza(valore):
    """Da "it", "en" o "en_US.UTF-8" alla lingua; per gli altri valori None."""
    v = str(valore or "").strip().lower()
    if v[:2] in LINGUE and (len(v) == 2 or not v[2].isalpha()):
        return v[:2]
    return None


def imposta_opzione(valore):
    """La lingua scelta con --lang (None se manca)."""
    _SCELTA["opzione"] = _normalizza(valore)


def imposta_plugin(valore):
    """La lingua del plugin, scritta nel lanciatore della Skill."""
    _SCELTA["plugin"] = _normalizza(valore)


def lingua() -> str:
    for scelta in (os.environ.get("TOKYN_LANG"), _SCELTA["opzione"], _SCELTA["plugin"]):
        if _normalizza(scelta):
            return _normalizza(scelta)
    for nome in ("LC_ALL", "LC_MESSAGES", "LANG"):  # come POSIX: decide la prima impostata
        valore = os.environ.get(nome)
        if valore:
            return "it" if valore.strip().lower().startswith("it") else "en"
    try:  # senza variabili (es. Windows) decide la lingua del sistema, come "Italian_Italy"
        valore = locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        valore = ""
    return "it" if valore.lower().startswith("it") else "en"


def tr(it: str, en: str) -> str:
    """Il messaggio nella lingua scelta."""
    return it if lingua() == "it" else en
