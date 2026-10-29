"""Crea dist/tokyn-skill.zip: la Skill per Claude con il compilatore incluso.

Uso: python scripts/build_skill.py [percorso dello zip]
Poi carica lo zip in Claude (Impostazioni > Skill).
"""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "tokyn-skill.zip"


def main(out: Path = OUT):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((ROOT / "skill" / "tokyn").iterdir()):
            if f.is_file() and f.suffix in (".py", ".md"):
                z.write(f, f"tokyn/{f.name}")
        z.write(ROOT / "tokyn" / "SPEC.md", "tokyn/SPEC.md")
        for f in sorted((ROOT / "tokyn").iterdir()):
            if f.is_file() and f.suffix in (".py", ".lark", ".md"):
                z.write(f, f"tokyn/tokyn/{f.name}")
        for f in sorted((ROOT / "examples").glob("*.tokyn")):
            z.write(f, f"tokyn/examples/{f.name}")
    print(f"creato {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else OUT)
