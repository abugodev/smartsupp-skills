# Smartsupp skills for Claude Code

A Claude Code plugin marketplace with skills that read your Smartsupp live-chat
conversations and turn them into things your team can act on, chiefly
**knowledge-gap articles** you can copy-paste into the Smartsupp knowledge base so the
AI chatbot answers what it could not answer before.

## Install

```
/plugin marketplace add abugodev/smartsupp-skills
/plugin install smartsupp-insights@smartsupp-skills
```

**Requirement:** a working connection to the Smartsupp MCP server
(`https://mcp.smartsupp.com/mcp`) in Claude Code, signed in to your Smartsupp account.
The skills only read from Smartsupp: they never send messages or close chats, and they
tag conversations only if you ask them to.

## What you get

The `smartsupp-insights` plugin contains these skills:

| Skill | What it does |
|---|---|
| `smartsupp-conversations` | Fetches closed conversations for a time window, splits them into chat sessions and redacts personal data (names, emails, phones, addresses, order and account numbers). All the other skills start from this. |
| `knowledge-gaps` | Finds what the AI chatbot could not answer and why chats were handed over to humans, then drafts one short article per gap from the answers your operators gave. Personal and one-off details are removed. **Main output:** Markdown articles to copy-paste into the Smartsupp knowledge base. |
| `cx-score` | Scores every chat 1–5 from the transcript itself, so you don't need a survey, and gives the reasons: answer quality, customer effort, emotion and feedback. |
| `topic-clusters` | Builds a two-level topic taxonomy from the chats and gives volume and CX score per topic. |
| `contradiction-finder` | Finds places where the AI chatbot, the operators and the knowledge base disagree, for example an outdated price, and names the source to fix. |
| `feedback-drafts` | Collects feature requests and product and policy feedback, counts demand and drafts tickets. |
| `product-info-gaps` | Finds details customers keep asking about because a product, room or plan page does not say them, and drafts the missing page copy. |
| `weekly-pulse` | A short, Slack-ready weekly digest: volume, CX, top topics, what hurt, what to fix next. |

Ask Claude in plain words, e.g. *"find knowledge gaps in last week's Smartsupp chats"*
or *"run the weekly pulse for 2026-W43"*. Results are written to
`./smartsupp-insights/<window>/results/`.

### Why copy-paste?

The Smartsupp MCP cannot write the AI chatbot's knowledge (text sources, custom
answers). The skills therefore produce drafts for you to review and paste into the
Smartsupp dashboard. Nothing is published automatically.

## Privacy

Transcripts are redacted with deterministic patterns first. Every output then goes
through a personal-data check and a leak check that fails if any contact's name, email
or phone, or any redacted value, appears in it. Review drafts before you publish them
anyway: automated redaction can miss things.

## Unattended weekly run (optional)

`plugins/smartsupp-insights/pipeline/` has a script that runs the whole pipeline
headless with the [pi coding agent](https://pi.dev). See its README.
