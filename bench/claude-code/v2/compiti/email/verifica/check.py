"""Controllo di `email`: 6 email nascoste dalla categoria e urgenza chiare (2 ordini, 2 reclami, 1 informazioni, 1 spam;
urgenti solo un reclamo e un ordine).

esegui() toglie la cartella email/ di prova (è in dati/), così il programma vede solo le email nascoste.
Passa se risultato.json è una lista con le 6 email in ordine di nome del file (chiave "file"), almeno 5 categorie
giuste e tutte tra le quattro ammesse, "urgente" booleano e giusto in almeno 5 casi, e un riassunto breve (10-350
caratteri) per ogni email, che in almeno 5 casi nomina l'argomento dell'email. 4 punti; ok solo con 4 su 4.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
ATTESI = [  # file, categoria, urgente, parole di cui il riassunto ne deve contenere almeno una
    ("msg_201.txt", "ordine", False, ["caffe", "arabica", "macin"]),
    ("msg_202.txt", "reclamo", True, ["lavatric", "acqua", "allag", "perdit"]),
    ("msg_203.txt", "informazioni", False, ["bologna", "negozio", "punto vendita", "fisic"]),
    ("msg_204.txt", "spam", False, ["follower", "instagram", "social"]),
    ("msg_205.txt", "ordine", True, ["bombonier", "matrimonio", "nozze"]),
    ("msg_206.txt", "reclamo", False, ["imball", "scatol", "pacc", "schiacciat", "danneggiat"]),
]
CATEGORIE = {"ordine", "reclamo", "informazioni", "spam"}

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, list):
    esito(False, 0, 4, ["risultato.json mancante o non è una lista"], ex)
punti = 0


def nome(elemento):
    return norm(elemento.get("file", "")).replace("\\", "/").split("/")[-1] if isinstance(elemento, dict) else ""


nomi = [nome(e) for e in dati]
ordine = len(dati) == 6 and all(n in (f, f[:-4]) for n, (f, *_) in zip(nomi, ATTESI))
punti += ordine
dettagli.append(f"6 email in ordine di nome del file: {ordine} ({nomi})")

per_file = {}
for e in dati:
    if isinstance(e, dict):
        per_file.setdefault(nome(e).removesuffix(".txt"), e)
trovate = [per_file.get(f[:-4], {}) for f, *_ in ATTESI]

categorie = [norm(e.get("categoria", "")) for e in trovate]
giuste = sum(c == a for c, (_, a, _, _) in zip(categorie, ATTESI))
cat_ok = all(c in CATEGORIE for c in categorie) and giuste >= 5
punti += cat_ok
dettagli.append(f"categorie ammesse e giuste: {cat_ok} ({giuste} su 6: {categorie})")

urgenze = [e.get("urgente") for e in trovate]
giuste = sum(u is a for u, (_, _, a, _) in zip(urgenze, ATTESI))
urg_ok = all(isinstance(u, bool) for u in urgenze) and giuste >= 5
punti += urg_ok
dettagli.append(f"urgente booleano e giusto: {urg_ok} ({giuste} su 6: {urgenze})")

riassunti = [e.get("riassunto") for e in trovate]
brevi = all(isinstance(r, str) and 10 <= len(r.strip()) <= 350 for r in riassunti)
a_tema = sum(isinstance(r, str) and any(p in norm(r) for p in parole) for r, (*_, parole) in zip(riassunti, ATTESI))
ria_ok = brevi and a_tema >= 5
punti += ria_ok
dettagli.append(f"riassunti brevi e sull'argomento: {ria_ok} (brevi: {brevi}, sull'argomento: {a_tema} su 6)")

esito(punti == 4, punti, 4, dettagli, ex)
