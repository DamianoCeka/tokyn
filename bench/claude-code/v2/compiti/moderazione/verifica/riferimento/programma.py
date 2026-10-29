# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
commenti = json.load(open("commenti.json", encoding="utf-8"))
decisioni = ["pubblica", "rifiuta", "rivedi", "pubblica", "rifiuta", "rivedi"]
motivi = ["Domanda pertinente e cortese.", "Pubblicità di un prodotto con un link: spam.",
          "Consiglio utile ma scritto con tono aggressivo.", "Aggiornamento cortese e pertinente.",
          "Contiene insulti e l'indirizzo e il telefono di una persona.", "Consiglio utile ma scritto con tono aggressivo."]
riscritture = {
    203: "Questa domanda torna spesso, quindi vi consiglio di provare anche la ricerca del forum. Le ortensie si potano "
         "a fine inverno, tagliando sopra la prima coppia di gemme gonfie, e mai in autunno.",
    206: "Non sono d'accordo con il consiglio qui sopra: le piante grasse non vanno annaffiate tutti i giorni. D'estate "
         "basta una volta ogni 10-15 giorni e d'inverno quasi mai, aspettando sempre che il terriccio sia asciutto.",
}
out = []
for c, d, m in zip(commenti, decisioni, motivi):
    r = {"id": c["id"], "decisione": d, "motivo": m}
    if d == "rivedi":
        r["riscrittura"] = riscritture[c["id"]]
    out.append(r)
json.dump(out, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
