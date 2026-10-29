"""Controllo di `catalogo`: 5 prodotti nascosti con descrizioni italiane dalla traduzione univoca.

Passa se catalogo_en.csv (separatore ";") ha l'intestazione codice;nome;descrizione;prezzo, i 5 prodotti nell'ordine
del file con codice, nome e prezzo identici all'originale (spazi ai lati e virgolette CSV ignorati) e ogni descrizione
tradotta in inglese: contiene le parole inglesi attese (con varianti) e nessuna delle parole italiane dell'originale.
"""

import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
INTESTAZIONE = ["codice", "nome", "descrizione", "prezzo"]

# Per ogni prodotto: gruppi di parole inglesi (ne serve almeno una per gruppo) e parole italiane che devono sparire.
INGLESE = {
    "CF-101": [r"coffee|moka|espresso", r"alumin", r"\bsix\b|\b6\b", r"\bgas\b"],
    "LN-220": [r"sheet|linen", r"cotton", r"\bwhite\b"],
    "BK-305": [r"bicycle|bike|cycle", r"basket", r"\bbell\b"],
    "OL-412": [r"\bolive\b", r"\boil\b", r"organic", r"bottle"],
    "OR-518": [r"clock", r"\bwall\b", r"silen|quiet|noiseless|tick", r"lumin|glow|illuminat|fluoresc|phosphoresc"],
}
ITALIANO = {
    "CF-101": ["caffettiera", "alluminio", "tazze", "fornelli", "adatta"],
    "LN-220": ["lenzuola", "matrimoniali", "cotone", "colore", "bianco"],
    "BK-305": ["bicicletta", "citta", "cestino", "vimini", "campanello"],
    "OL-412": ["olio", "extravergine", "oliva", "biologico", "bottiglia", "litro"],
    "OR-518": ["orologio", "parete", "silenzioso", "lancette", "luminose"],
}
COMUNI = ["con", "di", "da", "per", "della"]


def leggi(testo):
    righe = [r for r in csv.reader(io.StringIO(testo.lstrip("﻿")), delimiter=";") if any(c.strip() for c in r)]
    return [[c.strip() for c in r] for r in righe]


def inglese(codice, descrizione):
    t = norm(descrizione)
    return (all(re.search(g, t) for g in INGLESE[codice])
            and not any(re.search(rf"\b{p}\b", t) for p in ITALIANO[codice] + COMUNI))


originale = leggi((QUI / "nascosti" / "catalogo.csv").read_text(encoding="utf-8"))[1:]
ex = esegui(sys.argv[1], QUI / "nascosti", uscite=("catalogo_en.csv",))
testo = ex.file("catalogo_en.csv")
if testo is None:
    esito(False, 0, 4, ["catalogo_en.csv mancante"], ex)
righe = leggi(testo)
dettagli = []
punti = 0

intestazione = bool(righe) and [norm(c) for c in righe[0]] == INTESTAZIONE
punti += intestazione
dettagli.append(f"intestazione codice;nome;descrizione;prezzo: {intestazione} ({righe[0] if righe else None})")
prodotti = righe[1:] if intestazione else righe

ordine = len(prodotti) == 5 and all(len(r) == 4 and r[0] == o[0] for r, o in zip(prodotti, originale))
punti += ordine
dettagli.append(f"5 prodotti con 4 colonne e codici nell'ordine del file: {ordine} ({len(prodotti)} righe)")

diversi = [o[0] for r, o in zip(prodotti, originale) if len(r) != 4 or (r[0], r[1], r[3]) != (o[0], o[1], o[3])]
invariati = ordine and not diversi
punti += invariati
dettagli.append(f"codice, nome e prezzo identici: {invariati}" + (f" (diversi: {diversi})" if diversi else ""))

tradotti = [o[0] for r, o in zip(prodotti, originale) if len(r) == 4 and inglese(o[0], r[2])]
traduzioni = ordine and len(tradotti) == 5
punti += traduzioni
dettagli.append(f"descrizioni tradotte in inglese: {len(tradotti)} su 5"
                + "".join(f" | {r[0]}: {r[2]}" for r in prodotti if len(r) == 4 and r[0] not in tradotti))

esito(punti == 4, punti, 4, dettagli, ex)
