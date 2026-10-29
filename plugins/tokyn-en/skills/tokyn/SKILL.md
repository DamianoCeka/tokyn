---
name: tokyn
description: Writes AI-agent programs, chatbots and AI text extraction or classification with Claude in Tokyn (.tokyn files), which take far fewer tokens than the equivalent Python; checks and runs them with the bundled compiler and, when needed, turns them into a Python file. Use it when the user asks for a program or script with AI agents or Claude automations, Python included, when they mention Tokyn, or when the project contains .tokyn files. Do not use it when the user explicitly asks for another framework (Anthropic SDK, LangChain…) or when the code goes into a project written in a language other than Python.
---

# Tokyn

A language with Python syntax in which agents, tools and structured outputs are part of the language: the tool
loop, JSON schemas, validation, retries and caching are handled by the runtime. The same program takes about a
third of the tokens of Python. Everything you need to write it is in this file; the full spec,
`${CLAUDE_SKILL_DIR}/tokyn/SPEC.md` (in Italian), is only for rare details. Compiler messages are in Italian and
each one comes with the fix (`→`).

## Procedure

1. Write the program in a `.tokyn` file, even if the user wants Python: the Python is generated at step 4.
2. Check and try it for free, with fake answers: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --mock`
   - If there are errors, it lists them with line, column and fix (`→`) and runs nothing.
     Fix them with targeted edits, without rewriting the file, and repeat until it runs.
   - If the program uses `input()`, pass the answers one per line:
     `printf 'hello\nquit\n' | python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --mock`
   - In mock, agents do not call tools; `write_file`, `http_post` etc. do run for real.
   - If `lark` is missing: `pip install lark` (with `--break-system-packages` if pip asks).
3. When you need real answers: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --usage`.
   Without `ANTHROPIC_API_KEY` the agents answer through the user's Claude Code (`claude -p`: no key, a few
   seconds per `ask`); with the key they use the API. If the program makes many calls, tell the user first and run
   it in the background. `--usage` prints the tokens spent at the end.
4. If the user wants Python: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py build file.tokyn --standalone -o file.py`.
   The file does not depend on Tokyn and works with the API key or with Claude Code. Do not write the Python by
   hand: it would cost the tokens Tokyn saves.

## Language reference

```
import math                                    # Python libraries
LIMIT = 3                                      # global constant: cannot be reassigned

type Line:                                     # structured data; all fields are required
    product: str
    price: float "unit price in euros"         # string after the type = description for the AI

type Ticket:
    category: "technical" | "sales" | "other" "who should handle it"   # only one of these values
    urgent: bool
    tags: list[str]
    lines: list[Line]                          # types: str int float bool dict list[T] or another type

def search_faq(question: str) -> str:
    """Searches the company FAQ for an answer."""   # tool: parameter types and description required
    return read_file("faq.txt")

agent Technician:
    instructions: "Solve technical problems."
    effort: "low"                              # optional: "low" costs less for classifying and extracting

agent Support:
    model: "claude"                            # default "claude"; also "claude-opus", "claude-haiku", "mock" or an id
    instructions: """
        Answer customers in English.
    """                                        # required: any text, also f"... {CONSTANT}"
    tools: [search_faq, Technician]            # def functions or other agents to delegate to
    output: Ticket                             # optional: structured answer instead of str
    memory: True                               # optional (default False): remembers between asks
    max_steps: 10                              # optional: maximum steps for each ask

def by_price(l: Line) -> float:
    return l.price

main:                                          # entry point, only one
    counts = {"technical": 0, "sales": 0, "other": 0}
    for turn in range(20):                     # chat loop: for + break
        text = input("You: ")
        if text.strip().lower() == "quit":
            break
        t = Support.ask(text)                  # one argument; returns str or the output type
        counts[t.category] += 1
        if t.category == "technical" and t.urgent:
            lines = sorted(t.lines, key=by_price, reverse=True)   # sort by field: def + key=
            for i, l in enumerate(lines[:LIMIT]):
                print(f"{i + 1}. {l.product}: {l.price:.2f} €")
        elif t.category not in ["sales"]:
            print(json_dump(t))
    Support.reset()                            # clears the memory
    notes = Technician.ask_all(["The pc won't start", "The wifi is slow"])  # many texts: Batch API, half price
    new = Ticket(category="other", urgent=False, tags=[], lines=[])  # constructor with field names
    new.urgent = True
```

- Statements: `=` and `+= -= *= /= //= %=` (also on `d["k"]`, `list[i]`, `t.field`), `if`/`elif`/`else`,
  `for x in ...` (also `for k, v in d.items()` and `for a, b in zip(x, y)`), `break`, `continue`, `return` (in `main` it ends the program),
  `pass`. Variables are visible in the whole function, as in Python.
- Expressions as in Python: `+ - * / // % **`, chained comparisons (`0 <= x < 3`), `and or not in`,
  numbers `1_000` and `1e-9`, escapes (`"\n"`), `r"\d+"`, f-strings with any expression and format (`{x:.2f}`),
  indexes `x[-1]`, slices `x[:200]` and `x[::-1]`; lines can break inside brackets (trailing comma allowed). All str/list/dict
  methods and all Python modules (`import os`, `from x import y as z`, `os.listdir(folder)`). Names may have accents.
- Built-in functions: `print input len str int float bool list dict range enumerate zip sum min max sorted
  reversed abs round any all`, `write_file(p, text)`, `append_file(p, text)`, `sleep(s)` and:
  - `read_file(p, default)`, `http_get(url, default)`, `http_post(url, data, default)` → text;
    `json_parse(text, default)` → lists and dicts (not `type`s); `env(name, default)`. If something goes wrong
    (missing file, network, HTTP 4xx/5xx response, invalid address or JSON, unset variable) they return
    `default`; without `default` the program stops with a clear error. `http_post` sends `data` as JSON.
    URLs are not encoded: to put text in one use `urllib.parse.quote(text)`.
  - `to_number(text, default)` → int or float from text (`"42"`, `"4,50"`, `"1.234,56"`), `default` if it is not one.
  - `json_dump(value)` → indented JSON keeping accents, also of `type`s and lists of `type`s. `now()` →
    `"2026-10-28T14:30:00"` (the date is `now()[:10]`). At end of input `input()` stops the program with an error:
    to read several lines use a terminator (e.g. an empty line). Paths are relative to the folder you run from.

## Behaviour

- Order: `type`, `def` and `agent` can come in any order. Constants and parameter default values are
  computed immediately, top to bottom: they use only constants and functions written before them, never agents
  (not even through a function). A constant is any expression (`JOB = "Role: " + read_file("a.txt", "")`) and can
  be used as `instructions`; it cannot be reassigned, but constant lists and dicts can be modified (`LIST.append(x)`).
  Functions see every constant and import, wherever they are written.
- `def`: types and `->` are optional; tools need the type of every parameter and a description.
- Types for fields, parameters and returns: `str int float bool dict list list[T]` and `type`s; a description can
  follow any field. The runtime checks `type` fields, agent `output`s and the arguments the AI passes to tools
  (an int is fine for `float`); it does not check calls from your own code or limits like "from 1 to 5":
  put them in the description and, if needed, check them with an `if`. `|` choices are text only; no recursive
  types. Objects, including those returned by agents, can be modified with the dot.
- `output` is the name of a single `type`: for a list use a container type with a `list[Item]` field.
- A tool can return any value: the AI receives it as text or JSON (dates and the like become text).
  If it fails, the error goes back to the AI, which can retry. An agent used as a tool receives one text and
  returns its answer (JSON if it has an `output`); the agent using it sees the first 300 characters of its
  `instructions`, so say what it is for at the start.
- `memory` keeps questions and final answers (not tool results) for the whole run. Every AI call is one step:
  `max_steps` (default 10) must cover the tool calls plus the final answer, otherwise the program stops with an
  error (if the agent is used as a tool, the error goes back to the agent using it).
- In mock: texts `"esempio <field>"`, numbers 1 and 1.0, empty dicts, lists of 2 items; `"a" | "b"` values and
  bools change at every `ask` of that agent and from one item to the next (starting from the first value and True).
  Without `output` the answer is `"[mock Name] risposta a: ..."`.
- With Claude Code (no API key) `ask_all` sends the requests one at a time, because the Batch API needs the key,
  and `max_steps` does not apply.
- `Agent.ask_all(texts)` gives the same answers as a loop of `ask`, in the same order, but through the Batch API:
  half price, slower (usually minutes, at most 24 hours), no `memory`. Use it for bulk jobs (classifying 100 emails);
  for a few texts, or when you need them right away, use a loop of `ask`. In mock it is instant. If a text gets no
  answer even after a retry, the program stops saying which one.
- Costs: `"claude-haiku"` to classify or extract many simple texts, the default `"claude"` for the rest,
  `"claude-opus"` only for hard tasks; `effort: "low"` cuts reasoning tokens. Instructions and tools stay in
  the cache between calls: keep them fixed and put the data that changes in the `ask` text.

## Not available

`while` (use `for i in range(n):` with `break`), `class` (use `type`/`agent`), `try`/`except` (use the `default`s),
`raise`/`assert` (use `if` and `return`; a tool returns the error message as text), `lambda` (use `def`), nested
`def`, `with`, `async`/`await`, `yield`, `global`, `del` (use `.pop()`), `match`, comprehensions (use `for` and
`.append()`), `a if c else b` (use `if`/`else`), `is` (use `==`), tuples and sets (use lists), `a, b = ...` and
`return a, b` (use a list), optional fields like `str | None` (use `""`, `[]` or a value like `"none"`).
Inside an f-string use the other kind of quotes: `f"{d['k']}"`. Agents only have `.ask`, `.ask_all` and `.reset`.
`True`, `False`, `None` capitalized.
