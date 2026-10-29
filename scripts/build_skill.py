"""Crea dist/tokyn-skill.zip: la Skill per Claude con il compilatore incluso.

Uso: python scripts/build_skill.py
Poi carica lo zip in Claude (Impostazioni > Skill).
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "tokyn-skill.zip"


def main():
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / "skill" / "tokyn" / "SKILL.md", "tokyn/SKILL.md")
        z.write(ROOT / "tokyn" / "SPEC.md", "tokyn/SPEC.md")
        for f in sorted((ROOT / "tokyn").iterdir()):
            if f.is_file() and f.suffix in (".py", ".lark", ".md"):
                z.write(f, f"tokyn/tokyn/{f.name}")
        for f in sorted((ROOT / "examples").glob("*.tokyn")):
            z.write(f, f"tokyn/examples/{f.name}")
    print(f"creato {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
