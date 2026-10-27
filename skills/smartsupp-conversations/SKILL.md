---
name: smartsupp-conversations
description: Fetch Smartsupp conversations through the smartsupp CLI or the Smartsupp MCP and turn them into clean, session-level transcripts with personal data redacted. Use as the first step of any Smartsupp analysis (CX score, topics, knowledge gaps, contradictions, feedback, product info gaps, weekly pulse), or when asked to "pull/export Smartsupp chats".
---

# Smartsupp conversations → clean sessions

Paths below are relative to this skill's folder (`<this skill>`); the other
Smartsupp insight skills sit next to it, so from them this folder is
`../smartsupp-conversations/`.

Every other Smartsupp insight skill reads the files this skill produces. Run it once
per analysis window; re-use the workspace if it is already fresh.

## Workspace

Default `./smartsupp-insights/<window-id>/` (window id e.g. `2026-W41` or
`2026-10-01_2026-10-10`). Layout:

```
raw/<conversation_id>.json        compact conversation dumps (step 1)
contacts/<contact_id>.json        contact records (step 1)
sessions.jsonl                    one record per chat session (step 2)
sessions.redacted.jsonl           same, personal data replaced by [TYPE] placeholders (step 3)
digest.txt                        compact readable view of the redacted sessions (step 4)
manifest.json                     window, counts, account/domain info, skipped items
results/                          outputs of the analysis skills
```

Use one workspace per window. Never fetch a different window into an existing
workspace: its `raw/` would keep the other window's conversations.

## Step 0 — choose the route

The data comes either from the `smartsupp` CLI (straight to disk, see the
`smartsupp-cli` skill) or from the Smartsupp MCP (Step 1). Check `SMARTSUPP_ROUTE` in the
environment:

- `mcp` → go to Step 1.
- `cli` → use the CLI below; if `smartsupp` is missing or the check fails, stop and
  tell the user.
- `auto` or unset → run
  `smartsupp auth check --scopes conversations:read,contacts:read,tags:read`:
  - exit 0 → CLI;
  - exit 2, or `smartsupp` not found → Step 1 (MCP);
  - exit 1 → tell the user what failed, then Step 1 (MCP).

CLI route — one command does all of Step 1 (exclusion tags, paging, contacts, manifest):

```
smartsupp conversations +fetch --from YYYY-MM-DD --to YYYY-MM-DD --ws <ws>
```

Add `--status open` or `--status all` if the user wants in-progress chats. It prints
counts only and records `"route": "cli"` in `manifest.json`. If `+fetch` exits non-zero
mid-run, run the same command once more (it resumes from what is on disk); if it fails a
second time, report the error to the user and stop. Then skip to Step 2. Never
read, print or edit the CLI's config file, and never set its variables yourself.

## Step 1 — fetch via MCP

How the MCP returns data (fields, roles, ratings, the AI-agent visibility gap) is in
`references/smartsupp-data-model.md` — read it once. Tool names below are the Smartsupp
MCP's own; your harness may show them with a server prefix (in Claude Code, e.g.
`mcp__smartsupp__search_conversations`). Only the read tools named here are needed. Key point: conversations the AI
agent is still handling are invisible to `search_conversations` until closed, so
analyse closed conversations.

1. `search_conversations` with `finished_at_from`/`finished_at_to` for the window
   (ISO 8601) and `limit: 100`; follow the `after` cursor until it is null. Also run
   it with `status: "open"` if the user wants in-progress chats (default: closed only).
2. Skip conversations tagged with an exclusion tag (ask `list_tags`; names like
   `eval-exclude`, `exclude_from_cx`, `spam`, `test`).
3. For each conversation call `get_conversation` (messages included; if
   `messages.after` is not null, page the rest with `list_messages`). Write a
   **compact** JSON file `raw/<id>.json` keeping only:
   `id, created_at, finished_at, status, channel, domain, contact_id, rating_value,
   rating_text, tags, messages.items[] {created_at, type, sub_type, agent_id,
   trigger_id, trigger_name, page_url, content{type, text, data}, attachments}`.
   Drop `variables` — they are integration data, not conversation content.
4. For each distinct `contact_id` call `get_contact` and write `contacts/<id>.json`
   with `{id, name, email, phone}` only. These values are used for redaction and must
   never appear in any output.
5. Work in batches if your harness can call tools in parallel or from a script; otherwise
   fetch one by one. Write files as you go.
6. Write `manifest.json` with the window, counts, skipped items and `"route": "mcp"`.

## Step 2 — sessions

```
python3 <this skill>/scripts/normalize.py <ws>/raw <ws>/sessions.jsonl
```

Smartsupp keeps one conversation per visitor and reopens it for every new chat, so
the script splits conversations into **sessions** at each `chat_close` event and
labels each message with a role: `customer`, `operator` (human agent), `ai_agent`
(the AI chatbot), `bot` (rule-based automation), `system`. Ratings
(`rate_form`) attach to the session they rate. `stats.handover` is true when a human
replied after the AI agent.

Check the output once: if AI-agent replies show up as `operator` or `other`, look at
the raw `sub_type`/`trigger_name` of those messages and fix the role mapping
(`ROLE` / `role_of` in normalize.py) before continuing.

## Step 3 — redact (layer 1, deterministic)

```
python3 <this skill>/scripts/redact.py <ws>/sessions.jsonl <ws>/sessions.redacted.jsonl --contacts <ws>/contacts --kb <ws>/kb [--order-pattern 'REGEX']
```

Replaces emails, phones, IBAN/account/card numbers, birth numbers, company IDs,
order/invoice/contract numbers, street addresses, names after courtesy titles or
self-introductions, and the contact's own name (all inflected forms), email and
phone. Pass `--order-pattern` when the shop's order numbers have a known format.

## Step 4 — digest

```
python3 <this skill>/scripts/digest.py <ws>
```

Writes `<ws>/digest.txt`: one header line per session (id, start, status, who started it,
`handled_by`, handover, rating, page, domain), then one line per message — `C` customer,
`A` AI agent, `O` operator — with seconds since the first message. About half the size of
`sessions.redacted.jsonl`. All analysis skills read `digest.txt` (and
`sessions.redacted.jsonl` only for a field the digest leaves out), never the raw files.

## Working efficiently (all analysis skills)

Every extra turn re-sends everything read so far, so:
- Read `digest.txt` once, in as few reads as possible. Do not write your own dump,
  pretty-print or counting scripts.
- Numbers come from `scripts/insights.py`: `cx-summary` (cx-score.md), `topic-stats`
  (fills `stats` in topics.json and prints the table), `pulse-metrics` (every weekly-pulse
  number, ties marked). Judge, then let the script count.
- Write each output file in one step. Finish with
  `python3 <this skill>/scripts/insights.py check <ws> <files>` — it validates the JSON,
  checks every cited session id exists, rejects `[PLACEHOLDER]` tokens and runs the leak
  check below.

## Layer 2 — the personal-data gate on outputs

Pattern matching cannot see everything (a colleague's name, an employer, a
diagnosis, an amount tied to someone's case). So every artifact that leaves the
workspace — article drafts, digests, feedback items, quotes — must pass this gate
before it is written:

1. **Remove** anything that identifies or describes a specific person or case:
   names (customers, third parties), employers and company names of customers,
   addresses, contact details, order/invoice/contract numbers, account or ID numbers,
   dates or amounts tied to one person's situation, health, family, financial or
   legal circumstances of an individual, and `[PLACEHOLDER]` tokens.
2. **Keep** what is true for every customer: the business's own products, prices,
   policies, procedures, opening hours, legal rules, staff roles (not needed: staff
   names).
3. **Abstract** a personal case into the general rule it illustrates ("an employee
   on sick leave was dismissed" → "dismissal during sick leave"), or drop it if no
   general rule exists (e.g. "your parcel arrives tomorrow at 10").
4. Then run the deterministic leak check:
   ```
   python3 <this skill>/scripts/insights.py check <ws> <file-to-publish>...
   ```
   (runs `leakcheck.py` after the format checks). It fails if any contact name/email/phone or any value redacted in step 3 appears
   in the files. Fix and re-run until it passes.

## Output conventions for analysis skills

- **Several businesses in one account.** One Smartsupp account can serve several
  websites, brands or business lines. Detect them from `domain` and page paths
  (`pages`) plus content, and keep them apart: add a `business` field to every
  finding and never merge findings across businesses.
- **Language.** Write customer-facing text (articles, product copy, ticket drafts)
  in the language the business uses with most customers; keep numbers, units and
  prices exactly as written in the source. Analytical notes may be in English.
- **Missing optional inputs** (e.g. no `cx-score.jsonl`, no `kb/`): proceed, say in
  the output which inputs were missing, and leave the dependent fields `null`.
- Results go to `<ws>/results/<skill>.json` (machine-readable) and, if the skill
  produces something for people, `<ws>/results/<skill>.md`.
- Every finding cites evidence as `session_id`s so it can be checked and traced.
- Quotes are paraphrased or taken from the redacted text, max ~20 words each.
