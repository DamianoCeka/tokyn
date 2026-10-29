"""Usa il compilatore Tokyn incluso nella Skill, da qualsiasi cartella e senza installarlo.

Uso: python <cartella della skill>/tokyn_cli.py check|run|build|spec|new ...
"""

import sys
from pathlib import Path

# Lingua dei messaggi del plugin, al posto di quella del sistema (TOKYN_LANG e --lang vincono comunque).
# scripts/build_skill.py la cambia nella copia per il plugin inglese.
LINGUA = "en"

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))

from tokyn import lingua  # noqa: E402

lingua.imposta_plugin(LINGUA)

try:
    import lark  # noqa: F401
except ImportError:  # lark non è installato: si usa la copia inclusa nella Skill (vendor/lark, licenza MIT)
    for nome in [m for m in sys.modules if m == "lark" or m.startswith("lark.")]:
        del sys.modules[nome]  # i pezzi già caricati di un lark installato ma rotto
    sys.path.insert(1, str(SKILL / "vendor"))
    try:
        import lark  # noqa: F401
    except ImportError:
        sys.exit(lingua.tr("manca la libreria lark e nella Skill non c'è la sua copia (cartella vendor): "
                           "reinstalla il plugin oppure installa lark con `pip install lark`",
                           "the lark library is missing and so is its copy in the Skill (the vendor folder): "
                           "reinstall the plugin or install lark with `pip install lark`"))

from tokyn.cli import main  # noqa: E402

sys.exit(main())
