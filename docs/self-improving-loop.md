# Self-improving loop

The skills are most useful on a schedule. Each week the chatbot's misses become new
knowledge, and the next run checks whether that knowledge worked. This guide covers:

- the cycle;
- how to keep state between runs;
- scheduling recipes for each harness;
- the guardrails to keep in place;
- how to improve the skills themselves from what the runs show.

Every CLI flag below comes from the harness's official documentation or its `--help`.
Check them against your installed version.

- [The cycle](#the-cycle)
- [Keep state between runs](#keep-state-between-runs)
- [The weekly prompt](#the-weekly-prompt)
- [Schedule it](#schedule-it)
  - [Claude Code](#claude-code)
  - [Codex](#codex)
  - [pi](#pi)
  - [cron and launchd](#cron-and-launchd)
  - [GitHub Actions](#github-actions)
- [Guardrails](#guardrails)
- [Improve the skills from the results](#improve-the-skills-from-the-results)

## The cycle

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ 1. fetch        smartsupp-conversations: last week's closed chats, read tools   │
│                 only, personal data redacted                                    │
│ 2. analyse      contradiction-finder, cx-score, topic-clusters, knowledge-gaps, │
│                 feedback-drafts, product-info-gaps, weekly-pulse                │
│ 3. review       a person reads results/knowledge-gaps.md and the drafts:        │
│                 publish confident ones, check borderline / needs_review ones,   │
│                 fix the stale facts contradictions.md points at                 │
│ 4. publish      paste the approved articles into the Smartsupp AI chatbot's     │
│                 knowledge (custom Q&A or text sources) in the dashboard         │
│ 5. measure      next week's run: did the gap recur? did the AI answer that      │
│                 question alone? did the topic's CX score move?                  │
└───────────────────────────────── back to 1 ────────────────────────────────────┘
```

Step 4 is manual on purpose. The Smartsupp MCP server cannot read or write the chatbot's
knowledge, and a person should approve anything the chatbot will tell customers. For
where knowledge goes in Smartsupp, see
[How to train Mira AI](https://help.smartsupp.com/en/articles/12647700). It covers
custom Q&A pairs, text sources and web sources.

## Keep state between runs

The skills read earlier results when they find them. Keep one folder per week next to
each other:

```
smartsupp-insights/
├── taxonomy.json            topic-clusters reuses it, so topics stay stable week to week
├── kb/                      your current chatbot knowledge, exported as .md/.txt
├── 2026-W43/                last week's workspace (weekly-pulse compares against it)
│   ├── kb/ → ../kb          or a copy
│   └── results/
└── 2026-W44/                this week's workspace
```

- **Taxonomy.** `topic-clusters` saves `taxonomy.json` and reuses it on the next run. It
  proposes a new subtopic only when at least 3 sessions don't fit. That keeps topic
  shares comparable across weeks.
- **Previous week.** `weekly-pulse` uses the previous week's workspace, when it exists,
  for ▲/▼ movers and the CX change.
- **Knowledge export (`kb/`).** After you paste approved articles into Smartsupp, add
  them to your `kb/` export as well. On the next run, `knowledge-gaps` classifies those
  questions as `covered` and drafts nothing. If the AI still fails on them, it reports a
  retrieval or wording problem instead. `contradiction-finder` and `cx-score` also judge
  answers against `kb/`.
- **Did it work?** Session ids are per conversation and gap ids are per run, so
  comparing runs takes judgement. Ask your agent after the weekly run:

  > Compare `2026-W44/results/knowledge-gaps.json` with `2026-W43/results/knowledge-gaps.json`
  > and `kb/`. List gaps from last week that were published and still appear this week, and
  > for each, whether the AI now answered it alone. Then compare CX per parent topic in both
  > `topics.json` files. Write the result to `2026-W44/results/loop-check.md`. No personal data.

  A gap that keeps coming back after you published an article usually means the article's
  wording doesn't match how customers ask. Rewrite its title as the customer's question.

## The weekly prompt

All harness recipes below use the same instruction. Save it as
`smartsupp-insights/weekly-prompt.md`:

```markdown
Run the weekly Smartsupp insights for the last full ISO week (Monday–Sunday).

1. Use the smartsupp-conversations skill to fetch the closed conversations of that week into
   ./<YYYY-Www>/ (for example ./2026-W44/), using only the Smartsupp read tools
   (search_conversations, get_conversation, list_messages, list_tags, get_contact).
   Link or copy ./kb/ into the workspace as kb/ if it exists.
2. Then run these skills on that workspace, in this order: contradiction-finder, cx-score,
   topic-clusters (reuse ./taxonomy.json if present), knowledge-gaps, feedback-drafts,
   product-info-gaps, weekly-pulse (compare with the previous week's folder if present;
   get_statistics is allowed for this step).
3. Finish each skill with its insights.py check before starting the next.

Never send, close, assign or tag anything in Smartsupp. Do not post or publish anything.
At the end, list the files you wrote and anything in the skills that was ambiguous.
```

## Schedule it

Run the job where the Smartsupp MCP server is already connected and signed in. Smartsupp
documents a browser sign-in, so set the connection up once by hand on that machine or
account.

### Claude Code

Connect the MCP server once (from
[Connect Smartsupp to Claude](https://help.smartsupp.com/en/articles/16002692)), then
sign in when Claude Code asks:

```bash
claude mcp add --transport http smartsupp https://mcp.smartsupp.com/mcp
```

**Headless run** (`claude -p`). Use it from cron, launchd or a self-hosted CI runner:

```bash
cd ~/smartsupp-insights && claude -p "$(cat weekly-prompt.md)" \
  --permission-mode dontAsk \
  --allowedTools "Read,Write,Edit,Bash(python3 *),Bash(mkdir *),Bash(ln *),Bash(cp *),mcp__smartsupp__search_conversations,mcp__smartsupp__get_conversation,mcp__smartsupp__list_messages,mcp__smartsupp__list_tags,mcp__smartsupp__get_contact,mcp__smartsupp__get_statistics" \
  --disallowedTools "mcp__smartsupp__send_message,mcp__smartsupp__close_conversation,mcp__smartsupp__open_conversation,mcp__smartsupp__assign_operator,mcp__smartsupp__unassign_operator,mcp__smartsupp__tag_conversation,mcp__smartsupp__untag_conversation,mcp__smartsupp__create_tag,mcp__smartsupp__update_tag,mcp__smartsupp__delete_tag,mcp__smartsupp__send_transcript" \
  --max-budget-usd 30 \
  --output-format json > "run-$(date +%F).json"
```

- `--permission-mode dontAsk` denies every call that would otherwise prompt. Only what
  `--allowedTools` lists, plus actions that never need approval, can run.
- `--disallowedTools` blocks the Smartsupp write tools outright.
- `--max-budget-usd` caps API spend. It works only with `-p`.
- The `mcp__smartsupp__…` names assume you named the server `smartsupp`. If you use
  Smartsupp as a claude.ai connector instead, the tool names differ: check them with
  `/mcp` in an interactive session.
- The plugin must be installed for the user running the job. Don't add `--bare`: bare
  mode skips installed plugins and MCP servers and never reads stored OAuth credentials.

**Cloud scheduled task** (formerly routines): create one with `/schedule` in the CLI or at
[claude.ai/code/routines](https://claude.ai/code/routines), with a weekly schedule and
the weekly prompt.
- It runs on Anthropic's cloud with the connectors you include. Include Smartsupp (if
  you connected it as a claude.ai connector) and remove the others.
- A connector included in a scheduled task can also write. Keep the "never send, close,
  assign or tag" lines in the prompt.
- Results stay in the cloud session, so tell the task where they should go, e.g. "commit
  only results/*.md drafts to a private repository".
- See [Scheduled tasks](https://code.claude.com/docs/en/routines).

**Desktop scheduled task:** runs on your computer with your local MCP connection and
offers a Weekly trigger. See
[Desktop scheduled tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks).

### Codex

Install the plugin (see the README), then connect the MCP server and sign in:

```bash
codex mcp add smartsupp --url https://mcp.smartsupp.com/mcp
codex mcp login smartsupp
```

Make the connection read-only in `~/.codex/config.toml` (`enabled_tools` is an allow
list):

```toml
[mcp_servers.smartsupp]
url = "https://mcp.smartsupp.com/mcp"
enabled_tools = ["search_conversations", "get_conversation", "list_messages", "list_tags", "get_contact", "get_statistics"]
```

**Headless run** (`codex exec`):

```bash
cd ~/smartsupp-insights && codex exec --sandbox workspace-write --skip-git-repo-check \
  --json -o "last-message-$(date +%F).md" "$(cat weekly-prompt.md)" > "run-$(date +%F).jsonl"
```

- `--sandbox workspace-write` lets Codex write the workspace and nothing else. By
  default `codex exec` is read-only.
- `--skip-git-repo-check` is needed because the insights folder is not a Git repository.
  Alternatively, run `git init` there and add the workspaces to `.gitignore`.
- `--json` streams events, including token usage per turn, to stdout. `-o` writes the
  final message to a file.
- `codex exec` has no spending cap flag. Control cost through the model (`-m`) and the
  window size, and watch the `turn.completed` usage in the JSON output.

### pi

[`pipeline/weekly-pi.sh`](../pipeline/README.md) is a ready-made weekly job for the
[pi coding agent](https://pi.dev). It runs two sessions.
- **Fetch:** a session with only the Smartsupp read tools enabled through `--tools`.
- **Prepare:** the deterministic `normalize.py → redact.py → digest.py` step.
- **Analyse:** one session for all seven skills, which may call only `get_statistics`.
- **Check:** `insights.py check` over every output, plus a usage and cost line per
  session.

### cron and launchd

Wrap the harness command from above in a script, e.g. `~/smartsupp-insights/weekly.sh`.
Make sure it `cd`s into `~/smartsupp-insights` and uses absolute paths to the CLI.

**cron** (Monday 07:00):

```cron
0 7 * * 1  /Users/you/smartsupp-insights/weekly.sh >> /Users/you/smartsupp-insights/cron.log 2>&1
```

**launchd** (macOS; `~/Library/LaunchAgents/com.example.smartsupp-weekly.plist`, load it
with `launchctl load <path>`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.smartsupp-weekly</string>
  <key>ProgramArguments</key>
  <array><string>/Users/you/smartsupp-insights/weekly.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/Users/you/smartsupp-insights/launchd.log</string>
  <key>StandardErrorPath</key><string>/Users/you/smartsupp-insights/launchd.log</string>
</dict>
</plist>
```

launchd runs a missed job when the Mac wakes up; cron skips it.

### GitHub Actions

GitHub-hosted runners can't complete Smartsupp's browser sign-in, and chat data should
not land in a repository. So use a **self-hosted runner** on a machine where the harness
is installed and signed in to the Smartsupp MCP. Keep workspaces outside the checkout:

```yaml
name: Smartsupp weekly insights
on:
  schedule:
    - cron: "0 7 * * 1"
  workflow_dispatch:
jobs:
  weekly:
    runs-on: self-hosted
    permissions:
      contents: read
    steps:
      - name: Run the weekly job
        run: ~/smartsupp-insights/weekly.sh
```

This job calls the CLI you set up on the runner, so it doesn't need
`anthropics/claude-code-action` or `openai/codex-action`.

## Guardrails

| Guardrail | How |
|---|---|
| **Read-only MCP** | Claude Code: `--allowedTools` with only the read tools, `--disallowedTools` for the write tools, `--permission-mode dontAsk`. Codex: `enabled_tools` on `[mcp_servers.smartsupp]`. pi: `--tools` (see `pipeline/weekly-pi.sh`). Keep "never send, close, assign or tag" in the prompt for cloud runs. |
| **Redaction** | `smartsupp-conversations` redacts before any analysis. The analysis skills read only `digest.txt`. Every output must pass `insights.py check`, whose leak check fails on any contact name, email, phone or redacted value. |
| **Human approval** | Drafts stay drafts. Nothing is pasted into Smartsupp, posted to Slack or filed as a ticket without a person deciding to. `knowledge-gaps.md` lists `borderline` and `needs_review` articles separately. |
| **Cost caps** | Claude Code: `--max-budget-usd`. Codex: choose the model and keep the window to one week; read usage from `--json`. pi: the pipeline prints usage and cost per session. Keep the window to a week: cost grows with chat volume. |
| **Data handling** | Workspaces hold raw transcripts (`raw/`, `contacts/`, `sessions.jsonl`). Keep them on the machine that runs the job, never commit them, and delete old weeks you no longer compare against. Only `results/` is meant for people. |
| **Fail loudly** | Check the exit code. In `--json` / `--output-format json` output, look for errors before anyone reads the post. `weekly-pi.sh` exits 1 when a session or the check fails. |

## Improve the skills from the results

The runs show where the skills misjudge your chats. Turn that into skill changes:

1. **Collect evidence.** Every weekly prompt ends with "anything in the skills that was
   ambiguous". Keep those notes, plus the drafts reviewers rejected and why. Examples:
   an article built from one customer's case, a missed gap, a CX score that felt wrong.
2. **Find the rule.** Most fixes are a sentence in a `SKILL.md`, e.g. a class boundary in
   `knowledge-gaps` or a scoring rule in `cx-score`. Fix the rule, not one example. Keep
   examples fictional.
3. **Re-run on the same workspace.** The workspace is frozen, so re-running a changed
   skill on last week's folder shows the effect directly. Compare the outputs before and
   after.
4. **Keep it harness-neutral.** Describe actions, not one harness's tool names. Keep
   scripts on the Python standard library (see `AGENTS.md` → Maintaining the skills).
5. **Version and share.** Bump the version in every manifest. If the change helps
   everyone, open a pull request with the reasoning. Never include chat data.
