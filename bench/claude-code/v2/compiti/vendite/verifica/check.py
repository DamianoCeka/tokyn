"""Controllo di `vendite`: 31 ordini nascosti di 8 clienti in 4 paesi. Un nome di cliente contiene una virgola (tra
virgolette nel CSV). Il paese col fatturato più alto (Germania) non è quello del miglior cliente (francese), e i
clienti con più ordini non sono i migliori. Sommati con i float nell'ordine del file, tre fatturati escono con
residui come 21476.620000000003.

Fatturati attesi: Germania 27143.37, Italia 21476.62, Francia 20713.08, Spagna 7420.85. Migliori clienti: Dupont
Équipements SARL, Müller Werkzeuge GmbH, Ferretti Arredamenti Srl.

Passa se risultato.json ha: fatturato_per_paese con esattamente i 4 paesi (maiuscole e accenti liberi, nessun paese
in più o ripetuto) e importi giusti al centesimo, scritti come numeri JSON finiti (4 o 4.0 vanno bene); tutti i
fatturati arrotondati al centesimo (niente residui dei float); migliori_clienti con i 3 nomi giusti nell'ordine giusto;
riassunto di testo (da 40 a 3000 caratteri) che nomina il paese col fatturato più alto ("Germania" o
"tedesco/a/i/he"). Un punto per requisito; chiavi in più ammesse. Limite noto: il controllo non distingue un
riassunto scritto da Claude da una frase fissa scritta dal programma.
"""

import csv
import math
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
ATTESI = {"Germania": Decimal("27143.37"), "Italia": Decimal("21476.62"), "Francia": Decimal("20713.08"),
          "Spagna": Decimal("7420.85")}
MIGLIORI = ["Dupont Équipements SARL", "Müller Werkzeuge GmbH", "Ferretti Arredamenti Srl"]

# I valori attesi si ricontrollano sui dati nascosti, così un ritocco ai CSV non li lascia sbagliati.
with open(QUI / "nascosti" / "clienti.csv", encoding="utf-8", newline="") as f:
    clienti = {r["id"]: r for r in csv.DictReader(f)}
with open(QUI / "nascosti" / "ordini.csv", encoding="utf-8", newline="") as f:
    ordini = list(csv.DictReader(f))
per_paese, per_cliente = {}, {}
for o in ordini:
    c = clienti[o["cliente_id"]]
    per_paese[c["paese"]] = per_paese.get(c["paese"], Decimal(0)) + Decimal(o["importo"])
    per_cliente[c["nome"]] = per_cliente.get(c["nome"], Decimal(0)) + Decimal(o["importo"])
assert per_paese == ATTESI, per_paese
assert sorted(per_cliente, key=per_cliente.get, reverse=True)[:3] == MIGLIORI

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, dict):
    esito(False, 0, 4, ["risultato.json mancante o non è un oggetto JSON"], ex)
dettagli = []
punti = 0


def importo(valore):
    """Un importo scritto come numero JSON finito (non come testo, NaN o Infinity), o None."""
    if isinstance(valore, bool) or not isinstance(valore, (int, float)):
        return None
    if isinstance(valore, float) and not math.isfinite(valore):
        return None
    return Decimal(str(valore))


fatturato = dati.get("fatturato_per_paese")
fatturato = fatturato if isinstance(fatturato, dict) else {}
scritti = {norm(k): v for k, v in fatturato.items()}
paesi_ok = len(fatturato) == len(ATTESI) and set(scritti) == {norm(p) for p in ATTESI}
importi_ok = paesi_ok and all(importo(scritti[norm(p)]) is not None
                              and abs(importo(scritti[norm(p)]) - v) < Decimal("0.005") for p, v in ATTESI.items())
punti += importi_ok
dettagli.append(f"fatturato_per_paese con i 4 paesi e gli importi giusti: {importi_ok} ({dati.get('fatturato_per_paese')!r})")

arrotondati = bool(scritti) and all(importo(v) is not None and round(v, 2) == v for v in scritti.values())
punti += arrotondati
dettagli.append(f"fatturati arrotondati al centesimo: {arrotondati}")

migliori = dati.get("migliori_clienti")
migliori_ok = (isinstance(migliori, list) and len(migliori) == 3 and all(isinstance(m, str) for m in migliori)
               and [norm(m) for m in migliori] == [norm(m) for m in MIGLIORI])
punti += migliori_ok
dettagli.append(f"migliori_clienti giusti e in ordine: {migliori_ok} ({migliori!r})")

riassunto = dati.get("riassunto")
testo = norm(riassunto) if isinstance(riassunto, str) else ""
riassunto_ok = 40 <= len(testo) <= 3000 and ("germania" in testo or "tedesc" in testo)
punti += riassunto_ok
dettagli.append(f"riassunto di testo che nomina la Germania: {riassunto_ok} ({len(testo)} caratteri)")

esito(punti == 4, punti, 4, dettagli, ex)
