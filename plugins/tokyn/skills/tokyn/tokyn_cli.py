"""Usa il compilatore Tokyn incluso nella Skill, da qualsiasi cartella e senza installarlo.

Uso: python <cartella della skill>/tokyn_cli.py check|run|build|spec|new ...
"""

import sys
from pathlib import Path

# Lingua dei messaggi del plugin, al posto di quella del sistema (TOKYN_LANG e --lang vincono comunque).
# scripts/build_skill.py la cambia nella copia per il plugin inglese.
LINGUA = "it"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tokyn import lingua  # noqa: E402

lingua.imposta_plugin(LINGUA)

try:
    import lark  # noqa: F401
except ImportError:
    sys.exit(lingua.tr("manca la libreria lark: installala con `pip install lark anthropic` "
                       "(aggiungi --break-system-packages se pip lo chiede)",
                       "the lark library is missing: install it with `pip install lark anthropic` "
                       "(add --break-system-packages if pip asks for it)"))

from tokyn.cli import main  # noqa: E402

sys.exit(main())
