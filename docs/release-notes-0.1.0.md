# Tokyn 0.1.0

First public release of Tokyn, a small language with Python syntax for programs that use Claude.

## What's in it

- **The language**: `agent`, `type`, `def` and `main`. Agents can have tools (your functions or other agents),
  structured output (`output: Type`), `memory`, `effort` and `max_steps`. `Agent.ask_all(texts)` runs bulk jobs
  through the Message Batches API at half price.
- **The compiler** (`tokyn check | run | build | spec | new`): checks names, types and agent fields before anything
  runs. Compile errors have a line, a column and, for most of them, the fix. Messages are in English or Italian
  (`--lang`, `TOKYN_LANG`).
- **The runtime**: tool loop, JSON schemas, validation, retries, prompt caching, native structured outputs, and
  server-side fallback on refusals where the model supports it. `--mock` runs programs with fake answers for free;
  `--usage` prints the tokens spent.
- **Who answers the agents**: the Anthropic API (`ANTHROPIC_API_KEY`), or your Claude Code login (`claude -p`) for
  trying your own programs while you develop them. Under Anthropic's rules a product, or a program other people use,
  should use an API key; Tokyn prints a notice when it falls back to Claude Code.
- **Other providers** through one OpenAI-compatible adapter: OpenAI, Gemini, Mistral, DeepSeek, Groq, OpenRouter,
  xAI, Ollama and any compatible server (`model: "openai:..."` etc.). Tested against a fake server so far.
- **`tokyn build --standalone`**: one Python file that does not need Tokyn installed.
- **Claude Code plugins** `tokyn` (Italian) and `tokyn-en` (English): a Skill plus the bundled compiler and a copy of
  lark, so writing and trying programs needs no `pip install`.

## Benchmark

270 Claude Code sessions (Opus 5.5 and Sonnet 5.5, 15 tasks, 3 runs each), pre-registered: Tokyn sessions cost 68%
less than plain Python and 61-70% less than Python with the Claude Agent SDK; 89 of 90 Tokyn programs passed the
hidden tests. All benchmarks were run with Anthropic's Claude. Details: `bench/claude-code/v2/`.

## Install

- Claude Code: `/plugin install tokyn-en --marketplace DamianoCeka/tokyn`
- Python 3.10+: `pip install tokyn`

## Known limitations

- Compiles to Python only.
- No `while`, `class`, `try`/`except`, comprehensions or `lambda`, by design; the compiler says what to write instead.
- Through Claude Code, `ask_all` sends one request at a time and `max_steps` does not apply.
- Alpha: the language may still change before 1.0.
