"""Prepara la Skill di Tokyn: i plugin per Claude Code e gli zip da caricare in Claude.

Ogni plugin (plugins/tokyn in italiano, plugins/tokyn-en in inglese) deve contenere tutto quello che serve,
perché Claude Code installa solo la cartella del plugin: questo script ci copia il compilatore.

Uso: python scripts/build_skill.py            aggiorna i plugin e crea dist/tokyn-skill.zip e dist/tokyn-skill-en.zip
     python scripts/build_skill.py --check    controlla che i plugin siano aggiornati (per la CI)
     python scripts/build_skill.py percorso.zip [--en]    crea solo uno zip
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = {"it": ROOT / "plugins" / "tokyn", "en": ROOT / "plugins" / "tokyn-en"}
ZIPS = {"it": ROOT / "dist" / "tokyn-skill.zip", "en": ROOT / "dist" / "tokyn-skill-en.zip"}
LAUNCHER = PLUGINS["it"] / "skills" / "tokyn" / "tokyn_cli.py"  # l'originale sta nel plugin italiano


def skill_dir(lang: str) -> Path:
    return PLUGINS[lang] / "skills" / "tokyn"


def copies(lang: str) -> dict:
    """File copiati nella cartella della Skill: percorso nella Skill -> sorgente."""
    files = {f"tokyn/{f.name}": f for f in sorted((ROOT / "tokyn").iterdir())
             if f.is_file() and f.suffix in (".py", ".lark", ".md")}
    if lang != "it":
        files["tokyn_cli.py"] = LAUNCHER
    return files


def outdated() -> list:
    stale = []
    for lang in PLUGINS:
        wanted = copies(lang)
        for rel, src in wanted.items():
            dest = skill_dir(lang) / rel
            if not dest.exists() or dest.read_bytes() != src.read_bytes():
                stale.append(str(dest.relative_to(ROOT)))
        package = skill_dir(lang) / "tokyn"
        extra = [p for p in package.glob("*") if p.is_file() and f"tokyn/{p.name}" not in wanted] if package.exists() else []
        stale += [str(p.relative_to(ROOT)) for p in extra]
    return stale


def sync():
    for lang in PLUGINS:
        package = skill_dir(lang) / "tokyn"
        package.mkdir(parents=True, exist_ok=True)
        for old in package.glob("*"):
            if old.is_file():
                old.unlink()
        for rel, src in copies(lang).items():
            (skill_dir(lang) / rel).write_bytes(src.read_bytes())


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
