"""Controllo di `riunione`: una trascrizione nascosta con 2 decisioni chiare, 3 azioni con responsabile e data
esplicita (giorno, mese e anno) e alcune chiacchiere che non sono decisioni.

Passa se risultato.json ha `decisioni` (lista di stringhe) con entrambe le decisioni (il lancio dell'app slitta al 24
novembre, o di due settimane; da dicembre il budget pubblicitario passa dai giornali ai social) e nessuna delle chiacchiere (macchinetta
del caffè, partita), e `azioni` con esattamente 3 oggetti {cosa, chi, entro}: Marco, bug del pagamento, 2026-11-13;
Sara, risposte per il supporto, 2026-11-18; Davide, piano delle campagne social, 2026-11-30. Le date devono essere
esattamente AAAA-MM-GG; chi e cosa si confrontano senza badare a maiuscole, accenti e parole in più.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
DECISIONI = {"lancio dell'app al 24 novembre": [r"\b24\b|\b(due|2) settimane|\b(14|quattordici) giorni",
                                                r"lanc|app|rilasc|uscit|slitt|rinvi|posticip|rimand"],
             "budget pubblicitario dai giornali ai social": [r"social", r"giornal|stampa|cartace|budget|pubblicit"]}
CHIACCHIERE = r"caff|macchinett|partita|secondo tempo"
AZIONI = [("marco", "2026-11-13", r"bug|pagament|carta"),
          ("sara", "2026-11-18", r"rispost|support"),
          ("davide", "2026-11-30", r"campagn|social|piano")]

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, dict):
    esito(False, 0, 6, ["risultato.json mancante o non è un oggetto JSON"], ex)
decisioni, azioni = dati.get("decisioni"), dati.get("azioni")
dettagli = []
punti = 0

struttura = (isinstance(decisioni, list) and all(isinstance(d, str) for d in decisioni) and isinstance(azioni, list)
             and all(isinstance(a, dict) and all(isinstance(a.get(k), str) for k in ("cosa", "chi", "entro"))
                     for a in azioni))
punti += struttura
dettagli.append(f"decisioni lista di stringhe e azioni lista di {{cosa, chi, entro}} stringhe: {struttura}"
                + ("" if struttura else f" (risultato.json: {str(dati)[:400]})"))
# Il resto si valuta anche se la struttura è sbagliata (punti parziali); i valori che non sono testo contano come vuoti.
testo = lambda v: v if isinstance(v, str) else ""
decisioni = [d for d in decisioni if isinstance(d, str)] if isinstance(decisioni, list) else []
lista_azioni = azioni if isinstance(azioni, list) else []
azioni = [a for a in lista_azioni if isinstance(a, dict)]

testi = [norm(d) for d in decisioni]
trovate = [nome for nome, regole in DECISIONI.items() if any(all(re.search(r, t) for r in regole) for t in testi)]
intruse = [d for d, t in zip(decisioni, testi) if re.search(CHIACCHIERE, t)]
dec_ok = len(trovate) == 2 and not intruse
punti += dec_ok
dettagli.append(f"le 2 decisioni e nessuna chiacchiera: {dec_ok} (trovate: {trovate}; chiacchiere: {intruse}; "
                f"scritte: {decisioni})")

for nome, data, regola in AZIONI:
    mie = [a for a in azioni if nome in norm(testo(a.get("chi")))]
    giusta = any(testo(a.get("entro")).strip() == data and re.search(regola, norm(testo(a.get("cosa")))) for a in mie)
    punti += giusta
    dettagli.append(f"azione di {nome.capitalize()} entro {data}: {giusta} ({mie})")

numero_ok = len(lista_azioni) == 3
punti += numero_ok
dettagli.append(f"esattamente 3 azioni: {numero_ok} ({len(lista_azioni)})")

esito(punti == 6, punti, 6, dettagli, ex)
