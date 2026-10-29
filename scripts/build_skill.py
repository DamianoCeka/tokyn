"""Crea gli zip della Skill per Claude, con il compilatore incluso.

Uso: python scripts/build_skill.py                 -> dist/tokyn-skill.zip (italiano) e dist/tokyn-skill-en.zip (inglese)
     python scripts/build_skill.py percorso.zip [--en]
Poi carica lo zip in Claude (Impostazioni > Skill).
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = {"it": (ROOT / "skill" / "tokyn", ROOT / "dist" / "tokyn-skill.zip"),
          "en": (ROOT / "skill" / "tokyn-en", ROOT / "dist" / "tokyn-skill-en.zip")}


def main(out: Path, lang: str = "it"):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(SKILLS[lang][0] / "SKILL.md", "tokyn/SKILL.md")
        z.write(ROOT / "skill" / "tokyn" / "tokyn_cli.py", "tokyn/tokyn_cli.py")
        z.write(ROOT / "tokyn" / "SPEC.md", "tokyn/SPEC.md")
        for f in sorted((ROOT / "tokyn").iterdir()):
            if f.is_file() and f.suffix in (".py", ".lark", ".md"):
                z.write(f, f"tokyn/tokyn/{f.name}")
        for f in sorted((ROOT / "examples").glob("*.tokyn")):
            z.write(f, f"tokyn/examples/{f.name}")
    print(f"creato {out}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--en"]
    if args:
        main(Path(args[0]).resolve(), "en" if "--en" in sys.argv else "it")
    else:
        for lang, (_folder, out) in SKILLS.items():
            main(out, lang)
