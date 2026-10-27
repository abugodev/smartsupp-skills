# smartsupp CLI

`smartsupp` is a command-line client for the
[Smartsupp REST API](https://docs.smartsupp.com/rest-api/get-started/). It covers every
endpoint of the API (v2), prints JSON, and needs only Python 3.9 or later — no
dependencies.

It is part of [smartsupp-skills](../README.md) and optional: the skills use it when it is
installed and has a token, and fall back to the Smartsupp MCP otherwise. With it,
`smartsupp conversations +fetch` downloads chats straight to disk, so chat text and contact
details don't pass through your AI assistant and fetching costs no model tokens.

## Install

```bash
uv tool install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"
# or
pipx install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"
```

From a clone, without installing: `PYTHONPATH=cli python3 -m smartsupp_cli --help`.

## Set up a token

1. Create a token in the Smartsupp dashboard:
   [Settings → API Tokens](https://app.smartsupp.com/app/dashboard/settings/api-tokens).
2. Store it. Run this in your own terminal; it asks for the token without showing it and
   never takes it as an argument:

   ```bash
   smartsupp auth setup
   smartsupp auth check
   ```

The token is kept in `~/.config/smartsupp-cli/.env` (or
`$XDG_CONFIG_HOME/smartsupp-cli/.env`) with mode `0600`. Environment variables override
the file; the names are listed in [.env.example](../.env.example).

**Every token has full access to your Smartsupp account** — the dashboard offers no
read-only tokens. Write commands are blocked (exit code 4) unless you add
`SMARTSUPP_ALLOW_WRITES=1` to the config file, and every write command accepts
`--dry-run` to show the request without sending it. Keep writes off unless you need them.

## Use

```bash
smartsupp schema                                   # every command
smartsupp conversations search --where status=closed \
  --finished 2026-10-01..2026-10-07 --sort finished_at:asc --page-all
smartsupp statistics query --metric new_conversation --from 2026-10-01 --to 2026-10-07 \
  --group-by day
smartsupp conversations +fetch --from 2026-10-01 --to 2026-10-07 --ws ./smartsupp-insights/2026-W40
smartsupp tags create --name vip --dry-run         # writes: preview first
```

Commands follow `smartsupp <resource> <method>` (agents, bots, contacts, conversations,
files, messages, oauth, settings, statistics, tags, visitors), plus `auth` and `schema`.
`--help` on any command shows its options; `smartsupp schema <resource> <method>` shows
the endpoint, parameters and required token scope.

Dates are whole days in UTC unless you pass `--timezone`. A `+fetch` re-run resumes where
it stopped and updates conversations that changed since; it never deletes data — files of
conversations that are now excluded, and earlier manifests, are moved aside.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | API or network error |
| 2 | Token missing or rejected |
| 3 | Bad arguments |
| 4 | Write blocked (writes are off) |

The full command reference, for people and AI assistants, is in
[skills/smartsupp-cli/SKILL.md](../skills/smartsupp-cli/SKILL.md).
