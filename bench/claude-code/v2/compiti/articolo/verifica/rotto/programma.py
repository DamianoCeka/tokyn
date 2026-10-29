# Programma finto con un errore plausibile (in `citati` mette solo le persone, non le organizzazioni): il controllo
# deve bocciarlo.
import json
scheda = {
    "titolo": "Valtek investe 48 milioni a Montebrenna",
    "punti": [
        "Valtek Impianti costruirà a Montebrenna un nuovo stabilimento per produrre pompe di calore.",
        "L'investimento è di 48 milioni di euro, nell'area dismessa dell'ex vetreria di via delle Fornaci.",
        "A regime la fabbrica darà lavoro a 320 persone, con le prime 120 assunzioni all'avvio.",
        "La produzione partirà a settembre 2027, dopo la bonifica e la costruzione dei capannoni.",
        "Un accordo con l'Istituto Tecnico Volta prevede un corso serale e 40 tirocini all'anno.",
    ],
    "citati": ["Elena Marchesini", "Laura Benedetti", "Paolo Ricci"],
}
json.dump(scheda, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
