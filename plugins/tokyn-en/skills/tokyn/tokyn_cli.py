"""Usa il compilatore Tokyn incluso nella Skill, da qualsiasi cartella e senza installarlo.

Uso: python <cartella della skill>/tokyn_cli.py check|run|build|spec|new ...
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import lark  # noqa: F401
except ImportError:
    sys.exit("manca la libreria lark: installala con `pip install lark anthropic` "
             "(aggiungi --break-system-packages se pip lo chiede)")

from tokyn.cli import main

sys.exit(main())
