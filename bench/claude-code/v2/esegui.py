"""Esegue il benchmark: per ogni modello, compito, condizione e ripetizione una sessione nuova di Claude Code,
poi il controllo automatico del programma consegnato. Riprende da dove si era fermato: le prove concluse non si
rifanno, quelle fermate da un problema dell'infrastruttura (limiti d'uso, API sovraccarica) sì.

Uso: python esegui.py [--modelli opus,sonnet] [--compiti a,b] [--condizioni tokyn,python,agent-sdk]
                      [--ripetizioni 3] [--paralleli 4] [--lavoro CARTELLA] [--risultati CARTELLA]
                      [--commit SHA] [--solo-controlli] [--elenco]

Isolamento: ogni sessione gira fuori dal repository in una cartella dal nome neutro (/srv/progetti/<codice>), così
dal percorso Claude non capisce che è un benchmark né in quale condizione si trova, e con una /tmp tutta sua
(`unshare`), così le sessioni in parallelo non si scambiano file. Anche ogni controllo ha la sua /tmp.

Costi: oltre al costo della sessione riportato da Claude Code, tutti i processi `claude` (la sessione, le chiamate
all'IA dei programmi che Claude prova, quelle del controllo) mandano costi e token con OpenTelemetry a un
ricevitore locale. Si tengono solo quei numeri: nessun dato dell'account finisce nei risultati.

Ogni prova finisce in risultati/<modello>/<compito>/<condizione>/r<n>/: esito.json (misure e controllo),
sessione.jsonl (la sessione completa di Claude Code) e file/ (i file scritti da Claude).
"""

import argparse
import gzip
import hashlib
import json
import random
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from comune import clean_env

QUI = Path(__file__).resolve().parent
REPO = QUI.parents[2]
COMPITI = QUI / "compiti"
RISULTATI = QUI / "risultati"  # --risultati per una prova pilota tenuta a parte

CHIUSURA = "Provalo davvero prima di consegnarmelo."
CONDIZIONI = {
    "tokyn": "Usa la skill tokyn.",
    "python": "",
    "agent-sdk": "Usa il Claude Agent SDK (il pacchetto Python `claude-agent-sdk`, già installato).",
}
STRUMENTI = "Bash,Read,Write,Edit,Glob,Grep,Skill"
TEMPO_SESSIONE = 1800
TEMPO_CONTROLLO = 1200
SEGNI_INFRASTRUTTURA = ("rate limit", "rate_limit", "overloaded", "usage limit", "limit reached", "API Error",
                        "Credit balance", "hit your limit")
# Claude Code toglie le variabili OTEL_* ai comandi che lancia: questo wrapper, messo davanti a `claude` (nel PATH e al
# posto della copia di `claude` dentro l'Agent SDK), rimette la configurazione e avvia lo stesso claude di prima.
CC_BIN = Path("/srv/cc-bin")
WRAPPER = """#!/bin/sh
# Rimette la configurazione della telemetria (Claude Code toglie OTEL_* ai comandi che lancia) e avvia claude.
if [ -n "$CC_TEL_ENDPOINT" ]; then
  export CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_METRICS_EXPORTER=otlp OTEL_LOGS_EXPORTER=none \\
    OTEL_EXPORTER_OTLP_PROTOCOL=http/json OTEL_EXPORTER_OTLP_ENDPOINT="$CC_TEL_ENDPOINT" \\
    OTEL_METRIC_EXPORT_INTERVAL=5000 OTEL_RESOURCE_ATTRIBUTES="prova=$RUN_TAG,fase=$RUN_PHASE"
fi
exec "{vero}" "$@"
"""


def sdk_bundled() -> Path:
    import claude_agent_sdk
    return Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"


def prepara_wrapper():
    vero = CC_BIN / "claude"
    if not vero.exists():
        CC_BIN.mkdir(parents=True, exist_ok=True)
        vero.write_text(WRAPPER.format(vero=shutil.which("claude")))
        vero.chmod(0o755)
    sdk = sdk_bundled()
    originale = sdk.with_name("claude.vero")
    if not originale.exists():
        sdk.rename(originale)
        sdk.write_text(WRAPPER.format(vero=originale))
        sdk.chmod(0o755)


def ripristina_sdk():
    sdk = sdk_bundled()
    originale = sdk.with_name("claude.vero")
    if originale.exists():
        sdk.unlink()
        originale.rename(sdk)


# /tmp privata: tmpfs nuova in un mount namespace tutto suo
TMP_PRIVATA = ["unshare", "--mount", "--propagation", "private", "sh", "-c",
               'mount -t tmpfs tmpfs /tmp && exec "$@"', "sh"]

_stampa = threading.Lock()
IMPRONTA_PLUGIN = None


def log(msg):
    with _stampa:
        print(time.strftime("%H:%M:%S"), msg, flush=True)


class Telemetria:
    """Ricevitore OTLP/HTTP (JSON) per le metriche di Claude Code: somma costo e token per prova, fase e sessione.
    Tiene solo prova, fase, id della sessione, modello e i numeri; scarta gli altri attributi (account, email)."""

    def __init__(self):
        self.dati = {}
        self.lock = threading.Lock()
        tel = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.headers.get("Content-Encoding") == "gzip":
                    corpo = gzip.decompress(corpo)
                try:
                    tel.ricevi(json.loads(corpo))
                except ValueError:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @staticmethod
    def _attributi(lista):
        return {a["key"]: next(iter(a.get("value", {}).values()), None) for a in lista or []}

    def ricevi(self, d):
        for rm in d.get("resourceMetrics", []):
            risorsa = self._attributi(rm.get("resource", {}).get("attributes"))
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    if m.get("name") not in ("claude_code.cost.usage", "claude_code.token.usage"):
                        continue
                    for dp in (m.get("sum") or {}).get("dataPoints", []):  # temporalità delta: si somma
                        a = {**risorsa, **self._attributi(dp.get("attributes"))}
                        valore = float(dp.get("asDouble", dp.get("asInt", 0)) or 0)
                        chiave = (a.get("prova"), a.get("fase"), a.get("session.id"), a.get("model"))
                        campo = "costo" if m["name"] == "claude_code.cost.usage" else str(a.get("type"))
                        with self.lock:
                            voce = self.dati.setdefault(chiave, {})
                            voce[campo] = voce.get(campo, 0) + valore

    def env(self, prova, fase):
        porta = self.server.server_port
        locale = "127.0.0.1,localhost"
        env = clean_env()
        env.update({
            "CLAUDE_CODE_ENABLE_TELEMETRY": "1", "OTEL_METRICS_EXPORTER": "otlp", "OTEL_LOGS_EXPORTER": "none",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json", "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{porta}",
            "OTEL_METRIC_EXPORT_INTERVAL": "5000", "OTEL_RESOURCE_ATTRIBUTES": f"prova={prova},fase={fase}",
            "NO_PROXY": f"{locale},{env.get('NO_PROXY', '')}", "no_proxy": f"{locale},{env.get('no_proxy', '')}",
            # per il wrapper, che le rimette dove Claude Code le toglie
            "CC_TEL_ENDPOINT": f"http://127.0.0.1:{porta}", "RUN_TAG": prova, "RUN_PHASE": fase,
            "PATH": f"{CC_BIN}:{env.get('PATH', '')}",
        })
        return env

    def sessioni(self, prova, fase):
        """{session_id: {"costo": .., "input": .., "output": .., "cacheRead": .., "cacheCreation": .., "modelli": [..]}}"""
        out = {}
        with self.lock:
            for (p, f, sid, modello), voce in self.dati.items():
                if p == prova and f == fase:
                    s = out.setdefault(sid, {"modelli": []})
                    for k, v in voce.items():
                        s[k] = s.get(k, 0) + v
                    if modello and modello not in s["modelli"]:
                        s["modelli"].append(modello)
        return out


def richiesta(compito: str, condizione: str) -> str:
    testo = (COMPITI / compito / "richiesta.md").read_text(encoding="utf-8").strip()
    return "\n\n".join(p for p in (testo, CHIUSURA, CONDIZIONI[condizione]) if p)


def impronta(cartella: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(cartella.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            h.update(f.relative_to(cartella).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def leggi_sessione(righe):
    """Dalla sessione in stream-json: l'evento iniziale, quello finale e le chiamate agli strumenti con i risultati."""
    init, fine, chiamate, risultati = {}, {}, [], {}
    for riga in righe:
        try:
            ev = json.loads(riga)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            init = ev
        elif ev.get("type") == "result":
            fine = ev
        elif ev.get("type") in ("assistant", "user"):
            for blocco in (ev.get("message") or {}).get("content") or []:
                if not isinstance(blocco, dict):
                    continue
                if blocco.get("type") == "tool_use":
                    chiamate.append(blocco)
                elif blocco.get("type") == "tool_result":
                    contenuto = blocco.get("content")
                    if isinstance(contenuto, list):
                        contenuto = "\n".join(c.get("text", "") for c in contenuto if isinstance(c, dict))
                    risultati[blocco.get("tool_use_id")] = (bool(blocco.get("is_error")), str(contenuto or ""))
    return init, fine, chiamate, risultati


def provato_davvero(condizione, chiamate, risultati) -> bool:
    """Stima dai comandi: Claude ha eseguito il programma senza risposte finte e senza errori nell'uscita. La misura
    oggettiva è un'altra: le chiamate all'IA fatte dal programma durante la sessione (prove_del_programma)."""
    for c in chiamate:
        if c.get("name") != "Bash":
            continue
        cmd = str((c.get("input") or {}).get("command", ""))
        errore, uscita = risultati.get(c.get("id"), (True, ""))
        fallito = ("Traceback", "Error", "Errore", "errore", "ANTHROPIC_API_KEY", "api_key", "authentication",
                   "exit=1", "Exit code", "exit code")
        if errore or any(f in uscita for f in fallito) or any(f in cmd.lower() for f in ("mock", "fake", "finto")):
            continue
        if condizione == "tokyn" and " run " in f" {cmd} " and "--mock" not in cmd and ".tokyn" in cmd:
            return True
        if "programma.py" in cmd and "python" in cmd and "py_compile" not in cmd and "--help" not in cmd:
            return True
    return False


def righe_codice(testo: str) -> int:
    return sum(1 for r in testo.splitlines() if r.strip() and not r.strip().startswith("#"))


def costi(sessioni: dict, esclusa=None) -> dict:
    altre = {sid: v for sid, v in sessioni.items() if sid != esclusa}
    return {"costo_usd": round(sum(v.get("costo", 0) for v in altre.values()), 6),
            "token_output": int(sum(v.get("output", 0) for v in altre.values())),
            "chiamate": len(altre),
            "modelli": sorted({m for v in altre.values() for m in v["modelli"]})}


def controlla(tel: Telemetria, prova_id: str, compito: str, cartella: Path) -> dict:
    check = COMPITI / compito / "verifica" / "check.py"
    try:
        p = subprocess.run(TMP_PRIVATA + [sys.executable, str(check), str(cartella)], capture_output=True, text=True,
                           timeout=TEMPO_CONTROLLO, cwd=check.parent, env=tel.env(prova_id, "controllo"))
        uscita, errori = p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        uscita, errori = "", "controllo scaduto"
    time.sleep(6)  # ultime metriche dei processi appena chiusi
    esito = None
    for riga in reversed(uscita.strip().splitlines()):
        try:
            esito = json.loads(riga)
            break
        except ValueError:
            continue
    if esito is None:
        esito = {"ok": False, "punti": 0, "massimo": None, "eseguibile": True, "dettagli": [],
                 "errore": "il controllo non ha dato un esito: " + (errori or uscita)[-600:]}
    esito["costo_ia"] = costi(tel.sessioni(prova_id, "controllo"))
    return esito


def prova(tel, lavoro: Path, plugin: Path, modello: str, compito: str, condizione: str, rip: int, solo_controlli: bool):
    nome = f"{modello}/{compito}/{condizione}/r{rip}"
    dest = RISULTATI / modello / compito / condizione / f"r{rip}"
    esito_file = dest / "esito.json"
    precedente = json.loads(esito_file.read_text()) if esito_file.exists() else None
    codice = hashlib.sha256(f"tokyn-bench-v2/{nome}".encode()).hexdigest()[:10]
    cartella = lavoro / codice

    if solo_controlli:
        if not precedente or not precedente.get("completata") or not precedente.get("programma_consegnato"):
            return precedente
        precedente["controllo"] = controlla(tel, codice + "-c2", compito, cartella)
        esito_file.write_text(json.dumps(precedente, ensure_ascii=False, indent=1))
        log(f"{nome}: controllo rifatto -> {precedente['controllo'].get('ok')}")
        return precedente
    if precedente and precedente.get("completata"):
        return precedente

    if cartella.exists():
        shutil.rmtree(cartella)
    cartella.mkdir(parents=True)
    dati = COMPITI / compito / "dati"
    shutil.copytree(dati, cartella, dirs_exist_ok=True)
    visibili = {f.relative_to(dati).as_posix() for f in dati.rglob("*") if f.is_file()}

    cmd = ["claude", "-p", richiesta(compito, condizione), "--model", modello, "--output-format", "stream-json",
           "--verbose", "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
           "--tools", STRUMENTI, "--allowedTools", STRUMENTI.replace(",", " ")]
    if condizione == "tokyn":
        cmd += ["--plugin-dir", str(plugin)]
    log(f"{nome}: sessione avviata")
    inizio = time.time()
    scaduta = False
    try:
        p = subprocess.run(TMP_PRIVATA + cmd, cwd=cartella, capture_output=True, text=True, timeout=TEMPO_SESSIONE,
                           env=tel.env(codice, "sessione"))
        uscita, stderr = p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        scaduta = True
        uscita = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    secondi = round(time.time() - inizio, 1)
    time.sleep(6)  # ultime metriche dei processi appena chiusi

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sessione.jsonl").write_text(uscita, encoding="utf-8")
    init, fine, chiamate, risultati = leggi_sessione(uscita.splitlines())
    testo_fine = json.dumps(fine, ensure_ascii=False) + stderr[-2000:]
    infrastruttura = not scaduta and (not fine or (fine.get("is_error") and
                                                   any(s.lower() in testo_fine.lower() for s in SEGNI_INFRASTRUTTURA)))

    # i file scritti da Claude nella cartella del progetto (non i dati del compito)
    if (dest / "file").exists():
        shutil.rmtree(dest / "file")
    scritti = []
    for f in sorted(cartella.rglob("*")):
        rel = f.relative_to(cartella).as_posix()
        if f.is_file() and rel not in visibili and "__pycache__" not in f.parts:
            scritti.append(rel)
            if f.suffix in (".py", ".tokyn", ".json", ".csv", ".txt", ".md") and f.stat().st_size < 400_000:
                (dest / "file" / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest / "file" / rel)

    programma = cartella / "programma.py"
    testo_programma = programma.read_text(encoding="utf-8", errors="replace") if programma.exists() else ""
    sorgenti_tokyn = sorted(cartella.rglob("*.tokyn"))
    strumenti_usati = {}
    for c in chiamate:
        strumenti_usati[c.get("name")] = strumenti_usati.get(c.get("name"), 0) + 1
    usage = fine.get("usage") or {}
    tel_sessione = tel.sessioni(codice, "sessione")
    principale = init.get("session_id")
    esito = {
        "prova": nome, "cartella": codice, "modello": modello, "compito": compito, "condizione": condizione,
        "ripetizione": rip,
        "completata": not infrastruttura,
        "infrastruttura": infrastruttura,
        "scaduta": scaduta,
        "modello_usato": init.get("model"),
        "plugin": [x.get("name") for x in init.get("plugins", [])],
        "impronta_plugin": IMPRONTA_PLUGIN,
        "costo_usd": fine.get("total_cost_usd"),
        "costo_usd_telemetria": round((tel_sessione.get(principale) or {}).get("costo", 0), 6),
        "token_output": usage.get("output_tokens"),
        "token_input": usage.get("input_tokens"),
        "token_cache_scritti": usage.get("cache_creation_input_tokens"),
        "token_cache_letti": usage.get("cache_read_input_tokens"),
        "prove_del_programma": costi(tel_sessione, esclusa=principale),
        "turni": fine.get("num_turns"),
        "secondi": secondi,
        "secondi_api": round((fine.get("duration_api_ms") or 0) / 1000, 1),
        "errore_sessione": bool(fine.get("is_error")),
        "fine": fine.get("subtype"),
        "strumenti": strumenti_usati,
        "skill": [str((c.get("input") or {}).get("skill")) for c in chiamate if c.get("name") == "Skill"],
        "programma_consegnato": programma.exists(),
        "righe_programma": righe_codice(testo_programma),
        "righe_tokyn": sum(righe_codice(f.read_text(encoding="utf-8", errors="replace")) for f in sorgenti_tokyn),
        "tokyn_nel_progetto": bool(sorgenti_tokyn),
        "usa_agent_sdk": "claude_agent_sdk" in testo_programma,
        "usa_sdk_anthropic": "import anthropic" in testo_programma or "from anthropic" in testo_programma,
        "generato_da_tokyn": "Generato da Tokyn" in testo_programma or "tokyn" in testo_programma.lower(),
        "provato_da_claude": provato_davvero(condizione, chiamate, risultati),
        "letto_benchmark": "bench/claude-code" in uscita or "/home/user/tokyn" in uscita,
        "file_scritti": scritti,
        "risposta_finale": (fine.get("result") or "")[-1500:],
        "controllo": None,
    }
    if esito["completata"] and programma.exists():
        esito["controllo"] = controlla(tel, codice, compito, cartella)
    elif esito["completata"]:
        esito["controllo"] = {"ok": False, "punti": 0, "massimo": None, "eseguibile": False, "dettagli": [],
                              "errore": "programma.py non consegnato", "costo_ia": costi({})}
    esito_file.write_text(json.dumps(esito, ensure_ascii=False, indent=1))
    if infrastruttura:
        log(f"{nome}: PROBLEMA DELL'INFRASTRUTTURA, da rifare: {testo_fine[:300]}")
    else:
        log(f"{nome}: ${esito['costo_usd'] or 0:.2f} + prove ${esito['prove_del_programma']['costo_usd']:.2f}, "
            f"{esito['token_output']} token, {secondi:.0f} s, controllo {'ok' if esito['controllo']['ok'] else 'NO'}")
    return esito


def main():
    global RISULTATI
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelli", default="opus,sonnet")
    ap.add_argument("--compiti", default="")
    ap.add_argument("--condizioni", default=",".join(CONDIZIONI))
    ap.add_argument("--ripetizioni", type=int, default=3)
    ap.add_argument("--paralleli", type=int, default=4)
    ap.add_argument("--lavoro", default="/srv/progetti")
    ap.add_argument("--risultati", default=str(RISULTATI))
    ap.add_argument("--commit", default="HEAD", help="il commit da cui prendere il plugin Tokyn da misurare")
    ap.add_argument("--solo-controlli", action="store_true")
    ap.add_argument("--elenco", action="store_true")
    ap.add_argument("--ripristina", action="store_true", help="rimette la copia originale di claude nell'Agent SDK")
    a = ap.parse_args()
    if a.ripristina:
        ripristina_sdk()
        return
    RISULTATI = Path(a.risultati)

    compiti = a.compiti.split(",") if a.compiti else sorted(p.name for p in COMPITI.iterdir() if (p / "richiesta.md").exists())
    lavori = []
    for modello in a.modelli.split(","):
        gruppo = [(modello, c, cond, r) for c in compiti for cond in a.condizioni.split(",")
                  for r in range(1, a.ripetizioni + 1)]
        random.Random(f"tokyn-bench-v2-{modello}").shuffle(gruppo)  # condizioni mescolate nel tempo, ordine riproducibile
        lavori += gruppo
    if a.elenco:
        for l in lavori:
            print("/".join(map(str, l)))
        return

    lavoro = Path(a.lavoro)
    lavoro.mkdir(parents=True, exist_ok=True)
    plugin = lavoro.parent / "plugin-tokyn"  # fuori da --lavoro: le sessioni senza Tokyn non lo vedono
    # il plugin di un commit preciso (--commit, non la cartella di lavoro): si misura una versione pubblicata
    if plugin.exists():
        shutil.rmtree(plugin)
    plugin.mkdir(parents=True)
    commit = subprocess.run(["git", "rev-parse", a.commit], cwd=REPO, capture_output=True, text=True,
                            check=True).stdout.strip()
    archivio = subprocess.run(["git", "archive", "--format=tar", commit, "plugins/tokyn"], cwd=REPO,
                              capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "--strip-components=2", "-C", str(plugin)], input=archivio, check=True)
    global IMPRONTA_PLUGIN
    IMPRONTA_PLUGIN = impronta(plugin)
    RISULTATI.mkdir(parents=True, exist_ok=True)
    (RISULTATI / "versioni.json").write_text(json.dumps({
        "commit_plugin": commit,
        "plugin": IMPRONTA_PLUGIN,
        "claude_code": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip(),
        "claude_code_agent_sdk": subprocess.run([str(sdk_bundled().with_name("claude.vero") if sdk_bundled().with_name(
            "claude.vero").exists() else sdk_bundled()), "--version"], capture_output=True, text=True).stdout.strip(),
        "python": sys.version.split()[0],
    }, indent=1))

    prepara_wrapper()
    tel = Telemetria()
    log(f"{len(lavori)} prove, {a.paralleli} alla volta")
    with ThreadPoolExecutor(a.paralleli) as ex:
        esiti = list(ex.map(lambda l: prova(tel, lavoro, plugin, *l, a.solo_controlli), lavori))
    fatte = [e for e in esiti if e and e.get("completata")]
    log(f"concluse {len(fatte)} su {len(lavori)}; da rifare per l'infrastruttura: "
        f"{sum(1 for e in esiti if e and e.get('infrastruttura'))}")


if __name__ == "__main__":
    main()
