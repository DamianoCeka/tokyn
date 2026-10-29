from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

MODEL = "anthropic:claude-sonnet-5-5"

researcher = Agent(MODEL, instructions="Sei un ricercatore di mercato. Elenca in breve caratteristiche, target e punti di forza richiesti.")
copywriter = Agent(MODEL, instructions="Sei un copywriter social. Scrivi post Instagram in italiano, coinvolgenti, con emoji e hashtag.")
coordinator = Agent(
    MODEL,
    instructions="Coordini la creazione di un post Instagram: usa prima il ricercatore, poi il copywriter, e restituisci il testo finale del post.",
)


@coordinator.tool
async def ricerca(ctx: RunContext[None], argomento: str) -> str:
    """Chiede al ricercatore informazioni utili sull'argomento."""
    return (await researcher.run(argomento, usage=ctx.usage)).output


@coordinator.tool
async def scrivi_post(ctx: RunContext[None], brief: str) -> str:
    """Chiede al copywriter di scrivere il post a partire dal brief e dalla ricerca."""
    return (await copywriter.run(brief, usage=ctx.usage)).output


class Verdetto(BaseModel):
    approvato: bool
    problemi: list[str]
    testo_finale: str


revisore = Agent(
    "anthropic:claude-sonnet-5-5",
    output_type=Verdetto,
    instructions="Controlla il post Instagram: tono, correttezza, claim non verificabili, lunghezza, hashtag. Restituisci il testo finale corretto.",
)

post = coordinator.run_sync("Crea un post Instagram per il lancio di un nuovo mouse gaming.").output
verdetto = revisore.run_sync(post).output

print("POST:\n", post, "\n")
print("Approvato:", verdetto.approvato)
print("Problemi:", *verdetto.problemi, sep="\n- ")
print("\nTesto finale:\n", verdetto.testo_finale)
