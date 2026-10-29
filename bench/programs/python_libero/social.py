"""Coordinatore con due sub-agent (ricercatore e copywriter) usati come tool,
piu un agente revisore indipendente con verdetto strutturato."""
import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5-5"
MODEL_ECONOMICO = "claude-haiku-5-5"  # il ricercatore produce solo appunti: basta il modello economico

client = anthropic.Anthropic()

PRODOTTO = "un nuovo mouse da gaming ultraleggero, wireless, pensato per FPS competitivi"


def testo(risposta) -> str:
    return "".join(b.text for b in risposta.content if b.type == "text")


def esegui_agente(model: str, system: str, prompt: str, tools=None, handlers=None, max_giri=8) -> str:
    """Ciclo agentico generico: chiama il modello ed esegue i tool finche non risponde in testo."""
    messaggi = [{"role": "user", "content": prompt}]
    for _ in range(max_giri):
        kwargs = {"tools": tools} if tools else {}
        risposta = client.messages.create(
            model=model, max_tokens=2048, system=system, messages=messaggi, **kwargs
        )
        if risposta.stop_reason != "tool_use":
            return testo(risposta)
        messaggi.append({"role": "assistant", "content": risposta.content})
        risultati = []
        for b in risposta.content:
            if b.type != "tool_use":
                continue
            try:
                esito = handlers[b.name](**b.input)
            except Exception as e:
                esito = f"Errore: {e}"
            risultati.append({"type": "tool_result", "tool_use_id": b.id, "content": esito})
        messaggi.append({"role": "user", "content": risultati})
    raise RuntimeError("Troppi giri di tool")


# --- Sub-agent ---------------------------------------------------------------
def ricercatore(argomento: str) -> str:
    return esegui_agente(
        MODEL_ECONOMICO,
        "Sei un ricercatore di mercato per il mondo gaming. Elenca in modo conciso (max 8 punti) "
        "caratteristiche tipiche, benefici per il giocatore e tendenze rilevanti per l'argomento dato. "
        "Non inventare numeri precisi o dati tecnici: se mancano, indicali come da confermare.",
        argomento,
    )


def copywriter(brief: str) -> str:
    return esegui_agente(
        MODEL,
        "Sei un copywriter social esperto di gaming. Scrivi in italiano un post Instagram: "
        "gancio iniziale forte, 3-5 righe, tono energico, call to action e 5-8 hashtag. "
        "Restituisci solo il testo del post.",
        brief,
    )


# --- Coordinatore -------------------------------------------------------------
TOOLS_COORDINATORE = [
    {
        "name": "ricercatore",
        "description": "Sub-agent che raccoglie informazioni e spunti su un argomento.",
        "input_schema": {
            "type": "object",
            "properties": {"argomento": {"type": "string", "description": "Cosa ricercare"}},
            "required": ["argomento"],
        },
    },
    {
        "name": "copywriter",
        "description": "Sub-agent che scrive il post Instagram a partire da un brief con i punti chiave.",
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string", "description": "Brief completo per il post"}},
            "required": ["brief"],
        },
    },
]


def coordinatore(richiesta: str) -> str:
    return esegui_agente(
        MODEL,
        "Sei il coordinatore di un team social. Per produrre il post: 1) chiama prima il ricercatore, "
        "2) passa i risultati nel brief al copywriter, 3) rispondi solo con il testo finale del post.",
        richiesta,
        tools=TOOLS_COORDINATORE,
        handlers={"ricercatore": ricercatore, "copywriter": copywriter},
    )


# --- Revisore con output strutturato -----------------------------------------
class Verdetto(BaseModel):
    approvato: bool
    problemi: list[str]
    testo_finale: str


def revisore(post: str) -> Verdetto:
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=(
            "Sei un revisore di contenuti social. Controlla il post: tono adatto a Instagram, "
            "assenza di affermazioni esagerate o non verificabili, errori di italiano, CTA e hashtag. "
            "Se ci sono problemi, elencali e fornisci in testo_finale una versione corretta; "
            "se e a posto, approvato=true e testo_finale uguale al post."
        ),
        tools=[
            {
                "name": "emetti_verdetto",
                "description": "Emette il verdetto di revisione.",
                "input_schema": Verdetto.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "emetti_verdetto"},
        messages=[{"role": "user", "content": f"Post da revisionare:\n\n{post}"}],
    )
    for b in risposta.content:
        if b.type == "tool_use":
            return Verdetto.model_validate(b.input)
    raise RuntimeError("Nessun verdetto ricevuto")


def main() -> None:
    post = coordinatore(f"Crea un post Instagram per lanciare {PRODOTTO}.")
    print("=== POST ===")
    print(post)

    v = revisore(post)
    print("\n=== VERDETTO ===")
    print("Approvato:", "si" if v.approvato else "no")
    if v.problemi:
        print("Problemi:")
        for p in v.problemi:
            print(f" - {p}")
    print("\n=== TESTO FINALE ===")
    print(v.testo_finale)


if __name__ == "__main__":
    main()
