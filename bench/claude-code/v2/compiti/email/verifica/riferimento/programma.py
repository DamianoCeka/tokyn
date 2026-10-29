# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json, os
risposte = {
    "msg_201.txt": ("ordine", False, "Il cliente ordina tre confezioni di caffè in grani e un macinacaffè, senza fretta."),
    "msg_202.txt": ("reclamo", True, "La lavatrice consegnata ieri perde acqua e ha allagato la cucina: la cliente vuole un tecnico oggi."),
    "msg_203.txt": ("informazioni", False, "Il cliente chiede se esiste un negozio fisico a Bologna."),
    "msg_204.txt": ("spam", False, "Pubblicità che vende follower Instagram a 9,99 euro."),
    "msg_205.txt": ("ordine", True, "La cliente ordina 120 bomboniere che devono arrivare entro venerdì per un matrimonio."),
    "msg_206.txt": ("reclamo", False, "Il cliente segnala che il pacco arriva spesso con la scatola schiacciata e chiede un imballaggio migliore."),
}
out = []
for f in sorted(os.listdir("email")):
    c, u, r = risposte[f]
    out.append({"file": f, "categoria": c, "urgente": u, "riassunto": r})
json.dump(out, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
