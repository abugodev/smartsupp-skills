---
name: smartsupp-cli
description: Use the `smartsupp` command-line tool for the Smartsupp REST API — setup, the route check, every command, search and statistics flags, the write switch. Use when the user mentions the "Smartsupp API" or the "smartsupp CLI", wants to "search Smartsupp conversations with filters", needs "Smartsupp statistics by domain/agent", asks about "visitors", "office hours" or the "domain whitelist", or when another Smartsupp skill picks the CLI route.
---

# smartsupp CLI

`smartsupp` is a command-line client for the Smartsupp REST API
(`https://api.smartsupp.com/v2`). `conversations +fetch`, and any command run with
`--out FILE`, write the data straight from the API to disk, so it does not pass through the
conversation; other commands print the API's JSON to stdout. It is optional: without it
the other skills use the Smartsupp MCP.

## Rules

- **Never read, print or edit the config file** (`~/.config/smartsupp-cli/.env`, or
  `$XDG_CONFIG_HOME/smartsupp-cli/.env`). Only the user edits it.
- **Never set `SMARTSUPP_ALLOW_WRITES` or `SMARTSUPP_API_TOKEN` inline**, export them, or
  pass them to a command in any other way. Turning writes on is the user's decision.
- Never print, echo or log the token. The CLI never shows it; keep it that way.
- **Every token has full access to the account.** The Smartsupp dashboard offers no scope
  choice when you create a token, so a token cannot be made read-only. The write switch
  guards against accidents, not against a deliberate misuse.
- The output of `contacts get`, `contacts find`, `visitors get` and
  `conversations get --messages` contains personal data. Don't paste it into results,
  reports or chat. For analysis use `conversations +fetch` and the
  `smartsupp-conversations` pipeline, which redacts it.

## Install and set up (the user does this once)

```bash
uv tool install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"
# or
pipx install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"

smartsupp auth setup
```

`auth setup` asks for the API token (Smartsupp dashboard → API Tokens) on the terminal
and stores it in the config file with mode `0600`. It never takes the token as an
argument. The user runs it in their own terminal, not through the agent.

Variables (process environment first, then the config file):

| Variable | Meaning |
|---|---|
| `SMARTSUPP_API_TOKEN` | API token. Required for every command except `schema` and `--help`. |
| `SMARTSUPP_ALLOW_WRITES` | `1` turns write commands on. Anything else, or missing, means off. |
| `SMARTSUPP_ROUTE` | `auto` (default), `cli` or `mcp`. Read by the skills from the environment, not by the CLI. |
| `SMARTSUPP_API_URL` | Override the base URL (for tests). |

## The route check

Skills that can use either route decide like this:

1. `SMARTSUPP_ROUTE=mcp` → use the MCP.
2. `SMARTSUPP_ROUTE=cli` → use the CLI; if the check below fails, stop and tell the user.
3. `auto` or unset → run `smartsupp auth check --scopes <scopes the skill needs>`:
   - exit 0 → CLI;
   - exit 2, or `smartsupp` not found → MCP;
   - exit 1 → report the error to the user, then use the MCP.

`auth check` makes one cheap read per scope and prints only `{"ok": true}` or the
scopes that failed. Default scopes: `conversations:read,contacts:read,tags:read` (what
`+fetch` needs). Statistics need `statistics:read`.

## Commands

Shape: `smartsupp <resource> <command> [ID] [flags]`. Ids are positional
(`smartsupp conversations get co123`). Output is the API's JSON on stdout; `--out FILE`
writes it to a file. `smartsupp schema` lists every command;
`smartsupp schema <resource> <command>` prints its endpoint, scope and fields (offline).

| Resource | Read | Write |
|---|---|---|
| `agents` | `list`, `get` | `update`, `ping` |
| `bots` | `trigger` | — |
| `contacts` | `get`, `find --email` | `create` |
| `conversations` | `get [--messages] [--paths] [--statistics]`, `find --ext-id`, `search`, `messages`, `tags`, `+fetch` | `create`, `update`, `assign`, `unassign`, `open`, `close`, `reply`, `rate`, `trigger-rating`, `typing`, `tag`, `untag`, `transcript` |
| `files` | — | `upload-token` |
| `messages` | `get`, `find --ext-id` | — |
| `oauth` | — | `access` |
| `settings` | `office-hours`, `domain-whitelist` | `set-domain-whitelist` |
| `statistics` | `query` | — |
| `tags` | `list` | `create`, `update`, `delete` |
| `visitors` | `get`, `paths` | `update`, `start-conversation`, `send-message`, `open-conversation`, `typing` |
| `auth` | `setup`, `check [--scopes]` | — |

`transcript` sends an email and `files upload-token` / `oauth access` create credentials,
so they count as writes. `oauth access --client-secret` takes a credential as an argument,
where it shows in shell history and in `--dry-run` output; prefer
`--json @file.json` with the secret in the file.

### Search

`smartsupp conversations search` builds the API's query from flags:

| Flag | Meaning |
|---|---|
| `--where FIELD=VALUE` | must match (repeatable; JSON values allowed) |
| `--not FIELD=VALUE` | must not match (repeatable) |
| `--any FIELD=V1,V2` | matches any of the values (repeatable) |
| `--finished FROM..TO`, `--created FROM..TO` | day range on `finished_at` / `created_at` (`YYYY-MM-DD` each) |
| `--sort FIELD:asc\|desc` | at most 3 |
| `--size N`, `--after JSON` | page size, cursor |
| `--timezone TZ` | timezone of the dates (default UTC) |
| `--page-all`, `--page-limit N` | follow the cursor, one JSON line per page; limit default 10, `0` = no limit |
| `--json '{…}'` or `--json @file.json` | raw request body; explicit flags override it |

The API returns a cursor only for a sorted search, so `--page-all` adds
`sort: [{"created_at": "asc"}]` when you give no sort (flags or `--json`); without
`--page-all` the body is left alone. Pass `--sort` to page in another order; an explicit
`"sort": null` in `--json` with `--page-all` exits 3.

At most 15 query clauses. Example:
`smartsupp conversations search --where status=closed --finished 2026-10-01..2026-10-07 --page-all`.

### Reply and visitor messages

`conversations reply` takes `--text` and/or `--html` (HTML allows only `a` and `br` tags),
`--sub-type agent|contact|bot`, and `--virtual-agent '{…}'`, a JSON object with the virtual
agent's identity. A reply needs text, HTML or attachments. `visitors send-message` and
`visitors start-conversation` need `--text`, `--attachments` or content supplied via `--json`.

### Statistics

`smartsupp statistics query`:

| Flag | Meaning |
|---|---|
| `--metric NAME[:FROM..TO]` | repeatable; `new_conversation`, `closed_conversation`, `response_time`, `first_response_time`, `time_to_close`, `time_to_close_sum`, `conversation_ratings` |
| `--from`, `--to` | `YYYY-MM-DD`, inclusive; give both or neither (exit 3 otherwise); used by metrics without their own range, so at least one `--metric` must lack one |
| `--group-by` | `day`, `week`, `month`, `year`, `day_of_week`, `hour_of_day`, or a field (e.g. `domain`, `agent_id`) |
| `--filter FIELD=VALUE` | applied to every metric (repeatable) |
| `--timezone TZ` | default UTC |
| `--json` | raw body, e.g. for a different filter per metric |

Example:
`smartsupp statistics query --metric new_conversation --metric first_response_time --from 2026-10-01 --to 2026-10-07 --group-by domain`.

As with the MCP's `get_statistics`, these counts appear to cover only conversations a
human operator took part in; label them "operator-handled".

### +fetch

```bash
smartsupp conversations +fetch --from YYYY-MM-DD --to YYYY-MM-DD --ws <ws> \
  [--status closed|open|all] [--exclude-tag NAME ...] [--timezone TZ]
```

Does step 1 of `smartsupp-conversations` in one command: writes `raw/<id>.json`,
`contacts/<id>.json` and `manifest.json` (`"route": "cli"`) into the workspace. Day
windows are UTC unless `--timezone` is given. Closed conversations by default;
`--status all` runs two searches — closed chats by `finished_at`, open chats by
`created_at` — and merges them. Exclusion tags default to `eval-exclude`,
`exclude_from_cx`, `spam`, `test`; a conversation carrying one is dropped even if the
search returns it, and counted as `excluded`. An exclusion tag that the account lists
without an id cannot be filtered on: `+fetch` prints a warning naming it and records it in
`manifest.json` as `excluded_tags_without_id`. It prints counts only (`found`, `fetched`, `resumed`, `skipped`, …): `resumed` counts
conversations already on disk with the same `finished_at`, which a re-run skips, and
`fetched` counts only those downloaded in this run.
`manifest.json` has `"complete": false` while the run is going and after an aborted run,
`true` when it finished. A new run keeps the earlier manifest as `manifest.previous.json`
(older ones become `manifest.previous.1.json`, `.2`, …) and never deletes it, so one
accumulates per re-run; remove old ones yourself when you no longer need them. Use one workspace per window — files from another window in the same `raw/`
would be mixed in.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | API error (after retries: 429, 5xx and, for reads only, network errors); short message on stderr |
| 2 | Token missing, invalid or rejected (401/403) |
| 3 | Bad arguments (including a resource with no subcommand) |
| 4 | Write blocked (`SMARTSUPP_ALLOW_WRITES` is not `1`) |

## Writes

Write commands work only when the user has set `SMARTSUPP_ALLOW_WRITES=1` in the config
file; otherwise they exit 4 and send nothing. Every write accepts `--dry-run`, which
prints the request it would send (token shown as `***`) and sends nothing — it works
while writes are off. Run `--dry-run` first and show it to the user. Make a write only
when the user asked for exactly that change. On exit 4, tell the user writes are off;
don't turn them on yourself. If the token is missing, the user runs `smartsupp auth setup`
in their own terminal.
