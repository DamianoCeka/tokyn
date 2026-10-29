"""Controllo di `assistente`: conversazione scritta sullo standard input con le FAQ nascoste (prezzi e regole diversi
da quelli di prova).

Messaggi: presentazione ("mi chiamo Giulia"), tre domande la cui risposta è solo nelle FAQ nascoste (spedizione 6,90 €,
codice sconto CIAONESPOLO, reso entro 45 giorni), "Come mi chiamo?", "esci" e dopo "esci" un'ultima domanda (confezione
regalo 3,50 €) a cui il programma non deve più rispondere.
Passa se nell'output ci sono i tre fatti, il nome Giulia compare dopo l'inizio della risposta sul reso (l'ultima domanda
sulle FAQ, quindi il nome viene dalla memoria della conversazione) e il programma termina da solo con codice 0 su "esci"
senza rispondere alla domanda dopo. 5 punti, uno per requisito; ok solo con 5 su 5.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
MESSAGGI = [
    "Ciao, mi chiamo Giulia.",
    "Quanto costa la spedizione in Italia?",
    "Avete uno sconto per il primo ordine?",
    "Entro quanti giorni posso restituire un articolo?",
    "Come mi chiamo?",
    "esci",
    "Fate confezioni regalo?",
]
FATTI = {  # nome: espressione cercata nell'output
    "spedizione 6,90 euro": r"(?<![\d.,])6[.,]90?(?!\d)",
    "codice sconto CIAONESPOLO": r"ciao\s*nespolo",
    "reso entro 45 giorni": r"(?<![\d.,])45(?![\d.,]\d)|quarantacinque",
}
# 3,50 con due decimali, o 3,5 seguito da euro (non "3.5" in un nome di versione), o il biglietto della confezione
DOPO_ESCI = r"(?<![\d.,])3[.,]50(?!\d)|(?<![\d.,])3[.,]5\s*(?:€|euro)|biglietto"

ex = esegui(sys.argv[1], QUI / "nascosti", stdin="\n".join(MESSAGGI) + "\n", uscite=())
uscita = ex.stdout
dettagli = []
punti = 0

posizioni = []
for nome, espr in FATTI.items():
    m = re.search(espr, uscita, re.IGNORECASE)
    punti += m is not None
    dettagli.append(f"{nome}: {m is not None}")
    if m:
        posizioni.append(m.start())

# Il nome conta solo se compare dopo l'ultimo dei tre fatti (la risposta sul reso): lì il programma lo sa solo se ricorda.
# Con la prima posizione un programma senza memoria passerebbe citando un fatto e il nome già nella risposta al saluto.
memoria = bool(posizioni) and "giulia" in norm(uscita[max(posizioni):])
punti += memoria
dettagli.append(f"si ricorda il nome Giulia: {memoria}")

esce = not ex.scaduto and ex.codice == 0 and not re.search(DOPO_ESCI, uscita, re.IGNORECASE)
punti += esce
dettagli.append(f"termina su esci (codice {ex.codice}) senza rispondere dopo: {esce}")
dettagli.append("output (ultimi 1500 caratteri): " + uscita[-1500:])

esito(punti == 5, punti, 5, dettagli, ex)
