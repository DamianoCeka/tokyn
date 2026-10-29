# Tokyn privacy policy

Last updated: 2026-10-29

Tokyn is an open-source compiler, runtime and Claude Code plugin (`tokyn`, `tokyn-en`). It has no servers and no
accounts, and it collects nothing: no telemetry, no analytics, no usage statistics, no update checks.

## What runs where

- **The compiler** (`tokyn check`, `run --mock`, `build`) runs only on your computer and sends nothing anywhere.
- **When a Tokyn program runs for real**, each `Agent.ask(...)` sends the text the program passes to the agent, with
  the agent's instructions and tool descriptions, to the model you chose:
  - your own Claude Code (`claude -p`, with your login), when no API key is set;
  - the Anthropic API, when `ANTHROPIC_API_KEY` is set;
  - the provider named in the agent's `model` (for example OpenAI, Gemini, Mistral, DeepSeek, Groq, OpenRouter, xAI),
    or Ollama and other servers on your own machine.

  That data is handled under the privacy policy of the provider you chose. Tokyn does not keep a copy.
- **API keys** are read from your environment only when a program calls a model, and are sent only to that
  provider's API endpoint, over HTTPS. Tokyn never stores, logs or forwards them anywhere else.
- **Your own programs** may read files and call web addresses you write into them (`read_file`, `http_get`,
  `http_post`). That is your program's behaviour, not Tokyn's.

## Data retention

Tokyn retains nothing. Temporary files used to connect tools to Claude Code (a port, a one-time token and the tool
list) are deleted when each request ends.

## Children

Tokyn is a developer tool and is not intended for users under 18.

## Contact

Questions: open an issue at https://github.com/DamianoCeka/tokyn/issues.
