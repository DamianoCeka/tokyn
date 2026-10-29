"""Funzioni comuni del benchmark: ambiente pulito per Claude Code e controlli dei programmi consegnati.

Ogni compito ha verifica/check.py, che si lancia con `python check.py <cartella con programma.py>`: copia la cartella
in un posto temporaneo, ci mette i dati nascosti, esegue programma.py e stampa una riga JSON con l'esito.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Variabili che legano un processo alla sessione di Claude Code che lo ha lanciato o ne cambiano il comportamento
# (sforzo, compattazione, strumenti dell'ambiente cloud). Senza, `claude -p` parte come per un utente normale.
_DROP = {
    "CLAUDECODE", "CLAUDE_EFFORT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "CLAUDE_CODE_SYNC_PLUGINS", "CLAUDE_CODE_SYNC_SKILLS", "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_REMOTE_SEND_KEEPALIVES", "CLAUDE_CODE_TEE_SDK_STDOUT",
    "CLAUDE_CODE_DIAGNOSTICS_FILE", "CLAUDE_CODE_DEBUG", "CLAUDE_ADDITIONAL_DIRECTORIES",
    "CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD", "CLAUDE_AFTER_LAST_COMPACT", "CLAUDE_AUTO_BACKGROUND_TASKS",
    "CLAUDE_CODE_BG_TASKS_REPORT_RUNNING", "CLAUDE_PID", "CLAUDE_CODE_HOLD_UNANSWERED_PARKED_PERMISSION",
    "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_SYNC_SESSION_REFS", "CLAUDE_CODE_WORKER_EPOCH",
    "CLAUDE_CODE_CCR_EVENT_FLUSH_POLICY", "CLAUDE_CODE_ELEGANT_MEADOW", "CLAUDE_CODE_JIT_POLICY_AFTER_STARTUP",
    "CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_DISABLE_TERMINAL_TITLE", "CLAUDE_CODE_REMOTE", "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE",
    "CLAUDE_CODE_HOSTED_DESKTOP", "CLAUDE_CODE_DISABLE_BUILTIN_ANTMCP", "CLAUDE_CODE_REMOTE_SDK_URL",
    "CLAUDE_CODE_REMOTE_HERMETIC_MODE", "TOKYN_BACKEND", "TOKYN_MOCK", "ANTHROPIC_API_KEY",
}
_DROP_PREFIX = ("CLAUDE_CODE_ARTIFACT", "CLAUDE_CODE_POST_FOR_SESSION")

# Segni che il programma si è fermato perché manca una chiave API.
_KEY_ERRORS = ("ANTHROPIC_API_KEY", "api_key", "AuthenticationError", "authentication_error", "x-api-key",
               "Could not resolve authentication", "auth_token")


def clean_env(chiave=False) -> dict:
    """L'ambiente di chi usa Claude Code con l'abbonamento: login fatto, nessuna chiave API (a meno di chiave=True)."""
    drop = _DROP - {"ANTHROPIC_API_KEY"} if chiave else _DROP
    env = {k: v for k, v in os.environ.items() if k not in drop and not k.startswith(_DROP_PREFIX)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class Esecuzione:
    def __init__(self, cartella, codice, stdout, stderr, scaduto=False):
        self.cartella, self.codice, self.stdout, self.stderr, self.scaduto = cartella, codice, stdout, stderr, scaduto

    def file(self, nome):
        """Il contenuto di un file scritto dal programma, o None se non esiste."""
        p = self.cartella / nome
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None

    def json(self, nome):
        """Un file JSON scritto dal programma, o None se manca o non è JSON valido."""
        testo = self.file(nome)
        if testo is None:
            return None
        try:
            return json.loads(testo)
        except ValueError:
            return None

    def serve_chiave(self) -> bool:
        uscita = self.stdout + self.stderr
        return self.codice != 0 and any(s in uscita for s in _KEY_ERRORS)


def esegui(cartella_programma, nascosti, args=(), stdin=None, uscite=("risultato.json",), timeout=900) -> Esecuzione:
    """Copia la cartella del programma in un posto temporaneo, ci copia sopra i dati nascosti, toglie i file di
    uscita lasciati dalle prove precedenti ed esegue `python programma.py`."""
    lavoro = Path(tempfile.mkdtemp(prefix="verifica-"))
    shutil.copytree(cartella_programma, lavoro, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".venv", "venv", "node_modules"))
    nascosti = Path(nascosti)
    # via i dati visibili del compito (compiti/<id>/dati), così il programma vede solo quelli nascosti
    visibili = nascosti.parent.parent / "dati"
    if visibili.is_dir():
        for v in visibili.iterdir():
            dest = lavoro / v.name
            if dest.is_dir():
                shutil.rmtree(dest)
            elif dest.exists():
                dest.unlink()
    for f in nascosti.rglob("*"):
        if f.is_file():
            dest = lavoro / f.relative_to(nascosti)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dest)
    for nome in uscite:
        (lavoro / nome).unlink(missing_ok=True)
    try:
        p = subprocess.run([sys.executable, "programma.py", *args], cwd=lavoro, input=stdin, capture_output=True,
                           text=True, timeout=timeout, env=clean_env(chiave=os.environ.get("BENCH_CHIAVE") == "1"))
        return Esecuzione(lavoro, p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        dec = lambda b: b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
        return Esecuzione(lavoro, -1, dec(e.stdout), dec(e.stderr), scaduto=True)


def esito(ok, punti, massimo, dettagli, esecuzione=None):
    """Stampa l'esito come una riga JSON (l'ultima riga dell'output di check.py) ed esce."""
    out = {"ok": bool(ok), "punti": punti, "massimo": massimo, "dettagli": dettagli, "eseguibile": True, "errore": None}
    if esecuzione is not None:
        if esecuzione.scaduto:
            out.update(ok=False, errore="tempo scaduto")
        elif esecuzione.serve_chiave():
            out.update(ok=False, eseguibile=False, errore="serve ANTHROPIC_API_KEY")
        elif esecuzione.codice != 0 and not ok:
            out["errore"] = f"uscito con codice {esecuzione.codice}: " + (esecuzione.stderr or esecuzione.stdout)[-600:]
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)


def norm(testo) -> str:
    """Testo confrontabile: minuscolo, senza accenti né spazi in più."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(testo)).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def numero(valore):
    """Un numero da un valore JSON (anche "4,2" o "4.2"), o None."""
    if isinstance(valore, bool):
        return None
    if isinstance(valore, (int, float)):
        return float(valore)
    try:
        return float(str(valore).replace("€", "").replace(",", ".").strip())
    except ValueError:
        return None
