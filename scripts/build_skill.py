"""Prepara la Skill di Tokyn: i plugin per Claude Code e gli zip da caricare in Claude.

Ogni plugin (plugins/tokyn in italiano, plugins/tokyn-en in inglese) deve contenere tutto quello che serve,
perché Claude Code installa solo la cartella del plugin: questo script ci copia il compilatore e la copia di lark
in vendor/ (lark 1.3.1 da PyPI, non modificata, licenza MIT in vendor/lark/LICENSE), che il lanciatore usa solo
se lark non è installato. Per aggiornarla si copiano in vendor/lark i file .py e .lark di un lark installato e la sua licenza.

Uso: python scripts/build_skill.py            aggiorna i plugin e crea dist/tokyn-skill.zip e dist/tokyn-skill-en.zip
     python scripts/build_skill.py --check    controlla che i plugin siano aggiornati (per la CI)
     python scripts/build_skill.py percorso.zip [--en]    crea solo uno zip
"""

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
PLUGINS = {"it": ROOT / "plugins" / "tokyn", "en": ROOT / "plugins" / "tokyn-en"}
ZIPS = {"it": ROOT / "dist" / "tokyn-skill.zip", "en": ROOT / "dist" / "tokyn-skill-en.zip"}
LAUNCHER = PLUGINS["it"] / "skills" / "tokyn" / "tokyn_cli.py"  # l'originale sta nel plugin italiano
LAUNCHER_LANG = 'LINGUA = "it"'  # la riga del lanciatore con la lingua dei messaggi del plugin


def skill_dir(lang: str) -> Path:
    return PLUGINS[lang] / "skills" / "tokyn"


def copies(lang: str) -> dict:
    """File copiati nella cartella della Skill: percorso nella Skill -> sorgente."""
    files = {f"tokyn/{f.name}": f for f in sorted((ROOT / "tokyn").iterdir())
             if f.is_file() and f.suffix in (".py", ".lark", ".md")}
    files.update({f"vendor/{f.relative_to(VENDOR).as_posix()}": f for f in sorted(VENDOR.rglob("*"))
                  if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc"})
    if lang != "it":
        files["tokyn_cli.py"] = LAUNCHER
    return files


def generated(lang: str) -> list:
    """I file che lo script scrive nella Skill: quelli del compilatore e la copia di lark (non la cache di Python)."""
    base = skill_dir(lang)
    found = list((base / "tokyn").glob("*")) + list((base / "vendor").rglob("*"))
    return [p for p in found if p.is_file() and "__pycache__" not in p.parts]


def content(lang: str, src: Path) -> bytes:
    """Il contenuto copiato: uguale al sorgente, ma il lanciatore parla la lingua del plugin."""
    data = src.read_bytes()
    if src == LAUNCHER:
        line = LAUNCHER_LANG.encode()
        if data.count(line) != 1:
            sys.exit(f"{LAUNCHER.relative_to(ROOT)} deve contenere una sola volta la riga {LAUNCHER_LANG}")
        data = data.replace(line, f'LINGUA = "{lang}"'.encode())
    return data


def outdated() -> list:
    stale = []
    for lang in PLUGINS:
        wanted = copies(lang)
        for rel, src in wanted.items():
            dest = skill_dir(lang) / rel
            if not dest.exists() or dest.read_bytes() != content(lang, src):
                stale.append(str(dest.relative_to(ROOT)))
        extra = [p for p in generated(lang) if p.relative_to(skill_dir(lang)).as_posix() not in wanted]
        stale += [str(p.relative_to(ROOT)) for p in extra]
    return stale


def sync():
    for lang in PLUGINS:
        for old in generated(lang):
            old.unlink()
        shutil.rmtree(skill_dir(lang) / "vendor", ignore_errors=True)  # anche le cartelle rimaste vuote
        for rel, src in copies(lang).items():
            dest = skill_dir(lang) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content(lang, src))


def build_zip(out: Path, lang: str = "it"):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill_dir(lang).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f"tokyn/{f.relative_to(skill_dir(lang)).as_posix()}")
    print(f"creato {out}")


if __name__ == "__main__":
    if "--check" in sys.argv:
        stale = outdated()
        if stale:
            sys.exit("plugin non aggiornati, esegui python scripts/build_skill.py:\n  " + "\n  ".join(stale))
        print("plugin aggiornati")
        sys.exit(0)
    args = [a for a in sys.argv[1:] if a != "--en"]
    if args:  # solo lo zip, dai plugin così come sono
        build_zip(Path(args[0]).resolve(), "en" if "--en" in sys.argv else "it")
    else:
        sync()
        for lang, out in ZIPS.items():
            build_zip(out, lang)
