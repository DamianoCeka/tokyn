"""Genera in modo deterministico i log di `log`: quello nascosto (verifica/nascosti/access.log) e quello di esempio
(dati/access.log). Si lancia con `python genera.py` da verifica/; rigenera sempre gli stessi file.

I primi quattro IP hanno un numero fisso di richieste tutto diverso, così la classifica non ha pareggi; tutti gli
altri ne hanno meno del quarto.
"""

import random
from pathlib import Path

QUI = Path(__file__).resolve().parent

PAGINE = ["/", "/prodotti", "/prodotti/scarpe-trekking", "/prodotti/zaino-30l", "/prodotti/giacca-vento",
          "/offerte", "/chi-siamo", "/contatti", "/carrello", "/blog/come-scegliere-uno-zaino"]
STATICI = ["/static/css/main.css", "/static/js/app.js", "/img/logo.png", "/img/banner-autunno.jpg", "/favicon.ico"]
SBAGLIATE = ["/wp-login.php", "/prodotti/sacco-a-pelo-vecchio", "/.env", "/old/index.html", "/blog/pagina-rimossa"]
# peso di ogni ora del giorno (0 = nessuna richiesta in quell'ora)
PESI = [3, 2, 0, 0, 0, 0, 1, 3, 6, 9, 10, 9, 7, 6, 8, 9, 9, 8, 7, 6, 6, 5, 4, 3]


def richiesta(rnd):
    """Una riga di richiesta, il codice di stato e i byte."""
    x = rnd.random()
    if x < 0.40:
        p = rnd.choice(PAGINE)
        if rnd.random() < 0.04:
            return f"GET /api/ricerca?q={rnd.choice(['zaino', 'scarpe', 'giacca'])} HTTP/1.1", 500, 312
        return f"GET {p} HTTP/1.1", 200, rnd.randint(4200, 38000)
    if x < 0.68:
        s = rnd.choice(STATICI)
        if rnd.random() < 0.45:
            return f"GET {s} HTTP/1.1", 304, None
        return f"GET {s} HTTP/1.1", 200, rnd.randint(800, 160000)
    if x < 0.76:
        return f"GET /api/ricerca?q={rnd.choice(['zaino', 'scarpe', 'giacca', 'borraccia'])} HTTP/1.1", 200, rnd.randint(900, 6000)
    if x < 0.82:
        return "POST /carrello/aggiungi HTTP/1.1", 302, 0
    if x < 0.87:
        return "POST /login HTTP/1.1", rnd.choice([302, 302, 401]), rnd.choice([0, 512])
    if x < 0.95:
        return f"GET {rnd.choice(SBAGLIATE)} HTTP/1.1", 404, 196
    if x < 0.97:
        return "GET /admin HTTP/1.1", 403, 199
    if x < 0.99:
        return "GET /negozio HTTP/1.1", 301, 0
    return "HEAD / HTTP/1.1", 200, None


def genera(seme, data, fuso, primi, altri, ipv6, totale, uscita):
    rnd = random.Random(seme)
    ip = []
    for indirizzo, n in primi:
        ip += [indirizzo] * n
    soglia = min(n for _, n in primi)
    resto = totale - len(ip) - 1
    conteggi = {}
    while resto > 0:
        a = rnd.choice(altri + [ipv6])
        if conteggi.get(a, 0) < soglia - 4:
            conteggi[a] = conteggi.get(a, 0) + 1
            ip.append(a)
            resto -= 1
    rnd.shuffle(ip)
    righe = []
    for indirizzo in ip:
        ora = rnd.choices(range(24), weights=PESI)[0]
        secondi = ora * 3600 + rnd.randint(0, 3599)
        req, stato, byte = richiesta(rnd)
        utente = "mrossi" if req.startswith("POST /login") and stato == 302 and rnd.random() < 0.5 else "-"
        righe.append((secondi, indirizzo, utente, req, stato, byte))
    # una richiesta malformata (timeout senza riga di richiesta), come capita nei log veri
    righe.append((10 * 3600 + 1234, rnd.choice(altri), "-", "-", 408, None))
    righe.sort(key=lambda r: r[0])
    with open(uscita, "w", encoding="utf-8") as f:
        for secondi, indirizzo, utente, req, stato, byte in righe:
            h, m, s = secondi // 3600, secondi // 60 % 60, secondi % 60
            f.write(f'{indirizzo} - {utente} [{data}:{h:02d}:{m:02d}:{s:02d} {fuso}] "{req}" {stato} '
                    f'{"-" if byte is None else byte}\n')


if __name__ == "__main__":
    genera(
        seme=2026_03_17, data="17/Mar/2026", fuso="+0100", totale=240,
        primi=[("198.51.100.42", 34), ("203.0.113.88", 27), ("192.0.2.15", 21), ("198.51.100.7", 16)],
        altri=[f"203.0.113.{n}" for n in (3, 19, 27, 45, 61, 102, 133, 150, 177, 201, 230)]
              + [f"192.0.2.{n}" for n in (8, 33, 54, 76, 99, 120, 168, 212, 249)]
              + [f"198.51.100.{n}" for n in (11, 64, 89, 140, 222)],
        ipv6="2001:db8:4f2a::17", uscita=QUI / "nascosti" / "access.log",
    )
    genera(
        seme=2026_10_08, data="08/Oct/2026", fuso="+0200", totale=130,
        primi=[("203.0.113.5", 19), ("192.0.2.200", 14), ("198.51.100.31", 11), ("203.0.113.140", 9)],
        altri=[f"192.0.2.{n}" for n in (4, 17, 39, 66, 91, 130, 155, 181, 240)]
              + [f"198.51.100.{n}" for n in (2, 23, 58, 77, 109, 190, 233)] + [f"203.0.113.{n}" for n in (12, 71, 96, 210)],
        ipv6="2001:db8:85a3::8a2e", uscita=QUI.parent / "dati" / "access.log",
    )
