# Tokyn (English) for Claude Code

Tokyn is a small programming language with Python syntax for programs that use Claude. Agents, tools and
structured outputs are part of the language: the tool loop, JSON schemas, validation of the answers, retries and
prompt caching are handled by the runtime. So when you ask Claude Code for one of these programs, Claude writes
far less code, and spends fewer tokens, than it would in plain Python.

This plugin adds one Skill, `tokyn`, together with the Tokyn compiler. With it Claude writes the program in Tokyn,
checks it, tries it, and, if you want Python, hands you the Python file that the compiler generates. Compiler
messages are in English; the [`tokyn`](../tokyn) plugin is the same Skill in Italian.

## When to use it

Use it for programs that call Claude:

- AI agents, also with tools (your own Python functions) or other agents to delegate to;
- chatbots and assistants, in the terminal or behind your own code;
- extraction of structured data from text (invoices, emails, forms) and classification (tickets, reviews);
- batch jobs over many texts, through the Batch API at half price.

Do not use it for programs without AI, when you want a specific framework (the Anthropic SDK, LangChain…), or
when the code goes into a project written in a language other than Python: Tokyn compiles to Python only.

Claude uses the Skill by itself when you ask for a program that uses Claude or AI agents, when you mention Tokyn,
or when the project already has `.tokyn` files; adding "use tokyn" to the request makes sure. You can also call it
with `/tokyn-en:tokyn`.

## Install

In a Claude Code session:

```text
/plugin marketplace add DamianoCeka/tokyn
/plugin install tokyn-en@tokyn
```

## Requirements

- **Python 3.10 or newer.** Nothing to `pip install` for writing, checking and trying programs with fake answers:
  the compiler and the parsing library it uses ([lark](https://github.com/lark-parser/lark), MIT) are inside the
  plugin.
- **For real answers from the agents**, one of:
  - your **Claude Code login**, to try programs while you develop them (the `claude` command must be on the
    `PATH`; no API key needed);
  - an **Anthropic API key** in `ANTHROPIC_API_KEY`, plus the SDK: `pip install "anthropic>=0.108"`. This is the
    way for programs that run on their own or for other people (see [the rule below](#claude-code-login-or-api-key)).

## Example prompts

- *Write a Python script that reads `reviews.txt` and, for each review, gives the sentiment and a score from 1 to 5,
  then prints the average score. Try it for real and give me the Python file too. Use tokyn.*
- *Make a customer-support assistant for the terminal that looks up answers in `faq.txt` with a tool and remembers
  the conversation. Use tokyn.*
- *Extract supplier, date, line items and total from `invoice.txt`, recompute the total from the line items and
  tell me whether it matches. Use tokyn.*
- *Sort the support emails in the `inbox/` folder into technical, sales and other, using the cheapest model, and
  write the result to `sorted.json`. Use tokyn.*

## How it works

1. **Claude writes the program in a `.tokyn` file** in your project. For example:

   ```
   type Ticket:
       category: "technical" | "sales" | "other"
       urgent: bool "True if the customer cannot work"

   agent Triage:
       model: "claude-haiku"
       instructions: "Classify the customer's request."
       output: Ticket

   main:
       t = Triage.ask(input("How can I help? "))
       print(t.category, t.urgent)
   ```

2. **It checks the program and tries it for free**, with fake answers:
   `python <skill folder>/tokyn_cli.py run file.tokyn --mock`. Errors come with line, column and the fix, and
   Claude corrects them until the program runs.
3. **It runs the program with real answers** (`run file.tokyn --usage`, which also prints the tokens spent):
   through your Claude Code when there is no API key, or through the Anthropic API when `ANTHROPIC_API_KEY` is set.
   If the program makes many calls, Claude tells you first.
4. **If you want Python, it hands you the file the compiler generates**:
   `build file.tokyn --standalone -o file.py`. It is a single file that does not need Tokyn (with an API key it
   only needs `pip install anthropic`). The `.tokyn` file stays next to it as the source to edit.

## What this plugin runs and sends

**What is in the plugin.** The Skill instructions (`SKILL.md`), the Tokyn compiler and runtime as Python source
(`skills/tokyn/tokyn/`), a launcher (`skills/tokyn/tokyn_cli.py`), an unmodified copy of lark 1.3.1
(`skills/tokyn/vendor/lark/`, used only when lark is not installed), the license and the icon. There are no hooks,
MCP servers, commands, agents or binaries: nothing runs when you install the plugin or start a session.

**What runs.** Claude runs the launcher with its Bash tool (`python …/tokyn_cli.py check`, `run` or `build`), so your
Claude Code permission settings apply to every command. `check` and `build` only read your `.tokyn` file and, for
`build`, write the `.py` file. `run` compiles the program and runs it in a local Python process, with your user's
permissions.

**What is sent when agents answer.** With `--mock`, nothing. Otherwise, for each question, the agent's
instructions, the question, the earlier turns when the agent has `memory: True`, the description of its tools and
their results, and the output format are sent to Anthropic in one of two ways:

- **Without an API key, through your Claude Code.** Tokyn starts `claude -p` with your login. For that call it
  switches off Claude Code's own tools, settings files, slash commands and other MCP servers, and the session is
  not saved. If the agent has tools, Tokyn writes a small MCP bridge script to a temporary folder (deleted after
  the call) and listens on a random port of `127.0.0.1`, protected by a random token, so that the tools run inside
  your program.
- **With `ANTHROPIC_API_KEY`, through the Anthropic API**, with the official `anthropic` Python SDK: the Messages
  API, the Message Batches API for `ask_all`, and, on the models that support it, the server-side fallback beta
  (if a model refuses, the API retries on another one).

**What your programs do.** The programs Claude writes are ordinary programs. `read_file`, `write_file` and
`append_file` use your files, `http_get` and `http_post` call the URLs the program names, `env` reads environment
variables, and `import` gives access to any Python module. These run for real also with `--mock`, so when a
program writes files or calls URLs, read it before running it.

**Nothing else.** Tokyn has no telemetry or analytics, checks for no updates, downloads nothing and never installs
packages.

## Claude Code login or API key

Anthropic's [terms for Claude Code](https://code.claude.com/docs/en/legal-and-compliance) say that signing in with
a Claude subscription is meant for ordinary use of Claude Code, while developers of products or services, including
programs that serve other people, must use an API key from the [Claude Console](https://platform.claude.com/).

In practice:

- **Trying your programs through your Claude Code while you develop them is fine.**
- **A program that runs on its own** (on a server, as a scheduled job) **or for other people** (a bot, a web
  service) **must use `ANTHROPIC_API_KEY`.** Do not put online a program that answers through your Claude Code
  login.

When Tokyn chooses Claude Code by itself, because there is no API key, it prints this notice once:

```text
Tokyn: without an API key the agents answer through your Claude Code. That is fine for trying the program; if it
has to run on its own or for other people, it needs an Anthropic API key (https://code.claude.com/docs/en/legal-and-compliance).
```

When `ANTHROPIC_API_KEY` is set, Tokyn uses the API. You can also choose with `--backend api` or
`--backend claude-code` (or the `TOKYN_BACKEND` variable).

## Troubleshooting

- **`python: command not found`.** Install Python 3.10 or newer; where only `python3` exists, the same commands
  work with `python3`.
- **"ANTHROPIC_API_KEY is not set".** There is no API key and the `claude` command was not found (or you chose
  `--backend api`). Set the key, or install Claude Code and log in, or try the program with `--mock`.
- **"Claude Code did not answer for agent …".** Open `claude` once and complete the login, then try again.
- **"the anthropic package is missing".** Only needed with an API key: `pip install "anthropic>=0.108"`.
- **"agent … did not finish within 10 steps".** The agent needed more tool calls: raise `max_steps` in the agent or
  make its instructions more precise.
- **"input() got no line".** The program reads from the keyboard: pass the answers one per line, for example
  `printf 'hello\nquit\n' | python …/tokyn_cli.py run file.tokyn --mock`.
- **`ask_all` takes minutes.** It uses the Batch API: half price, but usually minutes and at most 24 hours. For a
  few texts, or when you need the answers right away, use a loop of `ask`. Through Claude Code, `ask_all` sends the
  texts one at a time.
- **Messages in Italian.** This plugin prints messages in English unless `TOKYN_LANG=it` is set; unset it, or set
  `TOKYN_LANG=en`.

## License and links

Tokyn is released under the [MIT license](LICENSE). The copy of lark in `skills/tokyn/vendor/lark/` keeps its own
MIT license.

- Source code and documentation: <https://github.com/DamianoCeka/tokyn>
- Full language specification: [`skills/tokyn/tokyn/SPEC.en.md`](skills/tokyn/tokyn/SPEC.en.md)
- Bugs and questions: <https://github.com/DamianoCeka/tokyn/issues>
