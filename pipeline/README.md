# Weekly run on pi (optional)

One way to run the skills unattended; it is not required. Any harness that loads
`skills/` can run the same steps (see `../docs/self-improving-loop.md` for Claude Code,
Codex, cron/launchd and GitHub Actions recipes).

`weekly-pi.sh` runs the whole Smartsupp insights pipeline unattended with the
[pi coding agent](https://pi.dev) (Homebrew build, `/opt/homebrew/bin/pi`):

1. **fetch** — one pi session (default `openai-codex/gpt-6.1-sol`) pages through the window
   with codemode scripts and writes `raw/`, `contacts/` and `manifest.json`. Only the read
   tools of the Smartsupp MCP are enabled (`--tools`): search, get conversation, list messages,
   list tags, get contact.
2. **prepare** — `normalize.py`, `redact.py` (with `--kb` when a knowledge export is given),
   `digest.py`.
3. **analyse** — one pi session (default `anthropic/claude-opus-5-5`) runs all seven skills in
   order; the only Smartsupp tool it can call is `get_statistics` (for weekly-pulse).
4. **check** — `insights.py check` over every output (JSON, session ids, placeholders, leak
   check), then a usage and cost line per session from pi's JSON events.

Nothing is posted anywhere: the post is written to `results/weekly-pulse.md` for review.

## Setup (once)

```bash
brew install pi-coding-agent
pi                                   # then /login: ChatGPT and/or Anthropic (or API keys)
pi mcp add smartsupp --url https://mcp.smartsupp.com/mcp
pi mcp login smartsupp               # browser sign-in to the Smartsupp account
pi mcp list                          # smartsupp: connected, 19 tools
```

## Run

```bash
pipeline/weekly-pi.sh                      # last full ISO week
pipeline/weekly-pi.sh --from 2026-10-05 --to 2026-10-11 \
    --kb path/to/knowledge-export --out ~/smartsupp-insights
```

Options: `--model` / `--fetch-model` (any `pi --list-models` id), `--thinking`.

## Fetching with the CLI (optional)

With the `smartsupp` CLI installed (see the root `README.md`: `uv tool install` or `pipx install` of the `cli` subdirectory) and a token configured
(`smartsupp auth setup`), the script fetches conversations itself with
`smartsupp conversations +fetch` and pre-fetches official statistics into
`statistics.json`. It then skips the pi fetch session, so fetching costs no model tokens
and happens outside any agent session. The analyse session is started with `SMARTSUPP_ROUTE=mcp`, which the skills honour (the CLI
itself ignores that variable), and with `SMARTSUPP_API_TOKEN` removed from its environment (a
prompt-level guard, not enforced against a deliberately misbehaving agent: the config file
stays readable). It drops the
`get_statistics` tool and weekly-pulse reads `statistics.json`. If the CLI fetch fails the
run stops (no mid-run fallback to the MCP route). The summary line `fetch: cli` or
`fetch: mcp` shows which route was used. Without the CLI (or without a token) the MCP
route above is used unchanged; when the CLI is installed but `auth check` fails, the script
prints the exit code of the check and uses the MCP route.

Run one job at a time when using subscription logins: parallel pi runs can deadlock on the
credential refresh.
