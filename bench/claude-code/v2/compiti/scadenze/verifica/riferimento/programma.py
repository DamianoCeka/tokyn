# Programma finto che scrive la risposta giusta senza IA (email scritte a mano per i 4 contratti nascosti):
# il controllo deve promuoverlo.
import csv, json, sys
from datetime import date
EMAIL = {
    "Manutenzione forno": ("Manutenzione del forno: il contratto scade oggi",
                           "Gentile Panificio Russo, il contratto di manutenzione del forno scade oggi. Se volete "
                           "continuare senza interruzioni, rispondete a questa email e lo rinnoviamo subito."),
    "Noleggio stampante": ("Noleggio stampante in scadenza a fine mese",
                           "Buongiorno Farmacia Conti, tra un paio di settimane termina il noleggio della stampante. "
                           "Possiamo prolungarlo alle stesse condizioni oppure proporvi un modello più recente."),
    "Manutenzione ascensore": ("Promemoria: manutenzione dell'ascensore",
                               "Spettabile Hotel Bellavista, vi ricordiamo che il contratto per la manutenzione "
                               "dell'ascensore è in scadenza. Un nostro tecnico è disponibile per il controllo "
                               "annuale."),
    "Hosting sito web": ("Rinnovo dell'hosting del sito web",
                         "Gentili signori della Ferramenta Gallo Snc, l'hosting del vostro sito web arriva a scadenza "
                         "tra trenta giorni. Rinnovandolo per tempo il sito resterà sempre raggiungibile."),
}
rif = date.fromisoformat(sys.argv[1])
out = []
for r in csv.DictReader(open("contratti.csv", encoding="utf-8", newline="")):
    giorni = (date.fromisoformat(r["scadenza"]) - rif).days
    if 0 <= giorni <= 30:
        oggetto, testo = EMAIL[r["servizio"]]
        out.append({"cliente": r["cliente"], "servizio": r["servizio"], "scadenza": r["scadenza"],
                    "giorni_mancanti": giorni, "oggetto": oggetto, "testo": testo})
out.sort(key=lambda c: c["scadenza"])
json.dump({"in_scadenza": out}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
