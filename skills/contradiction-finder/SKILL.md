---
name: contradiction-finder
description: Find places where the Smartsupp AI agent, the human operators, and the knowledge base say different things — e.g. the AI quotes an old price or policy and a human corrects it. Use for "contradictions", "inconsistent answers", "AI said the wrong thing", "outdated knowledge", "audit chatbot answers".
---

# Contradiction finder

Wrong-but-confident answers hurt more than missing ones. This skill finds factual
conflicts and traces them to the source that needs fixing.

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently); optional knowledge export `<ws>/kb/*`.
**Output:** `<ws>/results/contradictions.json`, `<ws>/results/contradictions.md`.

## What counts

A contradiction is two statements about the same **checkable fact** (number, price,
period, yes/no capability, rule) that cannot both be true. Look for:

1. **Within a session:** the AI agent states something and an operator later states
   something different, or the customer points out a conflict ("the website says …")
   and it is confirmed.
2. **Across sessions:** the AI or operators answer the same question differently in
   different chats (e.g. "free delivery over 50 €" in one, "over 80 €" in another).
3. **In the knowledge base** (if kb/ is provided): two sources disagree, or a source
   disagrees with what operators consistently say.

Not contradictions: different answers because the situation differs (product A vs.
B, customer-specific circumstances), opinions, or a human adding detail the AI
didn't give (that is a knowledge gap, not a conflict).

If there are no `ai_agent` messages (e.g. the AI agent is not live yet), the run is
still valid: compare operators with each other and with the knowledge base / website
facts customers quote. Speakers are `ai_agent`, `operator`, `knowledge_base` (cite
the file and section) or `customer_citing_website`.

## Process

1. Extract factual claims made by `ai_agent` and `operator` messages: `{subject,
   attribute, value, speaker, session_id}` — e.g. `{free trial, length, 30 days, ai_agent}`.
2. Normalise subjects/attributes so the same fact lines up across languages.
3. Report every subject/attribute with ≥ 2 incompatible values.
4. For each, decide the **likely truth**: prefer the latest operator statement, a
   customer-confirmed correction, or the public website; say how confident you are.
5. Name the **source to fix**: AI knowledge (which kb file/section if known), operator
   macro/training, or website.

## Output

```json
{"contradictions": [{"id": "trial-length", "subject": "free trial", "attribute": "length",
   "claims": [{"value": "30 days", "speaker": "ai_agent", "sessions": ["…"]},
              {"value": "21 days", "speaker": "operator", "sessions": ["…"]}],
   "likely_truth": "21 days", "confidence": "high", "fix": "AI knowledge: 'Pricing FAQ' still says 30 days",
   "sessions": ["…all involved…"]}]}
```
`confidence` is `high` (a correction is confirmed in a chat or several sources agree),
`medium` (consistent operator answers vs. one other source) or `low`. Order by the
number of sessions involved. Every `sessions` entry is a `session_id` exactly as in the input
(e.g. `coAbc123#0`), never a bare conversation id. `contradictions.md`: one block per contradiction, with the fix.
No personal data (apply the gate from `smartsupp-conversations`).
