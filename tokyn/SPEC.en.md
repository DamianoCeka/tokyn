# Tokyn v0.1 — Specification

Tokyn is a language for building **AI agents**. It has Python syntax, but with
agents, tools and structured outputs built into the language. It is translated into
Python, so it can use any Python library.

File: `.tokyn` · Indentation: 4 spaces · Comments: `#`

## Golden rules

1. Keywords in English, as in Python: `def`, `if`, `elif`, `else`, `for`, `in`, `return`, `and`, `or`, `not`, `True`, `False`, `None`.
2. **Only one way to do each thing.** Only one loop (`for`), only one way to define an agent, only one way to call it (`Agent.ask(text)`).
3. Before running, always check with `tokyn check file.tokyn` and fix all the reported errors.

## Structure of a file

A file contains, in any order:

| Construct | What it is for |
|---|---|
| `import x` / `from x import y as z` | using a Python library |
| `NAME = value` | global constant (cannot be changed afterwards) |
| `type Name:` | structured data |
| `def name(...):` | function; an agent can use it as a tool |
| `agent Name:` | an AI agent |
| `main:` | the starting point of the program (only one) |

Constants and parameter default values are computed immediately, from top to bottom:
they can only use constants and functions written before them (as in Python).

## Agents

```
agent Support:
    model: "claude"
    instructions: "Answer customers in English, briefly."
    tools: [search_faq, book]
    memory: True
```

Fields (written with `:`, never with `=`):

| Field | Required | Value |
|---|---|---|
| `instructions` | yes | text: who the agent is and what it must do. It can be `"""on several lines"""` or a constant |
| `model` | no (default `"claude"`) | `"claude"`, `"claude-opus"`, `"claude-haiku"`, `"mock"`, the full id of a Claude model, or `"provider:model"` for another provider (see [Other providers](#other-providers)) |
| `tools` | no | list of names of `def` functions or of other agents |
| `output` | no | name of a `type`: the agent answers with structured data |
| `memory` | no (default `False`) | `True` to remember the conversation from one `ask` to the next |
| `max_steps` | no (default `10`) | maximum number of steps for each `ask` |
| `effort` | no | how much the AI reasons: `"low"`, `"medium"`, `"high"`, `"xhigh"`, `"max"`. `"low"` costs less: fine for classifying and extracting |

An agent is used **only** like this:

- `Agent.ask(text)` → returns the answer. It is a `str`, or a value of the `type` given in `output`.
- `Agent.ask_all(texts)` → a list of answers, in the same order as the texts: like a loop of `ask`, but with
  Anthropic's Batch API, which costs half. It is slower (usually minutes, at most 24 hours) and does not use the memory:
  suited to bulk jobs, not to chats. A text that is refused or has an error in the batch is retried with a
  normal call; if it is still left without an answer, the program stops saying which one. With Claude Code and with
  other providers it makes normal requests without memory, up to 4 at once (`TOKYN_PARALLELO` changes the number).
- `Agent.reset()` → clears the memory.

During `ask` the runtime handles the loop of tool calls on its own,
plus retries and output validation. You do not need to write any loop.

An agent in the `tools` list of another agent becomes a sub-agent to delegate to.

## Other providers

Tokyn is designed for Claude, and its benchmarks were run with Anthropic Claude. An agent can however use another
provider with `model: "provider:model"`, through its OpenAI-compatible API (Chat Completions):

```
agent Summary:
    model: "openai:gpt-5.6-luna"
    instructions: "Summarize in three lines."
```

| Prefix | Key | Notes |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | for tools use `gpt-5.6-terra` or `gpt-5.6-luna`: other recent models use them only through the Responses API or with `reasoning_effort` `"none"`, which Tokyn does not send |
| `gemini` | `GEMINI_API_KEY` | Google's compatible API, still in beta |
| `mistral` | `MISTRAL_API_KEY` | `effort` only counts as `"high"` (or more) |
| `deepseek` | `DEEPSEEK_API_KEY` | output as free JSON, validated and retried |
| `groq` | `GROQ_API_KEY` | strict schema only on some models and without tools; otherwise free JSON or the `rispondi` tool |
| `openrouter` | `OPENROUTER_API_KEY` | the model is written with its author: `openrouter:google/gemini-3.8-flash` |
| `xai` | `XAI_API_KEY` | `effort` is not used |
| `ollama` | none | local (`http://localhost:11434/v1`); first `ollama pull model`. Short default context: raise it with `OLLAMA_CONTEXT_LENGTH` |
| `openai-compatible` | `TOKYN_OPENAI_API_KEY` (if needed) | any other compatible server, at the address in `TOKYN_OPENAI_BASE_URL` (e.g. `http://localhost:8000/v1`) |

- They behave like Claude agents: instructions, tools, `max_steps`, `memory`, `reset`, structured outputs validated
  and retried. Where the provider allows it the output uses a strict schema (`json_schema`), otherwise free JSON or
  the `rispondi` tool. `ask_all` sends up to 4 requests at once.
- `effort` becomes `reasoning_effort` only with `openai`, `gemini`, `mistral`, `deepseek` and `groq`; elsewhere it is ignored.
- Without the key the program stops saying which variable to set. `--mock` works with every provider, without keys.
  `--backend` and Claude Code apply only to Claude models.
- Rate limits and busy servers are retried on their own (honouring `Retry-After`); used-up credit and bad requests
  are not. `--usage` also counts the tokens of other providers.

## Tools (functions)

Every `def` is a normal function. If it appears in the `tools` of an agent, it must have:

- the **type of every parameter**;
- a **description** as the first line of the body (a string), which the AI reads to decide when to use it.

```
def find_customer(email: str) -> str:
    """Finds a customer by email and returns their name and active plan."""
    customers = json_parse(read_file("customers.json"))
    for c in customers:
        if c["email"] == email:
            return f"{c['name']} ({c['plan']})"
    return "Customer not found."
```

The arguments coming from the AI are checked and converted according to the declared
types. If the tool fails, the error goes back to the AI, which can try again.
With `ask_all` without the Batch API (Claude Code, other providers) a tool can run several times at once, in
different threads.

## Types

```
type Ticket:
    category: "technical" | "sales" | "other"
    urgent: bool "True if the customer is blocked"
    tags: list[str]
```

- Basic types: `str`, `int`, `float`, `bool`, `dict`, `list[T]`, or the name of another `type`.
- `"a" | "b" | "c"`: only one of the listed values. The checker reports comparisons with values that are not listed.
- A string after the type is the description of the field and is passed to the AI.
- All fields are required.
- It is created with the field names: `Ticket(category="other", urgent=False, tags=[])`.
- It is read and changed with the dot: `t.category`, `t.urgent = True`.

## Statements and expressions

As in Python:

- `x = value`, `x += 1`, `x -= 1`, `x *= 2`, `x /= 2`, `x //= 2`, `x %= 2`; also on `d["k"]`, `items[i]`, `t.field`
- `if` / `elif` / `else`
- `for x in items:`, `for i in range(n):`, `for k, v in dictionary.items():`, `break`, `continue`
- `return`, `pass`
- Numbers: `3`, `2.5`, `1_000`, `1e-9`
- Operators: `+ - * / // % **`, `== != < > <= >=` (also chained: `0 <= x < 3`), `in`, `not in`, `and`, `or`, `not`
- Lists `[1, 2]`, dictionaries `{"a": 1}`, indexes `x[0]`, attributes `x.y`, calls `f(a, b=1)`
- Slices of texts and lists: `text[:200]`, `items[1:]`, `items[-3:]`, `text[::-1]`
- Strings `"..."`, `'...'`, `"""..."""`, `r"\d+"` and f-strings `f"Hello {name}"`
- Python methods of strings, lists and dictionaries: `.upper()`, `.split()`, `.append()`, `.get()`, `.items()`…

These do not exist in Tokyn (the checker reports them and says what to use): `while`, `class`, `lambda`,
`try`/`except`, `with`, `async`/`await`, `yield`, `global`, `match`, comprehensions
`[x for x in ...]` (use `for` with `.append()`), `a if c else b` (use `if`/`else`),
`is` (use `==` and `!=`), tuples and sets (use lists), `a, b = ...` and `return a, b` (use a list),
`del` (use `.pop()`), `raise` and `assert` (use `if` and `return`), `def` inside other functions.
Instead of `try`/`except`, `read_file`, `http_get`, `http_post` and `json_parse` accept a fallback value (`default`).

## Built-in functions

`print`, `input`, `len`, `str`, `int`, `float`, `bool`, `list`, `dict`, `range`, `enumerate`,
`zip`, `sum`, `min`, `max`, `sorted`, `reversed`, `abs`, `round`, `any`, `all`, and also:

| Function | What it does |
|---|---|
| `read_file(path, default)` | reads a text file; if it does not exist returns `default` (without `default` it stops with an error) |
| `write_file(path, text)` | writes (overwrites) a file |
| `append_file(path, text)` | appends to the end of a file |
| `http_get(url, default)` | downloads a page and returns the text; if the network fails returns `default` |
| `http_post(url, data, default)` | sends JSON data and returns the response; if it fails returns `default` |
| `json_parse(text, default)` | from JSON text to lists/dictionaries; if it is not valid JSON returns `default` |
| `to_number(text, default)` | from text to `int` or `float` (`"42"`, `"4,50"`, `"1.234,56"`); if it is not a number returns `default` |
| `json_dump(value)` | from a value (also a `type`) to JSON text |
| `env(name, default)` | reads an environment variable |
| `now()` | current date and time, e.g. `"2026-10-28T14:30:00"` |
| `sleep(seconds)` | waits |

## Complete example

```
type Review:
    sentiment: "positive" | "neutral" | "negative"
    score: int "from 1 to 5"
    summary: str

agent Analyst:
    model: "claude-haiku"
    instructions: "Analyze a customer's review."
    output: Review

main:
    texts = read_file("reviews.txt").split("\n")
    negative = 0
    for text in texts:
        if not text.strip():
            continue
        r = Analyst.ask(text)
        if r.sentiment == "negative":
            negative += 1
            print(f"⚠️ {r.score}/5 — {r.summary}")
    print(f"Negative reviews: {negative}")
```

## Commands

| Command | What it does |
|---|---|
| `tokyn check file.tokyn` | checks the file and shows the errors with the hint to fix them |
| `tokyn check --json file.tokyn` | the same in JSON (for AI and tools) |
| `tokyn run file.tokyn` | runs: the agents answer with the API if `ANTHROPIC_API_KEY` is set, otherwise with Claude Code (`claude -p`, the account of whoever uses it) |
| `tokyn run file.tokyn --backend claude-code` | chooses who answers the agents (`claude-code` or `api`) |
| `tokyn run file.tokyn --mock` | runs with fake answers, without calling the AI |
| `tokyn run file.tokyn --usage` | at the end shows the tokens spent and those read from the cache |
| `tokyn build file.tokyn` | generates the equivalent Python file |
| `tokyn build file.tokyn --standalone` | generates a standalone Python file (only `anthropic` is needed, and nothing for other providers) |
| `tokyn spec` | prints this specification |
| `tokyn new name` | creates a starter file |
| `tokyn check --lang en file.tokyn` | language of the messages (`it` or `en`), with every command. The `TOKYN_LANG` variable wins; without either, the language of the Skill or of the system applies |

## Main error codes

| Code | Meaning |
|---|---|
| E002 | Python construct that Tokyn does not have (`while`, `class`, comprehension…) |
| E003 / E004 / E005 / E009 | missing `:` / missing indented block / wrong indentation |
| E101 | name defined twice |
| E110 | unknown type |
| E115 | recursive `type` (contains itself, also through other `type`s) |
| E121 / E122 | tool without parameter types / without description |
| E130–E139 | agent field that is wrong, missing or has an invalid value |
| E144 | agents that delegate to each other |
| E145 | invalid `effort` value |
| E146 | unknown provider in `model: "provider:model"`, or missing model name |
| E142 | attempt to change a constant |
| E160 / E161 | undefined name / variable used before it is assigned |
| E162 | constant or default value that uses something written further down |
| E170 | method that does not exist on an agent (only `.ask` and `.reset` exist) |
| E171 | field that does not exist in a `type` |
| E175 | method that does not exist on a text, list or dictionary |
| E180–E187 | wrong arguments in a call |
| E190 | unexpected value compared with an `"a" \| "b"` field |
| E194 | text + number |
