# Programma finto con un errore plausibile (traduce bene ma riscrive il prezzo come numero: 29.9 invece di 29,90):
# il controllo deve bocciarlo.
import csv
TRADUZIONI = {
    "CF-101": "Aluminium coffee maker for six cups, suitable for gas stoves",
    "LN-220": "Double bed sheet set in pure cotton, white",
    "BK-305": "City bicycle with wicker basket and bell",
    "OL-412": "Organic extra virgin olive oil, one-litre bottle",
    "OR-518": "Silent wall clock with luminous hands",
}
with open("catalogo.csv", encoding="utf-8", newline="") as f:
    righe = list(csv.reader(f, delimiter=";"))
with open("catalogo_en.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(righe[0])
    for codice, nome, descrizione, prezzo in righe[1:]:
        w.writerow([codice, nome, TRADUZIONI[codice], float(prezzo.replace(",", "."))])
