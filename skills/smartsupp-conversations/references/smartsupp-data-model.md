# How the Smartsupp MCP returns conversations

Observed on a live account (October 2026) with live chat, human operators and the
Mira AI agent. Treat as the working model; re-check when something looks off.

## Tools that matter

| Tool | Returns | Notes |
|---|---|---|
| `search_conversations` | `{items, total, after}` — conversation metadata, **no messages** | Filters: `status`, `created_at_*`, `finished_at_*`, `agent_id`, `tag_id`; `limit` ≤ 100; cursor `after` is an array, pass back verbatim. Newest first. |
| `get_conversation` | metadata + `messages.items` (newest first) | `include_messages=false` to skip messages; `messages.after` non-null → page with `list_messages`. |
| `list_messages` | `{items, total, after}` | `sort: asc|desc`. |
| `get_contact` | `{id, name, email, phone, properties, note, tags, gdpr_approved, …}` | Name/email/phone are set by the visitor, a pre-chat/contact form, or the website's JS API. |
| `get_statistics` | aggregated metrics | `new_conversation`, `closed_conversation`, `response_time`, `first_response_time`, `time_to_close`, `conversation_ratings`; `group_by` e.g. `day`, `rating_value`, `agent_id`. |
| `tag_conversation` / `create_tag` / `list_tags` | tagging | The only structured write-back for analysis results. |
| `send_message`, `close_conversation`, `assign_operator` | operator actions | `send_message` needs `agent_id` (sub_type agent) or `bot_id` (sub_type bot). |

There is **no** tool to read or write the AI agent's knowledge (text sources, web
sources, custom answers) — knowledge updates are a manual/dashboard step.

## REST API (the `smartsupp` CLI)

The CLI route reads the same data from the REST API (`https://api.smartsupp.com/v2`,
`Authorization: Bearer <token>`). The MCP appears to pass REST objects through, so the
conversation and message fields below are the same on both routes.

| Endpoint | CLI | Notes |
|---|---|---|
| `POST /conversations/search` | `conversations search` | Body `{query, sort, size, after, timezone}`. `query` is a list of clauses `{field, value, op}` (`op` omitted = must match, `must_not`, `or` with a list value), at most 15; a date clause takes a `[from, to]` range. `sort` is a list of `{field: "asc"\|"desc"}`, at most 3. Cursor `after` is an array, passed back verbatim. |
| `GET /conversations/{id}?messages=true` | `conversations get --messages` | Embeds at most the last 200 messages; a non-null `messages.after` means more. |
| `GET /conversations/{id}/messages` | `conversations messages` | Pages the rest. |
| `GET /contacts/{id}` | `contacts get` | Same contact object as `get_contact`. |
| `GET /tags` | `tags list` | Tag ids for exclusion. |
| `POST /statistics` | `statistics query` | Same metrics as `get_statistics`, plus filters and `group_by` on any field. |

The REST API also covers what the MCP does not: visitors, office hours, the domain
whitelist, lookups by your own external ids, and the full search query language.

## REST API (smartsupp-cli), verified 2026-10-27

Checked live against a test account:
- `POST /conversations/search` returns `after: null` unless the body has a `sort`, so paging
  without a sort silently stops after page 1 (`--page-all` adds `created_at` asc).
- Search clauses that work: `{"field":"status","value":"closed"}`,
  `{"field":"finished_at","value":[from,to]}` and `{"field":"tags","value":"<tag id>"}`, also
  with `op: "must_not"`. Tag ids are strings.
- `status=open` searches work; `status=pending` returns 0, so AI-handled pending chats are
  invisible, same as the MCP.
- One-day observation (2026-10-10), not an established rule: the REST statistics appeared to
  exclude AI-only chats too: `new_conversation` for that day was 272 while a `created_at`
  search for the same day found 452. Re-check before relying on it.
- `+fetch` output (`raw/`, `contacts/`) is identical to the MCP route's for a 10-conversation
  sample.
- A 443-conversation `+fetch` hit 2 transient network errors; the client now retries reads
  on those, and a re-run resumes anyway.
- Not tested live: paging the embedded message list past 200 messages (the largest
  conversation had 16).

## Visibility gap: AI-handled conversations

While the AI agent handles a chat, the conversation has `status: "pending"` and
**`search_conversations` does not return it** (not with `status: "pending"` either).
It becomes searchable once it is closed (by an operator, the API, or auto-close).
Consequences:
- Analyses should work on **closed** conversations (`finished_at` window).
- AI-only chats that are never closed stay invisible to the API. If AI-only volume
  looks too low, check the dashboard's open/pending list and the account's auto-close
  setting.
- `domain` is `null` on AI-handled conversations; use message `page_url` instead.

## Statistics vs. conversations

`get_statistics` counts (`new_conversation`, `closed_conversation`,
`first_response_time`) appear to cover only conversations a **human operator** took
part in: on the test account (2026-10-10) `new_conversation` was 129 while the transcripts
held 220 conversations, the AI-only ones missing. Use transcript counts for volume when an AI agent is live, and label the
official figure as "operator-handled".

## Conversation

```
id ("co…"), created_at, updated_at, finished_at (null while open), status
("open" | "pending" | "closed"), channel {type}, domain, referer, contact_id,
visitor_id, agent_ids[] (operators who took part), assigned_ids[], group_id,
rating_value (1|3|5 or null), rating_text, is_served, is_offline,
variables {} (custom data set by the website via JS API), tags {data:[{id}]},
location {country, city}
```

One conversation per **visitor**: when the same visitor chats again later, the same
conversation is reopened. Split into sessions at `chat_close` events.

## Message

```
id, created_at, type ("message" | "event"), sub_type, agent_id, trigger_id,
trigger_name, content {type, text, data}, attachments[], page_url,
is_reply, is_first_reply, response_time (s), is_offline
```

| Who | `type` | `sub_type` | Other markers |
|---|---|---|---|
| Customer | message | `contact` | `page_url` = page they wrote from |
| Human operator | message | `agent` | `agent_id` |
| AI agent (Mira) | message | `bot` | `trigger_id` = AI chatbot workflow id (`bo…`), `trigger_name` = workflow name |
| Rule-based automation | message | `bot` | `trigger_id` of the automation |
| Rating | message | `system` | `content.type = "rate_form"`, `content.data = {value, text, target}` (`target`: `agent` or AI) |
| Operator joined | event | `system` | `content.type = "agent_join"`, `data.agent_id` |
| Chat closed | event | `system` | `content.type = "chat_close"`, `data.close_type`: `agent_close`, `auto_close`, … |

Ratings: the visitor picks good / neutral / bad → `rating_value` 5 / 3 / 1. The AI
agent can be rated separately while it handles the chat.

## AI agent behaviour worth knowing for analysis

- It does not hand over silently: when it lacks knowledge it **offers** a human
  ("Chceš, abych tě přepojila na živou podporu?") and hands over only after the
  customer agrees. Many AI-only chats therefore end with an unanswered offer — count
  these as AI failures, not as resolved chats.
- Before handover it can ask for contact details (contact form), so handed-over
  conversations usually carry a contact name/email.
- It sometimes answers confidently from partial knowledge (e.g. guesses a size
  without a size chart) — answer quality must be judged, not assumed.
