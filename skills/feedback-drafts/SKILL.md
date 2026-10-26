---
name: feedback-drafts
description: Extract feature requests, product complaints/praise and policy feedback from Smartsupp chats, group duplicates, count demand, and draft tickets or notes ready to send anywhere (Linear, Jira, Notion, Slack, email). Use for "feature requests from chats", "what customers ask us to add", "product feedback", "complaints about our policies", "voice of customer items".
---

# Feedback → drafts

**Input:** `<ws>/digest.txt` (compact view of `sessions.redacted.jsonl`; see `smartsupp-conversations` → Working efficiently); optional `<ws>/results/cx-score.jsonl`
(re-use its product/policy feedback reasons).
**Output:** `<ws>/results/feedback.json`, `<ws>/results/feedback.md`.

## Types

| Type | Example |
|---|---|
| `feature_request` | Something the business does not offer and the customer wants: a service, product, payment method, delivery country, language, tool. Counts even when phrased as a question ("Do you ship to Austria?") if the answer was no and the customer showed they wanted it (see below). |
| `capability_question` | A question whether something is possible or included, answered no or "only up to a limit", where the customer did **not** show a want beyond asking. Low-signal; listed separately, never ranked with feature requests. |
| `product_feedback` | Praise or criticism of a product/service's quality (broke after a month, fits great, lawyer was quick). |
| `policy_feedback` | Praise or criticism of rules: return period, shipping cost, fees, billing practice, scope. |

Questions answered "yes, we do that" are not feature requests. A "no" makes a
question a feature request only when the customer shows the want: asks for it to be
added or changed, pushes back or is disappointed, asks for a workaround or an
alternative, says they would go elsewhere or that it works elsewhere, or says they
need it for a purpose the "no" now blocks. A follow-up asking to get around the limit
("we are five — can't you add an extra bed?") is a workaround request, so it counts. A plain fit question before buying ("Does
Pro keep a week offline?", "Can a manager export it?") answered no, with no reaction,
is a `capability_question` — a stated circumstance ("our warehouse loses signal") is
context, not yet a want.

## Process

1. Per session, extract items: `{type, polarity (positive|negative|request), subject,
   summary, strength (mention|ask|demand|churn-threat), session_id}`. A session can
   have several items.
2. Group items about the same thing into one entry (any language/wording). Count
   sessions; note strongest demand; keep up to 3 paraphrased quotes (redacted,
   ≤ 20 words).
3. Rank: feature requests by count × strongest strength (mention 1, ask 2, demand 3,
   churn-threat 4); feedback by count, then negative before positive, then strength.
   Sessions with no feedback (plain questions, greetings, misdirected chats) are
   ignored. A complaint about a rule that implies a missing option (no delivery to
   Austria) is filed once, as the feature request; mention the policy angle in it.
4. Draft each entry as a destination-neutral ticket: title, problem statement in the
   customer's terms, evidence (count, session ids), suggested next step. Apply the
   personal-data gate and run `python3 ../smartsupp-conversations/scripts/insights.py check <ws> <files>` (path relative to this skill's folder) on the output files.
5. Sending to a tool (Linear, Jira, Slack, …) happens only when the user asks and
   names the destination; show the drafts first.

## Output

```json
{"items": [{"id": "ship-to-austria", "business": "…", "type": "feature_request", "polarity": "request",
            "title": "Deliver to Austria and Germany", "problem": "…", "summary": "…", "count": 3,
            "strength": "ask", "sessions": ["…"], "quotes": ["…"], "next_step": "…"}]}
```
`capability_question` items use the same shape (`polarity: "request"`, `strength:
"mention"`).
`feedback.md`: three sections (feature requests, product feedback, policy feedback),
ranked, each item as a ready-to-paste ticket draft, then a short list "Capability
questions answered no" (one line each with count) — watch these for repeat demand.
