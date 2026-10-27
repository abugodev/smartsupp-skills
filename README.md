# Smartsupp skills

Agent skills that read your Smartsupp live-chat conversations and turn them into work
your team can act on. The main output is **knowledge-gap articles**: short,
ready-to-paste texts for your Smartsupp AI chatbot's knowledge, written from the answers
your human operators already gave.

The skills use the open [Agent Skills](https://agentskills.io) format (`SKILL.md`
folders with a few dependency-free Python scripts). They run in any harness that loads
skills:
- **Claude Code** and **Codex**, as a plugin;
- **Gemini CLI**, as an extension;
- **pi**, as a package;
- any other agent, by copying the `skills/` folder.

- [The problem](#the-problem)
- [How it works](#how-it-works)
- [Install](#install)
  - [Claude Code](#claude-code)
  - [Codex](#codex)
  - [Gemini CLI](#gemini-cli)
  - [pi](#pi)
  - [Other harnesses](#other-harnesses)
  - [Optional: the smartsupp CLI](#optional-the-smartsupp-cli)
- [The skills](#the-skills)
- [Self-improving loop](#self-improving-loop)
- [Privacy](#privacy)
- [Repository layout](#repository-layout)
- [Smartsupp documentation](#smartsupp-documentation)
- [Licence](#licence)

## The problem

An AI chatbot is only as good as its knowledge, and that knowledge drifts out of date.
Prices change and policies get updated. Customers ask questions nobody wrote down.
Operators then answer the same questions by hand, and the chatbot keeps handing chats
over, guessing, or quoting an outdated fact.

The answers already exist in your chat history. These skills find:

- **gaps:** what the chatbot could not answer, and what operators said instead;
- **drift:** where the chatbot, the operators and the knowledge base contradict each
  other.

They then draft the missing knowledge as short articles, with personal and one-off
details removed so that only knowledge true for every customer remains.

**Why copy-paste instead of auto-apply?** The Smartsupp MCP server has no tool to read or
write the AI chatbot's knowledge (custom Q&A, text sources, web sources). So the skills
write Markdown drafts, and an operator reviews them and pastes them into the chatbot's
knowledge in the Smartsupp dashboard. Nothing is published automatically.

## How it works

```
Smartsupp MCP (read tools)          local scripts                   skills                       outputs
───────────────────────────    ──────────────────────────    ───────────────────────    ─────────────────────────
search_conversations       →   normalize.py  (sessions)   →   cx-score               →   results/*.json  (data)
get_conversation               redact.py     (personal        topic-clusters             results/*.md    (people)
list_messages                                 data out)       knowledge-gaps             results/drafts/*.md
list_tags                      digest.py     (compact         contradiction-finder         (articles to paste)
get_contact                                   transcript)     feedback-drafts
get_statistics (pulse only)                                   product-info-gaps
                                                              weekly-pulse
```

1. **Fetch:** `smartsupp-conversations` pages through the closed conversations in a time
   window and writes compact JSON files to a local workspace
   (`./smartsupp-insights/<window>/`).
2. **Prepare:** deterministic Python scripts (standard library only) split conversations
   into chat sessions, label who wrote each message (customer, operator, AI agent, bot),
   redact personal data and write a compact digest.
3. **Analyse:** the analysis skills read only the redacted digest. They write
   machine-readable JSON plus Markdown for people, and every finding cites the session ids
   it rests on.
4. **Check:** before any output is written, a format and leak check validates it (see
   [Privacy](#privacy)).

With the optional [smartsupp CLI](#optional-the-smartsupp-cli) installed, step 1 runs as
one command over the Smartsupp REST API instead of the MCP tools above.

**Read-only by default.** The skills use the MCP's read tools only. They never send
messages, close, assign or change conversations. There is one opt-in exception:
`cx-score` can tag sessions `cx-1`…`cx-5`, but only when you ask for it. Any sending
(a weekly post to Slack, tickets to Linear or Jira) also happens only when you ask and
name the destination.

## Install

Every harness needs:
- **The Smartsupp MCP server** (`https://mcp.smartsupp.com/mcp`), connected and signed in
  to your Smartsupp account.
- **Python 3**, for the bundled scripts.

Installation differs by harness. If you use more than one, install separately for each.

### Claude Code

1. Connect the Smartsupp MCP server and sign in through the browser (see
   [Connect Smartsupp to Claude](https://help.smartsupp.com/en/articles/16002692)):

   ```bash
   claude mcp add --transport http smartsupp https://mcp.smartsupp.com/mcp
   ```

2. Install the plugin inside Claude Code:

   ```
   /plugin marketplace add abugodev/smartsupp-skills
   /plugin install smartsupp-insights@smartsupp-skills
   ```

### Codex

1. Connect the Smartsupp MCP server and sign in (per the
   [Codex MCP docs](https://developers.openai.com/codex/mcp)):

   ```bash
   codex mcp add smartsupp --url https://mcp.smartsupp.com/mcp
   codex mcp login smartsupp
   ```

2. Add this repository as a plugin marketplace and install the plugin:

   ```bash
   codex plugin marketplace add abugodev/smartsupp-skills
   codex plugin add smartsupp-insights@smartsupp-skills
   ```

   In Codex in the ChatGPT desktop app, the added marketplace also appears as a source in
   the Plugins Directory.

To keep Codex read-only towards Smartsupp, see the `enabled_tools` example in
[docs/self-improving-loop.md](docs/self-improving-loop.md#codex).

### Gemini CLI

1. Connect the Smartsupp MCP server as described in
   [Connect Smartsupp to Google Gemini](https://help.smartsupp.com/en/articles/16011665).
2. Install the extension. Gemini CLI discovers the bundled `skills/` automatically:

   ```bash
   gemini extensions install https://github.com/abugodev/smartsupp-skills
   ```

   Update later with `gemini extensions update smartsupp-insights`.

### pi

Install the skills as a [pi](https://pi.dev) package:

```bash
pi install git:github.com/abugodev/smartsupp-skills
```

Connect the Smartsupp MCP server in pi as shown in
[pipeline/README.md](pipeline/README.md#setup-once). That folder also has a ready-made
unattended weekly job for pi.

### Other harnesses

The skills are plain [Agent Skills](https://agentskills.io) folders. For any agent that
loads skills from a directory, copy (or symlink) the folders in `skills/` there:

- `~/.agents/skills/`: read by Codex, pi and Gemini CLI;
- `~/.claude/skills/`: Claude Code personal skills.

Then connect the Smartsupp MCP server in that agent.

```bash
git clone https://github.com/abugodev/smartsupp-skills
mkdir -p ~/.agents/skills && cp -R smartsupp-skills/skills/* ~/.agents/skills/
```

If your agent has no skill loader, point it at `AGENTS.md` and the relevant
`skills/<skill>/SKILL.md`: the instructions are self-contained.

### Optional: the smartsupp CLI

`smartsupp` is a command-line client for the
[Smartsupp REST API](https://docs.smartsupp.com/rest-api/get-started/), included in this
repository (`cli/`, Python 3.9+, no dependencies). When it is installed and has a token,
`smartsupp-conversations` fetches chats with one command and `weekly-pulse` reads the
statistics with it. The data goes straight to disk, so chat text and contact details do
not pass through your AI assistant on the way in, and fetching costs no model tokens.
Without it, the skills use the MCP as described above.

1. Install it with [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/):

   ```bash
   uv tool install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"
   # or
   pipx install "git+https://github.com/abugodev/smartsupp-skills#subdirectory=cli"
   ```

2. Create an API token in the Smartsupp dashboard (API Tokens), then store it. Run this in
   your own terminal; it asks for the token and never takes it as an argument:

   ```bash
   smartsupp auth setup
   smartsupp auth check
   ```

   The token is stored in `~/.config/smartsupp-cli/.env` (or
   `$XDG_CONFIG_HOME/smartsupp-cli/.env`) with mode `0600`. The variables are listed in
   [.env.example](.env.example).

**Every token has full access to your Smartsupp account.** The dashboard has no scope
choice when you create a token, so it cannot be made read-only. The CLI blocks every
write command (exit code 4) unless you add `SMARTSUPP_ALLOW_WRITES=1` to its config
file, and every write accepts `--dry-run`. The skills are told never to read the config
file or turn writes on, but this guards against accidents, not against an agent that
deliberately runs shell commands. Keep writes off unless you need them.

**Choosing the route:** by default (`SMARTSUPP_ROUTE=auto`) the skills run
`smartsupp auth check` and use the CLI when it passes, else the MCP. Set
`SMARTSUPP_ROUTE=cli` or `SMARTSUPP_ROUTE=mcp` in your shell environment to force one.
The `smartsupp-cli` skill documents every command.

**Using the skills:** ask in plain words, for example:
- *"find knowledge gaps in last week's Smartsupp chats"*;
- *"score CX for chats from 1 to 10 October"*;
- *"run the weekly pulse"*.

In Codex you can also mention a skill with `$`, e.g. `$knowledge-gaps`. The analysis
skills work on the workspace that `smartsupp-conversations` builds, so that skill runs
first for a new time window.

## The skills

All examples below are fictional.

### smartsupp-conversations

**Purpose:** fetch Smartsupp conversations and turn them into clean, session-level
transcripts with personal data redacted. This is the shared first step for every other
skill.

**Use when:** you start any analysis, or want to "pull/export Smartsupp chats".

**Input:** a time window (closed conversations whose `finished_at` falls in it).
Conversations with exclusion tags (e.g. `spam`, `test`) are skipped.

**Output:** a workspace with `raw/`, `contacts/`, `sessions.jsonl`,
`sessions.redacted.jsonl`, `digest.txt` and `manifest.json`. Smartsupp reopens one
conversation per visitor, so conversations are split into **sessions** at each
chat close. Session ids look like `coAbc123#0`.

```
=== coAbc123#0 | 2026-10-06 09:14 | closed | by customer | ai_and_operator | handover y | rating 5 | page /shipping | domain -
C 0: Do you deliver on Saturdays?
A 4: I don't have that information. Shall I connect you with a colleague?
C 20: yes please
O 95: Yes, Saturday delivery is available in larger cities for a small surcharge.
```

### smartsupp-cli

**Purpose:** how to use the optional `smartsupp` CLI: setup, the route check, every
command (agents, contacts, conversations, messages, visitors, settings, statistics, tags
and more), search and statistics flags, exit codes and the write switch.

**Use when:** "Smartsupp API", "smartsupp CLI", searching conversations with filters,
statistics by domain or agent, visitors, office hours, the domain whitelist.

```bash
smartsupp statistics query --metric new_conversation --from 2026-10-01 --to 2026-10-07 --group-by domain
```

### knowledge-gaps

**Purpose:** find what the AI chatbot could not answer and why chats were handed over to
humans. Then draft one help article per gap from the answers operators gave, keeping
only knowledge that holds for every customer.

**Use when:** "knowledge gaps", "what the bot didn't know", "handover reasons", "improve
the AI chatbot", "draft FAQ/knowledge from chats".

**Input:** `digest.txt`. Optional: the chatbot's current knowledge exported to `kb/*.md|txt`
(to skip questions it already covers) and `results/topics.json`.

**Output:** `knowledge-gaps.json`, `knowledge-gaps.md` and one Markdown draft per gap
in `results/drafts/<gap-id>.md`. **These drafts are what you paste into the chatbot's
knowledge.** Every question is classified as one of:

- `generalizable` (gets an article);
- `covered`, `account_specific`, `transient`, `personal_matter`, `feature_request` or
  `out_of_scope` (no article).

Each article is marked `confident` (an operator stated the rule in two or more sessions,
or once as an explicit general rule) or `borderline` (needs review). When operators gave
different answers, the article is marked `needs_review` with the conflicting statements.
Handover reasons are counted per session, e.g. `missing_knowledge`, `wrong_answer`,
`customer_requested_human` or `account_specific`.

```markdown
## Do you deliver on Saturdays?
Evidence: confident · 4 sessions · handover reason: missing_knowledge

Saturday delivery is available in larger cities for a surcharge, shown at checkout.
Orders placed by Friday noon arrive on Saturday. Elsewhere, parcels arrive on the next
working day.
```

### cx-score

**Purpose:** a survey-free customer-experience score, 1 (very negative) to 5 (very
positive), for every eligible closed chat session, read from the transcript itself, with
the reasons behind it. Scores of 4–5 count as positive.

**Use when:** "CX score", "customer satisfaction", "sentiment of chats", or as input for
topics and the weekly pulse.

**Input:** `digest.txt`. Optional: `kb/` and `results/contradictions.json`, used to build
a fact sheet so that confidently wrong AI answers are caught.

**Output:** `cx-score.jsonl` (one line per session) and `cx-score.md`. The summary has
the CX score %, the mean, a split by AI only / AI + operator / operator only, survey
coverage and agreement, and the top negative drivers. Individual operators are never
ranked.

```json
{"session_id": "coAbc123#0", "eligible": true, "score": 3,
 "reasons": {"answer_quality_ai": "poor", "answer_quality_operator": "good", "effort": "low",
             "emotion": "neutral", "product_feedback": "none", "policy_feedback": "none", "resolved": "yes"},
 "explanation": "The AI did not know about Saturday delivery; an operator answered correctly.",
 "handled_by": "ai_and_operator", "rating": 5, "rating_agrees": false}
```

### topic-clusters

**Purpose:** discover what customers talk about. The skill builds a two-level topic
taxonomy bottom-up from the conversations, with no predefined keywords, and assigns every
session to a topic, with volume and CX per topic. The taxonomy is saved and reused, so
topics stay stable week to week. If one account serves several businesses, they are kept
apart.

**Use when:** "topics", "what do customers ask about", "contact reasons", "drivers of
chat volume", or as input for the weekly pulse.

**Input:** `digest.txt`. Optional: `results/cx-score.jsonl` and an existing `taxonomy.json`.

**Output:** `topics.json` (taxonomy, assignment per session, stats), `topics.md` and the
updated taxonomy file.

```
| Topic                         | Sessions | Share | CX positive |
|-------------------------------|---------:|------:|------------:|
| Delivery                      |       38 |  27 % |        71 % |
|   └ Delivery days and times   |       17 |  12 % |        59 % |
|   └ Delivery countries        |       12 |   9 % |        75 % |
| Returns and exchanges         |       25 |  18 % |        80 % |
```

### contradiction-finder

**Purpose:** find places where the AI chatbot, the operators and the knowledge base say
different things about the same checkable fact (price, period, yes/no capability, rule).
For each one, decide the likely truth and name the source to fix.

**Use when:** "contradictions", "inconsistent answers", "AI said the wrong thing",
"outdated knowledge", "audit chatbot answers".

**Input:** `digest.txt`. Optional: the knowledge export `kb/`.

**Output:** `contradictions.json` and `contradictions.md`. Each contradiction has a
confidence of `high`, `medium` or `low` and a concrete fix.

```json
{"id": "free-shipping-threshold", "subject": "free shipping", "attribute": "minimum order",
 "claims": [{"value": "50 EUR", "speaker": "ai_agent", "sessions": ["coAbc123#0"]},
            {"value": "60 EUR", "speaker": "operator", "sessions": ["coDef456#1", "coGhi789#0"]}],
 "likely_truth": "60 EUR", "confidence": "high",
 "fix": "AI knowledge: the shipping FAQ still says 50 EUR"}
```

### feedback-drafts

**Purpose:** extract feature requests and product and policy feedback (complaints and
praise), group duplicates, count demand and draft destination-neutral tickets.

**Use when:** "feature requests from chats", "what customers ask us to add", "product
feedback", "complaints about our policies", "voice of customer".

**Input:** `digest.txt`. Optional: `results/cx-score.jsonl`.

**Output:** `feedback.json` and `feedback.md`. Feature requests are ranked by count ×
strength (mention, ask, demand, churn threat), followed by product feedback, policy
feedback and a short list of capability questions answered "no". Nothing is sent
anywhere unless you ask and name the destination (Linear, Jira, Notion, Slack, email…).

```markdown
### Deliver to Austria — feature request · 3 sessions · strength: ask
Problem: customers in Austria cannot order; two asked for an alternative carrier.
Evidence: coAbc123#0, coDef456#1, coGhi789#0
Next step: check carrier coverage and cost for Austria.
```

### product-info-gaps

**Purpose:** find which details of what a business offers customers keep asking about
in chat because the offering's page does not say them, and draft the missing page copy.
An offering can be a product, a room type, a plan, a package or a bookable service.
Prices, delivery and policies are knowledge gaps, not product info.

**Use when:** "missing product information", "what's missing on product pages", "PDP
gaps", "product questions from chat".

**Input:** `digest.txt`, which includes the page each customer wrote from. Optional:
product data `products/*` or `kb/`, used to tell a missing fact from a findability
problem.

**Output:** `product-info-gaps.json` and `product-info-gaps.md`: a table of product ×
attribute × count, then the suggested copy per gap. Gaps nobody answered are marked
`needs_input`.

```json
{"product": "trail-jacket", "attribute": "size-chart", "count": 5, "on_page": false,
 "example_questions": ["What size for 180 cm?", "Are the sleeves long?"],
 "suggested_copy": "Size chart: S 165–172 cm, M 172–180 cm, L 180–188 cm. Regular fit, sleeves cut long.",
 "status": "draft"}
```

### weekly-pulse

**Purpose:** a short, Slack-ready weekly customer-voice digest of 2,500 characters or
less. It covers headline numbers, the top parent topics with movers versus last week,
what hurt CX, what to fix next (top knowledge gaps, contradictions, product info gap)
and what customers asked for.

**Use when:** "weekly pulse", "weekly report of chats", "summary for the team", or a
scheduled weekly run.

**Input:** the week's workspace with the other skills' results (missing ones are run
first) and Smartsupp's statistics (through the CLI or `get_statistics`). Official statistics count only conversations a
human operator handled, so they are labelled "operator-handled". Total volume comes from
the transcripts.

**Output:** `weekly-pulse.md` (the post) and `weekly-pulse.json`. The post is shown to you
first and sent only when you ask and name the channel.

```markdown
**Chats this week: 142** · CX 74 % (▲ 3 pts) · AI only 41 % · AI + human 22 % · human only 37 %
**Top topics:** Delivery 27 % (CX 71 %) ▲ · Returns 18 % (CX 80 %) · Payments 11 % (CX 66 %)
**What hurt:** Saturday delivery questions the AI could not answer
**Fix next:** add the "Saturday delivery" article · fix the free-shipping threshold in the FAQ
**Customers asked for:** delivery to Austria (3)
```

## Self-improving loop

Run the skills every week and the chatbot improves each cycle:

1. fetch;
2. find gaps and contradictions;
3. a person reviews the drafts;
4. paste them into the chatbot's knowledge;
5. the next run shows whether the gap came back and whether CX moved.

[docs/self-improving-loop.md](docs/self-improving-loop.md) has practical recipes:
- a weekly job for Claude Code (`claude -p`, cloud or desktop scheduled tasks), Codex
  (`codex exec`), pi, cron, launchd and GitHub Actions;
- how to keep state between runs;
- guardrails: read-only MCP, redaction, human approval, cost caps;
- how to improve the skills from the results.

The [pipeline/](pipeline/README.md) folder is one ready-made option for pi.

## Privacy

Personal data is handled in layers:

1. **Deterministic redaction** (`redact.py`) replaces personal data with typed
   placeholders such as `[EMAIL]` or `[NAME]`. It covers:
   - emails and phones;
   - IBAN, account and card numbers;
   - national, personal and company IDs;
   - order, invoice and contract numbers;
   - street addresses and postcodes;
   - names after courtesy titles or self-introductions;
   - the contact's own name (including inflected forms), email and phone.
2. **Personal-data gate.** Every output must remove anything that identifies a specific
   person or case: names, employers, health, family or financial circumstances, and
   amounts tied to one case. Personal cases are abstracted into the general rule they
   illustrate, or dropped.
3. **Leak check** (`leakcheck.py`, run through `insights.py check`). It fails if any
   contact's name, email or phone, or any value redacted in step 1, appears in an output
   file. It ignores case, diacritics and spacing.

The workspace is a local folder; the plugin sends nothing to third parties. As with any
MCP connector, the data Claude fetches passes through your AI assistant as conversation
context (see Smartsupp's [MCP page](https://www.smartsupp.com/mcp/)); with the
[smartsupp CLI](#optional-the-smartsupp-cli) it goes straight to disk instead. The analysis
skills read only the redacted digest. Automated redaction can miss things, so review
drafts before you publish them.

## Repository layout

| Path | What |
|---|---|
| `skills/` | The nine skills (`SKILL.md` + `scripts/` + `references/`) |
| `cli/` | The optional `smartsupp` CLI for the REST API |
| `.env.example` | The CLI's config variables (names only) |
| `pipeline/` | Optional unattended weekly job for pi |
| `docs/` | Guides, starting with the self-improving loop |
| `AGENTS.md` | Instructions for agents using or maintaining the skills |
| `.claude-plugin/` | Claude Code plugin + marketplace manifests |
| `.codex-plugin/`, `.agents/plugins/marketplace.json` | Codex plugin manifest + marketplace |
| `gemini-extension.json` | Gemini CLI extension manifest |
| `package.json` | pi package manifest |

## Smartsupp documentation

- [Smartsupp MCP server](https://www.smartsupp.com/mcp/): what the MCP connector can do
- [Connect Smartsupp to Claude](https://help.smartsupp.com/en/articles/16002692): setup for Claude and Claude Code
- [Connect Smartsupp to Google Gemini](https://help.smartsupp.com/en/articles/16011665): setup for Gemini CLI
- [Connect Smartsupp to ChatGPT](https://help.smartsupp.com/en/articles/15996980): setup as a ChatGPT plugin
- [Developer quickstart: Smartsupp APIs](https://help.smartsupp.com/en/articles/16011742-developer-quickstart-smartsupp-apis): overview of APIs, data exports and the MCP connector
- [Smartsupp REST API: get started](https://docs.smartsupp.com/rest-api/get-started/)
- [Introduction to Mira AI Shopping Assistant](https://help.smartsupp.com/en/articles/12647224): Smartsupp's AI chatbot and its knowledge sources
- [How to train Mira AI](https://help.smartsupp.com/en/articles/12647700): custom Q&A, text and web sources. This is where knowledge-gap articles go.

## Licence

[MIT](LICENSE) © 2026 Abugo
