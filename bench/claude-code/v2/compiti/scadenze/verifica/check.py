"""Controllo di `scadenze`: 8 contratti nascosti, in disordine, con data di riferimento 2026-12-15 (finestra fino al
2027-01-14, a cavallo dell'anno). Dentro: scadenza il giorno stesso (0), a 13, 22 e 30 giorni. Fuori: il giorno prima
(-1), 74 giorni prima, a 31 e a 106 giorni. Due clienti hanno due contratti, uno dentro e uno fuori.

Attesi, in ordine: Panificio Russo / Manutenzione forno (0), Farmacia Conti / Noleggio stampante (13), Hotel
Bellavista / Manutenzione ascensore (22), Ferramenta Gallo Snc / Hosting sito web (30).

Passa se risultato.json ha in_scadenza con: esattamente i 4 contratti attesi (cliente e servizio come nel file,
maiuscole e accenti liberi); la scadenza scritta come nel file e i contratti in ordine di scadenza; giorni_mancanti
giusti (4 o 4.0 vanno bene); per ognuno dei 4 un oggetto e un testo non vuoti (testo di almeno 40 caratteri) che
insieme nominano il cliente e il servizio (basta la parola distintiva come parola intera per il cliente e come inizio
di parola per il servizio: Russo/forno, Conti/stampant-, Bellavista/ascensor-, Gallo/hosting); le 4 email scritte una
per una, come chiede la richiesta ("per ognuno usa Claude per scrivere un'email"): i 4 testi restano diversi tra loro
anche togliendo nome del cliente, servizio, indirizzi email, numeri, mesi e giorni della settimana, cosa che una
frase fissa riempita dal programma non fa. Un punto per requisito; chiavi in più ammesse.
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm, numero

QUI = Path(__file__).resolve().parent
RIFERIMENTO = "2026-12-15"
# (cliente, servizio) attesi in ordine, con le parole che l'email deve contenere
ATTESI = [("Panificio Russo", "Manutenzione forno", "russo", "forno"),
          ("Farmacia Conti", "Noleggio stampante", "conti", "stampant"),
          ("Hotel Bellavista", "Manutenzione ascensore", "bellavista", "ascensor"),
          ("Ferramenta Gallo Snc", "Hosting sito web", "gallo", "hosting")]

with open(QUI / "nascosti" / "contratti.csv", encoding="utf-8", newline="") as f:
    RIGHE = list(csv.DictReader(f))
FILE = {(norm(r["cliente"]), norm(r["servizio"])): r["scadenza"] for r in RIGHE}
rif = date.fromisoformat(RIFERIMENTO)
GIORNI = {k: (date.fromisoformat(s) - rif).days for k, s in FILE.items()}
# I valori attesi si ricontrollano sui dati nascosti, così un ritocco al CSV non li lascia sbagliati.
dentro = sorted((s, k) for k, s in FILE.items() if 0 <= GIORNI[k] <= 30)
assert [k for _, k in dentro] == [(norm(c), norm(s)) for c, s, _, _ in ATTESI], dentro

ex = esegui(sys.argv[1], QUI / "nascosti", args=(RIFERIMENTO,))
dati = ex.json("risultato.json")
if not isinstance(dati, dict) or not isinstance(dati.get("in_scadenza"), list):
    esito(False, 0, 5, ["risultato.json mancante o senza la lista in_scadenza"], ex)
lista = [c if isinstance(c, dict) else {} for c in dati["in_scadenza"]]
chiavi = [(norm(c.get("cliente", "")), norm(c.get("servizio", ""))) for c in lista]
dettagli = []
punti = 0

insieme_ok = len(chiavi) == len(ATTESI) and set(chiavi) == {(norm(c), norm(s)) for c, s, _, _ in ATTESI}
punti += insieme_ok
dettagli.append(f"esattamente i 4 contratti in scadenza: {insieme_ok} ({[c.get('cliente') for c in lista]})")

scadenze = [str(c.get("scadenza", "")).strip() for c in lista]
ordine_ok = (bool(lista) and all(k in FILE and s == FILE[k] for k, s in zip(chiavi, scadenze))
             and scadenze == sorted(scadenze))
punti += ordine_ok
dettagli.append(f"scadenze come nel file e in ordine di scadenza: {ordine_ok} ({scadenze})")

giorni = [numero(c.get("giorni_mancanti")) for c in lista]
giorni_ok = bool(lista) and all(k in GIORNI and g is not None and g == GIORNI[k] for k, g in zip(chiavi, giorni))
punti += giorni_ok
dettagli.append(f"giorni_mancanti giusti: {giorni_ok} ({[c.get('giorni_mancanti') for c in lista]})")

MESI_E_GIORNI = set("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre "
                    "lunedi martedi mercoledi giovedi venerdi sabato domenica".split())


def parole(testo):
    return re.findall(r"[a-z0-9]+", norm(testo))


def scheletro(testo, cliente, servizio):
    """Il testo senza nome del cliente, servizio, indirizzi email, numeri, mesi e giorni: ciò che resta di una frase
    fissa riempita dal programma è uguale per tutti i contratti."""
    t = norm(re.sub(r"\S+@\S+", " ", testo))
    for frase in (cliente, servizio):
        t = t.replace(norm(frase), " ")
    return " ".join(p for p in re.findall(r"[a-z]+", t) if p not in MESI_E_GIORNI)


email_ok = True
scheletri = []
for cliente, servizio, parola_cliente, parola_servizio in ATTESI:
    trovati = [c for c, k in zip(lista, chiavi) if k == (norm(cliente), norm(servizio))]
    oggetto = trovati[0].get("oggetto") if trovati else None
    testo = trovati[0].get("testo") if trovati else None
    buona = isinstance(oggetto, str) and oggetto.strip() != "" and isinstance(testo, str) and len(testo.strip()) >= 40
    if buona:
        scritte = parole(oggetto + " " + testo)
        buona = parola_cliente in scritte and any(w.startswith(parola_servizio) for w in scritte)
        scheletri.append(scheletro(testo, cliente, servizio))
    email_ok = email_ok and buona
    if not buona:
        dettagli.append(f"email per {cliente} / {servizio} mancante o senza cliente e servizio")
punti += email_ok
dettagli.append(f"email con oggetto e testo che nominano cliente e servizio: {email_ok}")

diverse_ok = len(scheletri) == len(ATTESI) and len(set(scheletri)) == len(ATTESI)
punti += diverse_ok
dettagli.append(f"email scritte una per una (testi diversi anche senza nomi, servizi e date): {diverse_ok}")

esito(punti == 5, punti, 5, dettagli, ex)
