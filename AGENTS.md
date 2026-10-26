# smartsupp-skills — instructions for agents

Agent skills that turn Smartsupp live-chat conversations (read through the Smartsupp
MCP server) into knowledge-gap articles, CX scores, topics, contradictions, feedback
drafts, product info gaps and a weekly pulse. The skills follow the open
[Agent Skills](https://agentskills.io) format and work in any harness that loads
`SKILL.md` folders: Claude Code, Codex, pi, Gemini CLI and others.

## Layout

| Path | What |
|---|---|
| `skills/<skill>/SKILL.md` | The skills: YAML front matter (`name`, `description`), then instructions. Optional `scripts/` and `references/`. |
| `skills/smartsupp-conversations/` | The shared first step (fetch → sessions → redaction → digest) and the scripts every other skill uses: `normalize.py`, `redact.py`, `digest.py`, `insights.py`, `leakcheck.py`. |
| `pipeline/` | One optional way to run everything unattended: a weekly script for the pi coding agent. |
| `docs/` | Longer guides, e.g. `docs/self-improving-loop.md`. |
| `.claude-plugin/` | Claude Code plugin and marketplace manifests. |
| `.codex-plugin/`, `.agents/plugins/marketplace.json` | Codex plugin manifest and marketplace. |
| `gemini-extension.json` | Gemini CLI extension manifest. |
| `package.json` | pi package manifest (`pi.skills`). |

## Using the skills

1. Run `smartsupp-conversations` first. It creates a workspace
   (`./smartsupp-insights/<window>/`) containing `sessions.redacted.jsonl` and `digest.txt`.
2. Run the analysis skills on that workspace. Each one writes `<ws>/results/<skill>.json`,
   plus `.md` when the output is meant for people. `weekly-pulse` runs last and reads the
   other results.
3. The scripts are Python 3, standard library only. Run them with `python3`. Paths in a
   `SKILL.md` are relative to that skill's folder.
4. Get numbers from `scripts/insights.py` instead of counting yourself. Finish every
   output with `insights.py check`, which runs the leak check.

## Harness notes

- **Tool names.** The skills name the Smartsupp MCP's own tools (`search_conversations`,
  `get_conversation`, `list_messages`, `list_tags`, `get_contact`, `get_statistics`).
  Harnesses show them with their own prefix, e.g. `mcp__smartsupp__search_conversations`
  in Claude Code. Use whatever name your harness exposes for the same tool.
- **Read-only.** Only the read tools above are needed. Never call `send_message`,
  `close_conversation`, `assign_operator` or tag-writing tools unless the user asks for
  exactly that. `cx-score` can tag sessions, but only on request.
- **Batching.** If your harness can call tools in parallel or from a script, fetch
  conversations in batches. Otherwise, fetch them one by one; the output is the same.
- **No skill tool?** Read the relevant `skills/<skill>/SKILL.md` and follow it.

## Personal data

Chat transcripts contain customers' personal data. Analysis reads only the redacted
digest. Anything written for people must pass the personal-data gate in
`skills/smartsupp-conversations/SKILL.md`, and `leakcheck.py` must pass. Never publish
or send anything (knowledge base, Slack, tickets, Smartsupp writes) unless the user asks
and names the destination.

## Maintaining the skills

- Keep skill text harness-neutral. Describe actions ("fetch", "read", "write a file"),
  not one harness's tool names. When a step really differs per harness, say so
  explicitly for each harness.
- Keep scripts dependency-free (Python 3 standard library).
- Examples in skills and code comments must be fictional and neutral. Never paste real
  customer data, real shop names or transcript excerpts.
- When you change the plugin version, bump it in every manifest:
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `.codex-plugin/plugin.json`, `gemini-extension.json` and `package.json`.
